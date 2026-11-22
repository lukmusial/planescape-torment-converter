import unittest

import helpers  # noqa: F401  (sets sys.path)

from torment_converter.savarchive import read_sav, write_sav


class SavArchiveTests(unittest.TestCase):
    def test_round_trip(self):
        entries = [('AR0100.ARE', b'AREAV1.0' + bytes(300)), ('SHOP.STO', b'STORV1.1' + b'x' * 50)]
        self.assertEqual(read_sav(write_sav(entries)), entries)

    def test_rejects_other_files(self):
        with self.assertRaises(ValueError):
            read_sav(b'GAMEV1.1' + bytes(10))


if __name__ == '__main__':
    unittest.main()
