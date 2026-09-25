#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "First-time setup detected. Installing dependencies..."
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install --upgrade pip
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi
streamlit run app.py
