import json
import os
import uuid
import time
import fcntl
from contextlib import contextmanager
from typing import List, Dict, Optional

class UserAccount:
    def __init__(self, username: str, protocol: str, password: str = "", 
                 uuid_str: str = None, expires_at: int = None, 
                 ip_limit: int = 2, quota_gb: int = 0):
        self.username = username
        self.protocol = protocol
        self.password = password
        self.uuid = uuid_str or str(uuid.uuid4())
        self.created_at = int(time.time())
        self.expires_at = expires_at or (self.created_at + 30 * 86400)
        self.status = "active"
        self.ip_limit = ip_limit
        self.quota_gb = quota_gb
        self.used_bandwidth = 0 # In bytes

    def to_dict(self):
        return self.__dict__

class VortexDB:
    def __init__(self, db_path="/usr/local/etc/vortex-x/db.json"):
        self.db_path = db_path
        self.lock_path = f"{db_path}.lock"
        self.data = self._load()

    @contextmanager
    def _lock(self):
        lock_dir = os.path.dirname(self.lock_path)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)
        with open(self.lock_path, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _load(self):
        with self._lock():
            if os.path.exists(self.db_path):
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        return {"users": [], "settings": {}, "hosts": []}

    def save(self):
        with self._lock():
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            tmp_path = f"{self.db_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            os.replace(tmp_path, self.db_path)

    def add_user(self, user: UserAccount):
        self.data["users"].append(user.to_dict())
        self.save()

    def get_user(self, username):
        for u in self.data["users"]:
            if u["username"] == username:
                return u
        return None
