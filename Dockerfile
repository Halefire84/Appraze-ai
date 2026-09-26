# Fly.io deployment image for the Appraze FastAPI backend: the Stripe
# webhook receiver, Stripe Connect POS backend, comps collector, and comps
# history poller (stripe_webhook_server.py mounts all of them; see
# docs/FLY_DEPLOY.md). Sized for a small (256MB) machine.
FROM python:3.11-slim

WORKDIR /app

# Only the exact modules this service imports (traced by hand, verified by
# actually booting this exact file set -- see docs/FLY_DEPLOY.md) -- not
# the whole repo, and never android/ (500+MB, irrelevant here) or any
# Streamlit-app-only file.
COPY requirements-fly.txt .
RUN pip install --no-cache-dir -r requirements-fly.txt

# The streamlit stub goes on PYTHONPATH ahead of site-packages so
# `import streamlit` resolves to it instead of a real (uninstalled, by
# design) streamlit package. See deploy/streamlit_stub/streamlit/__init__.py
# for exactly why this is safe.
COPY deploy/streamlit_stub /streamlit_stub
ENV PYTHONPATH=/streamlit_stub

COPY comps.py comps_adapters.py comps_collector.py comps_poller.py \
     finance.py pos_connect.py stripe_webhook_server.py stripe_webhooks.py \
     telemetry.py webhook_store.py ./

# SQLite state (pos_connect.py, comps_poller.py) lives on the mounted
# volume at /data, set via POS_CONNECT_DB / COMPS_POLLER_DB in fly.toml.
RUN mkdir -p /data

EXPOSE 8000

# Single process, single worker: this machine's whole memory budget is
# sized for one Python process, not a multi-worker pool.
CMD ["uvicorn", "stripe_webhook_server:app", "--host", "0.0.0.0", "--port", "8000"]
