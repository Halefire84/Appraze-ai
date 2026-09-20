# CRTC Android / Google Play

This directory contains the Android Trusted Web Activity (TWA) deployment shell for the existing CRTC Streamlit web application. It does not modify the web application.

## Before first build

1. Replace `REPLACE_WITH_CRTC_PRODUCTION_HOST` in `app/src/main/java/com/crtc/app/LauncherActivity.java` with the final HTTPS CRTC origin.
2. Publish `https://<host>/.well-known/assetlinks.json` containing this app's package name and release signing certificate SHA-256 fingerprint.
3. Keep the application ID `com.crtc.app` unless a deliberate package-ID change is made before the first Play upload.
4. Install Android SDK Platform 36 and Build Tools through Android Studio/SDK Manager.
5. Install a compatible JDK required by the selected Android Gradle Plugin.

## Release signing

Never commit a keystore or passwords. For local release builds, supply the signing properties through `~/.gradle/gradle.properties` or the environment. CI should use encrypted GitHub Actions secrets.

Expected properties:

- `RELEASE_STORE_FILE`
- `RELEASE_STORE_PASSWORD`
- `RELEASE_KEY_ALIAS`
- `RELEASE_KEY_PASSWORD`

A signed release is only valid after the real production hostname and certificate fingerprint are configured.

## Build

From `android/` with Gradle available:

```bash
gradle :app:assembleDebug
gradle :app:bundleRelease
```

If signing properties are present, `bundleRelease` produces the signed Play-uploadable AAB. Without them, the project is intentionally not silently signed with a development key.

## Digital Asset Links

The production website must serve an `assetlinks.json` that authorizes `com.crtc.app` using the SHA-256 fingerprint of the certificate that signs the Play release. Keep the fingerprint in deployment secrets/documentation, not in source control unless intentionally public.

## Scope boundary

- No Play Billing implementation in this phase.
- No native rewrite of the Streamlit app.
- No changes to the existing web beta behavior.
- Store listing, Data Safety, privacy policy, closed testing, and production-access work remain Play Console tasks.
