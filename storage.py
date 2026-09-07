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


def _identity_params() -> dict:
    """Params the backend uses to resolve which storage row this session owns."""
    return {
        "username": st.session_state.get("username", ""),
        "is_admin": str(bool(st.session_state.get("user_is_admin", False))).lower(),
    }


def save_table(df: pd.DataFrame, table: str = "deals") -> StorageResult:
    """Persist any named table (e.g. "deals", "inventory") under this
    session's owner key. Each table is stored independently server-side —
    saving one never touches another."""
    try:
        payload = df.to_json(orient="records", date_format="iso")
        resp = requests.get(
            _apps_script_url(),
            params={
                "token": _token(),
                "action": "save_data",
                "table": table,
                "payload": payload,
                **_identity_params(),
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return StorageResult(bool(data.get("success")), error=data.get("error", ""))
    except Exception as e:
        return StorageResult(False, error=f"connection error: {e}")


def load_table(table: str = "deals") -> StorageResult:
    try:
        resp = requests.get(
            _apps_script_url(),
            params={
                "token": _token(),
                "action": "load_data",
                "table": table,
                **_identity_params(),
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
