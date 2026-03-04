import os
import subprocess
import shutil
import sys

class SSLManager:
    def __init__(self, domain: str):
        self.domain = domain
        self.cert_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
        self.key_path = f"/etc/letsencrypt/live/{domain}/privkey.pem"
        self.renewal_conf = f"/etc/letsencrypt/renewal/{domain}.conf"

    def _run(self, cmd):
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def _issue_cert_standalone(self):
        subprocess.run(["systemctl", "stop", "nginx"], check=False)

        cmd = [
            "certbot", "certonly", "--standalone",
            "--preferred-challenges", "http",
            "--agree-tos", "--email", f"admin@{self.domain}",
            "-d", self.domain, "--non-interactive"
        ]

        result = self._run(cmd)
        subprocess.run(["systemctl", "start", "nginx"], check=False)
        return result

    def _ensure_webroot_renewal(self) -> None:
        if not os.path.exists(self.renewal_conf):
            return

        try:
            with open(self.renewal_conf, "r", encoding="utf-8") as handle:
                lines = handle.read().splitlines(True)
        except Exception:
            return

        in_params = False
        saw_params = False
        has_webroot_path = False
        changed = False
        out = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_params = stripped.lower() == "[renewalparams]"
                if in_params:
                    saw_params = True
            if in_params and stripped.startswith("authenticator") and "standalone" in stripped:
                out.append("authenticator = webroot\n")
                changed = True
                continue
            if in_params and stripped.startswith("webroot_path"):
                has_webroot_path = True
            out.append(line)

        if not saw_params:
            out.append("\n[renewalparams]\n")
            out.append("authenticator = webroot\n")
            changed = True
            in_params = True

        # Ensure webroot_path exists when authenticator is webroot
        text = "".join(out)
        if "authenticator = webroot" in text and not has_webroot_path:
            # Insert right after authenticator line inside [renewalparams]
            new_out = []
            in_params = False
            inserted = False
            for line in out:
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_params = stripped.lower() == "[renewalparams]"
                new_out.append(line)
                if in_params and stripped.startswith("authenticator") and ("webroot" in stripped) and not inserted:
                    new_out.append("webroot_path = /var/www/html\n")
                    inserted = True
                    changed = True
            out = new_out

        if changed:
            try:
                with open(self.renewal_conf, "w", encoding="utf-8") as handle:
                    handle.write("".join(out))
            except Exception:
                return

    def issue_cert(self):
        print(f"[INFO] Issuing SSL Certificate for {self.domain}...")

        if not shutil.which("certbot"):
            print("[ERROR] certbot is not installed.")
            return False

        os.makedirs("/var/www/html", exist_ok=True)

        # Prefer webroot method to avoid stopping nginx (more stable for production).
        # We create a temporary port-80 vhost for ACME challenge, then remove it.
        temp_conf = f"/etc/nginx/conf.d/vortex-acme-{self.domain}.conf"
        webroot_supported = os.path.isdir("/etc/nginx") and shutil.which("nginx")

        if webroot_supported:
            try:
                with open(temp_conf, "w") as f:
                    f.write(f"""server {{
    listen 80;
    listen [::]:80;
    server_name {self.domain};

    location /.well-known/acme-challenge/ {{
        root /var/www/html;
        try_files $uri =404;
    }}

    location / {{
        add_header Content-Type text/plain;
        return 200 'vortex-x acme';
    }}
}}
""")

                if subprocess.run(["nginx", "-t"], check=False).returncode == 0:
                    subprocess.run(["systemctl", "reload", "nginx"], check=False)
                else:
                    subprocess.run(["systemctl", "restart", "nginx"], check=False)

                cmd = [
                    "certbot", "certonly", "--webroot", "-w", "/var/www/html",
                    "--agree-tos", "--email", f"admin@{self.domain}",
                    "-d", self.domain, "--non-interactive"
                ]
                result = self._run(cmd)
                if result.returncode != 0:
                    print(f"[WARN] Webroot issuance failed: {result.stderr}")
                    raise RuntimeError("webroot_failed")

                print("[SUCCESS] SSL Certificate issued successfully.")
                self._ensure_webroot_renewal()
                self.apply_permissions()
                return True
            except Exception:
                # Fallback: standalone (will stop nginx temporarily)
                result = self._issue_cert_standalone()
                if result.returncode == 0:
                    print("[SUCCESS] SSL Certificate issued successfully.")
                    self._ensure_webroot_renewal()
                    self.apply_permissions()
                    return True
                print(f"[ERROR] SSL Issuance failed: {result.stderr}")
                return False
            finally:
                if os.path.exists(temp_conf):
                    try:
                        os.remove(temp_conf)
                    except Exception:
                        pass
                subprocess.run(["systemctl", "reload", "nginx"], check=False)

        # No nginx environment; use standalone
        result = self._issue_cert_standalone()
        if result.returncode == 0:
            print("[SUCCESS] SSL Certificate issued successfully.")
            self._ensure_webroot_renewal()
            self.apply_permissions()
            return True
        print(f"[ERROR] SSL Issuance failed: {result.stderr}")
        return False

    def renew_cert(self):
        print("[INFO] Renewing SSL Certificates...")
        self._ensure_webroot_renewal()
        result = self._run(["certbot", "renew", "--quiet"])
        if result.returncode == 0:
            subprocess.run(["systemctl", "reload", "nginx"], check=False)
            self.apply_permissions()
            print("[SUCCESS] SSL renewal complete.")
            return True
        print(f"[ERROR] SSL renewal failed: {result.stderr}")
        return False

    def apply_permissions(self):
        """
        Hardens permissions so non-root service user 'vortex-x' can read certs
        without giving access to the whole /etc/letsencrypt/archive.
        """
        print("[INFO] Hardening SSL permissions...")
        # 1. Allow traversal to the directory
        subprocess.run(["chmod", "755", "/etc/letsencrypt/live"], check=False)
        subprocess.run(["chmod", "755", "/etc/letsencrypt/archive"], check=False)

        # 2. Grant read access to the service user for specific domain certs
        if os.path.exists(self.cert_path):
            subprocess.run(["chown", "-R", "vortex-x:vortex-x", f"/etc/letsencrypt/live/{self.domain}"], check=False)
            subprocess.run(["chown", "-R", "vortex-x:vortex-x", f"/etc/letsencrypt/archive/{self.domain}"], check=False)
            subprocess.run(["chmod", "640", self.key_path], check=False)
            subprocess.run(["chmod", "644", self.cert_path], check=False)

    def check_expiry(self):
        if not os.path.exists(self.cert_path):
            return "Missing"

        # Get days left using openssl
        cmd = f"openssl x509 -enddate -noout -in {self.cert_path}"
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if result.returncode == 0:
            # Simple parsing of date format 'notAfter=Mar 27 14:49:19 2026 GMT'
            try:
                return result.stdout.strip().split('=')[1]
            except:
                return "Error Parsing"
        return "Unknown"

if __name__ == "__main__":
    # Add parent directory to path so we can import core
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from core.models import VortexDB

    domain = ""
    try:
        db = VortexDB()
        domain = db.data.get("settings", {}).get("domain", "")
    except Exception:
        domain = ""

    if not domain:
        domain = "yourdomain.com"

    manager = SSLManager(domain)
    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            expiry = manager.check_expiry()
            print(f"Domain: {domain}")
            print(f"SSL Status: {expiry}")
        elif sys.argv[1] == "renew":
            manager.renew_cert()
        elif sys.argv[1] == "issue":
            manager.issue_cert()
    else:
        print("Usage: ssl_manager.py [check|renew|issue]")