// Appraze persistence backend — Google Apps Script Web App.
//
// Paste this whole file into a Google Sheet's Extensions -> Apps Script
// editor (replacing whatever's there by default), set TOKEN below to a
// long random string of your own choosing, then Deploy -> New deployment
// -> type "Web app" -> Execute as "Me" -> Who has access "Anyone" ->
// Deploy. Copy the Web app URL it gives you.
//
// That URL + your TOKEN become two Streamlit secrets:
//   APPS_SCRIPT_URL = "the Web app URL"
//   APPS_SCRIPT_TOKEN = "the same string you set for TOKEN below"
//
// "Anyone" access sounds alarming, but it's safe here: the URL itself is
// long and effectively secret, and every request also has to present
// TOKEN below - anyone hitting this URL without it gets rejected before
// touching the spreadsheet. This exists specifically so Appraze doesn't
// need a Google Cloud service account / IAM / organization policies at
// all - just this one script running inside the spreadsheet it's meant
// to manage.
//
// Never sends this Sheet's data anywhere except back to whoever called
// this script with the right TOKEN.

var TOKEN = "REPLACE_WITH_YOUR_OWN_LONG_RANDOM_STRING";

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    if (body.token !== TOKEN) {
      return jsonResponse_({ ok: false, error: "unauthorized" });
    }
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheetName = sheetTitle_(body.table, body.workspace);

    if (body.action === "load") {
      return jsonResponse_({ ok: true, rows: loadTable_(ss, sheetName) });
    }
    if (body.action === "save") {
      saveTable_(ss, sheetName, body.rows || [], body.columns || []);
      return jsonResponse_({ ok: true });
    }
    return jsonResponse_({ ok: false, error: "unknown action: " + body.action });
  } catch (err) {
    return jsonResponse_({ ok: false, error: String(err) });
  }
}

// A plain GET just confirms the deployment is live and reachable - lets
// you sanity-check the URL by pasting it into a browser, without needing
// the token or a POST body.
function doGet(e) {
  return jsonResponse_({ ok: true, info: "Appraze Apps Script endpoint is live. Use POST with a token to read/write." });
}

function sheetTitle_(table, workspace) {
  // Mirrors sheets.py's _worksheet_title: "business" is unprefixed so an
  // existing single-workspace setup's tabs aren't renamed out from under
  // it; every other workspace gets its own suffixed tab.
  if (workspace === "business") return table;
  return table + "__" + workspace;
}

function loadTable_(ss, sheetName) {
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) return [];
  var values = sheet.getDataRange().getValues();
  if (values.length < 2) return [];
  var headers = values[0];
  var rows = [];
  for (var i = 1; i < values.length; i++) {
    var row = {};
    for (var j = 0; j < headers.length; j++) {
      row[headers[j]] = values[i][j];
    }
    rows.push(row);
  }
  return rows;
}

function saveTable_(ss, sheetName, rows, columns) {
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
  }
  sheet.clear();
  if (!columns.length) return;
  var data = [columns];
  for (var i = 0; i < rows.length; i++) {
    var row = [];
    for (var j = 0; j < columns.length; j++) {
      var val = rows[i][columns[j]];
      row.push(val === undefined || val === null ? "" : val);
    }
    data.push(row);
  }
  sheet.getRange(1, 1, data.length, columns.length).setValues(data);
}

function jsonResponse_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
