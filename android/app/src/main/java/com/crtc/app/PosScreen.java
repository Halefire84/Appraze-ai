package com.crtc.app;

import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import androidx.security.crypto.EncryptedSharedPreferences;
import androidx.security.crypto.MasterKey;

/**
 * POS tab. Merchants connect their OWN Stripe account (publishable + secret
 * key, stored in EncryptedSharedPreferences) and take payments from their own
 * customers via Stripe Payment Links. Funds settle to the merchant's Stripe
 * account and bank — never through Appraze. Not for Appraze subscriptions
 * (that's Play Billing, separate). Locked on the free plan.
 */
class PosScreen {

    static final String PREFS_NAME = "stripe_keys";
    static final String KEY_PK = "stripe_pk";
    static final String KEY_SK = "stripe_sk";

    static SharedPreferences secure(MainActivity a) throws Exception {
        MasterKey mk = new MasterKey.Builder(a).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build();
        return EncryptedSharedPreferences.create(a, PREFS_NAME, mk,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM);
    }

    static String savedPk(MainActivity a) {
        try {
            return secure(a).getString(KEY_PK, "");
        } catch (Exception e) {
            return "";
        }
    }

    static String savedSk(MainActivity a) {
        try {
            return secure(a).getString(KEY_SK, "");
        } catch (Exception e) {
            return "";
        }
    }

    static void show(final MainActivity a) {
        a.base("POS",
                "Take payments from your customers. Money goes straight to your Stripe account and your bank \u2014 never through Appraze.",
                5);
        final String plan = a.usage.plan();
        if (!Usage.posUnlocked(plan)) {
            LinearLayout c = a.card(a.body, false);
            TextView t = new TextView(a);
            t.setText("POS requires a paid plan.");
            t.setTextSize(18);
            t.setTypeface(Typeface.DEFAULT_BOLD);
            t.setTextColor(MainActivity.TEXT_PRIMARY);
            c.addView(t);
            TextView m = new TextView(a);
            m.setText("Card payments unlock on Starter and up. Your customers pay you through your own Stripe account.");
            m.setTextSize(15);
            m.setTextColor(MainActivity.TEXT_SECONDARY);
            m.setPadding(0, a.dp(8), 0, 0);
            c.addView(m);
            Button b = a.primaryButton("View Plans");
            b.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { a.goTab(3); }
            });
            c.addView(b);
            a.events.record("pos_locked_view", "plan=" + plan);
            return;
        }
        connectCard(a);
        if (!savedPk(a).isEmpty() && !savedSk(a).isEmpty()) chargeCard(a);
    }

    static void connectCard(final MainActivity a) {
        LinearLayout c = a.card(a.body, false);
        c.addView(a.sectionLabel("Connect Stripe"));
        final String pk = savedPk(a);
        final boolean connected = !pk.isEmpty() && !savedSk(a).isEmpty();
        TextView status = new TextView(a);
        if (connected) {
            status.setText("Connected: " + mask(pk));
            status.setTextColor(MainActivity.BUY);
        } else {
            status.setText("Not connected \u2014 enter your Stripe API keys to take payments.");
            status.setTextColor(MainActivity.TEXT_MUTED);
        }
        status.setTextSize(14);
        status.setPadding(a.dp(4), a.dp(4), a.dp(4), a.dp(4));
        c.addView(status);
        c.addView(a.caption("Use YOUR keys from the Stripe Dashboard (Developers > API keys). Test keys start with pk_test / sk_test."));
        final MainActivity.Field pkf = a.labeled(c, "Publishable key", connected ? "" : pk, InputType.TYPE_CLASS_TEXT);
        pkf.input.setHint("pk_live_...");
        final MainActivity.Field skf = a.labeled(c, "Secret key", "",
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        skf.input.setHint(connected ? "Saved \u2014 enter a new key to replace" : "sk_live_...");
        Button save = a.primaryButton(connected ? "Update Keys" : "Connect Stripe");
        save.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                String p = pkf.input.getText().toString().trim();
                String s = skf.input.getText().toString().trim();
                if (!p.startsWith("pk_")) { a.setFieldError(pkf, "Publishable keys start with pk_."); return; }
                if (!s.startsWith("sk_")) { a.setFieldError(skf, "Secret keys start with sk_."); return; }
                a.setFieldError(pkf, null);
                a.setFieldError(skf, null);
                try {
                    secure(a).edit().putString(KEY_PK, p).putString(KEY_SK, s).apply();
                } catch (Exception e) {
                    a.infoDialog("Couldn't save keys", "Secure storage failed: " + e.getMessage());
                    return;
                }
                a.events.record("stripe_connected", "pk_prefix=" + p.substring(0, Math.min(8, p.length())));
                Toast.makeText(a, "Stripe connected", Toast.LENGTH_SHORT).show();
                show(a);
            }
        });
        c.addView(save);
        if (connected) {
            TextView disc = a.textButton("Disconnect", MainActivity.PASS);
            disc.setGravity(Gravity.CENTER);
            disc.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    try { secure(a).edit().clear().apply(); } catch (Exception ignored) { }
                    a.events.record("stripe_disconnected", "");
                    Toast.makeText(a, "Stripe disconnected", Toast.LENGTH_SHORT).show();
                    show(a);
                }
            });
            c.addView(disc);
        }
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
        final Button charge = a.primaryButton("Charge");
        charge.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Double amt = a.parseNonNegative(amount);
                String d = desc.input.getText().toString().trim();
                if (d.isEmpty()) { a.setFieldError(desc, "Add a description."); return; }
                a.setFieldError(desc, null);
                if (amt == null || amt <= 0) { a.setFieldError(amount, "Enter an amount over $0."); return; }
                final long cents = Math.round(amt * 100);
                final String sk = savedSk(a);
                if (sk.isEmpty()) {
                    a.infoDialog("Stripe not connected", "Connect your Stripe keys first.");
                    return;
                }
                charge.setEnabled(false);
                charge.setText("Creating link...");
                a.events.record("pos_charge_started", "amount_cents=" + cents);
                StripeApi.createPaymentLink(sk, cents, d, new StripeApi.LinkCallback() {
                    public void done(final boolean ok, final String value) {
                        new Handler(Looper.getMainLooper()).post(new Runnable() {
                            public void run() {
                                charge.setEnabled(true);
                                charge.setText("Charge");
                                if (ok) {
                                    slot.removeAllViews();
                                    slot.addView(resultCard(a, value, cents));
                                    a.events.record("pos_link_created", "amount_cents=" + cents);
                                    Toast.makeText(a, "Payment link ready", Toast.LENGTH_SHORT).show();
                                } else {
                                    a.infoDialog("Charge failed", value);
                                    a.events.record("pos_link_failed", "error=" + value);
                                }
                            }
                        });
                    }
                });
            }
        });
        c.addView(charge);
    }

    static LinearLayout resultCard(final MainActivity a, final String url, final long cents) {
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
        t.setText("Payment link ready \u2014 " + a.money(cents / 100.0));
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
            public void onClick(View v) {
                a.startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
            }
        });
        r.addView(link);
        TextView note = new TextView(a);
        note.setText("Tap to open. Share this link with your customer \u2014 Stripe collects the card payment and deposits "
                + a.money(cents / 100.0) + " to your bank.");
        note.setTextSize(13);
        note.setTextColor(MainActivity.TEXT_SECONDARY);
        note.setPadding(0, a.dp(8), 0, 0);
        r.addView(note);
        return r;
    }

    static String mask(String pk) {
        if (pk.length() <= 8) return "\u2022\u2022\u2022\u2022";
        return pk.substring(0, 7) + "\u2022\u2022\u2022\u2022" + pk.substring(pk.length() - 4);
    }
}
