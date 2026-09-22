"""
Cooper River Trading Co. — Appraze Persistent Storage
--------------------------------------------------------
Saves/loads each user's `deals` data via the Apps Script backend.

Two-tier model (matches AppsScript_Code.gs):
  - Admins (Alex + Ashley) share ONE workspace — same data, same key.
  - Every other account gets its own private, isolated storage row.

This is deliberately a simple last-write-wins save — good enough for a
solo/small-team beta tool. If Alex and Ashley are both editing at the
exact same moment, whoever saves last wins; there's no merge logic.
"""

import json
from dataclasses import dataclass

import pandas as pd
import requests
import streamlit as st

from auth import _apps_script_url, _token  # reuse the same endpoint config


@dataclass
class StorageResult:
    success: bool
    payload: dict = None
    error: str = ""


def _identity_params(shared: bool = False) -> dict:
    """Params the backend uses to resolve which storage row this session
    owns. shared=True forces the fixed "admin_shared" row regardless of
    who's logged in — AppsScript_Code.gs's resolveOwnerKey_ resolves
    "admin_shared" whenever is_admin=true, independent of username, so
    this doesn't need a real username at all. Used for tables like
    "sales_log" that are one shared cash register for the whole business,
    not per-tester data — without this, a non-admin login's POS checkouts
    would land under their own "tester_<username>" row, where the
    standalone Stripe webhook service (which only ever looks at
    admin_shared) could never find them to reconcile."""
    if shared:
        return {"username": "", "is_admin": "true"}
    return {
        "username": st.session_state.get("username", ""),
        "is_admin": str(bool(st.session_state.get("user_is_admin", False))).lower(),
    }


def save_table(df: pd.DataFrame, table: str = "deals", shared: bool = False) -> StorageResult:
    """Persist any named table (e.g. "deals", "inventory") under this
    session's owner key, or under the fixed shared admin key when
    shared=True (see _identity_params). Each table is stored independently
    server-side — saving one never touches another."""
    try:
        payload = df.to_json(orient="records", date_format="iso")
        # POST, not GET - a GET here put the full table payload in the URL
        # query string, which has a length ceiling most servers/proxies
        # enforce (a few thousand characters). A table with enough rows or
        # long Notes fields would silently fail to save once it crossed
        # that line - moving the payload into the POST body removes the
        # limit entirely, since AppsScript_Code.gs's doPost reads
        # e.parameter the same way doGet does.
        resp = requests.post(
            _apps_script_url(),
            data={
                "token": _token(),
                "action": "save_data",
                "table": table,
                "payload": payload,
                **_identity_params(shared),
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return StorageResult(bool(data.get("success")), error=data.get("error", ""))
    except Exception as e:
        return StorageResult(False, error=f"connection error: {e}")


def load_table(table: str = "deals", shared: bool = False) -> StorageResult:
    try:
        # POST, same reasoning as save_table above - keeps the auth token
        # out of the URL (and therefore out of access/proxy logs), even
        # though this particular request's own payload is small.
        resp = requests.post(
            _apps_script_url(),
            data={
                "token": _token(),
                "action": "load_data",
                "table": table,
                **_identity_params(shared),
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return StorageResult(False, error=data.get("error", "load failed"))
        raw = data.get("payload")
        if not raw:
            return StorageResult(True, payload=None)  # no saved data yet — caller uses defaults
        records = json.loads(raw)
        return StorageResult(True, payload=records)
    except Exception as e:
        return StorageResult(False, error=f"connection error: {e}")


def save_deals(df: pd.DataFrame) -> StorageResult:
    return save_table(df, "deals")


def load_deals() -> StorageResult:
    return load_table("deals")
