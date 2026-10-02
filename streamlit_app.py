"""Streamlit Community Cloud entry point."""
import logging
import streamlit as st
from app import main

try:
    main()
except Exception:
    logging.exception("Dashboard rendering failed")
    st.error("This view could not be completed. Refresh public data or retry with another company.")
