"""Minimal stand-in for the real `streamlit` package, used ONLY in the
Fly.io deployment image for stripe_webhook_server.py's FastAPI app (see
docs/FLY_DEPLOY.md). That service is not a Streamlit app and never renders
a page; comps_adapters.py's ONLY use of streamlit is `st.secrets.get(...)`
inside _ebay_client_credentials(), which comps_collector.py and
comps_poller.py both replace at import time with an env-var-reading
version before it is ever called (_use_env_ebay_credentials()). The real
streamlit package is real weight (tens of MB of RSS at import alone, on
top of pandas' own cost) purely to satisfy that one `import streamlit as
st` line -- weight this single-purpose backend has no other reason to
carry on a memory-constrained machine. The real package is still
installed and used everywhere else in this repo (the actual Streamlit web
app, and every test that imports streamlit directly) -- this stub is
scoped to the Fly deploy image's Docker build only (via requirements-fly.txt
omitting streamlit, and PYTHONPATH ordering in the Dockerfile), and never
touches local dev, CI, comps_adapters.py's own source, or the debug/
release Android build.
"""


class _Secrets(dict):
    """dict.get() already matches st.secrets.get()'s call signature
    exactly; this only exists so `import streamlit as st; st.secrets`
    resolves at all. Empty on purpose -- the deployment never reads
    secrets this way (see module docstring above); real credentials come
    from Fly secrets / environment variables instead."""


secrets = _Secrets()
