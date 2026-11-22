"""Read-only access to Infinity Engine game resources (chitin.key + BIFF archives + override)."""
import os
import struct
import zlib

# Resource type codes used by this tool
CRE = 0x3F1
ARE = 0x3F2
DLG = 0x3F3
GAM = 0x3F5
STO = 0x3F6
WMP = 0x3F7
ITM = 0x3ED
WED = 0x3E9
BCS = 0x3EF
TWODA = 0x3F4

EXTENSIONS = {CRE: 'CRE', ARE: 'ARE', DLG: 'DLG', GAM: 'GAM', STO: 'STO', WMP: 'WMP',
              ITM: 'ITM', BCS: 'BCS', TWODA: '2DA', WED: 'WED'}


def _read(path):
    with open(path, 'rb') as fh:
        return fh.read()


def find_game_root(path):
    """Return the directory holding chitin.key at or below `path` (max depth 4)."""
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.isfile(os.path.join(path, 'chitin.key')):
        return path
    base_depth = path.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(path):
        if dirpath.count(os.sep) - base_depth >= 4:
            dirnames[:] = []
            continue
        if any(f.lower() == 'chitin.key' for f in filenames):
            return dirpath
    return None


def _find_case_insensitive(root, relpath):
    """Resolve `relpath` under `root` ignoring case (BIF names in chitin.key rarely match on disk)."""
    current = root
    for part in relpath.replace('\\', '/').split('/'):
        if not part:
            continue
        direct = os.path.join(current, part)
        if os.path.exists(direct):
            current = direct
            continue
        try:
            match = next((e for e in os.listdir(current) if e.lower() == part.lower()), None)
        except OSError:
            return None
        if match is None:
            return None
        current = os.path.join(current, match)
    return current


def _decompress_bif(data):
    sig = data[:8]
    if sig == b'BIFFV1  ':
        return data
    if sig == b'BIF V1.0':                      # single zlib stream
        name_len = struct.unpack_from('<I', data, 8)[0]
        o = 12 + name_len
        _ulen, clen = struct.unpack_from('<II', data, o)
        return zlib.decompress(data[o + 8:o + 8 + clen])
    if sig == b'BIFCV1.0':                      # block-compressed
        total = struct.unpack_from('<I', data, 8)[0]
        out = bytearray()
        o = 12
        while len(out) < total:
            _dlen, clen = struct.unpack_from('<II', data, o)
            out += zlib.decompress(data[o + 8:o + 8 + clen])
            o += 8 + clen
        return bytes(out)
    raise ValueError('unknown BIF signature %r' % sig)


class GameResources:
    """Looks up resources by (name, type): override folder first, then the BIFFs listed in chitin.key."""

    def __init__(self, root):
        self.root = root
        key = _read(os.path.join(root, 'chitin.key'))
        if key[:8] != b'KEY V1  ':
            raise ValueError('%s: not a chitin.key file' % root)
        n_bif, n_res, o_bif, o_res = struct.unpack_from('<IIII', key, 8)
        self.bifs = []
        for i in range(n_bif):
            _length, name_off, name_len, _loc = struct.unpack_from('<IIHH', key, o_bif + 12 * i)
            self.bifs.append(key[name_off:name_off + name_len].rstrip(b'\0').decode('latin1'))
        self.index = {}
        for i in range(n_res):
            name, typ, locator = struct.unpack_from('<8sHI', key, o_res + 14 * i)
            self.index[(name.rstrip(b'\0').decode('latin1').upper(), typ)] = locator
        self._bif_cache = {}
        self._override = {}
        override = _find_case_insensitive(root, 'override')
        if override and os.path.isdir(override):
            for f in os.listdir(override):
                self._override[f.upper()] = os.path.join(override, f)

    def names(self, typ):
        found = {n for (n, t) in self.index if t == typ}
        ext = '.' + EXTENSIONS.get(typ, '')
        found |= {f[:-len(ext)] for f in self._override if f.endswith(ext)}
        return found

    def exists(self, name, typ):
        name = name.upper()
        return (name, typ) in self.index or (name + '.' + EXTENSIONS.get(typ, '')) in self._override

    def _bif(self, idx):
        if idx not in self._bif_cache:
            path = _find_case_insensitive(self.root, self.bifs[idx])
            if path is None:
                raise FileNotFoundError(self.bifs[idx])
            data = _decompress_bif(_read(path))
            n_files, _n_tiles, off = struct.unpack_from('<III', data, 8)
            entries = {}
            for k in range(n_files):
                loc, o, size, _t = struct.unpack_from('<IIIH', data, off + 16 * k)
                entries[loc & 0x3FFF] = (o, size)
            self._bif_cache[idx] = (data, entries)
        return self._bif_cache[idx]

    def get(self, name, typ):
        """Return the resource bytes, or None when the game does not have it."""
        if isinstance(name, bytes):
            name = name.rstrip(b'\0').decode('latin1')
        name = name.upper()
        ov = self._override.get(name + '.' + EXTENSIONS.get(typ, ''))
        if ov:
            return _read(ov)
        locator = self.index.get((name, typ))
        if locator is None:
            return None
        data, entries = self._bif(locator >> 20)
        entry = entries.get(locator & 0x3FFF)
        if entry is None:
            return None
        o, size = entry
        return data[o:o + size]
