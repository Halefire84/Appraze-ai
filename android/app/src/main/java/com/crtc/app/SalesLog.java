package com.crtc.app;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

/**
 * On-device POS sales log: every sale with the date and time it was started
 * and the date and time it was confirmed paid. Status is only set to PAID
 * after the Appraze POS server re-reads the payment from Stripe.
 */
class SalesLog extends SQLiteOpenHelper {

    static final String PENDING = "PENDING";
    static final String PAID = "PAID";
    static final String FAILED = "FAILED";
    static final String CANCELED = "CANCELED";

    static final String METHOD_TAP = "TAP";
    static final String METHOD_LINK = "LINK";

    static class Sale {
        long id;
        long createdMs;
        long paidMs;
        String method;
        long amountCents;
        String description;
        String invoiceId;
        String stripeId;
        String status;
    }

    SalesLog(Context x) { super(x, "sales.db", null, 1); }

    public void onCreate(SQLiteDatabase d) {
        d.execSQL("CREATE TABLE sales(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at INTEGER NOT NULL,"
                + " paid_at INTEGER, method TEXT NOT NULL, amount_cents INTEGER NOT NULL, description TEXT,"
                + " invoice_id TEXT, stripe_id TEXT, status TEXT NOT NULL)");
        d.execSQL("CREATE UNIQUE INDEX sales_stripe_id ON sales(stripe_id)");
    }

    public void onUpgrade(SQLiteDatabase d, int a, int b) { }

    /** Records a new sale (or returns the existing row for a retried Stripe id). */
    long start(String method, long amountCents, String description, String invoiceId, String stripeId) {
        Sale existing = byStripeId(stripeId);
        if (existing != null) {
            // Retry of the same Stripe payment (e.g. customer canceled, then tapped again).
            if (!PAID.equals(existing.status) && !PENDING.equals(existing.status)) {
                ContentValues v = new ContentValues();
                v.put("status", PENDING);
                getWritableDatabase().update("sales", v, "stripe_id=?", new String[]{stripeId});
            }
            return existing.id;
        }
        ContentValues v = new ContentValues();
        v.put("created_at", System.currentTimeMillis());
        v.put("method", method);
        v.put("amount_cents", amountCents);
        v.put("description", description);
        v.put("invoice_id", invoiceId);
        v.put("stripe_id", stripeId);
        v.put("status", PENDING);
        return getWritableDatabase().insert("sales", null, v);
    }

    /** PAID is final: a late FAILED/CANCELED never overwrites it. */
    void setStatus(String stripeId, String status) {
        Sale s = byStripeId(stripeId);
        if (s == null || PAID.equals(s.status) || status.equals(s.status)) return;
        ContentValues v = new ContentValues();
        v.put("status", status);
        if (PAID.equals(status)) v.put("paid_at", System.currentTimeMillis());
        getWritableDatabase().update("sales", v, "stripe_id=?", new String[]{stripeId});
    }

    Sale byStripeId(String stripeId) {
        if (stripeId == null) return null;
        Cursor c = getReadableDatabase().query("sales", null, "stripe_id=?", new String[]{stripeId},
                null, null, null);
        try {
            return c.moveToFirst() ? read(c) : null;
        } finally {
            c.close();
        }
    }

    List<Sale> recent(int limit) {
        List<Sale> out = new ArrayList<>();
        Cursor c = getReadableDatabase().query("sales", null, null, null, null, null,
                "created_at DESC", String.valueOf(limit));
        try {
            while (c.moveToNext()) out.add(read(c));
        } finally {
            c.close();
        }
        return out;
    }

    private static Sale read(Cursor c) {
        Sale s = new Sale();
        s.id = c.getLong(c.getColumnIndexOrThrow("id"));
        s.createdMs = c.getLong(c.getColumnIndexOrThrow("created_at"));
        int paid = c.getColumnIndexOrThrow("paid_at");
        s.paidMs = c.isNull(paid) ? 0 : c.getLong(paid);
        s.method = c.getString(c.getColumnIndexOrThrow("method"));
        s.amountCents = c.getLong(c.getColumnIndexOrThrow("amount_cents"));
        s.description = c.getString(c.getColumnIndexOrThrow("description"));
        s.invoiceId = c.getString(c.getColumnIndexOrThrow("invoice_id"));
        s.stripeId = c.getString(c.getColumnIndexOrThrow("stripe_id"));
        s.status = c.getString(c.getColumnIndexOrThrow("status"));
        return s;
    }

    /** "Sat, Sep 26, 2026 · 8:45 AM" in the phone's time zone. */
    static String formatWhen(long ms, TimeZone tz, Locale locale) {
        SimpleDateFormat f = new SimpleDateFormat("EEE, MMM d, yyyy '·' h:mm a", locale);
        f.setTimeZone(tz);
        return f.format(new Date(ms));
    }

    static String formatWhen(long ms) {
        return formatWhen(ms, TimeZone.getDefault(), Locale.getDefault());
    }

    static String methodLabel(String method) {
        return METHOD_TAP.equals(method) ? "Tap to Pay" : "Payment link";
    }

    static String statusLabel(String status) {
        if (PAID.equals(status)) return "Paid";
        if (FAILED.equals(status)) return "Failed";
        if (CANCELED.equals(status)) return "Canceled";
        return "Pending";
    }
}
