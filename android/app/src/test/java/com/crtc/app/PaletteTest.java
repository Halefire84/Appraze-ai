package com.crtc.app;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertSame;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** Readability guards for both themes (WCAG AA: 4.5:1 body text, 3:1 large/bold UI text). */
public class PaletteTest {

    private static final Palette[] BOTH = {Palette.LIGHT, Palette.DARK};

    private static int opaqueOver(int argb, int bg) {
        double a = ((argb >>> 24) & 0xFF) / 255.0;
        int r = (int) Math.round(((argb >> 16) & 0xFF) * a + ((bg >> 16) & 0xFF) * (1 - a));
        int g = (int) Math.round(((argb >> 8) & 0xFF) * a + ((bg >> 8) & 0xFF) * (1 - a));
        int b = (int) Math.round((argb & 0xFF) * a + (bg & 0xFF) * (1 - a));
        return 0xFF000000 | (r << 16) | (g << 8) | b;
    }

    private static int card(Palette p) {
        return opaqueOver(p.glass, p.bg);
    }

    private static void assertContrast(String what, int fg, int bg, double min) {
        double c = Palette.contrast(fg, bg);
        assertTrue(what + " contrast " + c + " < " + min, c >= min);
    }

    @Test
    public void defaultIsLight() {
        assertSame(Palette.LIGHT, Palette.forDark(false));
        assertSame(Palette.DARK, Palette.forDark(true));
        assertFalse(Palette.LIGHT.dark);
        assertTrue(Palette.DARK.dark);
        assertTrue("light bg must be bright", Palette.luminance(Palette.LIGHT.bg) > 0.8);
    }

    @Test
    public void bodyTextReadableOnCardsAndBackground() {
        for (Palette p : BOTH) {
            String n = p.dark ? "dark " : "light ";
            assertContrast(n + "primary/bg", p.textPrimary, p.bg, 4.5);
            assertContrast(n + "primary/card", p.textPrimary, card(p), 4.5);
            assertContrast(n + "secondary/card", p.textSecondary, card(p), 4.5);
        }
    }

    @Test
    public void accentAndVerdictColorsReadable() {
        for (Palette p : BOTH) {
            String n = p.dark ? "dark " : "light ";
            assertContrast(n + "gold/card", p.gold, card(p), 3.0);
            assertContrast(n + "buy/card", p.buy, card(p), 3.0);
            assertContrast(n + "pass/card", p.pass, card(p), 3.0);
            assertContrast(n + "review/card", p.review, card(p), 3.0);
            assertContrast(n + "on-gold button text", p.onGold, p.gold, 4.5);
        }
    }

    @Test
    public void lightMutedTextStillReadable() {
        assertContrast("light muted/card", Palette.LIGHT.textMuted, card(Palette.LIGHT), 4.5);
    }

    @Test
    public void contrastMath() {
        assertEquals(21.0, Palette.contrast(0xFF000000, 0xFFFFFFFF), 0.01);
        assertEquals(1.0, Palette.contrast(0xFF777777, 0xFF777777), 0.0001);
    }
}
