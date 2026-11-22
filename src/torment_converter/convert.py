"""Convert one original Planescape: Torment save folder into a PST:EE save folder."""
import os
import struct

from . import creature
from .resources import ARE, BCS, CRE, GAM, WED, WMP
from .savarchive import read_sav, write_sav


def _read(path):
    with open(path, 'rb') as fh:
        return fh.read()

U = lambda d, o: struct.unpack_from('<I', d, o)[0]
W = lambda d, o: struct.unpack_from('<H', d, o)[0]

NPC_V11 = 0x168      # original GAM NPC record
NPC_V20 = 0x160      # EE GAM NPC record
VAR = 0x54           # variable record (GAM globals, ARE locals, kill variables)
ACTOR, REGION, CONTAINER, ITEM, DOOR = 0x110, 0xC4, 0xC0, 0x14, 0xC8
FAMILIAR_INFO = 400  # size of the (unused in PST) familiar section the EE writes

# Joinable characters: death variable -> EE creature used as the reference for static fields.
PARTY_REFERENCE = {
    b'Nameless': 'CHARBASE', b'Morte': 'MORTE', b'Dakkon': 'DAKKON', b'Annah': 'ANNAH',
    b'Grace': 'GRACE', b'Nordom': 'NORDOM', b'Ignus': 'IGNUS', b'Vhail': 'VHAILOR',
}


def map_internal_slot(v):
    """Original internal slot id (quick bars in GAM) -> PST:EE internal slot id (ITMSLOTS.2DA)."""
    if v == 0xFFFF:
        return v
    if v <= 14:
        return v                      # equipment, fist, quiver 1-4
    if v == 15:
        return 39                     # quiver 5
    if 17 <= v <= 19:
        return 15 + (v - 17)          # quick items 1-3
    if 20 <= v <= 21:
        return 41 + (v - 20)          # quick items 4-5
    if 22 <= v <= 37:
        return 18 + (v - 22)          # inventory 1-16
    if 38 <= v <= 41:
        return 44 + (v - 38)          # inventory 17-20
    if v == 42:
        return 34                     # magic weapon
    if 43 <= v <= 46:
        return 35 + (v - 43)          # weapons 1-4
    return 0xFFFF                     # quiver 6 and anything unknown


def remap_explored(old, width, height):
    """Original explored bitmask -> EE layout.

    Both games keep one bit per 32x32-pixel cell, least significant bit first, rows packed
    without padding. The original grid is (2*W) x (2*H) cells for a map of W x H 64-pixel
    tiles; the EE grid has one extra column and row: (2*W + 1) x (2*H + 1). The extra
    column/row copy their neighbours.
    Returns None when `old` does not have the size the original layout implies.
    """
    ow, oh = 2 * width, 2 * height
    if len(old) != (ow * oh + 7) // 8:
        return None
    ew, eh = ow + 1, oh + 1
    new = bytearray((ew * eh + 7) // 8)

    def seen(x, y):
        i = y * ow + x
        return (old[i >> 3] >> (i & 7)) & 1

    for y in range(eh):
        sy = min(y, oh - 1)
        for x in range(ew):
            if seen(min(x, ow - 1), sy):
                i = y * ew + x
                new[i >> 3] |= 1 << (i & 7)
    return bytes(new)


def wed_size(wed):
    """Map size in 64-pixel tiles from overlay 0 of a WED file, or None."""
    if not wed or wed[:8] != b'WED V1.3':
        return None
    overlay = U(wed, 0x10)
    return W(wed, overlay), W(wed, overlay + 2)


def variable(name, value):
    e = bytearray(VAR)
    raw = name.encode('latin1')[:32]
    e[:len(raw)] = raw
    struct.pack_into('<i', e, 0x28, value)
    return bytes(e)


class SaveConverter:
    def __init__(self, ee):
        """`ee` is a resources.GameResources for the Enhanced Edition install."""
        self.ee = ee
        self.report = []

    # ------------------------------------------------------------------ creatures
    def _blank_missing(self, buf, offsets, typ):
        """Clear script references the EE does not ship (Beamdog removed some the same way)."""
        for o in offsets:
            name = bytes(buf[o:o + 8]).rstrip(b'\0').decode('latin1')
            if name and name.upper() != 'NONE' and not self.ee.exists(name, typ):
                buf[o:o + 8] = b'\0' * 8

    def creature(self, old, party, reference=None):
        c = bytearray(creature.convert(old, party=party))
        self._blank_missing(c, [0x248 + 8 * k for k in range(5)], BCS)
        anim = U(c, 0x28)
        if anim >> 12 in (0x6, 0xE):          # EE moved PST animations to the 0xFxxx range
            anim = (anim & 0x0FFF) | 0xF000
        struct.pack_into('<I', c, 0x28, anim)
        flags = (U(c, 0x10) & ~0x3000) | 0x100001   # bits the EE sets / clears on every PST creature
        struct.pack_into('<I', c, 0x10, flags)
        ref = self.ee.get(reference, CRE) if reference else None
        if ref and ref[:8] == b'CRE V1.0' and (U(ref, 0x28) & 0xFFFF) == (anim & 0xFFFF):
            c[0x2C:0x33] = ref[0x2C:0x33]           # colours (EE derives them per animation)
            c[0x96:0x9A] = ref[0x96:0x9A]           # attribute flags (EE fixes)
            c[0x7F] = ref[0x7F]
            c[0x8C:0x8F] = ref[0x8C:0x8F]           # GOOD / LAW / LADY / MURDER increments
        return bytes(c)

    # ------------------------------------------------------------------ GAM
    def _npc_record(self, n):
        out = bytearray(NPC_V20)
        out[0x00:0x84] = n[0x00:0x84]
        qi = struct.unpack_from('<5H', n, 0xB4)
        qa = struct.unpack_from('<5h', n, 0xBE)
        struct.pack_into('<HHhh', out, 0x84, map_internal_slot(qi[3]), map_internal_slot(qi[4]), qa[3], qa[4])
        struct.pack_into('<4H', out, 0x8C, *[map_internal_slot(x) for x in struct.unpack_from('<4H', n, 0x8C)])
        out[0x94:0xB4] = n[0x94:0xB4]             # quick weapon abilities, quick spells
        struct.pack_into('<3H3h', out, 0xB4, *[map_internal_slot(x) for x in qi[:3]], *qa[:3])
        out[0xC0:0xE0] = n[0xC8:0xE8]             # name
        out[0xE0:0xE4] = n[0xE8:0xEC]             # talk count
        out[0xE4:0x158] = n[0xEC:0x160]           # character statistics
        return out

    def _npcs(self, g, offset, count):
        result = []
        for i in range(count):
            o = offset + NPC_V11 * i
            n = g[o:o + NPC_V11]
            old = g[U(n, 4):U(n, 4) + U(n, 8)]
            death = old[0x324:0x344].rstrip(b'\0')
            reference = PARTY_REFERENCE.get(death) or n[0x0C:0x14].rstrip(b'\0').decode('latin1')
            new = self.creature(old, party=True, reference=reference)
            self.report.append('character %s: %d items' % (death.decode('latin1') or '?', U(new, 0x2C0)))
            result.append((self._npc_record(n), new))
        return result

    def game(self, g):
        if g[:8] != b'GAMEV1.1':
            raise ValueError('not an original PST game file (%r)' % g[:8])
        template = self.ee.get('BALDUR', GAM)
        h = bytearray(0xB4)
        h[0:8] = b'GAMEV2.0'
        h[0x08:0x1C] = g[0x08:0x1C]                   # game time, formation, gold
        h[0x1E:0x20] = g[0x1E:0x20]                   # weather
        h[0x40:0x48] = g[0x40:0x48]                   # main area
        struct.pack_into('<i', h, 0x48, -1)
        struct.pack_into('<I', h, 0x54, U(g, 0x58))   # reputation
        h[0x58:0x60] = g[0x5C:0x64]                   # current area
        h[0x8C:0x94] = b'WORLDMAP'                    # current world map

        party = self._npcs(g, U(g, 0x20), U(g, 0x24))
        others = self._npcs(g, U(g, 0x30), U(g, 0x34))

        names, gvars = set(), []

        def add(entry):
            key = entry[:32].rstrip(b'\0').upper()
            if key in names:
                return False
            names.add(key)
            gvars.append(entry)
            return True

        for i in range(U(g, 0x3C)):
            add(g[U(g, 0x38) + VAR * i:U(g, 0x38) + VAR * (i + 1)])
        if template:                                  # EE start-of-game defaults not in the save
            for i in range(U(template, 0x3C)):
                add(template[U(template, 0x38) + VAR * i:U(template, 0x38) + VAR * (i + 1)])
        kills = 0
        for i in range(U(g, 0x68)):                   # KAPUTZ scope -> GLOBAL "<name>_KAPUTZ"
            e = g[U(g, 0x64) + VAR * i:U(g, 0x64) + VAR * (i + 1)]
            name = e[:32].rstrip(b'\0').decode('latin1') + '_KAPUTZ'
            if len(name) <= 32 and add(variable(name, struct.unpack_from('<i', e, 0x28)[0])):
                kills += 1
        known = 0
        if U(g, 0x6C):
            for i, flag in enumerate(g[U(g, 0x6C):U(g, 0x6C) + 260]):
                if flag and add(variable('BESTIARY_KNOWN_%d' % i, 1)):
                    known += 1
        journal = g[U(g, 0x50):U(g, 0x50) + 12 * U(g, 0x4C)]
        self.report.append('variables: %d (incl. %d kill counters, %d bestiary entries); journal entries: %d'
                           % (len(gvars), kills, known, U(g, 0x4C)))

        body = bytearray()

        def place(npcs):
            start = 0xB4 + len(body)
            cre_offset = start + NPC_V20 * len(npcs)
            records, cres = bytearray(), bytearray()
            for record, cre in npcs:
                struct.pack_into('<II', record, 4, cre_offset + len(cres), len(cre))
                records += record
                cres += cre
            body.extend(records + cres)
            return start

        o_party = place(party)
        o_others = place(others)
        o_vars = 0xB4 + len(body)
        body.extend(b''.join(gvars))
        o_journal = 0xB4 + len(body)
        body.extend(journal)
        o_familiar = 0xB4 + len(body)
        body.extend(bytes(FAMILIAR_INFO))          # empty familiar block, as the EE writes it
        end = 0xB4 + len(body)
        struct.pack_into('<IIII', h, 0x20, o_party, len(party), 0, 0)
        struct.pack_into('<IIII', h, 0x30, o_others, len(others), o_vars, len(gvars))
        struct.pack_into('<II', h, 0x4C, U(g, 0x4C), o_journal)
        struct.pack_into('<I', h, 0x68, o_familiar)
        struct.pack_into('<III', h, 0x6C, end, 0, 0)     # stored locations
        struct.pack_into('<II', h, 0x78, end, 0)         # pocket plane locations
        return bytes(h) + bytes(body)

    # ------------------------------------------------------------------ ARE
    def area(self, name, s):
        """Merge the saved state of one area into the EE's own version of that area."""
        base = self.ee.get(name, ARE)
        if base is None:
            self.report.append('area %s: not in the EE data, dropped' % name)
            return None
        b = bytearray(base)

        actors, cres = bytearray(), []
        for k in range(W(s, 0x58)):
            a = bytearray(s[U(s, 0x54) + ACTOR * k:U(s, 0x54) + ACTOR * (k + 1)])
            self._blank_missing(a, [0x50 + 8 * j for j in range(6)], BCS)
            co, cs = U(a, 0x88), U(a, 0x8C)
            c = None
            if cs and s[co:co + 8] == b'CRE V1.2':
                try:
                    c = self.creature(s[co:co + cs], party=False,
                                      reference=bytes(a[0x80:0x88]).rstrip(b'\0').decode('latin1'))
                except (ValueError, struct.error) as ex:
                    self.report.append('area %s: creature %r reset to EE default (%s)'
                                       % (name, bytes(a[:32]).rstrip(b'\0'), ex))
            actors += a
            cres.append(c)

        def containers(d):
            return [bytes(d[U(d, 0x70) + CONTAINER * k:U(d, 0x70) + CONTAINER * (k + 1)])
                    for k in range(W(d, 0x74))]

        def items_in(d, c):
            first, count = U(c, 0x40), U(c, 0x44)
            return [bytes(d[U(d, 0x78) + ITEM * (first + j):U(d, 0x78) + ITEM * (first + j + 1)])
                    for j in range(count)]

        saved = {c[:32].rstrip(b'\0').upper(): c for c in containers(s)}
        vertices = bytearray(b[U(b, 0x7C):U(b, 0x7C) + 4 * W(b, 0x80)])
        new_containers, new_items, matched = [], [], set()
        for c in containers(b):
            key = c[:32].rstrip(b'\0').upper()
            c = bytearray(c)
            if key in saved:
                matched.add(key)
                c[0x24:0x38] = saved[key][0x24:0x38]      # type, lock, flags, trap state
                its = items_in(s, saved[key])
            else:
                its = items_in(b, c)
            struct.pack_into('<II', c, 0x40, len(new_items), len(its))
            new_items += its
            new_containers.append(c)
        for key, sc in saved.items():                      # e.g. piles of dropped items
            if key in matched:
                continue
            c = bytearray(sc)
            first, count = U(sc, 0x50), W(sc, 0x54)
            struct.pack_into('<I', c, 0x50, len(vertices) // 4)
            vertices += s[U(s, 0x7C) + 4 * first:U(s, 0x7C) + 4 * (first + count)]
            its = items_in(s, sc)
            struct.pack_into('<II', c, 0x40, len(new_items), len(its))
            new_items += its
            new_containers.append(c)

        def by_name(d, off, count, size):
            return {bytes(d[off + size * k:off + size * k + 32]).rstrip(b'\0').upper(): off + size * k
                    for k in range(count)}

        saved_doors = by_name(s, U(s, 0xA8), U(s, 0xA4), DOOR)
        for key, o in by_name(b, U(b, 0xA8), U(b, 0xA4), DOOR).items():
            if key in saved_doors:
                b[o + 0x28:o + 0x2C] = s[saved_doors[key] + 0x28:saved_doors[key] + 0x2C]
        saved_regions = by_name(s, U(s, 0x5C), W(s, 0x5A), REGION)
        for key, o in by_name(b, U(b, 0x5C), W(b, 0x5A), REGION).items():
            if key in saved_regions:
                so = saved_regions[key]
                b[o + 0x60:o + 0x64] = s[so + 0x60:so + 0x64]
                b[o + 0x6C:o + 0x70] = s[so + 0x6C:so + 0x70]

        local_vars = {}
        for d in (b, s):                                   # saved values win
            for k in range(U(d, 0x8C)):
                e = bytes(d[U(d, 0x88) + VAR * k:U(d, 0x88) + VAR * (k + 1)])
                local_vars[e[:32].rstrip(b'\0').upper()] = e

        explored = None                                    # fog of war
        old_explored = bytes(s[U(s, 0xA0):U(s, 0xA0) + U(s, 0x9C)])
        if old_explored:
            size = wed_size(self.ee.get(bytes(b[0x08:0x10]), WED))
            if size:
                explored = remap_explored(old_explored, *size)
            if explored is None:
                self.report.append('area %s: explored map not carried over (unexpected size)' % name)
        b[0x10:0x14] = s[0x10:0x14]                        # last saved

        # Rewritten sections go at the end of the file; the header is repointed.
        o_actors = len(b)
        b.extend(actors)
        for k, c in enumerate(cres):
            a_off = o_actors + ACTOR * k
            if c is None:
                struct.pack_into('<II', b, a_off + 0x88, 0, 0)
            else:
                struct.pack_into('<II', b, a_off + 0x88, len(b), len(c))
                b.extend(c)

        def append(blob):
            start = len(b)
            b.extend(blob)
            return start

        struct.pack_into('<I', b, 0x54, o_actors)
        struct.pack_into('<H', b, 0x58, len(cres))
        struct.pack_into('<I', b, 0x70, append(b''.join(new_containers)))
        struct.pack_into('<H', b, 0x74, len(new_containers))
        struct.pack_into('<I', b, 0x78, append(b''.join(new_items)))
        struct.pack_into('<H', b, 0x76, len(new_items))
        struct.pack_into('<I', b, 0x7C, append(bytes(vertices)))
        struct.pack_into('<H', b, 0x80, len(vertices) // 4)
        struct.pack_into('<I', b, 0x88, append(b''.join(local_vars.values())))
        struct.pack_into('<I', b, 0x8C, len(local_vars))
        if explored is not None:
            struct.pack_into('<II', b, 0x9C, len(explored), append(explored))
        self.report.append('area %s: %d creatures, %d containers, %d items, %d variables'
                           % (name, len(cres), len(new_containers), len(new_items), len(local_vars)))
        return bytes(b)

    # ------------------------------------------------------------------ WMP
    def worldmap(self, saved):
        base = bytearray(self.ee.get('WORLDMAP', WMP))

        def areas(d):
            for m in range(U(d, 0x08)):
                mo = U(d, 0x0C) + 0xB8 * m
                for a in range(U(d, mo + 0x20)):
                    yield m, U(d, mo + 0x24) + 0xF0 * a

        status = {(m, bytes(saved[o:o + 8])): saved[o + 0x30:o + 0x34] for m, o in areas(saved)}
        for m, o in areas(base):
            st = status.get((m, bytes(base[o:o + 8])))
            if st is not None:
                base[o + 0x30:o + 0x34] = st        # visible / reachable / visited flags
        return bytes(base)

    # ------------------------------------------------------------------ whole save
    def convert_folder(self, src, dst):
        files = {f.upper(): os.path.join(src, f) for f in os.listdir(src)}
        if 'TORMENT.GAM' not in files or 'TORMENT.SAV' not in files:
            raise ValueError('%s: no TORMENT.GAM / TORMENT.SAV, not an original PST save' % src)
        read = lambda key: _read(files[key])
        out = {'BALDUR.gam': self.game(read('TORMENT.GAM'))}
        entries = []
        for name, data in read_sav(read('TORMENT.SAV')):
            stem, ext = os.path.splitext(name)
            if ext.upper() == '.ARE':
                merged = self.area(stem.upper(), data)
                if merged:
                    entries.append((name, merged))
            elif ext.upper() == '.STO':
                entries.append((name, data))          # store format is unchanged
            else:
                self.report.append('archive entry %s not converted' % name)
        out['BALDUR.sav'] = write_sav(entries)
        if 'WORLDMAP.WMP' in files:
            out['WORLDMAP.wmp'] = self.worldmap(read('WORLDMAP.WMP'))
        if 'TORMENT.BMP' in files:
            out['BALDUR.bmp'] = read('TORMENT.BMP')
        for key in files:
            if key.startswith('PORTRT') and key.endswith('.BMP'):
                out[key] = read(key)
        os.makedirs(dst, exist_ok=True)
        for name, data in out.items():
            with open(os.path.join(dst, name), 'wb') as fh:
                fh.write(data)
        return self.report
