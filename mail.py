"""
mail.py — optional inbound-mail tracking for Appraze (supplier invoices and
shipment tracking numbers), via read-only IMAP against a Gmail inbox.

Cooper River Trading Co. doesn't order through a fixed warehouse the way a
NAPA Auto Parts or a big-box retailer would — inventory comes from random
estate auctions, HiBid lots, and (maybe someday) liquidation companies, so
there's no single vendor portal to check. What actually needs watching is
whichever inbox those sellers/carriers send invoices and tracking numbers
to. This polls that inbox read-only and flags anything that looks like a
shipment or an invoice, so nothing gets missed scrolling through Gmail by
hand.

To enable it, set two Streamlit secrets (Settings -> Secrets):
    GMAIL_ADDRESS = "the inbox to watch, e.g. chale@cooperrivertradingco.com"
    GMAIL_APP_PASSWORD = "a 16-character Gmail App Password"

Setup, one time, on the Google account being watched:
    1. Turn on 2-Step Verification (myaccount.google.com/security) if it
       isn't already on — required before Google will issue App Passwords.
    2. Create an App Password at myaccount.google.com/apppasswords (choose
       "Mail" as the app). Google shows a 16-character password once — this
       is NOT the account's normal login password — paste it into the
       GMAIL_APP_PASSWORD secret above exactly as shown (spaces are fine,
       they're stripped automatically).
    3. Confirm IMAP is enabled: Gmail Settings (gear icon) -> See all
       settings -> Forwarding and POP/IMAP -> Enable IMAP -> Save Changes.
       It's on by default for most accounts.
    4. Reload the app — the Mail tab pulls the inbox's most recent messages
       and flags anything that looks like a tracking number or invoice.
       Nothing is ever sent, replied to, deleted, or modified — the IMAP
       connection is opened read-only.

Without those two secrets set, every function here returns None/False and
the Mail tab just explains how to turn it on — this mirrors the existing
optional-secret pattern already used for STRIPE_SECRET_KEY,
ANTHROPIC_API_KEY, and APPS_SCRIPT_URL/APPS_SCRIPT_TOKEN (sheets.py).

Split in two like sheets.py splits load/save from the rest of the app:
the actual pattern-matching (detect_tracking, detect_invoice_ref, etc.) is
pure and unit-tested in tests/test_mail_parse.py — see mail_parse.py. The
IMAP fetch here is live network/credential I/O and untested the same way
sheets.py's load/save is.
"""

import email
import imaplib
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime

import streamlit as st

from mail_parse import classify_message, detect_amount, detect_invoice_ref, detect_tracking

_IMAP_HOST = "imap.gmail.com"
# imaplib has no default timeout - an unreachable/slow IMAP server would
# otherwise hang the socket connect indefinitely, and since Streamlit runs
# the whole script top-to-bottom on every rerun, that doesn't just break
# this tab, it freezes the entire app for that session (nothing below the
# Mail tab in app.py would ever render). The timeout applies to the
# underlying socket for the connection's whole lifetime, so it also bounds
# every later login/select/search/fetch call on the same connection, not
# just the initial connect.
_IMAP_TIMEOUT_SECONDS = 15


def is_configured() -> bool:
    """True only once both secrets are present."""
    try:
        address = st.secrets.get("GMAIL_ADDRESS")
        app_password = st.secrets.get("GMAIL_APP_PASSWORD")
    except Exception:
        return False
    return bool(address) and bool(app_password)


def _connect():
    try:
        address = st.secrets.get("GMAIL_ADDRESS")
        app_password = st.secrets.get("GMAIL_APP_PASSWORD")
    except Exception:
        return None
    if not address or not app_password:
        return None
    try:
        conn = imaplib.IMAP4_SSL(_IMAP_HOST, timeout=_IMAP_TIMEOUT_SECONDS)
        conn.login(address, str(app_password).replace(" ", ""))
        return conn
    except Exception:
        return None


def _decode_header_value(value) -> str:
    if not value:
        return ""
    decoded = ""
    for text, encoding in decode_header(value):
        if isinstance(text, bytes):
            decoded += text.decode(encoding or "utf-8", errors="ignore")
        else:
            decoded += text
    return decoded


def _extract_body_snippet(msg, max_chars: int = 500) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition") or "")
            if part.get_content_type() == "text/plain" and "attachment" not in content_disposition:
                try:
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                except Exception:
                    continue
                break
    else:
        try:
            body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
        except Exception:
            body = ""
    return " ".join(body.split())[:max_chars]


def _parse_message(raw_bytes: bytes) -> dict:
    msg = email.message_from_bytes(raw_bytes)
    subject = _decode_header_value(msg.get("Subject"))
    sender = _decode_header_value(msg.get("From"))
    date_header = msg.get("Date")
    try:
        parsed_date = parsedate_to_datetime(date_header) if date_header else None
    except Exception:
        parsed_date = None
    snippet = _extract_body_snippet(msg)
    full_text = f"{subject} {snippet}"
    tracking = detect_tracking(full_text)
    return {
        "Date": parsed_date.strftime("%Y-%m-%d %H:%M") if parsed_date else "",
        "From": sender,
        "Subject": subject,
        "Category": classify_message(subject, snippet),
        "Carrier": tracking[0] if tracking else "",
        "Tracking #": tracking[1] if tracking else "",
        "Invoice/Order Ref": detect_invoice_ref(full_text) or "",
        "Amount": detect_amount(full_text),
        "Snippet": snippet[:200],
    }


@st.cache_data(ttl=120, show_spinner=False)
def fetch_recent_messages(days: int = 14, limit: int = 40):
    """Returns a list of dicts, most-recent first, for the inbox's messages
    in the last `days` days (read-only — nothing is modified/deleted), or
    None if Gmail isn't configured or isn't reachable right now (caller
    should show a "couldn't connect" message rather than treating this the
    same as "not configured").

    Cached for 2 minutes per (days, limit) so switching tabs or editing
    other tables doesn't re-hit the mailbox on every Streamlit rerun — use
    the Mail tab's Refresh button (which clears this cache) to force a
    fresh fetch sooner.
    """
    if not is_configured():
        return None
    conn = _connect()
    if conn is None:
        return None
    try:
        conn.select("INBOX", readonly=True)
        since = (datetime.utcnow() - timedelta(days=days)).strftime("%d-%b-%Y")
        status, data = conn.search(None, f'(SINCE "{since}")')
        if status != "OK" or not data or not data[0]:
            return []
        message_ids = data[0].split()[-limit:]
        messages = []
        for message_id in reversed(message_ids):
            status, msg_data = conn.fetch(message_id, "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                continue
            messages.append(_parse_message(msg_data[0][1]))
        return messages
    except Exception:
        return None
    finally:
        try:
            conn.logout()
        except Exception:
            pass
