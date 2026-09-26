# Android release signing (Play upload key)

Status as of 2026-09-26. This is the key that gets the app onto the Play closed-testing
track. **If it is lost before Play App Signing has taken a copy of it, the app can never be
updated on Play again** — a new app listing would be needed. Read this whole file before
touching anything here.

## What exists

- **The keystore file and its passwords are NOT in this repository, and never should be.**
  They were generated in a Claude Code session and delivered directly to Chris as
  downloadable files (`appraze-release.keystore` and `appraze-release-CREDENTIALS.txt`) —
  see the session's chat history for that message. **They must be saved somewhere durable
  immediately** (a password manager attachment, an encrypted backup, a safe) if that hasn't
  already been done — the session container they were generated in is temporary and is gone.
- **Key details** (not secret — the passwords are the secret, not this):
  - Alias: `appraze_upload`
  - Type: PKCS12, RSA 2048
  - Owner DN: `CN=Cooper River Trading Co., OU=Appraze, O=Cooper River Trading Co., L=Charleston, ST=SC, C=US`
  - Valid: 2026-09-26 through 2053-11-03 (Play requires validity past 2033-10-22; this clears
    it by ~20 years)
  - Certificate SHA-256: `7A:30:BE:FE:43:EB:35:C5:9B:98:88:90:42:FB:FD:6D:B5:64:99:15:D9:7B:3E:C3:41:61:54:0F:B8:0A:95:26`
    (use this to confirm any AAB was signed with the real key, e.g. after `bundletool` or
    `jarsigner -verify -verbose -certs app-release.aab`, whose "signer certificate" line
    should show the same expiry, 2053-11-03)
- **PKCS12 note:** PKCS12 keystores use one password for both the store and the key (a
  `keytool` limitation), so `storePassword` and `keyPassword` in the credentials file are
  the same value.

## How the build finds it (`android/app/build.gradle`)

The `release` build type signs with the real key only when one of these is present; with
neither, it silently falls back to the debug key (so a plain checkout / CI still builds,
just not something to ship):

1. **`android/keystore.properties`** (gitignored, never commit it) — the simplest path for
   a local/production build machine:
   ```properties
   storeFile=/absolute/path/to/appraze-release.keystore
   storePassword=<the password from the credentials file>
   keyAlias=appraze_upload
   keyPassword=<the same password>
   ```
2. **Environment variables** (for a CI secrets store): `APPRAZE_RELEASE_STORE_FILE`,
   `APPRAZE_RELEASE_STORE_PASSWORD`, `APPRAZE_RELEASE_KEY_ALIAS`, `APPRAZE_RELEASE_KEY_PASSWORD`.

Then build as usual:
```bash
cd android
gradle :app:bundleRelease   # app/build/outputs/bundle/release/app-release.aab
```

## Play Console: enrolling in Play App Signing

This keystore's job is to be the **upload key**, not the key Play ships to users:

1. Create the app in Play Console (needs Chris's Google/Play Console login — not done by
   this session).
2. On first release creation, opt in to **Play App Signing** (the modern default). Upload
   `app-release.aab` signed with this keystore.
3. Google generates and holds the actual **app signing key**; this keystore only proves
   "this upload really came from Appraze" from then on.
4. **If this upload key is later lost or compromised**, Google has a support-driven upload
   key **reset** process (Play Console → App integrity → App signing) — recoverable, unlike
   losing the app signing key itself. Still: don't rely on that process; keep the backup.

## Verified this session

- Debug build, lint, and unit tests unaffected (still pass; `gradle :app:assembleDebug
  :app:lintDebug :app:testDebugUnitTest` green) — the fallback path was exercised by not
  having `keystore.properties` present in CI/this checkout.
- `gradle :app:bundleRelease` produced an AAB whose embedded certificate's SHA-256
  fingerprint was diffed byte-for-byte against the generated keystore's fingerprint — they
  match exactly (see above).
- **Not verified:** the actual Play Console upload/enrollment (needs Chris's login), and
  whether Play accepts this specific AAB (its Data Safety form and closed-testing track
  setup are separate, not-yet-done steps — see `handoff.md`).

## If this file exists but you don't have the keystore

You're a future session/agent without file access to the actual keystore — that's correct
and expected; it's not supposed to be in git or in a container. Ask Chris for it (he was
told to save it durably) rather than generating a new one, which would produce a
**different app** as far as Play is concerned and orphan the one already submitted.
