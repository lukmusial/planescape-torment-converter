import struct
import unittest

from helpers import cre_v12, eff_v1, item

from torment_converter import creature

U = lambda d, o: struct.unpack_from('<I', d, o)[0]


class CreatureTests(unittest.TestCase):
    def test_header_fields_move_to_v10_positions(self):
        c = creature.convert(cre_v12(death=b'Morte'))
        self.assertEqual(c[:8], b'CRE V1.0')
        self.assertEqual(U(c, 0x08), 1234)
        self.assertEqual(struct.unpack_from('<HH', c, 0x24), (20, 30))
        self.assertEqual(c[0x238], 17)
        self.assertEqual(c[0x280:0x285], b'Morte')
        self.assertEqual(c[0x2CC:0x2D2], b'DTEST1')
        self.assertEqual(c[0x33], 1)  # EFF v2

    def test_party_inventory_layout(self):
        items = [item(b'EYEBALL'), item(b'TATTOO'), item(b'KNIFE'), item(b'CHARM'), item(b'BOOK')]
        slots = {6: 0, 19: 1, 9: 2, 23: 3, 44: 4}   # eyeball, upper tattoo, weapon 1, quick 4, inventory 20
        c = creature.convert(cre_v12(items=items, slots=slots), party=True)
        view = creature.summarize_v10(c)
        self.assertEqual(c[0x7C], creature.PARTY_SLOT_COUNT)
        self.assertEqual(dict(view['slots']),
                         {6: b'EYEBALL\0', 17: b'TATTOO\0\0', 9: b'KNIFE\0\0\0', 40: b'CHARM\0\0\0', 45: b'BOOK\0\0\0\0'})
        self.assertEqual(view['selected'], (0xFFFF, 0))

    def test_nonparty_drops_slots_that_do_not_exist(self):
        items = [item(b'CHARM'), item(b'KNIFE')]
        c = creature.convert(cre_v12(items=items, slots={23: 0, 9: 1}), party=False)
        view = creature.summarize_v10(c)
        self.assertEqual(c[0x7C], 0)
        self.assertEqual(dict(view['slots']), {9: b'KNIFE\0\0\0'})
        self.assertEqual(len(view['items']), 2)       # item kept, just not equipped

    def test_proficiencies_become_effects(self):
        c = creature.convert(cre_v12(proficiencies=(2, 1, 0, 3)))
        effs = creature.summarize_v10(c)['effects']
        got = sorted((U(e, 0x08), U(e, 0x14), U(e, 0x18)) for e in effs)
        self.assertEqual(got, [(233, 1, 96), (233, 2, 89), (233, 3, 92)])
        self.assertEqual(c[0x6E:0x76], bytes(8))

    def test_eff_v1_is_widened(self):
        e = creature.eff_v1_to_v2(eff_v1(17, p1=5, p2=1, timing=1, duration=60, resource=b'SPWI101'))
        self.assertEqual(len(e), creature.EFF_V2_SIZE)
        self.assertEqual(struct.unpack_from('<IIIII', e, 0x08), (17, 1, 0, 5, 1))
        self.assertEqual(struct.unpack_from('<H', e, 0x1C)[0], 1)
        self.assertEqual(U(e, 0x20), 60)
        self.assertEqual(e[0x28:0x2F], b'SPWI101')

    def test_rejects_other_versions(self):
        with self.assertRaises(ValueError):
            creature.convert(b'CRE V1.0' + bytes(0x400))


if __name__ == '__main__':
    unittest.main()
