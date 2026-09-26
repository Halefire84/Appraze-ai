package com.crtc.app;

import android.app.Application;
import com.stripe.stripeterminal.TerminalApplicationDelegate;
import com.stripe.stripeterminal.taptopay.TapToPay;

/** Required by Stripe Terminal: Tap to Pay runs in its own :stripetaptopay process. */
public final class ApprazeApp extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        if (TapToPay.isInTapToPayProcess()) return;
        TerminalApplicationDelegate.onCreate(this);
    }
}
