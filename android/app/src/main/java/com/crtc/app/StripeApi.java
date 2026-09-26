package com.crtc.app;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import org.json.JSONObject;

/**
 * Minimal Stripe client over HTTPS (no Stripe SDK — the SDK is heavy for a
 * single charge button). Creates a Stripe Payment Link with the merchant's own
 * secret key, so the merchant's customer pays into the merchant's own Stripe
 * account and bank. Never used for Appraze subscriptions (that's Play Billing).
 */
class StripeApi {

    interface LinkCallback {
        /** Called on a background thread. ok=true means value is the payment URL. */
        void done(boolean ok, String value);
    }

    static void createPaymentLink(final String secretKey, final long amountCents,
                                  final String description, final LinkCallback cb) {
        new Thread(new Runnable() {
            public void run() {
                HttpURLConnection con = null;
                try {
                    URL url = new URL("https://api.stripe.com/v1/payment_links");
                    con = (HttpURLConnection) url.openConnection();
                    con.setRequestMethod("POST");
                    con.setDoOutput(true);
                    con.setConnectTimeout(15000);
                    con.setReadTimeout(15000);
                    con.setRequestProperty("Authorization", "Bearer " + secretKey);
                    con.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
                    String body = "line_items[0][price_data][currency]=usd"
                            + "&line_items[0][price_data][unit_amount]=" + amountCents
                            + "&line_items[0][price_data][product_data][name]="
                            + URLEncoder.encode(description, "UTF-8");
                    byte[] bytes = body.getBytes("UTF-8");
                    con.setRequestProperty("Content-Length", String.valueOf(bytes.length));
                    OutputStream os = con.getOutputStream();
                    os.write(bytes);
                    os.flush();
                    os.close();
                    int code = con.getResponseCode();
                    InputStream is = (code >= 200 && code < 300) ? con.getInputStream() : con.getErrorStream();
                    String resp = readAll(is);
                    if (code >= 200 && code < 300) {
                        String link = new JSONObject(resp).optString("url", null);
                        if (link == null || link.isEmpty()) {
                            cb.done(false, "Stripe returned no payment URL.");
                        } else {
                            cb.done(true, link);
                        }
                    } else {
                        String msg = resp;
                        try {
                            JSONObject err = new JSONObject(resp).optJSONObject("error");
                            if (err != null) msg = err.optString("message", resp);
                        } catch (Exception ignored) { }
                        cb.done(false, "Stripe error (" + code + "): " + msg);
                    }
                } catch (Exception e) {
                    cb.done(false, e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()));
                } finally {
                    if (con != null) con.disconnect();
                }
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
