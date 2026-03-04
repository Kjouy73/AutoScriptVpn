import os
import sys
import tempfile
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "vpn_system"))

from core.models import VortexDB


class HostManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "db.json")
        self.db = VortexDB(db_path=self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_list_remove_hosts(self):
        self.assertEqual(self.db.list_hosts(), [])
        self.assertTrue(self.db.add_host("a.example.com"))
        self.assertFalse(self.db.add_host("a.example.com"))
        self.assertEqual(self.db.list_hosts(), ["a.example.com"])
        self.assertTrue(self.db.remove_host("a.example.com"))
        self.assertFalse(self.db.remove_host("a.example.com"))
        self.assertEqual(self.db.list_hosts(), [])


if __name__ == "__main__":
    unittest.main()
