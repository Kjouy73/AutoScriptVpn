import os
import sys
import tempfile
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "vpn_system"))

from core.models import VortexDB
from user_management.account_manager import AccountManager


class LinkGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "db.json")
        self.db = VortexDB(db_path=self.db_path)
        self.db.data["settings"] = {
            "domain": "example.com",
            "port": 443,
            "ntls_port": 80,
            "vless_path": "/vortex-vless",
            "vmess_path": "/vortex-vmess",
            "trojan_path": "/vortex-trojan",
            "ss_path": "/vortex-ss",
            "vless_grpc_service": "vortex-grpc",
        }

        self.manager = AccountManager.__new__(AccountManager)
        self.manager.db = self.db

        self.user = {
            "username": "alice",
            "uuid": "11111111-1111-1111-1111-111111111111",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_vless_ws_tls_link(self):
        link = self.manager.generate_vless_links(self.user)["WS TLS"]
        self.assertTrue(link.startswith("vless://"))
        self.assertIn("@example.com:443", link)
        self.assertIn("type=ws", link)
        self.assertIn("security=tls", link)

    def test_vmess_ws_tls_link(self):
        link = self.manager.generate_vmess_links(self.user)["WS TLS"]
        self.assertTrue(link.startswith("vmess://"))

    def test_trojan_ws_tls_link(self):
        link = self.manager.generate_trojan_links(self.user)["WS TLS"]
        self.assertTrue(link.startswith("trojan://"))
        self.assertIn("@example.com:443", link)

    def test_shadowsocks_ws_tls_link(self):
        link = self.manager.generate_ss_links(self.user)["WS TLS"]
        self.assertTrue(link.startswith("ss://"))
        self.assertIn("@example.com:443", link)
        self.assertIn("plugin=", link)


if __name__ == "__main__":
    unittest.main()
