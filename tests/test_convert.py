import os
import struct
import tempfile
import unittest

from helpers import FakeResources, cre_v12, item

from torment_converter.convert import SaveConverter, _read, map_internal_slot, variable
from torment_converter.resources import ARE, GAM, WMP
from torment_converter.savarchive import read_sav, write_sav

U = lambda d, o: struct.unpack_from('<I', d, o)[0]


def gam_v11(party_cres, globals_=(), kills=(), bestiary=()):
    """Minimal original GAMEV1.1 with party, globals, kill variables, journal and bestiary."""
    h = bytearray(0xB4)
    h[0:8] = b'GAMEV1.1'
    struct.pack_into('<I', h, 0x08, 18000)       # game time
    struct.pack_into('<I', h, 0x18, 811)         # gold
    h[0x40:0x46] = b'AR0101'
    struct.pack_into('<I', h, 0x58, 100)         # reputation
    h[0x5C:0x62] = b'AR0101'
    body = bytearray()
    records = bytearray()
    cre_base = 0xB4 + 0x168 * len(party_cres)
    cres = bytearray()
    for i, c in enumerate(party_cres):
        r = bytearray(0x168)
        struct.pack_into('<HHII', r, 0, 1, i, cre_base + len(cres), len(c))
        r[0x18:0x1E] = b'AR0101'
        struct.pack_into('<4H', r, 0x8C, 43, 44, 0xFFFF, 0xFFFF)     # quick weapons
        struct.pack_into('<5H', r, 0xB4, 17, 18, 19, 20, 21)         # quick items
        records += r
        cres += c
    body += records + cres
    o_glob = 0xB4 + len(body)
    body += b''.join(variable(n, v) for n, v in globals_)
    o_kill = 0xB4 + len(body)
    body += b''.join(variable(n, v) for n, v in kills)
    o_jour = 0xB4 + len(body)
    body += struct.pack('<IIBBBB', 5000, 100, 1, 0, 1, 0xFF)
    o_best = 0xB4 + len(body)
    best = bytearray(260)
    for i in bestiary:
        best[i] = 1
    body += best
    struct.pack_into('<II', h, 0x20, 0xB4, len(party_cres))
    struct.pack_into('<II', h, 0x30, o_glob, 0)
    struct.pack_into('<II', h, 0x38, o_glob, len(globals_))
    struct.pack_into('<II', h, 0x4C, 1, o_jour)
    struct.pack_into('<III', h, 0x64, o_kill, len(kills), o_best)
    return bytes(h) + bytes(body)


def ee_template():
    h = bytearray(0xB4)
    h[0:8] = b'GAMEV2.0'
    struct.pack_into('<II', h, 0x38, 0xB4, 1)
    return bytes(h) + variable('PARTYSCRIPTSACTIVE', 1)


def area(actors=(), containers=(), items=(), local_vars=()):
    """Minimal AREAV1.0 with actors (embedded CREs), containers, items and variables."""
    h = bytearray(0x11C)
    h[0:8] = b'AREAV1.0'
    body = bytearray()

    def put(blob):
        start = 0x11C + len(body)
        body.extend(blob)
        return start

    o_act = put(b''.join(bytes(name.ljust(0x110, b'\0')) for name, _ in actors))
    for k, (_, cre) in enumerate(actors):
        off = put(cre)
        struct.pack_into('<II', body, o_act - 0x11C + 0x110 * k + 0x88, off, len(cre))
    cont = bytearray()
    for name, first, count in containers:
        c = bytearray(0xC0)
        c[0:len(name)] = name
        struct.pack_into('<II', c, 0x40, first, count)
        cont += c
    o_cont = put(cont)
    o_items = put(b''.join(items))
    o_vars = put(b''.join(variable(n, v) for n, v in local_vars))
    struct.pack_into('<IH', h, 0x54, o_act, len(actors))
    struct.pack_into('<I', h, 0x5C, o_vars)
    struct.pack_into('<IH', h, 0x70, o_cont, len(containers))
    struct.pack_into('<HI', h, 0x76, len(items), o_items)
    struct.pack_into('<I', h, 0x7C, o_items)
    struct.pack_into('<II', h, 0x88, o_vars, len(local_vars))
    struct.pack_into('<II', h, 0xA4, 0, o_vars)
    return bytes(h) + bytes(body)


def worldmap(statuses):
    h = bytearray(16)
    h[0:8] = b'WMAPV1.0'
    struct.pack_into('<II', h, 8, 1, 16)
    m = bytearray(0xB8)
    struct.pack_into('<II', m, 0x20, len(statuses), 16 + 0xB8)
    areas = bytearray()
    for name, st in statuses:
        a = bytearray(0xF0)
        a[0:len(name)] = name
        struct.pack_into('<I', a, 0x30, st)
        areas += a
    return bytes(h + m + areas)


class SlotTests(unittest.TestCase):
    def test_internal_slot_mapping(self):
        self.assertEqual([map_internal_slot(v) for v in (10, 17, 19, 20, 21, 22, 37, 38, 42, 43, 46)],
                         [10, 15, 17, 41, 42, 18, 33, 44, 34, 35, 38])
        self.assertEqual(map_internal_slot(16), 0xFFFF)
        self.assertEqual(map_internal_slot(0xFFFF), 0xFFFF)


class GameTests(unittest.TestCase):
    def test_game_file(self):
        ee = FakeResources({('BALDUR', GAM): ee_template()})
        hero = cre_v12(items=[item(b'KNIFE')], slots={9: 0}, death=b'Nameless')
        gam = gam_v11([hero], globals_=[('QUEST_A', 2)], kills=[('GHOUL_DEAD', 3)], bestiary=[0, 7])
        out = SaveConverter(ee).game(gam)
        self.assertEqual(out[:8], b'GAMEV2.0')
        self.assertEqual((U(out, 0x08), U(out, 0x18), U(out, 0x54)), (18000, 811, 100))
        self.assertEqual(out[0x58:0x5E], b'AR0101')
        self.assertEqual(out[0x8C:0x94], b'WORLDMAP')

        npc = out[U(out, 0x20):U(out, 0x20) + 0x160]
        self.assertEqual(struct.unpack_from('<4H', npc, 0x8C), (35, 36, 0xFFFF, 0xFFFF))
        self.assertEqual(struct.unpack_from('<3H', npc, 0xB4), (15, 16, 17))
        self.assertEqual(struct.unpack_from('<2H', npc, 0x84), (41, 42))
        cre = out[U(npc, 4):U(npc, 4) + U(npc, 8)]
        self.assertEqual(cre[:8], b'CRE V1.0')
        self.assertEqual(U(cre, 0x28), 0xF032)               # animation moved to 0xFxxx

        base = U(out, 0x38)
        values = {out[base + 84 * i:base + 84 * i + 32].rstrip(b'\0'): U(out, base + 84 * i + 0x28)
                  for i in range(U(out, 0x3C))}
        self.assertEqual(values[b'QUEST_A'], 2)
        self.assertEqual(values[b'GHOUL_DEAD_KAPUTZ'], 3)
        self.assertEqual(values[b'BESTIARY_KNOWN_7'], 1)
        self.assertIn(b'PARTYSCRIPTSACTIVE', values)
        self.assertEqual(U(out, 0x4C), 1)
        self.assertEqual(U(out, U(out, 0x50)), 5000)


class AreaTests(unittest.TestCase):
    def test_saved_state_is_merged_into_ee_area(self):
        ee_area = area(containers=[(b'Chest', 0, 1)], items=[item(b'GOLD')], local_vars=[('EE_ONLY', 1)])
        saved = area(actors=[(b'Ghoul', cre_v12(death=b'Ghoul'))],
                     containers=[(b'Chest', 0, 2), (b'Pile', 2, 1)],
                     items=[item(b'KNIFE'), item(b'BOOK'), item(b'RING')],
                     local_vars=[('OPENED', 1)])
        out = SaveConverter(FakeResources({('AR0100', ARE): ee_area})).area('AR0100', saved)
        self.assertEqual(struct.unpack_from('<H', out, 0x58)[0], 1)
        a = out[U(out, 0x54):U(out, 0x54) + 0x110]
        self.assertEqual(out[U(a, 0x88):U(a, 0x88) + 8], b'CRE V1.0')
        self.assertEqual(struct.unpack_from('<H', out, 0x74)[0], 2)     # chest + pile
        self.assertEqual(struct.unpack_from('<H', out, 0x76)[0], 3)     # saved items replace EE's
        names = {out[U(out, 0x88) + 84 * i:U(out, 0x88) + 84 * i + 32].rstrip(b'\0') for i in range(U(out, 0x8C))}
        self.assertEqual(names, {b'EE_ONLY', b'OPENED'})

    def test_unknown_area_is_dropped(self):
        conv = SaveConverter(FakeResources())
        self.assertIsNone(conv.area('AR9999', area()))
        self.assertIn('not in the EE data', conv.report[-1])


class FolderTests(unittest.TestCase):
    def test_convert_folder(self):
        ee = FakeResources({
            ('BALDUR', GAM): ee_template(),
            ('AR0101', ARE): area(),
            ('WORLDMAP', WMP): worldmap([(b'AR0101', 0), (b'AR0200', 0)]),
        })
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = os.path.join(tmp, 'old'), os.path.join(tmp, 'new')
            os.makedirs(src)
            files = {
                'TORMENT.GAM': gam_v11([cre_v12(death=b'Nameless')]),
                'TORMENT.SAV': write_sav([('AR0101.ARE', area()), ('SHOP.STO', b'STORV1.1' + bytes(20))]),
                'WORLDMAP.WMP': worldmap([(b'AR0101', 0xF)]),
                'TORMENT.BMP': b'BM' + bytes(10),
                'PORTRT0.BMP': b'BM' + bytes(10),
            }
            for name, data in files.items():
                with open(os.path.join(src, name), 'wb') as fh:
                    fh.write(data)
            SaveConverter(ee).convert_folder(src, dst)
            self.assertEqual(sorted(os.listdir(dst)),
                             ['BALDUR.bmp', 'BALDUR.gam', 'BALDUR.sav', 'PORTRT0.BMP', 'WORLDMAP.wmp'])
            names = [n for n, _ in read_sav(_read(os.path.join(dst, 'BALDUR.sav')))]
            self.assertEqual(names, ['AR0101.ARE', 'SHOP.STO'])
            wmp = _read(os.path.join(dst, 'WORLDMAP.wmp'))
            first = 16 + 0xB8
            self.assertEqual((U(wmp, first + 0x30), U(wmp, first + 0xF0 + 0x30)), (0xF, 0))

    def test_rejects_non_pst_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                SaveConverter(FakeResources()).convert_folder(tmp, os.path.join(tmp, 'out'))


if __name__ == '__main__':
    unittest.main()


class ExploredTests(unittest.TestCase):
    def test_remap_adds_edge_column_and_row(self):
        from torment_converter.convert import remap_explored
        # 1x1 tile map: original grid 2x2 cells (1 byte), EE grid 3x3 cells (2 bytes)
        old = bytes([0b0000_1001])                  # cells (0,0) and (1,1) explored
        new = remap_explored(old, 1, 1)
        self.assertEqual(len(new), 2)
        bits = {(i % 3, i // 3) for i in range(9) if (new[i >> 3] >> (i & 7)) & 1}
        self.assertEqual(bits, {(0, 0), (1, 1), (2, 1), (1, 2), (2, 2)})

    def test_rejects_unexpected_size(self):
        from torment_converter.convert import remap_explored
        self.assertIsNone(remap_explored(bytes(5), 1, 1))
