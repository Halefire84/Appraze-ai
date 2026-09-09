"""Tenant-aware persistent storage for Appraze.

The Apps Script backend remains the physical storage layer during migration.
Every request derives identity from authenticated server-side session state.
Browser-supplied workspace values are never used for authorization.
"""

import json
from dataclasses import dataclass

import pandas as pd
import requests
import streamlit as st

from auth import _apps_script_url, _token
from tenant_context import require_tenant


@dataclass
class StorageResult:
    success: bool
    payload: dict = None
    error: str = ""


def _identity_params(shared: bool = False) -> dict:
    """Build storage identity from the authenticated tenant context."""
    context = require_tenant(st.session_state)
    if shared and not context.is_admin:
        raise PermissionError("only the Admin tenant may use shared storage")
    return {
        "username": "" if shared else context.username,
        "is_admin": "true" if shared else str(context.is_admin).lower(),
        "tenant_id": context.tenant_id,
    }


def save_table(df: pd.DataFrame, table: str = "deals", shared: bool = False) -> StorageResult:
    try:
        payload = df.to_json(orient="records", date_format="iso")
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
            return StorageResult(True, payload=None)
        return StorageResult(True, payload=json.loads(raw))
    except Exception as e:
        return StorageResult(False, error=f"connection error: {e}")


def save_deals(df: pd.DataFrame) -> StorageResult:
    return save_table(df, "deals")


def load_deals() -> StorageResult:
    return load_table("deals")
