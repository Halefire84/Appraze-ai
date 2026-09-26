# Android Build Log

**Architecture decision (2026-09-25):** This build is a native Android application using platform Java Views rather than a Streamlit WebView/TWA or Flutter. Native Android controls give the smallest dependable closed-testing footprint and direct local storage/event capture; the former TWA has been completely removed. Kotlin was preferred, but the environment has no cached Kotlin Gradle plugin and cannot resolve it, so Java was used to keep a genuinely buildable native project rather than shipping an unbuildable Kotlin skeleton.

## 2026-09-25 — Current checkpoint
- Replaced the Trusted Web Activity entry point with a native screen flow: deal analyzer, inventory, eBay Sandbox draft guidance, plans, and settings/privacy.
- Ported the core deal calculation from `finance.py`: buyer premium is added to purchase cost, resale fee is removed from expected resale, and the five real ROI verdict bands are used.
- Added editable Holy Grail input settings, a local SQLite structured event store (deal inputs/verdicts and screen views), and a local SQLite inventory store.
- Added all five final pricing tiers to the native Plans screen and the memorial dedication word-for-word on the analyzer.
- Kept permissions to Internet only, and disclosed the on-device usage-event collection in the Privacy screen.
- **Not yet complete:** Google Play Billing client integration, Firebase Crashlytics configuration, verified-email/free-limit enforcement, and the authenticated eBay Sandbox HTTP publishing sequence still need credentials/backend and the relevant SDK dependencies. The screen deliberately does not claim that an unconfigured publish succeeded.
- **Build status:** Gradle configuration starts successfully, but this container has no Android SDK (`ANDROID_HOME` / `sdk.dir` is absent), so APK/AAB compilation cannot be completed here. On a machine with SDK Platform 36 installed, run `cd android && gradle :app:assembleDebug :app:bundleRelease`.

## 2026-09-25 — Native foundation
- Replaced the existing Trusted Web Activity shell with a native Android application foundation on the `android` branch.
