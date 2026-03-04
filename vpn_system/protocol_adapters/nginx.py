import os
import subprocess

class NginxAdapter:
    def __init__(self, conf_dir: str = "/etc/nginx/conf.d"):
        self.conf_dir = conf_dir

    def cleanup_conflicts(self, domain: str = ""):
        """Removes default nginx configs and potentially conflicting domain configs."""
        defaults = [
            "/etc/nginx/conf.d/default.conf",
            "/etc/nginx/sites-enabled/default"
        ]
        for path in defaults:
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
        
        # If a specific domain is provided, ensure no other file in conf.d has it
        if domain:
            try:
                conf_files = [f for f in os.listdir(self.conf_dir) if f.endswith(".conf")]
                for f in conf_files:
                    # If the file is not exactly {domain}.conf but contains the domain, it's a conflict
                    if f != f"{domain}.conf":
                        f_path = os.path.join(self.conf_dir, f)
                        with open(f_path, 'r') as content:
                            if domain in content.read():
                                os.remove(f_path)
            except:
                pass

    def _ensure_cloudflare_realip_snippet(self) -> str:
        snippet_path = os.path.join(self.conf_dir, "vortex-x-cloudflare-realip.conf")
        if os.path.exists(snippet_path):
            return snippet_path

        snippet = """# Cloudflare real client IP support
# https://www.cloudflare.com/ips/
real_ip_header CF-Connecting-IP;
real_ip_recursive on;

set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;

set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;
"""
        try:
            os.makedirs(self.conf_dir, exist_ok=True)
            with open(snippet_path, "w") as f:
                f.write(snippet)
        except PermissionError:
            return ""
        return snippet_path

    def generate_vhost(
        self,
        domain: str,
        vless_port: int,
        vmess_port: int,
        trojan_port: int,
        ss_port: int = 0,
        vless_path: str = "/vortex-vless",
        vmess_path: str = "/vortex-vmess",
        trojan_path: str = "/vortex-trojan",
        ss_path: str = "/vortex-ss",
        grpc_service: str = "vortex-grpc"
    ):
        self.cleanup_conflicts(domain)

        snippet_path = self._ensure_cloudflare_realip_snippet()
        cloudflare_include = f"    include {snippet_path};\n" if snippet_path else ""
        
        # Location for Shadowsocks if port provided
        ss_location = ""
        if ss_port > 0:
            ss_location = f"""
    location {ss_path} {{
        if ($http_upgrade != \"websocket\") {{ return 404; }}
        proxy_redirect off;
        proxy_pass http://127.0.0.1:{ss_port};
        proxy_http_version 1.1;
        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host $host;
    }}"""

        vhost_content = f"""
server {{
    listen 80;
    listen [::]:80;
    server_name {domain};
{cloudflare_include}

    # ACME challenge for certbot --webroot
    location /.well-known/acme-challenge/ {{
        root /var/www/html;
        try_files $uri =404;
    }}

    # NTLS WebSocket (no TLS termination)
    location {vless_path} {{
        if ($http_upgrade != \"websocket\") {{ return 404; }}
        proxy_redirect off;
        proxy_pass http://127.0.0.1:{vless_port};
        proxy_http_version 1.1;
        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host $host;
    }}

    location {vmess_path} {{
        if ($http_upgrade != \"websocket\") {{ return 404; }}
        proxy_redirect off;
        proxy_pass http://127.0.0.1:{vmess_port};
        proxy_http_version 1.1;
        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host $host;
    }}

    location {trojan_path} {{
        if ($http_upgrade != \"websocket\") {{ return 404; }}
        proxy_redirect off;
        proxy_pass http://127.0.0.1:{trojan_port};
        proxy_http_version 1.1;
        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host $host;
    }}
    {ss_location}

    location / {{
        return 301 https://$host$request_uri;
    }}
}}

server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {domain};
{cloudflare_include}

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # VLESS WebSocket
    location {vless_path} {{
        if ($http_upgrade != \"websocket\") {{ return 404; }}
        proxy_redirect off;
        proxy_pass http://127.0.0.1:{vless_port};
        proxy_http_version 1.1;
        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host $host;
    }}

    # VMESS WebSocket
    location {vmess_path} {{
        if ($http_upgrade != \"websocket\") {{ return 404; }}
        proxy_redirect off;
        proxy_pass http://127.0.0.1:{vmess_port};
        proxy_http_version 1.1;
        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host $host;
    }}

    # Trojan WebSocket
    location {trojan_path} {{
        if ($http_upgrade != \"websocket\") {{ return 404; }}
        proxy_redirect off;
        proxy_pass http://127.0.0.1:{trojan_port};
        proxy_http_version 1.1;
        proxy_read_timeout 1h;
        proxy_send_timeout 1h;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host $host;
    }}
    {ss_location}

    # VLESS gRPC (Advanced Transport)
    location /{grpc_service} {{
        if ($request_method != \"POST\") {{ return 404; }}
        client_max_body_size 0;
        grpc_read_timeout 1h;
        grpc_send_timeout 1h;
        grpc_set_header Host $host;
        grpc_pass grpc://127.0.0.1:10003;
    }}

    # Fallback / Fake Website
    location / {{
        root /var/www/html;
        index index.html;
    }}
}}
"""
        conf_path = os.path.join(self.conf_dir, f"{domain}.conf")
        with open(conf_path, "w") as f:
            f.write(vhost_content)
        
        # Validate and Reload/Restart Nginx
        if subprocess.run(["nginx", "-t"], check=False).returncode == 0:
            if subprocess.run(["systemctl", "reload", "nginx"], check=False).returncode != 0:
                subprocess.run(["systemctl", "restart", "nginx"], check=False)
        else:
            print("[ERROR] Nginx configuration test failed.")
