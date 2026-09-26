package com.crtc.app;

import android.graphics.Typeface;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.Locale;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Comps collector on the Analyze screen: "What is it?" -> the Appraze
 * server looks up eBay comparable listings (comps_collector.py; eBay keys
 * never on the device) -> Expected resale is auto-filled with the suggested
 * value, and the evidence (confidence, sold/active counts, range, listings,
 * when it was collected) is shown so the number is never a black box.
 * The user can still overwrite the resale price.
 */
final class CompsLookup {

    /** Last value auto-filled into resale, so the verdict can say where resale came from. */
    static Double lastSuggested;
    static String lastConfidence;

    private CompsLookup() { }

    interface FieldRef {
        MainActivity.Field get();
    }

    static void reset() {
        lastSuggested = null;
        lastConfidence = null;
    }

    static void addTo(final MainActivity a, LinearLayout card, final FieldRef resale) {
        reset();
        final MainActivity.Field item = a.labeled(card, "What is it?", "",
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        item.input.setHint("Brand, model, size — e.g. Pyrex 403 mixing bowl");
        final LinearLayout slot = new LinearLayout(a);
        slot.setOrientation(LinearLayout.VERTICAL);
        final Button find = a.secondaryButton("Find Comps");
        final LinearLayout body = a.body;
        find.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                final String q = item.input.getText().toString().trim();
                if (q.length() < 2) { a.setFieldError(item, "Describe the item first."); return; }
                if (q.length() > 100) { a.setFieldError(item, "Keep it under 100 characters."); return; }
                a.setFieldError(item, null);
                if (!PosApi.configured()) {
                    a.infoDialog("Comps not available", "This build isn't connected to the Appraze server, so comps lookup is unavailable. Enter the resale price yourself.");
                    return;
                }
                JSONObject req = new JSONObject();
                try { req.put("query", q); } catch (Exception e) { return; }
                find.setEnabled(false);
                find.setText("Finding comps...");
                PosApi.call("POST", "/comps/search", null, req, new PosApi.Callback() {
                    public void done(int code, JSONObject j, String error) {
                        if (a.body != body) return;
                        find.setEnabled(true);
                        find.setText("Find Comps");
                        slot.removeAllViews();
                        if (code != 200) {
                            slot.addView(note(a, error, MainActivity.PASS));
                            a.events.record("comps_failed", "status=" + code);
                            return;
                        }
                        if (!j.optBoolean("found")) {
                            reset();
                            slot.addView(note(a, j.optString("message", "No comparable listings found."), MainActivity.REVIEW));
                            a.events.record("comps_none", "");
                            return;
                        }
                        double value = j.optDouble("suggested_value", 0);
                        MainActivity.Field r = resale.get();
                        r.input.setText(String.format(Locale.US, "%.2f", value));
                        a.setFieldError(r, null);
                        lastSuggested = value;
                        lastConfidence = j.optString("confidence", "low");
                        slot.addView(resultCard(a, j));
                        a.events.record("comps_found", "basis=" + j.optString("basis")
                                + "|count=" + j.optInt("count") + "|confidence=" + lastConfidence);
                    }
                });
            }
        });
        card.addView(find);
        card.addView(slot);
    }

    static int confidenceColor(String c) {
        if ("high".equals(c)) return MainActivity.BUY;
        if ("medium".equals(c)) return MainActivity.GOLD;
        return MainActivity.REVIEW;
    }

    static String confidenceLabel(String c) {
        if (c == null || c.isEmpty()) return "Low confidence";
        return Character.toUpperCase(c.charAt(0)) + c.substring(1) + " confidence";
    }

    /** One line under the verdict when resale came straight from comps. */
    static String provenance(double resaleUsed) {
        if (lastSuggested == null || Math.abs(resaleUsed - lastSuggested) > 0.005) return null;
        String s = "Resale from eBay comps · " + confidenceLabel(lastConfidence);
        return "low".equals(lastConfidence) ? s + " — verify before you buy." : s + ".";
    }

    private static TextView note(MainActivity a, String text, int color) {
        TextView t = new TextView(a);
        t.setText(text);
        t.setTextSize(14);
        t.setTextColor(color);
        t.setPadding(a.dp(4), a.dp(8), a.dp(4), 0);
        return t;
    }

    private static LinearLayout resultCard(final MainActivity a, JSONObject j) {
        LinearLayout r = new LinearLayout(a);
        r.setOrientation(LinearLayout.VERTICAL);
        r.setBackground(a.glassBg(12, MainActivity.GOLD_BORDER));
        int p = a.dp(14);
        r.setPadding(p, p, p, p);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = a.dp(10);
        r.setLayoutParams(lp);

        String conf = j.optString("confidence", "low");
        TextView head = new TextView(a);
        head.setText("Suggested resale " + a.money(j.optDouble("suggested_value", 0)));
        head.setTextSize(17);
        head.setTypeface(Typeface.DEFAULT_BOLD);
        head.setTextColor(MainActivity.TEXT_PRIMARY);
        r.addView(head);

        TextView c = new TextView(a);
        c.setText(confidenceLabel(conf));
        c.setTextSize(14);
        c.setTypeface(Typeface.DEFAULT_BOLD);
        c.setTextColor(confidenceColor(conf));
        c.setPadding(0, a.dp(4), 0, 0);
        r.addView(c);

        r.addView(a.caption(j.optString("confidence_reason")));
        String basis = "ebay_sold".equals(j.optString("basis")) ? "eBay sold listings" : "eBay active listings (asking prices)";
        r.addView(a.caption(j.optInt("sold_count") + " sold · " + j.optInt("active_count") + " active · range "
                + a.money(j.optDouble("low", 0)) + "–" + a.money(j.optDouble("high", 0)) + " · " + basis));
        r.addView(a.caption("Collected " + SalesLog.formatWhen(parseIsoMs(j.optString("collected_at")))
                + (j.optBoolean("cached") ? " (cached)" : "")));

        JSONArray list = j.optJSONArray("comps");
        if (list != null) {
            int n = Math.min(list.length(), 5);
            for (int i = 0; i < n; i++) {
                JSONObject o = list.optJSONObject(i);
                if (o == null) continue;
                final String url = o.optString("url", "");
                TextView t = new TextView(a);
                // Listing titles are untrusted marketplace text: shown as plain text only.
                t.setText(a.money(o.optDouble("price", 0) + o.optDouble("shipping", 0)) + "  ·  "
                        + ("sold".equals(o.optString("listing_type")) ? "Sold" : "Active") + "  ·  "
                        + o.optString("title", ""));
                t.setTextSize(13);
                t.setMaxLines(2);
                t.setTextColor(url.isEmpty() ? MainActivity.TEXT_SECONDARY : MainActivity.GOLD);
                t.setPadding(0, a.dp(6), 0, 0);
                if (!url.isEmpty()) {
                    t.setOnClickListener(new View.OnClickListener() {
                        public void onClick(View v) { PosScreen.openUrl(a, url); }
                    });
                }
                r.addView(t);
            }
        }
        r.addView(a.caption("Filled into Expected resale. Change it if your item differs."));
        return r;
    }

    /** ISO-8601 from the server -> epoch ms (falls back to now). */
    static long parseIsoMs(String iso) {
        try {
            java.text.SimpleDateFormat f = new java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US);
            f.setTimeZone(java.util.TimeZone.getTimeZone("UTC"));
            return f.parse(iso.substring(0, 19)).getTime();
        } catch (Exception e) {
            return System.currentTimeMillis();
        }
    }
}
