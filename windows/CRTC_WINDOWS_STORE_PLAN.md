# Appraze Windows Store Launch Plan

## Recommended fast/free path — added 2026-09-21

Before building the native WinUI 3 project below, try
**[PWABuilder.com](https://www.pwabuilder.com/)** (free, Microsoft-run,
needs no Windows dev machine): paste in the production URL
(`https://appraze-ai-dkc8kpa7pbtzhgwpgztqyh.streamlit.app/`), it scores
the site as a PWA and generates a store-ready **MSIX** package directly
from `static/manifest.json` — no native project, no local Windows/Visual
Studio setup. This is very likely enough to satisfy the Microsoft Store's
technical requirements for a straightforward app like this one. Only fall
back to the native WinUI 3 project below if PWABuilder's package fails
Store certification or you need native capabilities it can't provide.

Either path still needs a Microsoft Partner Center developer account
(currently a one-time individual registration fee — check the exact
current amount at
[partner.microsoft.com](https://partner.microsoft.com/dashboard/registration)
before paying, pricing changes).

## Status — 2026-09-20
- [x] Deployment strategy documented: Windows App SDK/WinUI 3 + WebView2 wrapper (fallback path).
- [x] Existing web app remains unchanged.
- [ ] Try PWABuilder.com MSIX generation first (see above).
- [ ] Create Windows App SDK project on Windows (only if PWABuilder isn't sufficient).
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
Use a thin WebView2 shell rather than rewriting Appraze natively — or
PWABuilder's generated wrapper, which does the same thing without a
hand-written project.

## Testing
The current environment is not Windows, so MSIX/build certification has NOT been claimed. Windows validation must run on the Windows development machine, PWABuilder's own build service, or CI.

## Monetization
No Microsoft Store billing in this pass. Appraze remains free during beta.
