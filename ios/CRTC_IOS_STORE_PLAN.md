# Appraze iOS Store Launch Plan

## Hard blocker — added 2026-09-21

Unlike Android/Windows, there is **no free/no-Mac path for iOS.** Apple
requires Xcode running on macOS to build, sign, and submit any iOS app,
and an active Apple Developer Program membership (currently $99/year —
confirm current price at
[developer.apple.com/programs](https://developer.apple.com/programs/))
to distribute it, even via TestFlight. This is unavoidable.

**Next concrete step, once you have both a Mac and the paid account:**
[PWABuilder.com](https://www.pwabuilder.com/) can generate a starter
Capacitor-based iOS project pointed at the production URL, which saves
writing the Phase 2 Swift/WKWebView shell from scratch — but you still
need Xcode on a Mac to open it, build it, and run Phases 3-5 below.
Without a Mac, this phase stays blocked; don't spend budget on the Apple
Developer Program until a Mac (owned, borrowed, or a cloud Mac CI
service) is lined up to actually use it.

## Phase 1 — Apple setup
- Enroll in Apple Developer Program.
- Create/confirm App ID / bundle identifier.
- Create App Store Connect app record.
- Prepare privacy policy/support URLs and store metadata.

## Phase 2 — iOS wrapper
- Create a native Swift/SwiftUI or UIKit shell using WKWebView.
- Load only the production HTTPS CRTC URL.
- Allow normal web navigation inside the app where appropriate.
- Handle external URLs through the system browser when needed.
- Add a visible loading/error state.
- Keep credentials out of native source.

## Phase 3 — Device validation
- Simulator smoke test.
- Physical iPhone smoke test.
- Test network loss/recovery, authentication/session persistence, forms, uploads, downloads, links, keyboard behavior, safe areas, and orientation.

## Phase 4 — TestFlight
- Archive Release.
- Upload to App Store Connect.
- Add internal/external TestFlight testers.
- Record any review/build issues and fix before submission.

## Phase 5 — App Review
- Complete privacy/data declarations.
- Provide review notes and a working demo/test account if the app requires login.
- Submit only after device and TestFlight validation.

## Current production URL
https://appraze-ai-dkc8kpa7pbtzhgwpgztqyh.streamlit.app/

## Billing
Native App Store billing is a future phase and is not implemented by this deployment layer.
