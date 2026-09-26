package com.crtc.app;

/**
 * The two Appraze color themes. Every color in the UI comes from the active
 * Palette via MainActivity.applyTheme() — no screen hardcodes a color.
 *
 * LIGHT is the default (Material You look: bright tonal surfaces, dark text,
 * deep-gold accent so gold text stays readable on white).
 * DARK is the v5 black + gold glass design, kept as a Settings toggle.
 */
final class Palette {

    static final String PREF_KEY = "theme_dark";

    final boolean dark;
    final int bg;
    final int glass;
    final int glassBorder;
    final int goldBorder;
    /** Accent: section labels, stat values, active tab, primary button fill. */
    final int gold;
    /** Primary button pressed state. */
    final int goldLight;
    /** Primary button disabled state. */
    final int goldDeep;
    /** Text drawn on top of a gold fill. */
    final int onGold;
    final int textPrimary;
    final int textSecondary;
    final int textMuted;
    final int buy;
    final int pass;
    final int review;

    private Palette(boolean dark, int bg, int glass, int glassBorder, int goldBorder,
                    int gold, int goldLight, int goldDeep, int onGold,
                    int textPrimary, int textSecondary, int textMuted,
                    int buy, int pass, int review) {
        this.dark = dark;
        this.bg = bg;
        this.glass = glass;
        this.glassBorder = glassBorder;
        this.goldBorder = goldBorder;
        this.gold = gold;
        this.goldLight = goldLight;
        this.goldDeep = goldDeep;
        this.onGold = onGold;
        this.textPrimary = textPrimary;
        this.textSecondary = textSecondary;
        this.textMuted = textMuted;
        this.buy = buy;
        this.pass = pass;
        this.review = review;
    }

    static final Palette LIGHT = new Palette(false,
            0xFFFAF8F3,   // bg: warm off-white surface
            0xFFFFFFFF,   // glass: card surface
            0x1F000000,   // glassBorder
            0x668C6D1F,   // goldBorder
            0xFF8C6D1F,   // gold: deep gold, readable on white
            0xFF6F5716,   // goldLight: pressed (darker in light mode)
            0xFFE3D7B4,   // goldDeep: disabled fill
            0xFFFFFFFF,   // onGold
            0xFF1C1B1F,   // textPrimary
            0xFF49454F,   // textSecondary
            0xFF6B6770,   // textMuted
            0xFF15803D,   // buy
            0xFFB91C1C,   // pass
            0xFFB45309);  // review

    static final Palette DARK = new Palette(true,
            0xFF0A0A0D,
            0xCC16161C,
            0x14FFFFFF,
            0x33D4AF37,
            0xFFD4AF37,
            0xFFF0D878,
            0xFF8C6E1F,
            0xFF0A0A0D,
            0xFFF5F2E8,
            0xFFA8A29E,
            0xFF6E6A63,
            0xFF22C55E,
            0xFFEF4444,
            0xFFF59E0B);

    static Palette forDark(boolean dark) {
        return dark ? DARK : LIGHT;
    }

    /** WCAG relative luminance of an opaque ARGB color. */
    static double luminance(int argb) {
        double r = channel((argb >> 16) & 0xFF);
        double g = channel((argb >> 8) & 0xFF);
        double b = channel(argb & 0xFF);
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    }

    private static double channel(int c) {
        double s = c / 255.0;
        return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    }

    /** WCAG contrast ratio between two opaque colors (1.0 .. 21.0). */
    static double contrast(int a, int b) {
        double la = luminance(a);
        double lb = luminance(b);
        return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
    }
}
