package com.crtc.app;

import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Typeface;
import android.net.Uri;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import androidx.security.crypto.EncryptedSharedPreferences;
import androidx.security.crypto.MasterKey;
import java.security.SecureRandom;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import org.json.JSONObject;

/**
 * POS tab. Merchants connect their OWN Stripe account through Stripe Connect
 * onboarding (Stripe-hosted, via the Appraze POS backend) and take payments
 * from their own customers with one-time Stripe Checkout pages. Funds settle
 * to the merchant's Stripe account and bank — never through Appraze.
 *
 * No Stripe key is ever entered, stored, or sent from this device. The only
 * thing stored (EncryptedSharedPreferences) is a revocable device token for
 * the Appraze POS backend. Not for Appraze subscriptions (Play Billing).
 * Locked on the free plan.
 */
class PosScreen {

    static final String PREFS_NAME = "stripe_keys";
    static final String KEY_TOKEN = "pos_device_token";
    static final String KEY_ACCT = "pos_account_id";
    /** v5 stored the merchant's raw Stripe keys under these; purged on launch. */
    static final String LEGACY_KEY_PK = "stripe_pk";
    static final String LEGACY_KEY_SK = "stripe_sk";

    /** Current sale's invoice id, reused on retry so the backend returns the same checkout. */
    static String pendingInvoice;
    static String pendingSignature;

    static SharedPreferences secure(MainActivity a) throws Exception {
        MasterKey mk = new MasterKey.Builder(a).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build();
        return EncryptedSharedPreferences.create(a, PREFS_NAME, mk,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM);
    }

    /** Deletes any Stripe secret/publishable key a v5 build saved on this device. */
    static void purgeLegacyKeys(MainActivity a) {
        try {
            SharedPreferences p = secure(a);
            if (p.contains(LEGACY_KEY_SK) || p.contains(LEGACY_KEY_PK)) {
                p.edit().remove(LEGACY_KEY_SK).remove(LEGACY_KEY_PK).apply();
                a.events.record("stripe_legacy_keys_purged", "");
            }
        } catch (Exception ignored) { }
    }

    static String savedToken(MainActivity a) {
        try {
            return secure(a).getString(KEY_TOKEN, "");
        } catch (Exception e) {
            return "";
        }
    }

    static String savedAccount(MainActivity a) {
        try {
            return secure(a).getString(KEY_ACCT, "");
        } catch (Exception e) {
            return "";
        }
    }

    static void clearConnection(MainActivity a) {
        TapPay.reset();
        try { secure(a).edit().remove(KEY_TOKEN).remove(KEY_ACCT).apply(); } catch (Exception ignored) { }
    }

    static void show(final MainActivity a) {
        a.base("POS",
                "Take payments from your customers. Money goes straight to your Stripe account and your bank — never through Appraze.",
                5);
        final String plan = a.usage.plan();
        if (!Usage.posUnlocked(plan)) {
            LinearLayout c = a.card(a.body, false);
            c.addView(title(a, "POS requires a paid plan."));
            c.addView(message(a, "Card payments unlock on Starter and up. Your customers pay you through your own Stripe account."));
            Button b = a.primaryButton("View Plans");
            b.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { a.goTab(3); }
            });
            c.addView(b);
            a.events.record("pos_locked_view", "plan=" + plan);
            return;
        }
        if (!PosApi.configured()) {
            LinearLayout c = a.card(a.body, false);
            c.addView(title(a, "POS server not set up"));
            c.addView(message(a, "This build isn't connected to the Appraze POS server yet, so card payments are unavailable."));
            a.events.record("pos_unconfigured_view", "");
            return;
        }
        if (savedToken(a).isEmpty()) {
            connectCard(a);
        } else {
            statusCard(a);
        }
    }

    static TextView title(MainActivity a, String text) {
        TextView t = new TextView(a);
        t.setText(text);
        t.setTextSize(18);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(MainActivity.TEXT_PRIMARY);
        return t;
    }

    static TextView message(MainActivity a, String text) {
        TextView m = new TextView(a);
        m.setText(text);
        m.setTextSize(15);
        m.setTextColor(MainActivity.TEXT_SECONDARY);
        m.setPadding(0, a.dp(8), 0, 0);
        return m;
    }

    static void openUrl(MainActivity a, String url) {
        try {
            a.startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception e) {
            a.infoDialog("Couldn't open link", url);
        }
    }

    /** True when the screen the callback was started from is still showing. */
    static boolean stillShowing(MainActivity a, LinearLayout body) {
        return a.body == body;
    }

    static void connectCard(final MainActivity a) {
        LinearLayout c = a.card(a.body, false);
        c.addView(a.sectionLabel("Connect Stripe"));
        c.addView(message(a, "Set up payments on Stripe's secure site. You'll use your own Stripe account — Appraze never sees your keys or your money."));
        c.addView(a.caption("Stripe will ask for your business and bank details. You can come back here anytime to finish."));
        final Button connect = a.primaryButton("Connect Stripe");
        final LinearLayout body = a.body;
        connect.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                connect.setEnabled(false);
                connect.setText("Opening Stripe...");
                PosApi.call("POST", "/pos/connect/start", null, null, new PosApi.Callback() {
                    public void done(int status, JSONObject j, String error) {
                        if (status != 200) {
                            if (stillShowing(a, body)) {
                                connect.setEnabled(true);
                                connect.setText("Connect Stripe");
                            }
                            a.infoDialog("Couldn't start Stripe setup", error);
                            a.events.record("pos_connect_failed", "status=" + status);
                            return;
                        }
                        try {
                            secure(a).edit()
                                    .putString(KEY_TOKEN, j.optString("device_token"))
                                    .putString(KEY_ACCT, j.optString("account_id"))
                                    .apply();
                        } catch (Exception e) {
                            a.infoDialog("Couldn't save connection", "Secure storage failed: " + e.getMessage());
                            return;
                        }
                        a.events.record("pos_connect_started", "");
                        openUrl(a, j.optString("onboarding_url"));
                        if (stillShowing(a, body)) show(a);
                    }
                });
            }
        });
        c.addView(connect);
    }

    static void statusCard(final MainActivity a) {
        final LinearLayout c = a.card(a.body, false);
        c.addView(a.sectionLabel("Stripe"));
        final TextView status = new TextView(a);
        status.setText("Checking your Stripe account...");
        status.setTextSize(14);
        status.setTextColor(MainActivity.TEXT_MUTED);
        status.setPadding(a.dp(4), a.dp(4), a.dp(4), a.dp(4));
        c.addView(status);
        final LinearLayout actions = new LinearLayout(a);
        actions.setOrientation(LinearLayout.VERTICAL);
        c.addView(actions);
        final LinearLayout body = a.body;
        final String token = savedToken(a);
        PosApi.call("GET", "/pos/connect/status", token, null, new PosApi.Callback() {
            public void done(int code, JSONObject j, String error) {
                if (!stillShowing(a, body)) return;
                if (code == 401) {
                    clearConnection(a);
                    Toast.makeText(a, "Stripe connection expired — connect again", Toast.LENGTH_LONG).show();
                    show(a);
                    return;
                }
                if (code != 200) {
                    status.setText(error);
                    status.setTextColor(MainActivity.PASS);
                    Button retry = a.secondaryButton("Retry");
                    retry.setOnClickListener(new View.OnClickListener() {
                        public void onClick(View v) { show(a); }
                    });
                    actions.addView(retry);
                    actions.addView(disconnectButton(a));
                    return;
                }
                if (j.optBoolean("charges_enabled")) {
                    status.setText("Connected: " + mask(savedAccount(a)) + " — ready for payments");
                    status.setTextColor(MainActivity.BUY);
                    actions.addView(disconnectButton(a));
                    chargeCard(a);
                } else {
                    status.setText("Stripe setup isn't finished yet. Finish it on Stripe's site, then refresh.");
                    status.setTextColor(MainActivity.REVIEW);
                    actions.addView(finishSetupButton(a));
                    Button refresh = a.secondaryButton("Refresh Status");
                    refresh.setOnClickListener(new View.OnClickListener() {
                        public void onClick(View v) { show(a); }
                    });
                    actions.addView(refresh);
                    actions.addView(disconnectButton(a));
                }
            }
        });
    }

    static Button finishSetupButton(final MainActivity a) {
        final Button b = a.primaryButton("Finish Stripe Setup");
        b.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                b.setEnabled(false);
                PosApi.call("POST", "/pos/connect/link", savedToken(a), null, new PosApi.Callback() {
                    public void done(int code, JSONObject j, String error) {
                        b.setEnabled(true);
                        if (code == 200) {
                            openUrl(a, j.optString("onboarding_url"));
                        } else {
                            a.infoDialog("Couldn't open Stripe setup", error);
                        }
                    }
                });
            }
        });
        return b;
    }

    static TextView disconnectButton(final MainActivity a) {
        TextView disc = a.textButton("Disconnect", MainActivity.PASS);
        disc.setGravity(Gravity.CENTER);
        disc.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                final LinearLayout body = a.body;
                PosApi.call("POST", "/pos/disconnect", savedToken(a), null, new PosApi.Callback() {
                    public void done(int code, JSONObject j, String error) {
                        // Forget the token locally even if the server was unreachable.
                        clearConnection(a);
                        a.events.record("pos_disconnected", "server_status=" + code);
                        Toast.makeText(a, "Stripe disconnected from this device", Toast.LENGTH_SHORT).show();
                        if (stillShowing(a, body)) show(a);
                    }
                });
            }
        });
        return disc;
    }

    static String newInvoiceId() {
        byte[] b = new byte[4];
        new SecureRandom().nextBytes(b);
        StringBuilder hex = new StringBuilder();
        for (byte x : b) hex.append(String.format(Locale.US, "%02x", x));
        return "AND-" + new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date()) + "-" + hex;
    }

    /** Same amount + description = same sale (reuse invoice id); anything else is a new sale. */
    static String invoiceFor(long cents, String desc) {
        String sig = cents + "|" + desc;
        if (pendingInvoice == null || !sig.equals(pendingSignature)) {
            pendingInvoice = newInvoiceId();
            pendingSignature = sig;
        }
        return pendingInvoice;
    }

    static void chargeCard(final MainActivity a) {
        LinearLayout c = a.card(a.body, false);
        LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) c.getLayoutParams();
        lp.topMargin = a.dp(12);
        c.setLayoutParams(lp);
        c.addView(a.sectionLabel("New Charge"));
        final MainActivity.Field amount = a.labeled(c, "Amount (USD)", "", a.decimalInput());
        final MainActivity.Field desc = a.labeled(c, "Description", "", InputType.TYPE_CLASS_TEXT);
        final LinearLayout slot = new LinearLayout(a);
        slot.setOrientation(LinearLayout.VERTICAL);
        c.addView(slot);
        final LinearLayout body = a.body;
        final boolean tapOk = TapPay.deviceSupported(a);

        final Button tap = a.primaryButton("Tap to Pay");
        tap.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                final Sale sale = readSale(a, amount, desc);
                if (sale == null) return;
                tap.setEnabled(false);
                tap.setText("Hold card near phone...");
                TapPay.charge(a, sale.cents, sale.description, sale.invoice, new TapPay.Result() {
                    public void done(boolean paid, String message) {
                        if (!stillShowing(a, body)) return;
                        tap.setEnabled(true);
                        tap.setText("Tap to Pay");
                        if (paid) {
                            pendingInvoice = null;
                            pendingSignature = null;
                            amount.input.setText("");
                            desc.input.setText("");
                            slot.removeAllViews();
                            slot.addView(paidBanner(a, sale.cents));
                            Toast.makeText(a, message, Toast.LENGTH_SHORT).show();
                        } else {
                            a.infoDialog("Tap to Pay", message);
                        }
                        refreshSales(a, body);
                    }
                });
            }
        });
        if (tapOk) {
            c.addView(tap);
        } else {
            c.addView(a.caption("Tap to Pay needs Android 11 or newer with NFC. Use a payment link instead."));
        }

        final Button charge = tapOk ? a.secondaryButton("Send Payment Link") : a.primaryButton("Send Payment Link");
        charge.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                final Sale sale = readSale(a, amount, desc);
                if (sale == null) return;
                JSONObject req = new JSONObject();
                try {
                    req.put("amount_cents", sale.cents);
                    req.put("description", sale.description);
                    req.put("invoice_id", sale.invoice);
                } catch (Exception e) {
                    return;
                }
                final String label = charge.getText().toString();
                charge.setEnabled(false);
                charge.setText("Creating checkout...");
                a.events.record("pos_charge_started", "amount_cents=" + sale.cents + "|invoice=" + sale.invoice);
                PosApi.call("POST", "/pos/checkout", savedToken(a), req, new PosApi.Callback() {
                    public void done(int code, JSONObject j, String error) {
                        if (!stillShowing(a, body)) return;
                        charge.setEnabled(true);
                        charge.setText(label);
                        if (code == 200) {
                            pendingInvoice = null;
                            pendingSignature = null;
                            String sessionId = j.optString("session_id");
                            a.sales.start(SalesLog.METHOD_LINK, sale.cents, sale.description, sale.invoice, sessionId);
                            slot.removeAllViews();
                            slot.addView(resultCard(a, j.optString("checkout_url"), sessionId, sale.cents));
                            a.events.record("pos_link_created", "amount_cents=" + sale.cents + "|invoice=" + sale.invoice);
                            Toast.makeText(a, "Checkout ready", Toast.LENGTH_SHORT).show();
                            refreshSales(a, body);
                        } else if (code == 401) {
                            clearConnection(a);
                            a.infoDialog("Stripe connection expired", "Connect Stripe again to take payments.");
                            show(a);
                        } else {
                            a.infoDialog("Charge failed", error);
                            a.events.record("pos_link_failed", "status=" + code);
                        }
                    }
                });
            }
        });
        c.addView(charge);
        c.addView(a.caption("The amount and description are sent to the Appraze POS server to create the Stripe payment. Card details go only to Stripe."));
        salesCard(a);
    }

    /** One sale's validated inputs. */
    static final class Sale {
        long cents;
        String description;
        String invoice;
    }

    static Sale readSale(MainActivity a, MainActivity.Field amount, MainActivity.Field desc) {
        Double amt = a.parseNonNegative(amount);
        String d = desc.input.getText().toString().trim();
        if (d.isEmpty()) { a.setFieldError(desc, "Add a description."); return null; }
        if (d.length() > 200) { a.setFieldError(desc, "Keep it under 200 characters."); return null; }
        a.setFieldError(desc, null);
        if (amt == null) return null;
        long cents = Math.round(amt * 100);
        if (cents < 50) { a.setFieldError(amount, "Enter at least $0.50."); return null; }
        Sale s = new Sale();
        s.cents = cents;
        s.description = d;
        s.invoice = invoiceFor(cents, d);
        return s;
    }

    static TextView paidBanner(MainActivity a, long cents) {
        TextView t = new TextView(a);
        t.setText("Paid \u2713 " + a.money(cents / 100.0) + " \u2014 " + SalesLog.formatWhen(System.currentTimeMillis()));
        t.setTextSize(16);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(MainActivity.BUY);
        t.setPadding(a.dp(4), a.dp(12), a.dp(4), 0);
        return t;
    }

    /* ---------- Recent Sales (date + time of every sale) ---------- */

    static LinearLayout salesList;

    static void salesCard(MainActivity a) {
        LinearLayout c = a.card(a.body, false);
        LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) c.getLayoutParams();
        lp.topMargin = a.dp(12);
        c.setLayoutParams(lp);
        c.addView(a.sectionLabel("Recent Sales"));
        salesList = new LinearLayout(a);
        salesList.setOrientation(LinearLayout.VERTICAL);
        c.addView(salesList);
        fillSales(a);
    }

    static void refreshSales(MainActivity a, LinearLayout body) {
        if (stillShowing(a, body) && salesList != null) fillSales(a);
    }

    static void fillSales(final MainActivity a) {
        salesList.removeAllViews();
        java.util.List<SalesLog.Sale> rows = a.sales.recent(25);
        if (rows.isEmpty()) {
            salesList.addView(a.caption("No sales yet. Each sale is logged here with its date and time."));
            return;
        }
        for (final SalesLog.Sale s : rows) {
            LinearLayout row = new LinearLayout(a);
            row.setOrientation(LinearLayout.VERTICAL);
            row.setPadding(a.dp(4), a.dp(10), a.dp(4), a.dp(10));
            LinearLayout top = new LinearLayout(a);
            top.setOrientation(LinearLayout.HORIZONTAL);
            TextView amt = new TextView(a);
            amt.setText(a.money(s.amountCents / 100.0));
            amt.setTextSize(16);
            amt.setTypeface(Typeface.DEFAULT_BOLD);
            amt.setTextColor(MainActivity.TEXT_PRIMARY);
            top.addView(amt, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
            TextView st = new TextView(a);
            st.setText(SalesLog.statusLabel(s.status));
            st.setTextSize(14);
            st.setTypeface(Typeface.DEFAULT_BOLD);
            st.setTextColor(SalesLog.PAID.equals(s.status) ? MainActivity.BUY
                    : SalesLog.PENDING.equals(s.status) ? MainActivity.REVIEW : MainActivity.PASS);
            top.addView(st);
            row.addView(top);
            TextView when = new TextView(a);
            when.setText(SalesLog.formatWhen(s.createdMs) + "  \u00B7  " + SalesLog.methodLabel(s.method));
            when.setTextSize(13);
            when.setTextColor(MainActivity.TEXT_SECONDARY);
            row.addView(when);
            String detail = s.description == null ? "" : s.description;
            if (s.paidMs > 0) detail += (detail.isEmpty() ? "" : "  \u00B7  ") + "Paid " + SalesLog.formatWhen(s.paidMs);
            if (!detail.isEmpty()) {
                TextView dv = new TextView(a);
                dv.setText(detail);
                dv.setTextSize(13);
                dv.setTextColor(MainActivity.TEXT_MUTED);
                row.addView(dv);
            }
            if (SalesLog.PENDING.equals(s.status) && s.stripeId != null) {
                TextView hint = new TextView(a);
                hint.setText("Tap to check status");
                hint.setTextSize(12);
                hint.setTextColor(MainActivity.GOLD);
                row.addView(hint);
                row.setClickable(true);
                row.setFocusable(true);
                row.setOnClickListener(new View.OnClickListener() {
                    public void onClick(View v) { checkSale(a, s); }
                });
            }
            salesList.addView(row);
        }
    }

    static void checkSale(final MainActivity a, final SalesLog.Sale s) {
        final LinearLayout body = a.body;
        String path = SalesLog.METHOD_TAP.equals(s.method)
                ? "/pos/terminal/payment_intent/" + Uri.encode(s.stripeId) + "/status"
                : "/pos/checkout/" + Uri.encode(s.stripeId) + "/status";
        PosApi.call("GET", path, savedToken(a), null, new PosApi.Callback() {
            public void done(int code, JSONObject j, String error) {
                if (code != 200) {
                    Toast.makeText(a, error, Toast.LENGTH_LONG).show();
                    return;
                }
                String status = j.optString("status");
                if (j.optBoolean("paid")) {
                    a.sales.setStatus(s.stripeId, SalesLog.PAID);
                } else if ("canceled".equals(status) || "expired".equals(status)) {
                    a.sales.setStatus(s.stripeId, SalesLog.CANCELED);
                } else {
                    Toast.makeText(a, "Not paid yet (" + status + ")", Toast.LENGTH_SHORT).show();
                }
                refreshSales(a, body);
            }
        });
    }

    static LinearLayout resultCard(final MainActivity a, final String url, final String sessionId, final long cents) {
        LinearLayout r = new LinearLayout(a);
        r.setOrientation(LinearLayout.VERTICAL);
        r.setBackground(a.glassBg(12, MainActivity.GOLD_BORDER));
        int p = a.dp(16);
        r.setPadding(p, p, p, p);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = a.dp(12);
        r.setLayoutParams(lp);
        TextView t = new TextView(a);
        t.setText("Checkout ready — " + a.money(cents / 100.0));
        t.setTextSize(16);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(MainActivity.GOLD);
        r.addView(t);
        TextView link = new TextView(a);
        link.setText(url);
        link.setTextSize(14);
        link.setTextColor(MainActivity.TEXT_PRIMARY);
        link.setPadding(0, a.dp(8), 0, 0);
        link.setClickable(true);
        link.setFocusable(true);
        link.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { openUrl(a, url); }
        });
        r.addView(link);
        TextView note = new TextView(a);
        note.setText("Open it on this phone for your customer, or share the link. It can be paid once. Stripe deposits "
                + a.money(cents / 100.0) + " to your bank.");
        note.setTextSize(13);
        note.setTextColor(MainActivity.TEXT_SECONDARY);
        note.setPadding(0, a.dp(8), 0, 0);
        r.addView(note);
        Button share = a.secondaryButton("Share Link");
        share.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Intent i = new Intent(Intent.ACTION_SEND);
                i.setType("text/plain");
                i.putExtra(Intent.EXTRA_TEXT, url);
                a.startActivity(Intent.createChooser(i, "Share checkout link"));
            }
        });
        r.addView(share);
        final TextView paid = new TextView(a);
        paid.setTextSize(14);
        paid.setPadding(0, a.dp(8), 0, 0);
        paid.setVisibility(View.GONE);
        final Button check = a.secondaryButton("Check Payment Status");
        check.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                check.setEnabled(false);
                PosApi.call("GET", "/pos/checkout/" + Uri.encode(sessionId) + "/status", savedToken(a), null,
                        new PosApi.Callback() {
                            public void done(int code, JSONObject j, String error) {
                                check.setEnabled(true);
                                paid.setVisibility(View.VISIBLE);
                                if (code != 200) {
                                    paid.setText(error);
                                    paid.setTextColor(MainActivity.PASS);
                                } else if (j.optBoolean("paid")) {
                                    a.sales.setStatus(sessionId, SalesLog.PAID);
                                    refreshSales(a, a.body);
                                    paid.setText("Paid \u2713 " + SalesLog.formatWhen(System.currentTimeMillis()));
                                    paid.setTextColor(MainActivity.BUY);
                                    a.events.record("pos_payment_confirmed", "amount_cents=" + cents);
                                } else {
                                    paid.setText("Not paid yet (" + j.optString("status", "open") + ").");
                                    paid.setTextColor(MainActivity.REVIEW);
                                }
                            }
                        });
            }
        });
        r.addView(check);
        r.addView(paid);
        return r;
    }

    static String mask(String acct) {
        if (acct == null || acct.length() <= 9) return "Stripe account";
        return acct.substring(0, 5) + "••••" + acct.substring(acct.length() - 4);
    }
}
