# CRTC Windows Store deployment

CRTC remains the existing HTTPS Streamlit web application. The Windows Store package should be a thin WebView2-based Windows App SDK shell; no web application rewrite is required.

## Planned package
- Windows App SDK / WinUI 3 shell
- WebView2 control pointing at the production HTTPS CRTC URL
- MSIX package for Microsoft Store submission
- Store identity/signing handled by Partner Center / Store association

## Prerequisites
- Windows development machine
- Visual Studio 2022 with Windows App SDK/WinUI 3 and MSIX tooling
- WebView2
- Production HTTPS CRTC URL
- Microsoft Partner Center developer account
- Store listing assets and privacy policy

## Validation
Build Debug and Release on Windows, launch on a clean Windows machine, test authentication/navigation/network failure behavior, generate and validate MSIX, then associate with Microsoft Store.

Billing is out of scope.