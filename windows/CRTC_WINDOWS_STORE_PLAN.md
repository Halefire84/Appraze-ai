# CRTC Windows Store Launch Plan

## Status — 2026-09-20
- [x] Deployment strategy documented: Windows App SDK/WinUI 3 + WebView2 wrapper.
- [x] Existing web app remains unchanged.
- [ ] Create Windows App SDK project on Windows.
- [ ] Set permanent package identity.
- [ ] Configure production HTTPS URL.
- [ ] Build Debug/Release.
- [ ] Run Windows smoke tests.
- [ ] Generate/validate MSIX.
- [ ] Create/verify Microsoft Partner Center account.
- [ ] Complete Store listing/privacy information.
- [ ] Upload and complete certification.
- [ ] Publish.

## Architecture
Use a thin WebView2 shell rather than rewriting CRTC natively.

## Testing
The current environment is not Windows, so MSIX/build certification has NOT been claimed. Windows validation must run on the Windows development machine or CI.

## Monetization
No Microsoft Store billing in this pass. CRTC remains free during beta.
