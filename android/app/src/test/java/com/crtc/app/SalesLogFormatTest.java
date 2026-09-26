package com.crtc.app;

import static org.junit.Assert.assertEquals;

import java.util.Locale;
import java.util.TimeZone;
import org.junit.Test;

public class SalesLogFormatTest {

    @Test
    public void formatsDateAndTimeInGivenZone() {
        long ms = 1790426700000L; // 2026-09-26T12:45:00Z
        assertEquals("Sat, Sep 26, 2026 · 8:45 AM",
                SalesLog.formatWhen(ms, TimeZone.getTimeZone("America/New_York"), Locale.US));
        assertEquals("Sat, Sep 26, 2026 · 12:45 PM",
                SalesLog.formatWhen(ms, TimeZone.getTimeZone("UTC"), Locale.US));
    }

    @Test
    public void labels() {
        assertEquals("Tap to Pay", SalesLog.methodLabel(SalesLog.METHOD_TAP));
        assertEquals("Payment link", SalesLog.methodLabel(SalesLog.METHOD_LINK));
        assertEquals("Paid", SalesLog.statusLabel(SalesLog.PAID));
        assertEquals("Pending", SalesLog.statusLabel(SalesLog.PENDING));
        assertEquals("Pending", SalesLog.statusLabel(null));
    }
}
