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
 */

const SHEET_ID = "1WGF1rkhIsKn64QjTcWwSHFs3zNjDrtofguHzPNHFFYk";
const TOKEN = "aX9k2mQ7rT4vY8pL1nW6zC3jH5bF0sD";

// Change this to your own private value before deploying, then share it only
// with Ashley. Anyone who signs up with this code becomes an admin and joins
// the shared workspace. Leave blank to disable admin signup entirely.
const ADMIN_SETUP_CODE = "9XlW1kpXbNZhJizlsGjf";

const USERS_SHEET_NAME = "Users";
const USERS_HEADER = ["username", "password_hash", "display_name", "is_admin", "is_paid", "created_at"];

const STORAGE_SHEET_NAME = "Storage";
const STORAGE_HEADER = ["owner_key", "payload_json", "updated_at"];

const PROCESSED_SHEET_NAME = "ProcessedFiles";
const PROCESSED_HEADER = ["file_id", "file_name", "processed_at"];

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
        return handleSaveData_(getStorageSheet_(), params);
      case "load_data":
        return handleLoadData_(getStorageSheet_(), params);
      case "set_paid":
        return handleSetPaid_(getUsersSheet_(), params);
      case "scan_folder":
        return handleScanFolder_(params);
      case "mark_processed":
        return handleMarkProcessed_(getProcessedSheet_(), params);
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
  }
  return sheet;
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

function resolveOwnerKey_(params) {
  // Admins all share one workspace row; everyone else is isolated by username.
  const isAdmin = String(params.is_admin || "").toLowerCase() === "true";
  if (isAdmin) return "admin_shared";
  const username = String(params.username || "").trim().toLowerCase();
  return "tester_" + username;
}

function handleSaveData_(sheet, params) {
  const ownerKey = resolveOwnerKey_(params);
  const payload = String(params.payload || "{}");

  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === ownerKey) {
      sheet.getRange(i + 1, 2).setValue(payload);
      sheet.getRange(i + 1, 3).setValue(new Date().toISOString());
      return jsonResponse({ success: true });
    }
  }
  sheet.appendRow([ownerKey, payload, new Date().toISOString()]);
  return jsonResponse({ success: true });
}

function handleLoadData_(sheet, params) {
  const ownerKey = resolveOwnerKey_(params);
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === ownerKey) {
      return jsonResponse({ success: true, payload: data[i][1], updated_at: data[i][2] });
    }
  }
  return jsonResponse({ success: true, payload: null });
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
