"""Synthetic game records for tests (no game data is shipped with this repository)."""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def item(resref, charges=1):
    e = bytearray(20)
    e[0:len(resref)] = resref
    struct.pack_into('<H', e, 0x0A, charges)
    struct.pack_into('<I', e, 0x10, 1)          # identified
    return bytes(e)


def cre_v12(items=(), slots=None, proficiencies=(), effects=(), death=b'Test', anim=0x6032):
    """Minimal CRE V1.2: header, items, 48-word slot table, EFF v1 effects."""
    h = bytearray(0x378)
    h[0:8] = b'CRE V1.2'
    struct.pack_into('<I', h, 0x08, 1234)        # long name strref
    struct.pack_into('<HH', h, 0x24, 20, 30)     # HP
    struct.pack_into('<I', h, 0x28, anim)
    h[0x238] = 17                                # STR
    for i, stars in enumerate(proficiencies):
        h[0x6E + i] = stars
    h[0x324:0x324 + len(death)] = death
    h[0x370:0x376] = b'DTEST1'
    table = [0xFFFF] * 48
    for slot, idx in (slots or {}).items():
        table[slot] = idx
    body = bytearray()
    o_items = 0x378
    body += b''.join(items)
    o_slots = 0x378 + len(body)
    body += struct.pack('<48H', *table)
    o_eff = 0x378 + len(body)
    body += b''.join(effects)
    struct.pack_into('<11I', h, 0x344, 0x378, 0, 0x378, 0, 0x378, 0,
                     o_slots, o_items, len(items), o_eff, len(effects))
    return bytes(h) + bytes(body)


def eff_v1(opcode, p1=0, p2=0, timing=0, duration=0, resource=b''):
    e = bytearray(48)
    struct.pack_into('<HBBIIBBIBB', e, 0, opcode, 1, 0, p1, p2, timing, 0, duration, 100, 0)
    e[0x14:0x14 + len(resource)] = resource
    return bytes(e)


class FakeResources:
    """Stands in for resources.GameResources."""

    def __init__(self, files=None):
        self.files = {(k[0].upper(), k[1]): v for k, v in (files or {}).items()}

    def get(self, name, typ):
        if isinstance(name, bytes):
            name = name.rstrip(b'\0').decode('latin1')
        return self.files.get((name.upper(), typ))

    def exists(self, name, typ):
        return (name.upper(), typ) in self.files

    def names(self, typ):
        return {n for (n, t) in self.files if t == typ}
