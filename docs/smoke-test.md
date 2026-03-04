# Vortex-x Smoke Test (Post-Install)

Dokumen ini adalah checklist minimal untuk memastikan instalasi Vortex-x sehat setelah deploy/update.

## Supported OS (target)
- Ubuntu/Debian family
- Alma/Rocky/CentOS/Alibaba Linux family

## 1) Verifikasi binary & runtime sync
```bash
vortex-x --version
bash vpn_system/installer/install.sh --sync-runtime
```

## 2) Verifikasi dependency Python
```bash
python3 -c "import psutil, yaml"
```

## 3) Verifikasi nginx
```bash
nginx -t
systemctl restart nginx
systemctl status nginx --no-pager
```

## 4) Verifikasi xray
```bash
systemctl restart xray
systemctl status xray --no-pager
```

## 5) Jalankan doctor
```bash
vortex-x doctor
vortex-x doctor --json
```

## 6) Verifikasi cron jobs
```bash
cat /etc/cron.d/vortex-x
```

## 7) Verifikasi fail2ban (jika dipakai)
```bash
systemctl restart fail2ban
fail2ban-client status
fail2ban-client status xray-access
```

## 8) Verifikasi SSL
```bash
python3 /usr/local/lib/vortex-x/scripts/ssl_manager.py check
python3 /usr/local/lib/vortex-x/scripts/ssl_manager.py renew
```

## 9) Verifikasi WireGuard (opsional)
```bash
systemctl status wg-quick@wg0 --no-pager
wg show
```

## 10) Verifikasi OpenVPN (opsional)
```bash
systemctl status openvpn-server@server --no-pager || true
ls -la /usr/local/etc/vortex-x/openvpn-clients || true
```
