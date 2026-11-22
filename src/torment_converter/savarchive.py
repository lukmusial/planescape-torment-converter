"""SAV V1.0: the zlib-compressed archive of area and store files inside a save folder."""
import struct
import zlib


def read_sav(data):
    """Return [(filename, bytes), ...] from a SAV V1.0 archive."""
    if data[:8] != b'SAV V1.0':
        raise ValueError('not a SAV V1.0 archive: %r' % data[:8])
    o = 8
    entries = []
    while o < len(data):
        name_len = struct.unpack_from('<I', data, o)[0]
        name = data[o + 4:o + 4 + name_len].rstrip(b'\0').decode('latin1')
        o += 4 + name_len
        ulen, clen = struct.unpack_from('<II', data, o)
        o += 8
        payload = zlib.decompress(data[o:o + clen])
        o += clen
        if len(payload) != ulen:
            raise ValueError('%s: size mismatch in SAV archive' % name)
        entries.append((name, payload))
    return entries


def write_sav(entries):
    """Build a SAV V1.0 archive from [(filename, bytes), ...]."""
    out = bytearray(b'SAV V1.0')
    for name, payload in entries:
        name_bytes = name.encode('latin1') + b'\0'
        compressed = zlib.compress(payload, 6)
        out += struct.pack('<I', len(name_bytes)) + name_bytes
        out += struct.pack('<II', len(payload), len(compressed)) + compressed
    return bytes(out)
