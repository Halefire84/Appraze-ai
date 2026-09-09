"""Tenant-aware persistent storage for Appraze.

The Apps Script backend still owns the physical storage rows. This module
ensures every request derives its identity from the authenticated server-side
session and sends the stable tenant id as an additional audit/context field.
A browser-supplied ``workspace`` value is never used for authorization.
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
    """Return storage identity derived from authenticated tenant context.

    ``shared=True`` is intentionally restricted to the owner/admin tenant.
    Customer sessions cannot request the shared owner row merely by setting a
    flag in session state. The Apps Script-compatible username/is_admin fields
    remain in place for backward compatibility while ``tenant_id`` provides a
    stable application-level tenant identity.
    """
    context = require_tenant(st.session_state)
    if shared:
        if not context.is_admin:
            raise PermissionError("only the Admin tenant may use shared storage")
        return {
            "username": "",
            "is_admin": "true",
            "tenant_id": context.tenant_id,
        }
    return {
        "username": context.username,
        "is_admin": str(context.is_admin).lower(),
        "tenant_id": context.tenant_id,
    }


def save_table(df: pd.DataFrame, table: str = "deals", shared: bool = False) -> StorageResult:
    """Persist a table under the authenticated tenant's storage identity."""
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
