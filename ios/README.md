# CRTC iOS App Store Deployment

## Architecture
CRTC web app (Streamlit HTTPS) -> thin native iOS WebKit shell -> App Store.

Production web URL:
https://appraze-ai-dkc8kpa7pbtzhgwpgztqyh.streamlit.app/

This deployment layer is intentionally a thin wrapper. The existing Streamlit application remains the source of truth and its web behavior is unchanged.

## Requirements
- macOS with current Xcode and iOS SDK
- Apple Developer Program membership
- App Store Connect access
- Production HTTPS URL (above)
- Bundle identifier reserved in Apple Developer account
- App icons, screenshots, privacy details, and support/privacy URLs for App Store Connect

## Build
On a Mac, open the generated Xcode project/workspace and select an iOS Simulator or physical device.

Before release:
1. Run Debug on simulator.
2. Run on a physical iPhone.
3. Test launch, navigation, login/session behavior, forms, uploads/downloads if used, external links, offline/network failure, and rotation.
4. Archive a Release build.
5. Validate the archive in Xcode Organizer.
6. Upload to App Store Connect.
7. Complete TestFlight testing.
8. Submit for App Review.

## Important App Store consideration
Apple may reject an app that is only a minimally wrapped website if it does not provide sufficient app-like functionality or value. Treat the WebKit shell as the initial deployment experiment, not a guarantee of approval. Keep the web app responsive and functional on iOS.

## Out of scope
- Native rewrite of CRTC
- In-app subscriptions/billing
- Changes to existing Streamlit behavior

## Security
Do not hard-code credentials, API keys, signing certificates, or private provisioning data in the repository.
