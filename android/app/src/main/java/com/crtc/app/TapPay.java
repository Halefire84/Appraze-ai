package com.crtc.app;

import android.Manifest;
import android.app.Dialog;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.os.Build;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.stripe.stripeterminal.Terminal;
import com.stripe.stripeterminal.external.callable.Callback;
import com.stripe.stripeterminal.external.callable.ConnectionTokenCallback;
import com.stripe.stripeterminal.external.callable.ConnectionTokenProvider;
import com.stripe.stripeterminal.external.callable.DiscoveryListener;
import com.stripe.stripeterminal.external.callable.PaymentIntentCallback;
import com.stripe.stripeterminal.external.callable.ReaderCallback;
import com.stripe.stripeterminal.external.callable.TapToPayReaderListener;
import com.stripe.stripeterminal.external.callable.TerminalListener;
import com.stripe.stripeterminal.external.models.ConnectionConfiguration;
import com.stripe.stripeterminal.external.models.ConnectionTokenException;
import com.stripe.stripeterminal.external.models.DiscoveryConfiguration;
import com.stripe.stripeterminal.external.models.PaymentIntent;
import com.stripe.stripeterminal.external.models.PaymentIntentStatus;
import com.stripe.stripeterminal.external.models.Reader;
import com.stripe.stripeterminal.external.models.TapUseCase;
import com.stripe.stripeterminal.external.models.TerminalErrorCode;
import com.stripe.stripeterminal.external.models.TerminalException;
import com.stripe.stripeterminal.log.LogLevel;
import java.util.List;
import org.json.JSONObject;

/**
 * Tap to Pay on Android (Stripe Terminal). The customer taps their card or
 * phone on the merchant's phone; the charge is a card_present PaymentIntent
 * created by the Appraze POS server ON the merchant's own Stripe account.
 *
 * No Stripe key on the device: the Terminal SDK gets short-lived connection
 * tokens from the POS server, which mints them on the merchant's account.
 * A sale is only logged as PAID after the server re-reads it from Stripe.
 *
 * Debug builds use Stripe's simulated reader (Stripe does not allow real
 * Tap to Pay in debuggable apps); release builds use the phone's NFC.
 */
final class TapPay {

    static final int REQ_PERM_LOCATION = 3001;

    interface Result {
        /** Main thread. paid=true only after the server confirmed it with Stripe. */
        void done(boolean paid, String message);
    }

    private static Runnable pendingAfterPermission;
    private static boolean connecting;

    private TapPay() { }

    /** Tap to Pay needs Android 11+ and NFC hardware (simulated reader in debug builds skips NFC). */
    static boolean deviceSupported(MainActivity a) {
        if (Build.VERSION.SDK_INT < 30) return false;
        return BuildConfig.DEBUG || a.getPackageManager().hasSystemFeature(PackageManager.FEATURE_NFC);
    }

    static void onPermissionResult(MainActivity a, int req, boolean granted) {
        if (req != REQ_PERM_LOCATION) return;
        Runnable r = pendingAfterPermission;
        pendingAfterPermission = null;
        if (granted && r != null) {
            r.run();
        } else if (!granted) {
            a.infoDialog("Location needed for Tap to Pay",
                    "Stripe requires location access to accept in-person card payments. "
                    + "Enable it in Android Settings > Apps > Appraze > Permissions.");
        }
    }

    /** Called when Stripe is disconnected on this device, so the next merchant starts clean. */
    static void reset() {
        if (!Terminal.isInitialized()) return;
        try {
            Terminal t = Terminal.getInstance();
            if (t.getConnectedReader() != null) {
                t.disconnectReader(new Callback() {
                    public void onSuccess() { }
                    public void onFailure(TerminalException e) { }
                });
            }
            t.clearCachedCredentials();
        } catch (Exception ignored) { }
    }

    private static void ui(MainActivity a, Runnable r) {
        a.runOnUiThread(r);
    }

    private static String friendly(TerminalException e) {
        if (e.getErrorCode() == TerminalErrorCode.CANCELED) return "Payment canceled.";
        String m = e.getErrorMessage();
        return m == null || m.isEmpty() ? "Tap to Pay error: " + e.getErrorCode() : m;
    }

    private static void ensureInit(final MainActivity a) throws TerminalException {
        if (Terminal.isInitialized()) return;
        Terminal.init(a.getApplicationContext(), LogLevel.NONE, new ConnectionTokenProvider() {
            public void fetchConnectionToken(final ConnectionTokenCallback cb) {
                PosApi.call("POST", "/pos/terminal/connection_token", PosScreen.savedToken(a), null,
                        new PosApi.Callback() {
                            public void done(int code, JSONObject j, String error) {
                                if (code == 200 && !j.optString("secret").isEmpty()) {
                                    cb.onSuccess(j.optString("secret"));
                                } else {
                                    cb.onFailure(new ConnectionTokenException(
                                            error == null ? "No connection token" : error));
                                }
                            }
                        });
            }
        }, new TerminalListener() { }, null);
    }

    /** Full sale: business address (first time) -> NFC reader -> payment -> server-confirmed result. */
    static void charge(final MainActivity a, final long cents, final String description,
                       final String invoiceId, final Result result) {
        ensureLocation(a, new LocationReady() {
            public void ready(final String locationId) {
                withLocationPermission(a, new Runnable() {
                    public void run() {
                        ensureReader(a, locationId, result, new Runnable() {
                            public void run() { collect(a, cents, description, invoiceId, result); }
                        });
                    }
                });
            }
        }, result);
    }

    interface LocationReady {
        void ready(String locationId);
    }

    private static void ensureLocation(final MainActivity a, final LocationReady next, final Result result) {
        PosApi.call("GET", "/pos/terminal/location", PosScreen.savedToken(a), null, new PosApi.Callback() {
            public void done(int code, JSONObject j, String error) {
                if (code != 200) { result.done(false, error); return; }
                String loc = j.optString("location_id", "");
                if (!loc.isEmpty() && !"null".equals(loc)) {
                    next.ready(loc);
                } else {
                    addressDialog(a, next, result);
                }
            }
        });
    }

    private static void withLocationPermission(MainActivity a, Runnable next) {
        if (a.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            next.run();
        } else {
            pendingAfterPermission = next;
            a.requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_PERM_LOCATION);
        }
    }

    private static void ensureReader(final MainActivity a, final String locationId, final Result result,
                                     final Runnable next) {
        try {
            ensureInit(a);
        } catch (TerminalException e) {
            result.done(false, friendly(e));
            return;
        }
        final Terminal t = Terminal.getInstance();
        if (t.getConnectedReader() != null) { next.run(); return; }
        if (a.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            result.done(false, "Location permission is required for Tap to Pay.");
            return;
        }
        if (connecting) { result.done(false, "Tap to Pay is still starting. Try again in a moment."); return; }
        connecting = true;
        final ReaderCallback onConnected = new ReaderCallback() {
            public void onSuccess(Reader reader) {
                connecting = false;
                a.events.record("tap_reader_connected", "simulated=" + BuildConfig.DEBUG);
                ui(a, next);
            }
            public void onFailure(final TerminalException e) {
                connecting = false;
                ui(a, new Runnable() { public void run() { result.done(false, friendly(e)); } });
            }
        };
        t.discoverReaders(new DiscoveryConfiguration.TapToPayDiscoveryConfiguration(BuildConfig.DEBUG),
                new DiscoveryListener() {
                    private boolean started;
                    public void onUpdateDiscoveredReaders(List<Reader> readers) {
                        if (started || readers == null || readers.isEmpty()) return;
                        started = true;
                        t.connectReader(readers.get(0),
                                new ConnectionConfiguration.TapToPayConnectionConfiguration(
                                        new TapUseCase.Pay(locationId), true, new TapToPayReaderListener() { }),
                                onConnected);
                    }
                },
                new Callback() {
                    public void onSuccess() { }
                    public void onFailure(final TerminalException e) {
                        if (t.getConnectedReader() != null) return;
                        connecting = false;
                        ui(a, new Runnable() { public void run() { result.done(false, friendly(e)); } });
                    }
                });
    }

    private static void collect(final MainActivity a, final long cents, final String description,
                                final String invoiceId, final Result result) {
        JSONObject req = new JSONObject();
        try {
            req.put("amount_cents", cents);
            req.put("description", description);
            req.put("invoice_id", invoiceId);
        } catch (Exception e) {
            result.done(false, "Couldn't build the payment.");
            return;
        }
        PosApi.call("POST", "/pos/terminal/payment_intent", PosScreen.savedToken(a), req, new PosApi.Callback() {
            public void done(int code, JSONObject j, String error) {
                if (code != 200) { result.done(false, error); return; }
                final String piId = j.optString("payment_intent_id");
                a.sales.start(SalesLog.METHOD_TAP, cents, description, invoiceId, piId);
                a.events.record("tap_payment_started", "amount_cents=" + cents + "|invoice=" + invoiceId);
                final Terminal t = Terminal.getInstance();
                t.retrievePaymentIntent(j.optString("client_secret"), new PaymentIntentCallback() {
                    public void onSuccess(PaymentIntent pi) {
                        t.collectPaymentMethod(pi, new PaymentIntentCallback() {
                            public void onSuccess(PaymentIntent collected) {
                                t.confirmPaymentIntent(collected, new PaymentIntentCallback() {
                                    public void onSuccess(PaymentIntent confirmed) {
                                        ui(a, new Runnable() {
                                            public void run() { verify(a, piId, cents, result); }
                                        });
                                    }
                                    public void onFailure(TerminalException e) { fail(a, piId, e, result); }
                                });
                            }
                            public void onFailure(TerminalException e) { fail(a, piId, e, result); }
                        });
                    }
                    public void onFailure(TerminalException e) { fail(a, piId, e, result); }
                });
            }
        });
    }

    private static void fail(final MainActivity a, final String piId, final TerminalException e, final Result result) {
        ui(a, new Runnable() {
            public void run() {
                boolean canceled = e.getErrorCode() == TerminalErrorCode.CANCELED;
                a.sales.setStatus(piId, canceled ? SalesLog.CANCELED : SalesLog.FAILED);
                a.events.record(canceled ? "tap_payment_canceled" : "tap_payment_failed",
                        "code=" + e.getErrorCode());
                result.done(false, friendly(e));
            }
        });
    }

    /** The server re-reads the PaymentIntent from Stripe; only that marks the sale PAID. */
    static void verify(final MainActivity a, final String piId, final long cents, final Result result) {
        PosApi.call("GET", "/pos/terminal/payment_intent/" + android.net.Uri.encode(piId) + "/status",
                PosScreen.savedToken(a), null, new PosApi.Callback() {
                    public void done(int code, JSONObject j, String error) {
                        if (code == 200 && j.optBoolean("paid")) {
                            a.sales.setStatus(piId, SalesLog.PAID);
                            a.events.record("tap_payment_confirmed", "amount_cents=" + cents);
                            result.done(true, "Paid " + a.money(cents / 100.0));
                        } else if (code == 200) {
                            String st = j.optString("status");
                            if (PaymentIntentStatus.CANCELED.name().equalsIgnoreCase(st)) {
                                a.sales.setStatus(piId, SalesLog.CANCELED);
                            }
                            result.done(false, "Not confirmed yet (" + st + "). Check Recent Sales in a moment.");
                        } else {
                            result.done(false, "Payment sent, but confirmation failed: " + error
                                    + " It will show in Recent Sales once confirmed.");
                        }
                    }
                });
    }

    /** First-time setup: Stripe needs the business address for in-person payments. */
    private static void addressDialog(final MainActivity a, final LocationReady next, final Result result) {
        final Dialog d = new Dialog(a);
        LinearLayout l = a.dialogLayout();
        TextView t = new TextView(a);
        t.setText("Business address");
        t.setTextSize(18);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(MainActivity.TEXT_PRIMARY);
        l.addView(t);
        l.addView(a.caption("Stripe needs where you sell in person before Tap to Pay can take cards. One time only."));
        int text = InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_WORDS;
        final MainActivity.Field name = a.labeled(l, "Business name", "", text);
        final MainActivity.Field line1 = a.labeled(l, "Street address", "", text | InputType.TYPE_TEXT_VARIATION_POSTAL_ADDRESS);
        final MainActivity.Field city = a.labeled(l, "City", "", text);
        final MainActivity.Field state = a.labeled(l, "State (2 letters)", "",
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
        final MainActivity.Field zip = a.labeled(l, "ZIP", "", InputType.TYPE_CLASS_NUMBER);
        final Button save = a.primaryButton("Save & Continue");
        save.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                MainActivity.Field[] all = {name, line1, city, state, zip};
                boolean ok = true;
                for (MainActivity.Field f : all) {
                    if (f.input.getText().toString().trim().isEmpty()) {
                        a.setFieldError(f, "Required.");
                        ok = false;
                    } else {
                        a.setFieldError(f, null);
                    }
                }
                if (!ok) return;
                JSONObject body = new JSONObject();
                try {
                    body.put("display_name", name.input.getText().toString().trim());
                    body.put("line1", line1.input.getText().toString().trim());
                    body.put("city", city.input.getText().toString().trim());
                    body.put("state", state.input.getText().toString().trim().toUpperCase(java.util.Locale.US));
                    body.put("postal_code", zip.input.getText().toString().trim());
                    body.put("country", "US");
                } catch (Exception e) {
                    return;
                }
                save.setEnabled(false);
                PosApi.call("POST", "/pos/terminal/location", PosScreen.savedToken(a), body, new PosApi.Callback() {
                    public void done(int code, JSONObject j, String error) {
                        save.setEnabled(true);
                        if (code == 200) {
                            d.dismiss();
                            a.events.record("tap_location_saved", "");
                            next.ready(j.optString("location_id"));
                        } else {
                            a.infoDialog("Couldn't save address", error);
                        }
                    }
                });
            }
        });
        l.addView(save);
        TextView cancel = a.textButton("Cancel", MainActivity.TEXT_MUTED);
        cancel.setGravity(android.view.Gravity.CENTER);
        cancel.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                d.dismiss();
                result.done(false, "Tap to Pay needs your business address first.");
            }
        });
        l.addView(cancel);
        android.widget.ScrollView sv = new android.widget.ScrollView(a);
        sv.addView(l);
        d.setContentView(sv);
        a.showDialog(d);
    }
}
