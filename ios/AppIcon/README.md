# Appraze iOS App Icon assets

Pre-rendered from `static/appraze-mark.svg`, opaque (no alpha channel —
Apple rejects a transparent App Store icon), ready to drop into an
`AppIcon.appiconset` once the Xcode project from `ios/CRTC_IOS_STORE_PLAN.md`
exists.

**Modern Xcode (14+):** you only need `AppIcon-1024.png` — Xcode's
"single size" app icon generates every other size automatically. Just
drag it into the AppIcon slot in Assets.xcassets.

**Older Xcode / a multi-size asset catalog:** every other file here maps
to a standard iOS icon slot by its pixel size:

| File | Use |
|---|---|
| `AppIcon-1024.png` | App Store |
| `AppIcon-180.png` | iPhone App, 60pt @3x |
| `AppIcon-167.png` | iPad Pro App, 83.5pt @2x |
| `AppIcon-152.png` | iPad App, 76pt @2x |
| `AppIcon-120.png` | iPhone App 60pt @2x / Spotlight 40pt @3x |
| `AppIcon-87.png` | iPhone Settings 29pt @3x |
| `AppIcon-80.png` | Spotlight 40pt @2x |
| `AppIcon-76.png` | iPad App, 76pt @1x |
| `AppIcon-60.png` | iPhone Notification 20pt @3x |
| `AppIcon-58.png` | Settings 29pt @2x |
| `AppIcon-40.png` | Spotlight 40pt @1x / Notification 20pt @2x |
| `AppIcon-29.png` | Settings 29pt @1x |
| `AppIcon-20.png` | Notification 20pt @1x |

Not verified against an actual Xcode build in this environment (no
Xcode/macOS available here) — sizes/opacity match Apple's published
requirements, but do a real build on a Mac before submitting.
