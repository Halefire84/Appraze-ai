/**
 * Appraze — Auth + Data Storage backend
 * Deploy: Extensions > Apps Script (from inside your Google Sheet) > paste this
 * as Code.gs > Deploy > New deployment > Web app
 *   - Execute as: Me
 *   - Who has access: Anyone with the link
 * Copy the resulting Web App URL into Streamlit secrets as APPS_SCRIPT_URL.
 *
 * SHEET_ID below should match your existing GOOGLE_SHEET_ID.
 * TOKEN below should match your existing APPS_SCRIPT_TOKEN secret —
 * this is what stops randoms from hitting your endpoint.
 *
 * Two-tier storage model:
 *   - Admins (you + Ashley) all read/write the SAME row, key "admin_shared" —
 *     so your deal data is one shared workspace, not two separate copies.
 *   - Everyone else gets their own private row keyed by their username —
 *     fully isolated, nobody else can read or overwrite it.
 *
 * SECURITY: SHEET_ID, TOKEN, and ADMIN_SETUP_CODE below are placeholders.
 * Replace all three with your own values before deploying — never commit
 * real values to source control. This file previously had real values
 * checked in; if this repo is that one, treat that TOKEN and
 * ADMIN_SETUP_CODE as compromised and rotate them (redeploy with new
 * values and update the APPS_SCRIPT_TOKEN secret) even after this fix.
 */

const SHEET_ID = "REPLACE_WITH_YOUR_GOOGLE_SHEET_ID";
const TOKEN = "REPLACE_WITH_YOUR_OWN_LONG_RANDOM_STRING";

// Change this to your own private value before deploying, then share it only
// with whoever else should be an admin. Anyone who signs up with this code
// becomes an admin and joins the shared workspace. Leave blank to disable
// admin signup entirely.
const ADMIN_SETUP_CODE = "REPLACE_WITH_YOUR_OWN_ADMIN_INVITE_CODE";

const USERS_SHEET_NAME = "Users";
const USERS_HEADER = ["username", "password_hash", "display_name", "is_admin", "is_paid", "created_at"];

const STORAGE_SHEET_NAME = "Storage";
const STORAGE_HEADER = ["owner_key", "table", "payload_json", "updated_at"];

const PROCESSED_SHEET_NAME = "ProcessedFiles";
const PROCESSED_HEADER = ["file_id", "file_name", "processed_at"];

// Server-side Appraze AI usage controls. These limits are enforced here,
// not in Streamlit session state, so browser reruns cannot reset them.
const AI_USAGE_SHEET_NAME = "AIUsage";
const AI_USAGE_HEADER = ["username","month_key","day_key","successful_calls","reserved_calls","daily_successful","daily_reserved","input_tokens","output_tokens","estimated_cost_usd","updated_at"];
const AI_CUSTOMER_MONTHLY_LIMIT = 100;
const AI_CUSTOMER_DAILY_LIMIT = 10;
const AI_ADMIN_MONTHLY_LIMIT = 500;
const AI_ADMIN_DAILY_LIMIT = 25;
const AI_RESERVATION_TTL_MS = 15 * 60 * 1000;

// Operational event log (errors + financial-decision/payment events), kept
// as a normal "table" row in the Storage sheet under admin_shared -- no new
// sheet needed. Capped so the payload_json cell never approaches Google
// Sheets' ~50,000-character per-cell limit; the log is meant for recent
// diagnostic visibility, not a permanent audit trail (durable financial
// records already live in sales_log/AIUsage, which have their own
// precedence/idempotency rules and are never trimmed).
const EVENT_LOG_TABLE = "event_log";
const EVENT_LOG_MAX_ENTRIES = 300;

// Supported file types for invoice/inventory scanning — images and PDFs only
// (matches what Claude's vision API can read directly).
const SUPPORTED_MIME_TYPES = [
  "image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf",
];
const MAX_FILES_PER_SCAN = 12; // keeps each response small and fast

function doGet(e) {
  return handleRequest(e);
}

function doPost(e) {
  // Apps Script Web Apps receive POST params the same way as GET params
  // when the client sends them as form-encoded data.
  return handleRequest(e);
}

function handleRequest(e) {
  try {
    const params = e.parameter;
    if (params.token !== TOKEN) {
      return jsonResponse({ success: false, error: "unauthorized" });
    }

    switch (params.action) {
      case "signup":
        return handleSignup_(getUsersSheet_(), params);
      case "login":
        return handleLogin_(getUsersSheet_(), params);
      case "save_data":
        return handleSaveData_(getStorageSheet_(), getUsersSheet_(), params);
      case "load_data":
        return handleLoadData_(getStorageSheet_(), getUsersSheet_(), params);
      case "update_sales_log_status":
        return handleUpdateSalesLogStatus_(getStorageSheet_(), params);
      case "set_paid":
        return handleSetPaid_(getUsersSheet_(), params);
      case "scan_folder":
        return handleScanFolder_(params);
      case "mark_processed":
        return handleMarkProcessed_(getProcessedSheet_(), params);
      case "reserve_ai_usage":
        return handleReserveAiUsage_(getUsersSheet_(), getAiUsageSheet_(), params);
      case "finalize_ai_usage":
        return handleFinalizeAiUsage_(getAiUsageSheet_(), params);
      case "release_ai_usage":
        return handleReleaseAiUsage_(getAiUsageSheet_(), params);
      case "get_ai_usage":
        return handleGetAiUsage_(getUsersSheet_(), getAiUsageSheet_(), params);
      case "log_event":
        return handleLogEvent_(getStorageSheet_(), params);
      default:
        return jsonResponse({ success: false, error: "unknown action" });
    }
  } catch (err) {
    return jsonResponse({ success: false, error: String(err) });
  }
}

function getUsersSheet_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName(USERS_SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(USERS_SHEET_NAME);
    sheet.appendRow(USERS_HEADER);
  }
  return sheet;
}

function getStorageSheet_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName(STORAGE_SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(STORAGE_SHEET_NAME);
    sheet.appendRow(STORAGE_HEADER);
    return sheet;
  }
  migrateStorageSheetIfNeeded_(sheet);
  return sheet;
}

// One-time migration for sheets created before multi-table support: the
// old schema was [owner_key, payload_json, updated_at] (every row was
// implicitly the "deals" table, the only one that existed). Detecting
// this per-row at read time doesn't work — payload_json is always
// truthy, so a naive "column B is empty -> legacy row" check silently
// misreads every legacy row's JSON payload as if it were the table name,
// meaning the row never matches table="deals" again and looks like the
// data vanished. Migrating the whole sheet once, keyed off the header
// row, is the only reliable way to tell old rows from new ones.
function migrateStorageSheetIfNeeded_(sheet) {
  // Cheap check before taking the lock: the common case (already migrated,
  // or a brand-new sheet) never needs to wait on anything.
  if (!isLegacySchema_(sheet)) return;

  // Two requests can both reach here for the same still-legacy sheet at
  // the same time (Apps Script Web Apps run concurrently). Without a
  // lock, both would see 3 columns and both call insertColumnAfter(1),
  // inserting two columns instead of one and shifting payload/updated_at
  // out of place. The lock plus a second header check after acquiring it
  // (double-checked locking) guarantees only the first execution to get
  // the lock actually performs the insert; the second sees the
  // already-migrated 4-column header and no-ops.
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    if (!isLegacySchema_(sheet)) return;

    const lastRow = sheet.getLastRow();
    sheet.insertColumnAfter(1);
    sheet.getRange(1, 2).setValue("table");
    const numDataRows = lastRow - 1;
    if (numDataRows > 0) {
      const tableColumnValues = [];
      for (let i = 0; i < numDataRows; i++) tableColumnValues.push(["deals"]);
      sheet.getRange(2, 2, numDataRows, 1).setValues(tableColumnValues);
    }
  } finally {
    lock.releaseLock();
  }
}

function isLegacySchema_(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow === 0) return false; // brand-new empty sheet, nothing to migrate
  const header = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  return header.length === 3 && header[0] === "owner_key" && header[1] === "payload_json";
}

function getProcessedSheet_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName(PROCESSED_SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(PROCESSED_SHEET_NAME);
    sheet.appendRow(PROCESSED_HEADER);
  }
  return sheet;
}

// ---------------------------------------------------------------------------
// AUTH
// ---------------------------------------------------------------------------

function handleSignup_(sheet, params) {
  const username = String(params.username || "").trim().toLowerCase();
  const passwordHash = String(params.password_hash || "");
  const displayName = String(params.display_name || username);
  const adminCode = String(params.admin_code || "");

  if (!username || !passwordHash) {
    return jsonResponse({ success: false, error: "username and password are required" });
  }
  if (username.length < 3) {
    return jsonResponse({ success: false, error: "username must be at least 3 characters" });
  }

  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).toLowerCase() === username) {
      return jsonResponse({ success: false, error: "that username is already taken" });
    }
  }

  const isAdmin = !!ADMIN_SETUP_CODE && adminCode === ADMIN_SETUP_CODE;

  sheet.appendRow([username, passwordHash, displayName, isAdmin ? "TRUE" : "FALSE", "FALSE", new Date().toISOString()]);
  return jsonResponse({ success: true, display_name: displayName, is_admin: isAdmin, is_paid: false, username: username });
}

function handleLogin_(sheet, params) {
  const username = String(params.username || "").trim().toLowerCase();
  const passwordHash = String(params.password_hash || "");

  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).toLowerCase() === username) {
      if (String(data[i][1]) === passwordHash) {
        return jsonResponse({
          success: true,
          display_name: data[i][2],
          is_admin: String(data[i][3]).toUpperCase() === "TRUE",
          is_paid: String(data[i][4]).toUpperCase() === "TRUE",
          username: username,
        });
      }
      return jsonResponse({ success: false, error: "incorrect password" });
    }
  }
  return jsonResponse({ success: false, error: "no account with that username" });
}

function handleSetPaid_(sheet, params) {
  const username = String(params.username || "").trim().toLowerCase();
  if (!username) {
    return jsonResponse({ success: false, error: "username required" });
  }
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).toLowerCase() === username) {
      sheet.getRange(i + 1, 5).setValue("TRUE"); // is_paid column
      return jsonResponse({ success: true });
    }
  }
  return jsonResponse({ success: false, error: "no account with that username" });
}

// ---------------------------------------------------------------------------
// DATA STORAGE (shared admin workspace + per-tester isolated storage)
// ---------------------------------------------------------------------------

function resolveOwnerKey_(usersSheet, params) {
  // Admins all share one workspace row; everyone else is isolated by
  // username. Admin status is looked up from the Users sheet by username --
  // it is NEVER taken from a client-supplied is_admin param, since that
  // would let anyone read/write the shared admin workspace just by sending
  // is_admin=true.
  const username = String(params.username || "").trim().toLowerCase();
  const user = username ? findUser_(usersSheet, username) : null;
  if (user && user.isAdmin) return "admin_shared";
  return "tester_" + username;
}

function handleSaveData_(sheet, usersSheet, params) {
  // migrateStorageSheetIfNeeded_ (called from getStorageSheet_, before this
  // ever runs) guarantees every row already has a real "table" value, so
  // there's no legacy-row case left to special-case here.
  const ownerKey = resolveOwnerKey_(usersSheet, params);
  const table = String(params.table || "deals");
  const payload = String(params.payload || "{}");

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const data = sheet.getDataRange().getValues();
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] === ownerKey && data[i][1] === table) {
        sheet.getRange(i + 1, 3).setValue(payload);
        sheet.getRange(i + 1, 4).setValue(new Date().toISOString());
        return jsonResponse({ success: true });
      }
    }
    sheet.appendRow([ownerKey, table, payload, new Date().toISOString()]);
    return jsonResponse({ success: true });
  } finally {
    lock.releaseLock();
  }
}

function handleLoadData_(sheet, usersSheet, params) {
  const ownerKey = resolveOwnerKey_(usersSheet, params);
  const table = String(params.table || "deals");
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === ownerKey && data[i][1] === table) {
      return jsonResponse({ success: true, payload: data[i][2], updated_at: data[i][3] });
    }
  }
  return jsonResponse({ success: true, payload: null });
}

// Status precedence for sales_log rows -- mirrors stripe_webhooks.py's
// STATUS_RANK exactly (keep the two in sync if either changes). A delayed/
// out-of-order webhook delivery must never downgrade a more-final status:
// a late "charge.succeeded" arriving after its own refund must not
// resurrect "Paid (Card)" over "Refunded" (F-09). This is the one place
// that actually enforces it for the live webhook path -- stripe_webhooks.py's
// own can_transition()/update_invoice_status() only protect an in-memory
// list a caller passes in; stripe_webhook_server.py never calls those, it
// calls this function directly, so the precedence check has to live here
// too or the live path stays unprotected regardless of what the Python
// module does.
var SALES_LOG_STATUS_RANK_ = {
  "Awaiting Payment": 0,
  "Failed": 1,
  "Payment Failed": 1,
  "Paid": 2,
  "Paid (Card)": 2,
  "Partially Refunded": 3,
  "Refunded": 4
};

function salesLogStatusRank_(status) {
  if (!status || !(status in SALES_LOG_STATUS_RANK_)) return -1;
  return SALES_LOG_STATUS_RANK_[status];
}

// Atomic single-row update for the sales_log table, used by the Stripe
// webhook service instead of load-mutate-save (see webhook_store.py /
// stripe_webhook_server.py). Read + mutate + write happen inside this one
// locked execution, so two webhook deliveries arriving close together
// can't race and silently clobber each other's status update the way a
// separate load-then-save round trip from the caller could.
//
// Durable event-id idempotency: when the caller passes event_id, the last
// Stripe event id that was actually applied to this invoice is persisted
// in the row itself (_last_event_id -- no new sheet/schema needed, since
// sales_log rows are already free-form JSON). Stripe guarantees
// at-least-once delivery, so the same event can arrive more than once,
// including after this process has restarted or across multiple instances
// of stripe_webhook_server.py -- an in-memory "seen events" set would not
// survive either of those, but this row field does. A redelivery of an
// event_id already recorded on the row is a no-op duplicate, distinct from
// the ordinary status-precedence downgrade check below.
function handleUpdateSalesLogStatus_(sheet, params) {
  const invoiceId = String(params.invoice_id || "");
  const newStatus = String(params.new_status || "");
  const eventId = String(params.event_id || "");
  const force = String(params.force || "") === "true";
  if (!invoiceId || !newStatus) {
    return jsonResponse({ success: false, error: "invoice_id and new_status are required" });
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const ownerKey = "admin_shared";
    const table = "sales_log";
    const data = sheet.getDataRange().getValues();
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] === ownerKey && data[i][1] === table) {
        let rows;
        try {
          rows = JSON.parse(data[i][2] || "[]");
        } catch (e) {
          return jsonResponse({ success: false, error: "sales_log payload is not valid JSON" });
        }
        let found = false;
        let applied = false;
        let duplicate = false;
        let currentStatus = null;
        for (let j = 0; j < rows.length; j++) {
          if (rows[j]["Invoice #"] === invoiceId) {
            found = true;
            currentStatus = rows[j]["Status"];
            if (eventId && rows[j]["_last_event_id"] === eventId) {
              // Same Stripe event redelivered -- already applied, skip
              // entirely so a replay can never produce a duplicate effect.
              duplicate = true;
              break;
            }
            if (force || salesLogStatusRank_(newStatus) >= salesLogStatusRank_(currentStatus)) {
              rows[j]["Status"] = newStatus;
              if (eventId) rows[j]["_last_event_id"] = eventId;
              applied = true;
            }
            break;
          }
        }
        if (!found) {
          return jsonResponse({ success: true, found: false });
        }
        if (duplicate) {
          return jsonResponse({ success: true, found: true, applied: false, duplicate: true, current_status: currentStatus });
        }
        if (!applied) {
          // Found the row but refused to downgrade it -- not an error,
          // the caller (and Stripe) still gets a 2xx acknowledgment.
          return jsonResponse({ success: true, found: true, applied: false, current_status: currentStatus });
        }
        sheet.getRange(i + 1, 3).setValue(JSON.stringify(rows));
        sheet.getRange(i + 1, 4).setValue(new Date().toISOString());
        return jsonResponse({ success: true, found: true, applied: true });
      }
    }
    return jsonResponse({ success: true, found: false }); // sales_log table doesn't exist yet
  } finally {
    lock.releaseLock();
  }
}

// Appends one diagnostic entry to the shared event_log table. Best-effort
// by design from the caller's side (storage.py's log_event() never raises),
// but this handler itself is atomic (lock + read + append + trim + write)
// so concurrent loggers (two Streamlit sessions, the webhook service) can
// never race and silently drop each other's entry the way a naive
// load-then-save round trip could.
function handleLogEvent_(sheet, params) {
  const level = String(params.level || "INFO").toUpperCase().slice(0, 20);
  const eventType = String(params.event_type || "").slice(0, 60);
  const source = String(params.source || "").slice(0, 80);
  const message = String(params.message || "").slice(0, 500);
  let context = String(params.context || "").slice(0, 1000);

  const entry = {
    timestamp: new Date().toISOString(),
    level: level,
    event_type: eventType,
    source: source,
    message: message,
    context: context,
  };

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const ownerKey = "admin_shared";
    const data = sheet.getDataRange().getValues();
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] === ownerKey && data[i][1] === EVENT_LOG_TABLE) {
        let rows;
        try {
          rows = JSON.parse(data[i][2] || "[]");
        } catch (e) {
          rows = []; // corrupted payload -- start fresh rather than fail every future log call
        }
        rows.push(entry);
        if (rows.length > EVENT_LOG_MAX_ENTRIES) {
          rows = rows.slice(rows.length - EVENT_LOG_MAX_ENTRIES);
        }
        sheet.getRange(i + 1, 3).setValue(JSON.stringify(rows));
        sheet.getRange(i + 1, 4).setValue(new Date().toISOString());
        return jsonResponse({ success: true });
      }
    }
    sheet.appendRow([ownerKey, EVENT_LOG_TABLE, JSON.stringify([entry]), new Date().toISOString()]);
    return jsonResponse({ success: true });
  } finally {
    lock.releaseLock();
  }
}

function getAiUsageSheet_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  let sheet = ss.getSheetByName(AI_USAGE_SHEET_NAME);
  if (!sheet) { sheet = ss.insertSheet(AI_USAGE_SHEET_NAME); sheet.appendRow(AI_USAGE_HEADER); }
  return sheet;
}

function aiPeriodKeys_() {
  const now = new Date();
  return {
    monthKey: Utilities.formatDate(now, Session.getScriptTimeZone(), "yyyy-MM"),
    dayKey: Utilities.formatDate(now, Session.getScriptTimeZone(), "yyyy-MM-dd"),
    nowMs: now.getTime()
  };
}

function findUser_(sheet, username) {
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim().toLowerCase() === username) {
      return { row: i + 1, isAdmin: String(data[i][3]).toUpperCase() === "TRUE", isPaid: String(data[i][4]).toUpperCase() === "TRUE" };
    }
  }
  return null;
}

function findAiUsageRow_(sheet, username, monthKey) {
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim().toLowerCase() === username && String(data[i][1]) === monthKey) return i + 1;
  }
  return 0;
}

function usagePayload_(vals, allowed, error, monthlyLimit, dailyLimit, dayKey) {
  const dailyKey = vals.length ? String(vals[2]) : dayKey;
  return {success: allowed, allowed: allowed, error: error || "",
    monthly_used: vals.length ? Number(vals[3]) || 0 : 0,
    monthly_reserved: vals.length ? Number(vals[4]) || 0 : 0,
    monthly_limit: monthlyLimit,
    daily_used: vals.length && dailyKey === dayKey ? Number(vals[5]) || 0 : 0,
    daily_reserved: vals.length && dailyKey === dayKey ? Number(vals[6]) || 0 : 0,
    daily_limit: dailyLimit,
    monthly_cost_usd: vals.length ? Number((Number(vals[9]) || 0).toFixed(6)) : 0};
}

function handleReserveAiUsage_(usersSheet, usageSheet, params) {
  const username = String(params.username || "").trim().toLowerCase();
  if (!username) return jsonResponse({success:false,error:"account identity is unavailable"});
  const user = findUser_(usersSheet, username);
  // Admin status is authoritative from the Users sheet only -- a
  // client-supplied is_admin param is never trusted for quota decisions.
  if (!user) return jsonResponse({success:false,error:"account is not recognized"});
  const isAdmin = user.isAdmin;
  if (!user.isPaid && !isAdmin) return jsonResponse({success:false,error:"AI features require an active Appraze subscription"});
  const monthlyLimit = isAdmin ? AI_ADMIN_MONTHLY_LIMIT : AI_CUSTOMER_MONTHLY_LIMIT;
  const dailyLimit = isAdmin ? AI_ADMIN_DAILY_LIMIT : AI_CUSTOMER_DAILY_LIMIT;
  const period = aiPeriodKeys_();
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    let rowNum = findAiUsageRow_(usageSheet, username, period.monthKey);
    if (!rowNum) {
      usageSheet.appendRow([username,period.monthKey,period.dayKey,0,0,0,0,0,0,0,new Date().toISOString()]);
      rowNum = usageSheet.getLastRow();
    }
    const row = usageSheet.getRange(rowNum,1,1,AI_USAGE_HEADER.length);
    const vals = row.getValues()[0];
    const updatedMs = new Date(String(vals[10] || "")).getTime();
    if (Number.isFinite(updatedMs) && period.nowMs - updatedMs > AI_RESERVATION_TTL_MS) { vals[4]=0; vals[6]=0; }
    if (String(vals[2]) !== period.dayKey) { vals[2]=period.dayKey; vals[5]=0; vals[6]=0; }
    const successful=Number(vals[3])||0, reserved=Number(vals[4])||0;
    const dailySuccessful=Number(vals[5])||0, dailyReserved=Number(vals[6])||0;
    if (successful+reserved >= monthlyLimit) { row.setValues([vals]); return jsonResponse(usagePayload_(vals,false,"Monthly AI usage limit reached",monthlyLimit,dailyLimit,period.dayKey)); }
    if (dailySuccessful+dailyReserved >= dailyLimit) { row.setValues([vals]); return jsonResponse(usagePayload_(vals,false,"Daily AI usage limit reached",monthlyLimit,dailyLimit,period.dayKey)); }
    vals[4]=reserved+1; vals[6]=dailyReserved+1; vals[10]=new Date().toISOString(); row.setValues([vals]);
    return jsonResponse(usagePayload_(vals,true,"",monthlyLimit,dailyLimit,period.dayKey));
  } finally { lock.releaseLock(); }
}

function handleFinalizeAiUsage_(usageSheet, params) {
  const username=String(params.username||"").trim().toLowerCase();
  const inputTokens=Math.max(0,Number(params.input_tokens)||0);
  const outputTokens=Math.max(0,Number(params.output_tokens)||0);
  const cost=Math.max(0,Number(params.estimated_cost_usd)||0);
  if(!username) return jsonResponse({success:false,error:"account identity is unavailable"});
  const period=aiPeriodKeys_(), lock=LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const rowNum=findAiUsageRow_(usageSheet,username,period.monthKey);
    if(!rowNum) return jsonResponse({success:false,error:"usage reservation not found"});
    const row=usageSheet.getRange(rowNum,1,1,AI_USAGE_HEADER.length), vals=row.getValues()[0];
    vals[4]=Math.max(0,(Number(vals[4])||0)-1);
    if(String(vals[2])!==period.dayKey){vals[2]=period.dayKey;vals[5]=0;vals[6]=0;}
    vals[6]=Math.max(0,(Number(vals[6])||0)-1); vals[3]=(Number(vals[3])||0)+1; vals[5]=(Number(vals[5])||0)+1;
    vals[7]=(Number(vals[7])||0)+inputTokens; vals[8]=(Number(vals[8])||0)+outputTokens; vals[9]=(Number(vals[9])||0)+cost; vals[10]=new Date().toISOString();
    row.setValues([vals]); return jsonResponse({success:true,monthly_cost_usd:Number(vals[9].toFixed(6))});
  } finally { lock.releaseLock(); }
}

function handleReleaseAiUsage_(usageSheet, params) {
  const username=String(params.username||"").trim().toLowerCase(); if(!username)return jsonResponse({success:false,error:"account identity is unavailable"});
  const period=aiPeriodKeys_(), lock=LockService.getScriptLock(); lock.waitLock(10000);
  try {
    const rowNum=findAiUsageRow_(usageSheet,username,period.monthKey); if(!rowNum)return jsonResponse({success:true});
    const row=usageSheet.getRange(rowNum,1,1,AI_USAGE_HEADER.length), vals=row.getValues()[0];
    vals[4]=Math.max(0,(Number(vals[4])||0)-1); if(String(vals[2])===period.dayKey)vals[6]=Math.max(0,(Number(vals[6])||0)-1);
    vals[10]=new Date().toISOString(); row.setValues([vals]); return jsonResponse({success:true});
  } finally { lock.releaseLock(); }
}

function handleGetAiUsage_(usersSheet, usageSheet, params) {
  const username=String(params.username||"").trim().toLowerCase(); if(!username)return jsonResponse({success:false,error:"account identity is unavailable"});
  const user=findUser_(usersSheet,username);
  // Admin status is authoritative from the Users sheet only -- a
  // client-supplied is_admin param is never trusted for quota decisions.
  if(!user) return jsonResponse({success:false,error:"account is not recognized"});
  const isAdmin=user.isAdmin;
  if(!user.isPaid && !isAdmin)return jsonResponse({success:false,error:"active subscription required"});
  const monthlyLimit=isAdmin?AI_ADMIN_MONTHLY_LIMIT:AI_CUSTOMER_MONTHLY_LIMIT, dailyLimit=isAdmin?AI_ADMIN_DAILY_LIMIT:AI_CUSTOMER_DAILY_LIMIT, period=aiPeriodKeys_();
  const rowNum=findAiUsageRow_(usageSheet,username,period.monthKey);
  if(!rowNum)return jsonResponse({success:true,monthly_used:0,monthly_limit:monthlyLimit,daily_used:0,daily_limit:dailyLimit,monthly_cost_usd:0,input_tokens:0,output_tokens:0});
  const vals=usageSheet.getRange(rowNum,1,1,AI_USAGE_HEADER.length).getValues()[0], dailyUsed=String(vals[2])===period.dayKey?Number(vals[5])||0:0;
  return jsonResponse({success:true,monthly_used:Number(vals[3])||0,monthly_limit:monthlyLimit,daily_used:dailyUsed,daily_limit:dailyLimit,monthly_cost_usd:Number((Number(vals[9])||0).toFixed(6)),input_tokens:Number(vals[7])||0,output_tokens:Number(vals[8])||0});
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// ---------------------------------------------------------------------------
// DRIVE FOLDER SCANNING (Invoices/Inventory) — runs under your own Drive
// access since the script executes "as Me". No separate Google Drive
// credentials needed, unlike the service-account route.
// ---------------------------------------------------------------------------

function getAlreadyProcessedIds_(processedSheet) {
  const data = processedSheet.getDataRange().getValues();
  const ids = new Set();
  for (let i = 1; i < data.length; i++) {
    ids.add(String(data[i][0]));
  }
  return ids;
}

function handleScanFolder_(params) {
  const folderName = String(params.folder_name || "").trim();
  if (!folderName) {
    return jsonResponse({ success: false, error: "folder_name is required" });
  }

  const folders = DriveApp.getFoldersByName(folderName);
  if (!folders.hasNext()) {
    return jsonResponse({
      success: false,
      error: "No Drive folder named exactly \"" + folderName + "\" found. Check spelling/capitalization — folder names must match exactly.",
    });
  }
  const folder = folders.next();

  const processedSheet = getProcessedSheet_();
  const alreadyProcessed = getAlreadyProcessedIds_(processedSheet);

  const files = folder.getFiles();
  const results = [];
  while (files.hasNext() && results.length < MAX_FILES_PER_SCAN) {
    const file = files.next();
    const fileId = file.getId();
    if (alreadyProcessed.has(fileId)) continue;

    const mimeType = file.getMimeType();
    if (SUPPORTED_MIME_TYPES.indexOf(mimeType) === -1) continue;

    const blob = file.getBlob();
    const base64 = Utilities.base64Encode(blob.getBytes());
    results.push({
      file_id: fileId,
      file_name: file.getName(),
      mime_type: mimeType,
      base64: base64,
      modified_at: file.getLastUpdated().toISOString(),
    });
  }

  return jsonResponse({ success: true, files: results, folder_name: folder.getName() });
}

function handleMarkProcessed_(sheet, params) {
  const fileIdsRaw = String(params.file_ids || "");
  const fileNamesRaw = String(params.file_names || "");
  if (!fileIdsRaw) {
    return jsonResponse({ success: false, error: "file_ids is required" });
  }
  const ids = fileIdsRaw.split(",").filter(function (x) { return x; });
  const names = fileNamesRaw.split(",");
  const now = new Date().toISOString();
  for (let i = 0; i < ids.length; i++) {
    sheet.appendRow([ids[i], names[i] || "", now]);
  }
  return jsonResponse({ success: true, count: ids.length });
}
