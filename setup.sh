#!/usr/bin/env bash
# Tao moi truong ao va cai thu vien (macOS / Linux). Chay: bash setup.sh
set -e
python3.11 -m venv .venv || python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-holistic.txt
echo
echo "Xong. Mo VS Code, chon interpreter .venv, nhan F5 de chay 'Holistic + Sim (webcam)'."
