# Appraze Windows tile/logo assets

Pre-rendered from `static/appraze-mark-maskable.svg` (the full-bleed
variant — no rounded corners baked in, since Windows tiles apply their
own shape/background). Ready to reference from an MSIX manifest's
`<uap:VisualElements>` once the packaging step (see
`../CRTC_WINDOWS_STORE_PLAN.md`) happens.

| File | MSIX manifest attribute |
|---|---|
| `Square44x44Logo.png` | `Square44x44Logo` — taskbar/app list icon |
| `Square71x71Logo.png` | small tile |
| `Square150x150Logo.png` | `Square150x150Logo` — medium tile (also the default Start tile) |
| `Square310x310Logo.png` | large tile |
| `StoreLogo.png` | `StoreLogo` — Microsoft Store listing |

**If you use PWABuilder.com instead** (the recommended fast path — see
`../CRTC_WINDOWS_STORE_PLAN.md`), you don't need these files at all:
PWABuilder generates its own full tile set directly from
`static/manifest.json` and `static/icon-512.png`. These are here for the
native-MSIX fallback path, or if you want to double-check PWABuilder's
output matches this same mark.

No `Wide310x150Logo` (the wide rectangular tile) is included — the mark
is designed as a square icon; a wide tile would need its own horizontal
layout (icon + wordmark side by side) rather than a stretched version of
this square mark.
