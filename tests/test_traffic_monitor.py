import os
import sys
import tempfile
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "vpn_system"))

from core.models import VortexDB
from monitoring.traffic_monitor import TrafficMonitor


class TrafficMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "db.json")
        self.db = VortexDB(db_path=self.db_path)
        self.db.data["users"] = [
            {
                "username": "alice",
                "protocol": "vless",
                "used_bandwidth": 0,
                "xray_last": {"uplink": 0, "downlink": 0},
            }
        ]
        self.db.save()

        self.monitor = TrafficMonitor.__new__(TrafficMonitor)
        self.monitor.db = self.db
        self.monitor.xray_api = "127.0.0.1:10085"

    def tearDown(self):
        self.tmp.cleanup()

    def test_delta_accounting(self):
        payload1 = {
            "stat": [
                {"name": "user>>>alice>>>traffic>>>uplink", "value": "100"},
                {"name": "user>>>alice>>>traffic>>>downlink", "value": "200"},
            ]
        }
        counters = self.monitor._parse_xray_user_counters(payload1)
        self.assertEqual(counters["alice"]["uplink"], 100)
        self.assertEqual(counters["alice"]["downlink"], 200)

        # Apply first sync
        self.monitor.get_xray_stats = lambda: payload1
        self.monitor.sync_stats()
        self.assertEqual(self.db.data["users"][0]["used_bandwidth"], 300)

        # Second sync with cumulative counters; delta should be +50
        payload2 = {
            "stat": [
                {"name": "user>>>alice>>>traffic>>>uplink", "value": "120"},
                {"name": "user>>>alice>>>traffic>>>downlink", "value": "230"},
            ]
        }
        self.monitor.get_xray_stats = lambda: payload2
        self.monitor.sync_stats()
        self.assertEqual(self.db.data["users"][0]["used_bandwidth"], 350)


if __name__ == "__main__":
    unittest.main()
