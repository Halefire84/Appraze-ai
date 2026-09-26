# Appraze native Android app

This is a **native Kotlin Android application**, not a WebView or Trusted Web Activity. It contains native deal analysis, local inventory, eBay Sandbox draft/publish flow, Play Billing hooks, structured local usage events, and privacy/settings controls.

## Build

Requirements: JDK 17 and Android SDK Platform 36. From this directory:

```bash
./gradlew assembleDebug
./gradlew bundleRelease
```

The release build is debuggably signed for closed-testing automation. Before public Play production, configure a separate upload/release signing key in CI and add `google-services.json` from the Appraze Firebase project to `app/` (it is intentionally not committed).

## Play Console configuration required

Create these subscription IDs exactly: `appraze_starter_monthly`, `appraze_pro_monthly`, `appraze_business_monthly`, and `appraze_enterprise_monthly`, at $25, $50, $100, and $200 per month. Free is enforced locally as 5 analyses/month after email verification is connected to the app backend. The app never calls an eBay production endpoint; Sandbox policy/location and a user OAuth token are required before publishing.
