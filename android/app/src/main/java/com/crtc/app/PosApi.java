package com.crtc.app;

import android.os.Handler;
import android.os.Looper;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONObject;

/**
 * Client for the Appraze POS backend (pos_connect.py, Stripe Connect).
 *
 * The app holds NO Stripe credential. Appraze's platform key lives only on
 * the backend; this device holds a revocable device token that maps to the
 * merchant's own connected Stripe account. Charges are Stripe Checkout
 * Sessions created on that account, so money settles to the merchant — never
 * through Appraze. Not used for Appraze subscriptions (Play Billing).
 */
class PosApi {

    interface Callback {
        /** Called on the main thread. status is the HTTP code, or 0 when the server was unreachable. */
        void done(int status, JSONObject body, String error);
    }

    /** Set at build time: gradle -PapprazePosApi=https://your-host */
    static String base() {
        String b = BuildConfig.POS_API_BASE;
        return b == null ? "" : b.trim().replaceAll("/+$", "");
    }

    /** Only HTTPS backends are accepted — the device token must never travel in cleartext. */
    static boolean configured() {
        return base().startsWith("https://");
    }

    static void call(final String method, final String path, final String token,
                     final JSONObject body, final Callback cb) {
        final Handler main = new Handler(Looper.getMainLooper());
        new Thread(new Runnable() {
            public void run() {
                int code = 0;
                JSONObject json = new JSONObject();
                String error = null;
                HttpURLConnection con = null;
                try {
                    if (!configured()) throw new IllegalStateException("POS server not configured");
                    con = (HttpURLConnection) new URL(base() + path).openConnection();
                    con.setRequestMethod(method);
                    con.setConnectTimeout(15000);
                    con.setReadTimeout(30000);
                    con.setRequestProperty("Accept", "application/json");
                    if (token != null && !token.isEmpty()) {
                        con.setRequestProperty("Authorization", "Bearer " + token);
                    }
                    if (body != null) {
                        byte[] bytes = body.toString().getBytes("UTF-8");
                        con.setDoOutput(true);
                        con.setRequestProperty("Content-Type", "application/json");
                        con.setFixedLengthStreamingMode(bytes.length);
                        OutputStream os = con.getOutputStream();
                        os.write(bytes);
                        os.close();
                    }
                    code = con.getResponseCode();
                    InputStream is = code >= 400 ? con.getErrorStream() : con.getInputStream();
                    String resp = is == null ? "" : readAll(is);
                    try {
                        json = new JSONObject(resp);
                    } catch (Exception ignored) {
                        json = new JSONObject();
                    }
                    if (code >= 400) {
                        error = json.optString("error", "Server error (" + code + ").");
                    }
                } catch (Exception e) {
                    code = 0;
                    error = "Couldn't reach the Appraze POS server. Check your connection and try again.";
                } finally {
                    if (con != null) con.disconnect();
                }
                final int c = code;
                final JSONObject j = json;
                final String err = error;
                main.post(new Runnable() {
                    public void run() { cb.done(c, j, err); }
                });
            }
        }).start();
    }

    static String readAll(InputStream is) throws Exception {
        StringBuilder sb = new StringBuilder();
        byte[] buf = new byte[4096];
        int n;
        while ((n = is.read(buf)) != -1) sb.append(new String(buf, 0, n, "UTF-8"));
        is.close();
        return sb.toString();
    }
}
