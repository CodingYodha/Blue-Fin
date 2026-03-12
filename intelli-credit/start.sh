#!/bin/bash
# Startup script for HuggingFace Spaces
# Creates required directories and launches supervisord

set -e

# Ensure shared tmp exists
mkdir -p /tmp/intelli-credit

# Ensure nginx temp dirs exist (non-root in HF Spaces)
mkdir -p /tmp/nginx_client_body /tmp/nginx_proxy /tmp/nginx_fastcgi /tmp/nginx_uwsgi /tmp/nginx_scgi

echo "========================================"
echo " Intelli-Credit — Starting all services"
echo "========================================"
echo " Frontend : nginx serving static @ :7860"
echo " Backend  : Node.js (Hono) @ :3001"
echo " Go Svc   : Gin @ :8081"
echo " AI Svc   : FastAPI @ :8000"
echo "========================================"

exec supervisord -c /etc/supervisor/conf.d/supervisord.conf
