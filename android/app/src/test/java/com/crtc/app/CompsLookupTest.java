package com.crtc.app;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class CompsLookupTest {

    @Test
    public void provenanceOnlyWhenResaleIsTheCompsValue() {
        CompsLookup.reset();
        assertNull(CompsLookup.provenance(40.0));
        CompsLookup.lastSuggested = 40.0;
        CompsLookup.lastConfidence = "low";
        assertTrue(CompsLookup.provenance(40.0).contains("verify before you buy"));
        assertNull("user overwrote resale", CompsLookup.provenance(55.0));
        CompsLookup.lastConfidence = "high";
        assertEquals("Resale from eBay comps · High confidence.", CompsLookup.provenance(40.0));
        CompsLookup.reset();
    }

    @Test
    public void confidenceLabels() {
        assertEquals("Medium confidence", CompsLookup.confidenceLabel("medium"));
        assertEquals("Low confidence", CompsLookup.confidenceLabel(""));
        assertEquals("Low confidence", CompsLookup.confidenceLabel(null));
    }

    @Test
    public void parsesServerTimestamp() {
        assertEquals(1790426700000L, CompsLookup.parseIsoMs("2026-09-26T12:45:00+00:00"));
        long now = System.currentTimeMillis();
        assertTrue(CompsLookup.parseIsoMs("garbage") >= now);
    }
}
