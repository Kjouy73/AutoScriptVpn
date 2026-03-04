import os
import sys
import subprocess
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import VortexDB

class TrafficMonitor:
    def __init__(self):
        self.db = VortexDB()
        self.xray_api = "127.0.0.1:10085"

    def get_xray_stats(self):
        """Fetches traffic stats from Xray API via xray stats command."""
        try:
            cmd = ["xray", "api", "statsquery", "--server", self.xray_api, "--pattern", "user"]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception:
            return None
        return None

    def _parse_xray_user_counters(self, xray_data: dict) -> dict:
        """
        Returns: {email: {"uplink": int, "downlink": int}}
        Xray counters are cumulative, so we store last seen counters per user and apply deltas.
        """
        counters = {}
        if not xray_data or "stat" not in xray_data:
            return counters

        for stat in xray_data["stat"]:
            name = stat.get("name", "")
            value_raw = stat.get("value", 0)
            try:
                value = int(value_raw)
            except Exception:
                continue

            parts = name.split(">>>")
            # Expected: user>>>email>>>traffic>>>uplink|downlink
            if len(parts) < 4 or parts[0] != "user":
                continue

            email = parts[1]
            direction = parts[3]
            if direction not in {"uplink", "downlink"}:
                continue

            entry = counters.setdefault(email, {"uplink": 0, "downlink": 0})
            entry[direction] = value

        return counters

    def sync_stats(self):
        """Syncs cumulative counters from Xray into per-user used_bandwidth via delta accounting."""
        xray_data = self.get_xray_stats()
        counters = self._parse_xray_user_counters(xray_data)

        if not counters:
            return

        for user in self.db.data.get("users", []):
            email = user.get("username")
            if not email or email not in counters:
                continue

            current = counters[email]

            if "xray_last" not in user:
                user["xray_last"] = {"uplink": int(current.get("uplink", 0)), "downlink": int(current.get("downlink", 0))}
                continue

            last = user.get("xray_last") or {"uplink": 0, "downlink": 0}

            delta_up = max(0, int(current.get("uplink", 0)) - int(last.get("uplink", 0)))
            delta_down = max(0, int(current.get("downlink", 0)) - int(last.get("downlink", 0)))
            delta_total = delta_up + delta_down

            if delta_total:
                user["used_bandwidth"] = int(user.get("used_bandwidth", 0)) + delta_total

            user["xray_last"] = {"uplink": int(current.get("uplink", 0)), "downlink": int(current.get("downlink", 0))}

        self.db.save()

if __name__ == "__main__":
    monitor = TrafficMonitor()
    monitor.sync_stats()
