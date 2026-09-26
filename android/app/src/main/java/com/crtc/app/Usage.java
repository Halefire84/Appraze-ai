package com.crtc.app;

import android.content.SharedPreferences;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Freemium usage gating. Counters live in SharedPreferences and reset on the
 * calendar month. Metered actions: analyses, cross-list publishes, Holy Grail
 * scans. Plan limits — free 5, starter 50, pro 250, business 1000,
 * enterprise 5000 per action per month. POS is unlocked on any paid tier.
 *
 * The Holy Grail scan counter is tracked here for the future scan UI / backend;
 * the current Android build has no dedicated scan screen, so nothing consumes
 * it yet (see TODO in PlanSettings).
 */
class Usage {
    static final String ANALYSES = "analyses";
    static final String PUBLISHES = "publishes";
    static final String SCANS = "scans";

    static final int FREE_LIMIT = 5;

    final SharedPreferences p;

    Usage(SharedPreferences prefs) {
        p = prefs;
    }

    /** Local plan id. Defaults to free; everyone is free until backend verification lands. */
    String plan() {
        return p.getString("plan", "free");
    }

    void setPlan(String plan) {
        p.edit().putString("plan", plan).apply();
    }

    static int limitFor(String plan) {
        if ("starter".equals(plan)) return 50;
        if ("pro".equals(plan)) return 250;
        if ("business".equals(plan)) return 1000;
        if ("enterprise".equals(plan)) return 5000;
        return FREE_LIMIT;
    }

    static boolean posUnlocked(String plan) {
        return !"free".equals(plan);
    }

    static String actionLabel(String action) {
        if (PUBLISHES.equals(action)) return "cross-list publishes";
        if (SCANS.equals(action)) return "Holy Grail scans";
        return "analyses";
    }

    static String planLabel(String plan) {
        if (plan == null || plan.isEmpty()) return "Free";
        return plan.substring(0, 1).toUpperCase(Locale.US) + plan.substring(1);
    }

    String monthStamp() {
        return new SimpleDateFormat("yyyy-MM", Locale.US).format(new Date());
    }

    /** Zeroes every counter when the calendar month rolls over. */
    void rollover() {
        String m = monthStamp();
        if (!m.equals(p.getString("usage_month", ""))) {
            p.edit()
                    .putString("usage_month", m)
                    .putInt("usage_" + ANALYSES, 0)
                    .putInt("usage_" + PUBLISHES, 0)
                    .putInt("usage_" + SCANS, 0)
                    .apply();
        }
    }

    int used(String action) {
        rollover();
        return p.getInt("usage_" + action, 0);
    }

    int limit() {
        return limitFor(plan());
    }

    /**
     * Records one use when under the plan limit. Returns false when the limit
     * is already reached — the caller shows the upgrade dialog and nothing is
     * recorded, so the app never silently fails.
     */
    boolean tryConsume(String action) {
        rollover();
        int u = p.getInt("usage_" + action, 0);
        if (u >= limitFor(plan())) return false;
        p.edit().putInt("usage_" + action, u + 1).apply();
        return true;
    }
}
