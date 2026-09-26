package com.crtc.app;

import android.app.Activity;
import android.app.Dialog;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.view.Window;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;
import java.util.ArrayList;
import java.util.Locale;

/** Native Android entry point. No WebView or Trusted Web Activity is used. */
public final class MainActivity extends Activity {

    /* ---------- Appraze brand palette ----------
     * Assigned only by applyTheme() from the active Palette (light default,
     * dark optional). Screens are rebuilt on every navigation, so a toggle
     * takes effect on the next render with no stale colors. */
    static boolean darkTheme;
    static int BG;
    static int GLASS;
    static int GLASS_BORDER;
    static int GOLD_BORDER;
    static int GOLD;
    static int GOLD_LIGHT;
    static int GOLD_DEEP;
    static int ON_GOLD;
    static int TEXT_PRIMARY;
    static int TEXT_SECONDARY;
    static int TEXT_MUTED;
    static int BUY;
    static int PASS;
    static int REVIEW;

    static {
        setPalette(Palette.LIGHT);
    }

    static void setPalette(Palette p) {
        darkTheme = p.dark;
        BG = p.bg;
        GLASS = p.glass;
        GLASS_BORDER = p.glassBorder;
        GOLD_BORDER = p.goldBorder;
        GOLD = p.gold;
        GOLD_LIGHT = p.goldLight;
        GOLD_DEEP = p.goldDeep;
        ON_GOLD = p.onGold;
        TEXT_PRIMARY = p.textPrimary;
        TEXT_SECONDARY = p.textSecondary;
        TEXT_MUTED = p.textMuted;
        BUY = p.buy;
        PASS = p.pass;
        REVIEW = p.review;
    }

    /** Loads the saved theme choice (light by default) and styles the system bars to match. */
    void applyTheme() {
        setPalette(Palette.forDark(prefs.getBoolean(Palette.PREF_KEY, false)));
        Window w = getWindow();
        w.setStatusBarColor(BG);
        w.setNavigationBarColor(GLASS | 0xFF000000);
        w.getDecorView().setBackgroundColor(BG);
        if (Build.VERSION.SDK_INT >= 30) {
            android.view.WindowInsetsController c = w.getInsetsController();
            if (c != null) {
                int light = android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                        | android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                c.setSystemBarsAppearance(darkTheme ? 0 : light, light);
            }
        } else {
            View decor = w.getDecorView();
            int flags = decor.getSystemUiVisibility();
            int light = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            if (Build.VERSION.SDK_INT >= 26) light |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            decor.setSystemUiVisibility(darkTheme ? (flags & ~light) : (flags | light));
        }
    }

    void setDarkTheme(boolean dark) {
        prefs.edit().putBoolean(Palette.PREF_KEY, dark).apply();
        applyTheme();
        events.record("theme_changed", "theme=" + (dark ? "dark" : "light"));
    }

    static final String APP_VERSION = "1.0.0-native";
    static final String SUPPORT_EMAIL = "chale@cooperrivertrading.com";

    LinearLayout body;
    LinearLayout headerRow;
    EventStore events;
    InventoryStore inventory;
    SharedPreferences prefs;
    Usage usage;
    String analysisPhoto;
    Uri pendingPhotoUri;
    ImageView photoThumb;

    void refreshPhotoThumb() {
        if (photoThumb == null) return;
        if (analysisPhoto == null) {
            photoThumb.setVisibility(View.GONE);
        } else {
            photoThumb.setImageURI(Uri.parse(analysisPhoto));
            photoThumb.setVisibility(View.VISIBLE);
        }
    }

    public void onCreate(Bundle b) {
        super.onCreate(b);
        events = new EventStore(this);
        inventory = new InventoryStore(this);
        prefs = getPreferences(0);
        usage = new Usage(prefs);
        usage.rollover();
        applyTheme();
        splash();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        PhotoCapture.onActivityResult(this, requestCode, resultCode, data);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        boolean granted = grantResults.length > 0
                && grantResults[0] == android.content.pm.PackageManager.PERMISSION_GRANTED;
        PhotoCapture.onPermissionResult(this, requestCode, granted);
    }

    /* ---------- units & drawables ---------- */

    int dp(float v) {
        return (int) (v * getResources().getDisplayMetrics().density + 0.5f);
    }

    int withAlpha(int color, float alpha) {
        return (color & 0x00FFFFFF) | ((int) (255 * alpha) << 24);
    }

    GradientDrawable glassBg(int radiusDp, int strokeColor) {
        GradientDrawable d = new GradientDrawable();
        d.setShape(GradientDrawable.RECTANGLE);
        d.setCornerRadius(dp(radiusDp));
        d.setColor(GLASS);
        d.setStroke(dp(1), strokeColor);
        return d;
    }

    GradientDrawable btnBg(int color) {
        GradientDrawable d = new GradientDrawable();
        d.setShape(GradientDrawable.RECTANGLE);
        d.setCornerRadius(dp(12));
        d.setColor(color);
        return d;
    }

    /** Glass card: 16dp radius, glass fill, 1dp border, 8dp elevation, 16dp padding. */
    LinearLayout card(ViewGroup parent, boolean highlight) {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setBackground(glassBg(16, highlight ? GOLD_BORDER : GLASS_BORDER));
        c.setElevation(dp(8));
        int p = dp(16);
        c.setPadding(p, p, p, p);
        parent.addView(c, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        return c;
    }

    /** 13sp bold gold uppercase label, letter-spaced. */
    TextView sectionLabel(String text) {
        TextView t = new TextView(this);
        t.setText(text.toUpperCase(Locale.US));
        t.setTextSize(13);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(GOLD);
        t.setLetterSpacing(0.08f);
        t.setPadding(dp(4), dp(4), dp(4), dp(4));
        return t;
    }

    /** 12sp muted caption. */
    TextView caption(String text) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextSize(12);
        t.setTextColor(TEXT_MUTED);
        t.setPadding(dp(4), dp(8), dp(4), 0);
        return t;
    }

    /** Small gold/red text button for inline actions. */
    TextView textButton(String text, int color) {
        TextView t = new TextView(this);
        t.setText(text.toUpperCase(Locale.US));
        t.setTextSize(13);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(color);
        t.setPadding(dp(12), dp(12), dp(12), dp(12));
        t.setClickable(true);
        t.setFocusable(true);
        return t;
    }

    /* ---------- gold-labeled inputs ---------- */

    static class Field {
        EditText input;
        TextView error;
    }

    int decimalInput() {
        return InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL;
    }

    Field labeled(LinearLayout parent, String label, String value, int inputType) {
        TextView t = sectionLabel(label);
        t.setPadding(dp(4), dp(12), dp(4), dp(6));
        parent.addView(t);
        EditText e = new EditText(this);
        e.setText(value == null ? "" : value);
        e.setHint(label);
        e.setTextSize(16);
        e.setTextColor(TEXT_PRIMARY);
        e.setHintTextColor(TEXT_MUTED);
        e.setInputType(inputType);
        e.setSingleLine(true);
        e.setBackground(glassBg(12, GLASS_BORDER));
        int p = dp(12);
        e.setPadding(p, dp(14), p, dp(14));
        parent.addView(e, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        TextView err = new TextView(this);
        err.setTextSize(12);
        err.setTextColor(PASS);
        err.setVisibility(View.GONE);
        err.setPadding(dp(4), dp(4), dp(4), 0);
        parent.addView(err);
        Field f = new Field();
        f.input = e;
        f.error = err;
        return f;
    }

    void setFieldError(Field f, String msg) {
        if (msg == null) {
            f.input.setBackground(glassBg(12, GLASS_BORDER));
            f.error.setVisibility(View.GONE);
        } else {
            f.input.setBackground(glassBg(12, PASS));
            f.error.setText(msg);
            f.error.setVisibility(View.VISIBLE);
        }
    }

    /** Returns null and shows an inline error when the input is not a number >= 0. */
    Double parseNonNegative(Field f) {
        try {
            String s = f.input.getText().toString().trim();
            if (s.isEmpty()) { setFieldError(f, "Enter a number."); return null; }
            double x = Double.parseDouble(s);
            if (!Double.isFinite(x) || x < 0) { setFieldError(f, "Enter 0 or more."); return null; }
            setFieldError(f, null);
            return x;
        } catch (Exception e) {
            setFieldError(f, "Enter a number.");
            return null;
        }
    }

    String money(double x) {
        return String.format(Locale.US, "$%,.2f", x);
    }

    double prefsDouble(String key, double def) {
        try {
            return Double.parseDouble(prefs.getString(key, String.valueOf(def)));
        } catch (Exception e) {
            return def;
        }
    }

    /* ---------- buttons ---------- */

    void styleButton(Button b) {
        b.setAllCaps(true);
        b.setTypeface(Typeface.DEFAULT_BOLD);
        b.setMinHeight(0);
        b.setMinimumHeight(0);
        b.setPadding(dp(16), 0, dp(16), 0);
        b.setStateListAnimator(null);
    }

    /** Primary: gold fill, 12dp radius, 16sp bold on-gold text, 52dp tall. */
    Button primaryButton(String text) {
        Button b = new Button(this);
        styleButton(b);
        b.setText(text);
        b.setTextSize(16);
        b.setTextColor(new ColorStateList(
                new int[][]{new int[]{-android.R.attr.state_enabled}, new int[]{}},
                new int[]{TEXT_MUTED, ON_GOLD}));
        StateListDrawable s = new StateListDrawable();
        s.addState(new int[]{android.R.attr.state_pressed}, btnBg(GOLD_LIGHT));
        s.addState(new int[]{-android.R.attr.state_enabled}, btnBg(GOLD_DEEP));
        s.addState(new int[]{}, btnBg(GOLD));
        b.setBackground(s);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(52));
        lp.topMargin = dp(16);
        b.setLayoutParams(lp);
        return b;
    }

    /** Secondary: transparent, 1dp gold border, gold text. */
    Button secondaryButton(String text) {
        Button b = new Button(this);
        styleButton(b);
        b.setText(text);
        b.setTextSize(14);
        b.setTextColor(GOLD);
        GradientDrawable d = btnBg(Color.TRANSPARENT);
        d.setStroke(dp(1), GOLD);
        b.setBackground(d);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(48));
        lp.topMargin = dp(12);
        b.setLayoutParams(lp);
        return b;
    }

    /* ---------- verdict banner ---------- */

    LinearLayout verdictBanner(int color, String word, String reason) {
        LinearLayout banner = new LinearLayout(this);
        banner.setOrientation(LinearLayout.HORIZONTAL);
        GradientDrawable bg = new GradientDrawable();
        bg.setShape(GradientDrawable.RECTANGLE);
        bg.setCornerRadius(dp(16));
        bg.setColor(withAlpha(color, 0.12f));
        bg.setStroke(dp(1), GLASS_BORDER);
        banner.setBackground(bg);
        banner.setElevation(dp(8));
        View strip = new View(this);
        strip.setBackgroundColor(color);
        banner.addView(strip, new LinearLayout.LayoutParams(dp(4),
                LinearLayout.LayoutParams.MATCH_PARENT));
        LinearLayout inner = new LinearLayout(this);
        inner.setOrientation(LinearLayout.VERTICAL);
        inner.setPadding(dp(12), dp(16), dp(16), dp(16));
        TextView w = new TextView(this);
        w.setText(word);
        w.setTextSize(22);
        w.setTypeface(Typeface.DEFAULT_BOLD);
        w.setTextColor(color);
        inner.addView(w);
        TextView r = new TextView(this);
        r.setText(reason);
        r.setTextSize(15);
        r.setTextColor(TEXT_SECONDARY);
        r.setPadding(0, dp(4), 0, 0);
        inner.addView(r);
        banner.addView(inner, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(16);
        banner.setLayoutParams(lp);
        banner.setAlpha(0f);
        banner.setTranslationY(-dp(12));
        banner.animate().alpha(1f).translationY(0f).setDuration(250).start();
        return banner;
    }

    LinearLayout stat(String label, String value) {
        LinearLayout s = new LinearLayout(this);
        s.setOrientation(LinearLayout.VERTICAL);
        s.setLayoutParams(new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView l = new TextView(this);
        l.setText(label);
        l.setTextSize(12);
        l.setTextColor(TEXT_MUTED);
        l.setLetterSpacing(0.08f);
        s.addView(l);
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(28);
        v.setTypeface(Typeface.DEFAULT_BOLD);
        v.setTextColor(GOLD);
        s.addView(v);
        return s;
    }

    LinearLayout verdictBanner(Deal d, double holyRoi) {
        int color = d.verdict.equals("BUY") ? BUY : d.verdict.equals("REVIEW") ? REVIEW : PASS;
        String hb = holyRoi == Math.rint(holyRoi) ? String.valueOf((long) holyRoi) : String.valueOf(holyRoi);
        String reason = d.verdict.equals("BUY") ? "Clears your " + hb + "% Holy Grail. Run it."
                : d.verdict.equals("REVIEW") ? "Near the line. Verify comps before you commit."
                : "Misses your thresholds. Move on.";
        LinearLayout banner = verdictBanner(color, d.verdict, reason);
        LinearLayout inner = (LinearLayout) banner.getChildAt(1);
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setPadding(0, dp(12), 0, 0);
        row.addView(stat("PROFIT", money(d.profit)));
        row.addView(stat("ROI", Double.isInfinite(d.roi) ? "\u221E" : String.format(Locale.US, "%.1f%%", d.roi)));
        inner.addView(row);
        return banner;
    }

    /* ---------- dialogs ---------- */

    LinearLayout dialogLayout() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setBackground(glassBg(16, GLASS_BORDER));
        int p = dp(20);
        l.setPadding(p, p, p, p);
        return l;
    }

    void showDialog(Dialog d) {
        d.show();
        Window w = d.getWindow();
        if (w != null) {
            w.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
            w.setLayout((int) (getResources().getDisplayMetrics().widthPixels * 0.92),
                    ViewGroup.LayoutParams.WRAP_CONTENT);
        }
    }

    void infoDialog(String title, String message) {
        final Dialog d = new Dialog(this);
        LinearLayout l = dialogLayout();
        TextView t = new TextView(this);
        t.setText(title);
        t.setTextSize(18);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(TEXT_PRIMARY);
        l.addView(t);
        TextView m = new TextView(this);
        m.setText(message);
        m.setTextSize(15);
        m.setTextColor(TEXT_SECONDARY);
        m.setPadding(0, dp(8), 0, 0);
        l.addView(m);
        Button ok = primaryButton("Got it");
        ok.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { d.dismiss(); }
        });
        l.addView(ok);
        d.setContentView(l);
        showDialog(d);
    }

    void confirmDialog(String title, String message, final Runnable onConfirm) {
        final Dialog d = new Dialog(this);
        LinearLayout l = dialogLayout();
        TextView t = new TextView(this);
        t.setText(title);
        t.setTextSize(18);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(TEXT_PRIMARY);
        l.addView(t);
        TextView m = new TextView(this);
        m.setText(message);
        m.setTextSize(15);
        m.setTextColor(TEXT_SECONDARY);
        m.setPadding(0, dp(8), 0, 0);
        l.addView(m);
        LinearLayout btns = new LinearLayout(this);
        btns.setOrientation(LinearLayout.HORIZONTAL);
        Button cancel = secondaryButton("Cancel");
        Button del = primaryButton("Delete");
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(0, dp(52), 1);
        bp.topMargin = dp(8);
        bp.rightMargin = dp(8);
        cancel.setLayoutParams(bp);
        LinearLayout.LayoutParams bp2 = new LinearLayout.LayoutParams(0, dp(52), 1);
        bp2.topMargin = dp(8);
        del.setLayoutParams(bp2);
        btns.addView(cancel);
        btns.addView(del);
        l.addView(btns);
        cancel.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { d.dismiss(); }
        });
        del.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                d.dismiss();
                onConfirm.run();
            }
        });
        d.setContentView(l);
        showDialog(d);
    }

    /* ---------- splash (the only place the memorial appears) ---------- */

    void splash() {
        final LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setGravity(Gravity.CENTER_HORIZONTAL);
        l.setBackgroundColor(BG);
        l.setPadding(dp(48), dp(48), dp(48), dp(56));
        l.addView(new View(this), new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        TextView t = new TextView(this);
        t.setText("In memory of my father, Christopher Hale, who tracked trucks in C++ before I ever tracked a deal.");
        t.setTextSize(17);
        t.setTextColor(TEXT_SECONDARY);
        t.setGravity(Gravity.CENTER);
        t.setLineSpacing(0, 1.5f);
        t.setMaxWidth(dp(280));
        l.addView(t, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        TextView mark = new TextView(this);
        mark.setText("APPRAZE");
        mark.setTextSize(15);
        mark.setTypeface(Typeface.DEFAULT_BOLD);
        mark.setTextColor(GOLD);
        mark.setLetterSpacing(0.3f);
        mark.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams mp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        mp.topMargin = dp(24);
        l.addView(mark, mp);
        l.addView(new View(this), new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        final ProgressBar p = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        p.setMax(100);
        p.setProgress(0);
        p.setProgressTintList(ColorStateList.valueOf(GOLD));
        p.setProgressBackgroundTintList(ColorStateList.valueOf(GOLD_BORDER));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(4));
        lp.setMargins(dp(48), dp(24), dp(48), 0);
        l.addView(p, lp);
        setContentView(l);
        final Handler h = new Handler(Looper.getMainLooper());
        final long start = SystemClock.uptimeMillis();
        h.post(new Runnable() {
            public void run() {
                int v = (int) Math.min(100, (SystemClock.uptimeMillis() - start) * 100 / 3500);
                p.setProgress(v);
                if (v >= 100) {
                    l.animate().alpha(0f).setDuration(300)
                            .withEndAction(new Runnable() {
                                public void run() { analyze(); }
                            }).start();
                } else {
                    h.postDelayed(this, 50);
                }
            }
        });
    }

    /* ---------- screen chrome ---------- */

    void base(String title, String help, int activeTab) {
        ScrollView s = new ScrollView(this);
        s.setBackgroundColor(BG);
        body = new LinearLayout(this);
        body.setPadding(dp(24), dp(24), dp(24), dp(24));
        body.setOrientation(LinearLayout.VERTICAL);
        s.addView(body, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        headerRow = new LinearLayout(this);
        headerRow.setOrientation(LinearLayout.HORIZONTAL);
        headerRow.setGravity(Gravity.CENTER_VERTICAL);
        TextView tv = new TextView(this);
        tv.setText(title);
        tv.setTextSize(20);
        tv.setTypeface(Typeface.DEFAULT_BOLD);
        tv.setTextColor(TEXT_PRIMARY);
        headerRow.addView(tv, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        body.addView(headerRow, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        if (help != null) {
            TextView h = new TextView(this);
            h.setText(help);
            h.setTextSize(15);
            h.setTextColor(TEXT_SECONDARY);
            h.setPadding(0, dp(8), 0, dp(16));
            body.addView(h);
        }
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        root.addView(s, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        LinearLayout n = new LinearLayout(this);
        n.setOrientation(LinearLayout.HORIZONTAL);
        n.setBackgroundColor(GLASS);
        final String[] names = {"Analyze", "Inventory", "Cross-list", "Plans", "Settings", "POS"};
        for (int ti = 0; ti < names.length; ti++) {
            final int idx = ti;
            final boolean active = ti == activeTab;
            LinearLayout tab = new LinearLayout(this);
            tab.setOrientation(LinearLayout.VERTICAL);
            tab.setGravity(Gravity.CENTER);
            tab.setMinimumHeight(dp(56));
            View ind = new View(this);
            ind.setBackgroundColor(active ? GOLD : Color.TRANSPARENT);
            tab.addView(ind, new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, dp(2)));
            TextView lab = new TextView(this);
            lab.setText(names[ti]);
            lab.setTextSize(12);
            lab.setTextColor(active ? GOLD : TEXT_MUTED);
            lab.setGravity(Gravity.CENTER);
            lab.setPadding(0, dp(8), 0, dp(8));
            tab.addView(lab, new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
            tab.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { goTab(idx); }
            });
            n.addView(tab, new LinearLayout.LayoutParams(0,
                    LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        }
        n.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            public WindowInsets onApplyWindowInsets(View v, WindowInsets insets) {
                int sb = Build.VERSION.SDK_INT >= 30
                        ? insets.getInsets(WindowInsets.Type.systemBars()).bottom
                        : insets.getSystemWindowInsetBottom();
                v.setPadding(v.getPaddingLeft(), v.getPaddingTop(), v.getPaddingRight(), sb);
                return insets;
            }
        });
        s.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            public WindowInsets onApplyWindowInsets(View v, WindowInsets insets) {
                int st = Build.VERSION.SDK_INT >= 30
                        ? insets.getInsets(WindowInsets.Type.systemBars()).top
                        : insets.getSystemWindowInsetTop();
                body.setPadding(dp(24), dp(24) + st, dp(24), dp(24));
                return insets;
            }
        });
        root.addView(n, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        setContentView(root);
        events.record("screen_view", "screen=" + title);
    }

    void goTab(int idx) {
        if (idx == 0) analyze();
        else if (idx == 1) inventory();
        else if (idx == 2) cross(null);
        else if (idx == 3) plans();
        else if (idx == 4) settings();
        else PosScreen.show(this);
    }

    /* ---------- Analyze ---------- */

    void analyze() {
        base("Analyze a Deal", null, 0);
        LinearLayout c = card(body, false);
        final Field cost = labeled(c, "Purchase / hammer price", "0", decimalInput());
        final Field resale = labeled(c, "Expected resale price", "0", decimalInput());
        final Field fee = labeled(c, "Resale fee %", prefs.getString("def_fee", "13"), decimalInput());
        final Field premium = labeled(c, "Buyer premium %", prefs.getString("def_premium", "18"), decimalInput());
        final LinearLayout slot = new LinearLayout(this);
        slot.setOrientation(LinearLayout.VERTICAL);
        c.addView(slot);
        final TextView teach = new TextView(this);
        teach.setText("Enter what you'd pay and what it'll sell for. We'll do the math.");
        teach.setTextSize(13);
        teach.setTextColor(TEXT_MUTED);
        teach.setPadding(dp(4), dp(12), dp(4), 0);
        c.addView(teach);
        LinearLayout photoRow = new LinearLayout(this);
        photoRow.setOrientation(LinearLayout.HORIZONTAL);
        photoRow.setGravity(Gravity.CENTER_VERTICAL);
        Button take = secondaryButton("Take Photo");
        take.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { PhotoCapture.onTakeClicked(MainActivity.this); }
        });
        Button upload = secondaryButton("Upload Photo");
        upload.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { PhotoCapture.onUploadClicked(MainActivity.this); }
        });
        photoRow.addView(take, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        photoRow.addView(upload, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        c.addView(photoRow);
        photoThumb = new ImageView(this);
        int thumb = dp(96);
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(thumb, thumb);
        tlp.topMargin = dp(8);
        photoThumb.setLayoutParams(tlp);
        photoThumb.setScaleType(ImageView.ScaleType.CENTER_CROP);
        c.addView(photoThumb);
        refreshPhotoThumb();
        Button b = primaryButton("Get Verdict");
        b.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Double co = parseNonNegative(cost);
                Double re = parseNonNegative(resale);
                Double fe = parseNonNegative(fee);
                Double pr = parseNonNegative(premium);
                if (co == null || re == null || fe == null || pr == null) return;
                if (co == 0 && re == 0) {
                    setFieldError(cost, "Enter what you'd pay.");
                    setFieldError(resale, "Enter what it'll sell for.");
                    return;
                }
                if (!usage.tryConsume(Usage.ANALYSES)) {
                    PlanSettings.upgradeDialog(MainActivity.this, usage, Usage.ANALYSES);
                    return;
                }
                double h = prefsDouble("holy_roi", 40);
                Deal d = Deal.calc(co, re, fe, pr, h);
                slot.removeAllViews();
                slot.addView(verdictBanner(d, h));
                teach.setVisibility(View.GONE);
                events.record("deal_analyzed", "cost=" + co + "|resale=" + re + "|verdict=" + d.verdict + "|roi=" + d.roi);
            }
        });
        c.addView(b);
    }

    /* ---------- Inventory ---------- */

    void inventory() {
        base("Inventory", null, 1);
        Button add = secondaryButton("Add Item");
        add.setLayoutParams(new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, dp(44)));
        add.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { itemForm(null); }
        });
        headerRow.addView(add);
        ArrayList<Item> items = inventory.all();
        if (items.isEmpty()) {
            LinearLayout c = card(body, false);
            c.setGravity(Gravity.CENTER_HORIZONTAL);
            TextView t1 = new TextView(this);
            t1.setText("No inventory yet.");
            t1.setTextSize(16);
            t1.setTypeface(Typeface.DEFAULT_BOLD);
            t1.setTextColor(TEXT_PRIMARY);
            t1.setGravity(Gravity.CENTER);
            c.addView(t1);
            TextView t2 = new TextView(this);
            t2.setText("Items you buy live here so you always know what's tied up and what's profit.");
            t2.setTextSize(15);
            t2.setTextColor(TEXT_SECONDARY);
            t2.setGravity(Gravity.CENTER);
            t2.setPadding(0, dp(8), 0, 0);
            c.addView(t2);
            Button f = secondaryButton("Add your first item");
            f.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { itemForm(null); }
            });
            c.addView(f);
        } else {
            for (Item i : items) body.addView(itemCard(i));
        }
    }

    LinearLayout itemCard(final Item i) {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setBackground(glassBg(16, GLASS_BORDER));
        c.setElevation(dp(8));
        c.setPadding(dp(16), dp(16), dp(16), dp(8));
        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        TextView name = new TextView(this);
        name.setText(i.name);
        name.setTextSize(16);
        name.setTypeface(Typeface.DEFAULT_BOLD);
        name.setTextColor(TEXT_PRIMARY);
        top.addView(name, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView margin = new TextView(this);
        margin.setText(marginText(i));
        margin.setTextSize(16);
        margin.setTypeface(Typeface.DEFAULT_BOLD);
        margin.setTextColor(GOLD);
        top.addView(margin);
        c.addView(top);
        LinearLayout bottom = new LinearLayout(this);
        bottom.setOrientation(LinearLayout.HORIZONTAL);
        bottom.setGravity(Gravity.CENTER_VERTICAL);
        TextView info = new TextView(this);
        info.setText("Cost " + money(i.cost) + " \u2022 List " + money(i.price));
        info.setTextSize(15);
        info.setTextColor(TEXT_SECONDARY);
        info.setPadding(0, dp(4), 0, 0);
        bottom.addView(info, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView edit = textButton("Edit", GOLD);
        edit.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { itemForm(i); }
        });
        bottom.addView(edit);
        c.addView(bottom);
        c.setClickable(true);
        c.setFocusable(true);
        c.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { cross(i); }
        });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(12);
        c.setLayoutParams(lp);
        return c;
    }

    String marginText(Item i) {
        if (i.cost > 0) return String.format(Locale.US, "%.1f%%", (i.price - i.cost) / i.cost * 100);
        if (i.price > 0) return "\u221E";
        return "\u2014";
    }

    void itemForm(final Item it) {
        base(it == null ? "Add Item" : "Edit Item", null, 1);
        LinearLayout c = card(body, false);
        final Field name = labeled(c, "Item name", it == null ? "" : it.name, InputType.TYPE_CLASS_TEXT);
        final Field cost = labeled(c, "Cost basis", it == null ? "0" : String.valueOf(it.cost), decimalInput());
        final Field price = labeled(c, "List price", it == null ? "0" : String.valueOf(it.price), decimalInput());
        Button save = primaryButton(it == null ? "Save Item" : "Save Changes");
        save.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                String n = name.input.getText().toString().trim();
                if (n.isEmpty()) { setFieldError(name, "Give it a name."); return; }
                setFieldError(name, null);
                Double co = parseNonNegative(cost);
                Double pr = parseNonNegative(price);
                if (co == null || pr == null) return;
                if (it == null) {
                    inventory.add(n, co, pr);
                    events.record("item_added", "name=" + n);
                    Toast.makeText(MainActivity.this, "Item saved", Toast.LENGTH_SHORT).show();
                } else {
                    inventory.update(it.id, n, co, pr);
                    events.record("item_updated", "name=" + n);
                    Toast.makeText(MainActivity.this, "Item updated", Toast.LENGTH_SHORT).show();
                }
                inventory();
            }
        });
        c.addView(save);
        Button cancel = secondaryButton("Cancel");
        cancel.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { inventory(); }
        });
        c.addView(cancel);
        if (it != null) {
            TextView del = textButton("Delete item", PASS);
            del.setGravity(Gravity.CENTER);
            del.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    confirmDialog("Delete this item?",
                            "\u201C" + it.name + "\u201D leaves your inventory. This can't be undone.",
                            new Runnable() {
                                public void run() {
                                    inventory.delete(it.id);
                                    events.record("item_deleted", "name=" + it.name);
                                    inventory();
                                }
                            });
                }
            });
            c.addView(del);
        }
    }

    /* ---------- Cross-list ---------- */

    void cross(final Item i) {
        base("Cross-List",
                "Push this item to eBay Sandbox. Production marketplaces stay labeled Coming Soon until publishing is proven.", 2);
        LinearLayout c = card(body, false);
        final Field title = labeled(c, "Listing title", i == null ? "" : i.name, InputType.TYPE_CLASS_TEXT);
        final Field price = labeled(c, "Price", i == null ? "0" : String.valueOf(i.price), decimalInput());
        c.addView(sectionLabel("Linked inventory item"));
        TextView lv = new TextView(this);
        lv.setText(i == null ? "None \u2014 add one from Inventory." : i.name + " \u2022 " + money(i.cost));
        lv.setTextSize(15);
        lv.setTextColor(TEXT_SECONDARY);
        lv.setPadding(dp(4), 0, dp(4), dp(4));
        c.addView(lv);
        final LinearLayout slot = new LinearLayout(this);
        slot.setOrientation(LinearLayout.VERTICAL);
        c.addView(slot);
        Button p = primaryButton("Publish to Sandbox");
        p.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                String t = title.input.getText().toString().trim();
                if (t.isEmpty()) { setFieldError(title, "Give the listing a title."); return; }
                setFieldError(title, null);
                Double pr = parseNonNegative(price);
                if (pr == null) return;
                if (!usage.tryConsume(Usage.PUBLISHES)) {
                    PlanSettings.upgradeDialog(MainActivity.this, usage, Usage.PUBLISHES);
                    return;
                }
                slot.removeAllViews();
                slot.addView(verdictBanner(PASS, "Not listed",
                        "Sandbox publish needs a user token, location, and policies."));
                TextView fix = new TextView(MainActivity.this);
                fix.setText("To fix: follow docs/EBAY_SELL_SETUP.md to configure ebay_sell.py, then publish again.");
                fix.setTextSize(13);
                fix.setTextColor(TEXT_SECONDARY);
                fix.setPadding(dp(4), dp(8), dp(4), 0);
                slot.addView(fix);
                events.record("ebay_publish", "result=configuration_needed|title=" + t + "|price=" + pr);
            }
        });
        c.addView(p);
        TextView mh = sectionLabel("Marketplaces");
        LinearLayout.LayoutParams mhp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        mhp.topMargin = dp(20);
        body.addView(mh, mhp);
        for (String m : new String[]{"eBay Production", "Mercari", "Poshmark", "Depop"}) {
            body.addView(marketRow(m));
        }
    }

    LinearLayout marketRow(final String name) {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setBackground(glassBg(12, GLASS_BORDER));
        r.setPadding(dp(16), dp(12), dp(16), dp(12));
        TextView n = new TextView(this);
        n.setText(name);
        n.setTextSize(15);
        n.setTextColor(TEXT_MUTED);
        r.addView(n, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView tag = new TextView(this);
        tag.setText("Coming Soon");
        tag.setTextSize(12);
        tag.setTextColor(TEXT_MUTED);
        GradientDrawable td = new GradientDrawable();
        td.setShape(GradientDrawable.RECTANGLE);
        td.setCornerRadius(dp(8));
        td.setStroke(dp(1), TEXT_MUTED);
        tag.setBackground(td);
        tag.setPadding(dp(10), dp(4), dp(10), dp(4));
        r.addView(tag);
        r.setClickable(true);
        r.setFocusable(true);
        r.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                infoDialog(name + " is coming soon.",
                        "Production marketplaces stay off until Sandbox publishing is proven. eBay Sandbox is the only live channel right now.");
            }
        });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(8);
        r.setLayoutParams(lp);
        return r;
    }

    /* ---------- Plans ---------- */

    void plans() {
        base("Choose a plan", "Subscriptions unlock monthly analysis limits. Free requires verified email.", 3);
        String[][] ps = {
                {"Free", "$0", "5 analyses / month"},
                {"Starter", "$25", "50 analyses / month"},
                {"Pro", "$50", "250 analyses / month \u00B7 Most popular"},
                {"Business", "$100", "1,000 analyses / month \u00B7 3 seats"},
                {"Enterprise", "$200", "5,000 analyses / month \u00B7 10 seats"}};
        for (final String[] p : ps) {
            LinearLayout c = card(body, false);
            LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) c.getLayoutParams();
            lp.topMargin = dp(12);
            c.setLayoutParams(lp);
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            TextView n = new TextView(this);
            n.setText(p[0]);
            n.setTextSize(16);
            n.setTypeface(Typeface.DEFAULT_BOLD);
            n.setTextColor(TEXT_PRIMARY);
            row.addView(n, new LinearLayout.LayoutParams(0,
                    LinearLayout.LayoutParams.WRAP_CONTENT, 1));
            TextView pr = new TextView(this);
            pr.setText(p[1]);
            pr.setTextSize(16);
            pr.setTypeface(Typeface.DEFAULT_BOLD);
            pr.setTextColor(GOLD);
            row.addView(pr);
            c.addView(row);
            TextView d = new TextView(this);
            d.setText(p[2]);
            d.setTextSize(15);
            d.setTextColor(TEXT_SECONDARY);
            d.setPadding(0, dp(4), 0, 0);
            c.addView(d);
            Button s = secondaryButton("Select " + p[0]);
            s.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    events.record("plan_selected", "plan=" + p[0]);
                    infoDialog("Billing isn't connected yet.",
                            "Register this subscription in Play Console to enable test purchases.");
                }
            });
            c.addView(s);
        }
    }

    /* ---------- Settings ---------- */

    void settings() {
        base("Settings", null, 4);
        PlanSettings.addPlanGroup(this);
        appearanceGroup();
        settingsGroup("Holy Grail", new String[][]{
                {"holy_roi", "Minimum ROI %", "40", "%"},
                {"holy_profit", "Minimum profit $", "15", "$"},
                {"holy_max", "Maximum buy cost $", "100", "$"}});
        settingsGroup("Defaults", new String[][]{
                {"def_fee", "Default resale fee %", "13", "%"},
                {"def_premium", "Default buyer premium %", "18", "%"}});
        aboutGroup();
        body.addView(caption("Privacy: Appraze stores deal inputs, verdicts, screen views, and publishing outcomes on this device as structured usage events. This build does not share ad data. Usage-data collection is disclosed here."));
    }

    LinearLayout settingsGroup(String label, String[][] rows) {
        LinearLayout c = card(body, false);
        LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) c.getLayoutParams();
        lp.topMargin = dp(12);
        c.setLayoutParams(lp);
        c.addView(sectionLabel(label));
        for (final String[] r : rows) {
            final String key = r[0];
            final String name = r[1];
            final String def = r[2];
            final String kind = r[3];
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(4), dp(10), dp(4), dp(10));
            TextView l = new TextView(this);
            l.setText(name);
            l.setTextSize(15);
            l.setTextColor(TEXT_SECONDARY);
            row.addView(l, new LinearLayout.LayoutParams(0,
                    LinearLayout.LayoutParams.WRAP_CONTENT, 1));
            TextView v = new TextView(this);
            v.setText(displaySetting(key, def, kind));
            v.setTextSize(16);
            v.setTypeface(Typeface.DEFAULT_BOLD);
            v.setTextColor(GOLD);
            row.addView(v);
            row.setClickable(true);
            row.setFocusable(true);
            row.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { editSetting(key, name, prefs.getString(key, def)); }
            });
            c.addView(row);
        }
        return c;
    }

    LinearLayout appearanceGroup() {
        LinearLayout c = card(body, false);
        LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) c.getLayoutParams();
        lp.topMargin = dp(12);
        c.setLayoutParams(lp);
        c.addView(sectionLabel("Appearance"));
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(4), dp(6), dp(4), dp(6));
        TextView l = new TextView(this);
        l.setText("Dark mode");
        l.setTextSize(15);
        l.setTextColor(TEXT_SECONDARY);
        row.addView(l, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        Switch sw = new Switch(this);
        sw.setChecked(darkTheme);
        sw.setContentDescription("Dark mode");
        int[][] states = {new int[]{android.R.attr.state_checked}, new int[]{}};
        sw.setThumbTintList(new ColorStateList(states, new int[]{GOLD, darkTheme ? TEXT_MUTED : GLASS}));
        sw.setTrackTintList(new ColorStateList(states, new int[]{withAlpha(GOLD, 0.5f), withAlpha(TEXT_MUTED, 0.5f)}));
        sw.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            public void onCheckedChanged(CompoundButton b, boolean on) {
                setDarkTheme(on);
                settings();
            }
        });
        row.addView(sw);
        c.addView(row);
        c.addView(caption("Light is the default. Dark mode is the black-and-gold glass look."));
        return c;
    }

    String displaySetting(String key, String def, String kind) {
        String raw = prefs.getString(key, def);
        try {
            double x = Double.parseDouble(raw);
            if ("%".equals(kind)) {
                String r = x == Math.rint(x) ? String.valueOf((long) x) : String.valueOf(x);
                return r + "%";
            }
            return money(x);
        } catch (Exception e) {
            return raw;
        }
    }

    void editSetting(final String key, final String label, String current) {
        final Dialog d = new Dialog(this);
        LinearLayout l = dialogLayout();
        TextView t = new TextView(this);
        t.setText(label);
        t.setTextSize(18);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(TEXT_PRIMARY);
        t.setPadding(0, 0, 0, dp(4));
        l.addView(t);
        final Field f = labeled(l, label, current == null ? "" : current, decimalInput());
        LinearLayout btns = new LinearLayout(this);
        btns.setOrientation(LinearLayout.HORIZONTAL);
        Button cancel = secondaryButton("Cancel");
        Button save = primaryButton("Save");
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(0, dp(52), 1);
        bp.topMargin = dp(8);
        bp.rightMargin = dp(8);
        cancel.setLayoutParams(bp);
        LinearLayout.LayoutParams bp2 = new LinearLayout.LayoutParams(0, dp(52), 1);
        bp2.topMargin = dp(8);
        save.setLayoutParams(bp2);
        btns.addView(cancel);
        btns.addView(save);
        l.addView(btns);
        cancel.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) { d.dismiss(); }
        });
        save.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Double x = parseNonNegative(f);
                if (x == null) return;
                prefs.edit().putString(key, f.input.getText().toString().trim()).apply();
                events.record("setting_saved", "key=" + key);
                d.dismiss();
                settings();
            }
        });
        d.setContentView(l);
        showDialog(d);
    }

    LinearLayout aboutGroup() {
        LinearLayout c = card(body, false);
        LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) c.getLayoutParams();
        lp.topMargin = dp(12);
        c.setLayoutParams(lp);
        c.addView(sectionLabel("About"));
        c.addView(aboutRow("Appraze version", APP_VERSION, false));
        TextView tag = new TextView(this);
        tag.setText("Complete Resale Business Suite");
        tag.setTextSize(15);
        tag.setTextColor(TEXT_SECONDARY);
        tag.setPadding(dp(4), dp(10), dp(4), dp(10));
        c.addView(tag);
        LinearLayout r = aboutRow("Support", SUPPORT_EMAIL, true);
        r.setClickable(true);
        r.setFocusable(true);
        r.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Intent i = new Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:" + SUPPORT_EMAIL));
                startActivity(Intent.createChooser(i, "Contact support"));
            }
        });
        c.addView(r);
        return c;
    }

    LinearLayout aboutRow(String label, String value, boolean goldValue) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(4), dp(10), dp(4), dp(10));
        TextView l = new TextView(this);
        l.setText(label);
        l.setTextSize(15);
        l.setTextColor(TEXT_SECONDARY);
        row.addView(l, new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(16);
        v.setTypeface(Typeface.DEFAULT_BOLD);
        v.setTextColor(goldValue ? GOLD : TEXT_PRIMARY);
        row.addView(v);
        return row;
    }
}

class Deal {
    double cost, net, profit, roi;
    String verdict;
    static Deal calc(double cost, double resale, double fee, double premium, double buyBar) {
        Deal d = new Deal();
        d.cost = cost * (1 + premium / 100);
        d.net = resale * (1 - fee / 100);
        d.profit = d.net - d.cost;
        d.roi = d.cost > 0 ? d.profit / d.cost * 100 : d.profit > 0 ? Double.POSITIVE_INFINITY : 0;
        d.verdict = d.roi >= buyBar ? "BUY" : d.roi >= 5 ? "REVIEW" : "PASS";
        return d;
    }
}

class Item {
    long id;
    String name;
    double cost, price;
    Item(long i, String n, double c, double p) { id = i; name = n; cost = c; price = p; }
}

class EventStore extends SQLiteOpenHelper {
    EventStore(Context x) { super(x, "events.db", null, 1); }
    public void onCreate(SQLiteDatabase d) { d.execSQL("CREATE TABLE events(type TEXT,payload TEXT,created_at INTEGER)"); }
    public void onUpgrade(SQLiteDatabase d, int a, int b) { }
    void record(String t, String p) {
        ContentValues v = new ContentValues();
        v.put("type", t);
        v.put("payload", p);
        v.put("created_at", System.currentTimeMillis());
        getWritableDatabase().insert("events", null, v);
    }
}

class InventoryStore extends SQLiteOpenHelper {
    InventoryStore(Context x) { super(x, "inventory.db", null, 1); }
    public void onCreate(SQLiteDatabase d) { d.execSQL("CREATE TABLE inventory(name TEXT,cost REAL,price REAL)"); }
    public void onUpgrade(SQLiteDatabase d, int a, int b) { }
    void add(String n, double co, double pr) {
        ContentValues v = new ContentValues();
        v.put("name", n); v.put("cost", co); v.put("price", pr);
        getWritableDatabase().insert("inventory", null, v);
    }
    void update(long id, String n, double co, double pr) {
        ContentValues v = new ContentValues();
        v.put("name", n); v.put("cost", co); v.put("price", pr);
        getWritableDatabase().update("inventory", v, "rowid=?", new String[]{String.valueOf(id)});
    }
    void delete(long id) {
        getWritableDatabase().delete("inventory", "rowid=?", new String[]{String.valueOf(id)});
    }
    ArrayList<Item> all() {
        ArrayList<Item> x = new ArrayList<>();
        Cursor c = getReadableDatabase().rawQuery("SELECT rowid,name,cost,price FROM inventory ORDER BY rowid DESC", null);
        while (c.moveToNext()) x.add(new Item(c.getLong(0), c.getString(1), c.getDouble(2), c.getDouble(3)));
        c.close();
        return x;
    }
}
