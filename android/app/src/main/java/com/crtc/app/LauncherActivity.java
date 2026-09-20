package com.crtc.app;

import android.net.Uri;
import android.os.Bundle;



/**
 * CRTC Trusted Web Activity entry point.
 * The production URL is intentionally configured through the Android Browser Helper
 * metadata so the web app remains unchanged.
 */
public final class LauncherActivity extends com.google.androidbrowserhelper.trusted.LauncherActivity {
    @Override
    protected Uri getLaunchingUrl() {
        return Uri.parse("https://appraze-ai-dkc8kpa7pbtzhgwpgztqyh.streamlit.app/");
    }
}
