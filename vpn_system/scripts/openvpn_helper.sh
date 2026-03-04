#!/bin/bash

set -euo pipefail

ACTION="${1:-}"
USERNAME="${2:-}"

if [ -z "$ACTION" ] || [ -z "$USERNAME" ]; then
    echo "Usage: $0 add <username>"
    exit 1
fi

LIB_PATH="/usr/local/lib/vortex-x"
if [ ! -d "$LIB_PATH" ]; then
    LIB_PATH="$(cd "$(dirname "$0")/.." && pwd)"
fi

case "$ACTION" in
    add)
        # Try to generate client cert with easy-rsa if available.
        EASYRSA_DIR=""
        if [ -d "/etc/openvpn/server/easy-rsa" ]; then
            EASYRSA_DIR="/etc/openvpn/server/easy-rsa"
        elif [ -d "/etc/openvpn/easy-rsa" ]; then
            EASYRSA_DIR="/etc/openvpn/easy-rsa"
        fi

        if [ -n "$EASYRSA_DIR" ] && [ -x "$EASYRSA_DIR/easyrsa" ]; then
            (cd "$EASYRSA_DIR" && ./easyrsa --batch build-client-full "$USERNAME" nopass) || true
        elif command -v easyrsa >/dev/null 2>&1; then
            # If easyrsa is installed as a command, it still requires an initialized PKI dir.
            if [ -n "$EASYRSA_DIR" ]; then
                (cd "$EASYRSA_DIR" && easyrsa --batch build-client-full "$USERNAME" nopass) || true
            else
                easyrsa --batch build-client-full "$USERNAME" nopass || true
            fi
        else
            echo "[WARN] easy-rsa not found. Skipping client cert generation."
        fi

        OUT_DIR="/usr/local/etc/vortex-x/openvpn-clients"
        mkdir -p "$OUT_DIR"

        python3 - <<PY > "$OUT_DIR/${USERNAME}.ovpn"
import sys

sys.path.append("${LIB_PATH}")

from core.models import VortexDB
from protocol_adapters.openvpn import OpenVPNAdapter

db = VortexDB()
domain = db.data.get("settings", {}).get("domain", "YOUR_DOMAIN")
adapter = OpenVPNAdapter()
print(adapter.generate_client_config("${USERNAME}", domain))
PY

        chmod 600 "$OUT_DIR/${USERNAME}.ovpn" || true
        echo "[OK] OpenVPN profile written: $OUT_DIR/${USERNAME}.ovpn"
        ;;
    *)
        echo "Usage: $0 add <username>"
        exit 1
        ;;
esac
