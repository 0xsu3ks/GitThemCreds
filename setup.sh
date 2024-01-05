#!/bin/bash

cat .banner
echo ""
echo "[+] Installing Python packages..."
pip install -r requirements.txt
echo ""
echo "[+] Installing Trufflehog binary..."
7z x trufflehog.7z
echo ""
echo "[+] All set!"
echo ""
python3 GitThemCreds.py --help
