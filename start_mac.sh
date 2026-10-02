#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -r requirements.txt
exec python -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port "${PORT:-8501}"
