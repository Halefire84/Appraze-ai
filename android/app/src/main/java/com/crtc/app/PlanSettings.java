package com.crtc.app;

import android.app.Dialog;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Freemium plan setting (Settings tab) + gold upgrade dialog.
 *
 * The plan is stored locally so it can be changed manually for testing.
 * TODO: verify the plan server-side (Play Billing / backend entitlement check)
 * before enforcing paid limits in production — treat the local value as
 * provisional until that hook lands. For now, everyone is Free by default.
 *
 * TODO: wire Usage.SCANS to the future Holy Grail scan UI — the counter,
 * monthly reset, and limits already work; there is just no scan screen in this
 * build yet.
 */
class PlanSettings {

    static final String[] PLANS = {"free", "starter", "pro", "business", "enterprise"};

    static void addPlanGroup(final MainActivity a) {
        LinearLayout c = a.card(a.body, false);
        LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) c.getLayoutParams();
        lp.topMargin = a.dp(12);
        c.setLayoutParams(lp);
        c.addView(a.sectionLabel("Plan"));
        final Usage u = a.usage;

        LinearLayout row = new LinearLayout(a);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(a.dp(4), a.dp(10), a.dp(4), a.dp(10));
        TextView l = new TextView(a);
        l.setText("Current plan");
        l.setTextSize(15);
        l.setTextColor(MainActivity.TEXT_SECONDARY);
        row.addView(l, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView v = new TextView(a);
        v.setText(Usage.planLabel(u.plan()));
        v.setTextSize(16);
        v.setTypeface(Typeface.DEFAULT_BOLD);
        v.setTextColor(MainActivity.GOLD);
        row.addView(v);
        row.setClickable(true);
        row.setFocusable(true);
        row.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { pickPlan(a); }
        });
        c.addView(row);

        String[] actions = {Usage.ANALYSES, Usage.PUBLISHES, Usage.SCANS};
        for (String act : actions) {
            c.addView(usageRow(a, u, act));
        }
        TextView pos = new TextView(a);
        boolean unlocked = Usage.posUnlocked(u.plan());
        pos.setText("POS: " + (unlocked ? "Unlocked" : "Locked (paid plans)"));
        pos.setTextSize(14);
        pos.setTextColor(unlocked ? MainActivity.BUY : MainActivity.TEXT_MUTED);
        pos.setPadding(a.dp(4), a.dp(10), a.dp(4), a.dp(4));
        c.addView(pos);
        c.addView(a.caption("Testing only: the plan is stored on this device. Usage resets on the 1st of each month."));
    }

    static LinearLayout usageRow(MainActivity a, Usage u, String action) {
        LinearLayout row = new LinearLayout(a);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(a.dp(4), a.dp(6), a.dp(4), a.dp(6));
        TextView l = new TextView(a);
        l.setText(Usage.actionLabel(action));
        l.setTextSize(14);
        l.setTextColor(MainActivity.TEXT_SECONDARY);
        row.addView(l, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView v = new TextView(a);
        v.setText(u.used(action) + " / " + u.limit() + " this month");
        v.setTextSize(14);
        v.setTextColor(MainActivity.GOLD);
        row.addView(v);
        return row;
    }

    static void pickPlan(final MainActivity a) {
        final Dialog d = new Dialog(a);
        LinearLayout l = a.dialogLayout();
        TextView t = new TextView(a);
        t.setText("Choose plan");
        t.setTextSize(18);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(MainActivity.TEXT_PRIMARY);
        t.setPadding(0, 0, 0, a.dp(4));
        l.addView(t);
        for (final String plan : PLANS) {
            final boolean current = plan.equals(a.usage.plan());
            TextView opt = new TextView(a);
            opt.setText(Usage.planLabel(plan) + " \u2014 " + Usage.limitFor(plan) + " / month"
                    + (current ? "  \u2713" : ""));
            opt.setTextSize(16);
            opt.setTextColor(current ? MainActivity.GOLD : MainActivity.TEXT_PRIMARY);
            opt.setPadding(a.dp(4), a.dp(14), a.dp(4), a.dp(14));
            opt.setClickable(true);
            opt.setFocusable(true);
            opt.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    a.usage.setPlan(plan);
                    a.events.record("plan_changed", "plan=" + plan);
                    d.dismiss();
                    a.settings();
                }
            });
            l.addView(opt);
        }
        Button cancel = a.secondaryButton("Cancel");
        cancel.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { d.dismiss(); }
        });
        l.addView(cancel);
        d.setContentView(l);
        a.showDialog(d);
    }

    /** Gold-styled upgrade dialog shown when a user hits a monthly limit. Never silently fails. */
    static void upgradeDialog(final MainActivity a, final Usage u, final String action) {
        final Dialog d = new Dialog(a);
        LinearLayout l = a.dialogLayout();
        TextView kicker = new TextView(a);
        kicker.setText("UPGRADE");
        kicker.setTextSize(13);
        kicker.setTypeface(Typeface.DEFAULT_BOLD);
        kicker.setTextColor(MainActivity.GOLD);
        kicker.setLetterSpacing(0.08f);
        l.addView(kicker);
        TextView t = new TextView(a);
        t.setText("You've hit your monthly limit");
        t.setTextSize(18);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(MainActivity.TEXT_PRIMARY);
        t.setPadding(0, a.dp(4), 0, 0);
        l.addView(t);
        TextView m = new TextView(a);
        m.setText("Free includes " + u.limit() + " " + Usage.actionLabel(action)
                + " per month and you've used them all.\n\nUpgrade for more: Starter 50, Pro 250, Business 1,000, Enterprise 5,000 per month \u2014 plus POS card payments on any paid plan.");
        m.setTextSize(15);
        m.setTextColor(MainActivity.TEXT_SECONDARY);
        m.setPadding(0, a.dp(8), 0, 0);
        l.addView(m);
        Button plans = a.primaryButton("View Plans");
        plans.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                d.dismiss();
                a.goTab(3);
            }
        });
        l.addView(plans);
        Button later = a.secondaryButton("Not now");
        later.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { d.dismiss(); }
        });
        l.addView(later);
        d.setContentView(l);
        a.showDialog(d);
        a.events.record("limit_reached", "action=" + action + "|plan=" + u.plan());
    }
}
