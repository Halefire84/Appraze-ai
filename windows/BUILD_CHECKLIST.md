# CRTC Windows Store Build Checklist

1. Install Visual Studio 2022 with Windows App SDK/WinUI 3 and MSIX tooling.
2. Create the Windows project under windows/ with a permanent package identity.
3. Add WebView2 and point it to the production HTTPS CRTC origin.
4. Keep secrets out of source control.
5. Build Debug and Release.
6. Test login, core search, tester limits, errors, navigation, external links and network failures.
7. Generate and validate MSIX.
8. Verify package identity/signing.
9. Create/verify Microsoft Partner Center developer account.
10. Complete Store listing, screenshots, description and privacy information.
11. Upload to Partner Center and follow certification feedback.
12. Publish only after certification.
