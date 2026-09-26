# Appraze / CRTC — Security Notes

Standalone write-up for `CRTC_SESSION_PROMPTS.md`'s Session 7 ("Security
pass — listing text = untrusted"). This is not a penetration test and not
a claim of completeness; it's an honest record of what was actually
checked, what was found, what got fixed, and what still needs a human.

Last verified: 2026-09-22. Every finding below was checked against the
actual code on this branch, not copied from an earlier session's notes
without re-verification.

## Methodology

- `bandit -r . -x ./tests,./.git` — static analysis for common Python
  security anti-patterns.
- `pip-audit -r requirements.txt` and `-r requirements-webhook.txt` —
  known-CVE scan of pinned dependencies.
- Manual review of every place marketplace/user-supplied text reaches an
  LLM prompt, a spreadsheet cell, or an `unsafe_allow_html=True` render.
- Manual review of every Apps Script action for whether authorization is
  re-derived server-side or trusted from a client-supplied parameter.
- `git ls-files` grep for any secret-shaped file that shouldn't be tracked.

## 1. Marketplace listing text as untrusted input (AI/prompt-injection boundary)

**Claim to verify:** a listing's title/description must never become an
instruction to the app or to an LLM — it's data, always.

**Finding: still true, re-verified.**

- `opportunity_radar.py` / `holy_grail_pipeline.py` — the pipeline that
  processes scraped/imported marketplace listings — is pure deterministic
  regex/keyword matching. No LLM call anywhere in that path, so there is
  no prompt-injection surface through scraped listing content today.
- The only LLM call in the app is the AI Analyzer (`app.py:1131-1162`):
  a fixed `system` string (the app's own instructions) is sent separately
  from `messages[0].content`, which holds the **logged-in user's own**
  uploaded photo/description of their own item — self-directed input, not
  third-party listing data, and not a cross-user vector. If this pipeline
  is ever extended to auto-analyze *scraped* listings (not user-uploaded
  photos), this exact separation must be preserved, and the scraped text
  must go in `messages[0].content`, never concatenated into `system`.
- Checked what happens to the AI's JSON response before it reaches the
  page: every field (`itemName`, `reasoning`, draft titles/descriptions)
  is rendered through plain-text Streamlit widgets (`st.success`,
  `st.caption`, `st.metric`, `st.text_input(value=...)`,
  `st.text_area(value=...)`), none of which interpret HTML. The one
  `unsafe_allow_html=True` block in that tab (`app.py:1213-1214`)
  interpolates only a float (`suggested_price`, via `{:,.2f}`), never an
  AI- or user-controlled string. **No self-XSS path found** through the
  AI Analyzer's response.

## 2. Spreadsheet formula/CSV injection

**Claim to verify:** a user-controlled string that starts with
`=`/`+`/`-`/`@` and later gets exported/opened in Excel/Sheets can't
execute as a formula.

**Finding: covered where it matters, verified by tracing every write path.**

- `handleSignup_`'s `display_name` and `handleMarkProcessed_`'s
  `file_name` are the only two places a *raw, single* user-controlled
  string is written directly into its own spreadsheet cell — both go
  through `sanitizeForSheetCell_()` (prefixes a literal `'` to defuse a
  leading `=+-@\t\r`), with `unsanitizeFromSheetCell_()` stripping it back
  out on read.
- `save_data`/`load_data` (the deals/inventory persistence path) and
  `log_event` write a `JSON.stringify(...)`-wrapped payload into a single
  cell. JSON's grammar means that string always starts with `{` or `[`,
  never a formula-trigger character, so this path is structurally safe
  without needing explicit sanitization — confirmed by reading
  `handleSaveData_`/`handleLoadData_`/`handleLogEvent_` directly rather
  than assuming.

## 3. Automated scans

**bandit** (`bandit -r . -x ./tests,./.git`): 9 findings, 0 High. All
reviewed individually — none required a code change:

| Finding | Location | Verdict |
|---|---|---|
| B310 urlopen scheme audit (Medium) | `app.py:1161` | False positive — hardcoded call to `https://api.anthropic.com/v1/messages`, not attacker-influenced. |
| B310 urlopen scheme audit (Medium) | `listing_bridge.py:181` | False positive — `_default_transport()`'s `url` param is only ever called with the hardcoded `_ANTHROPIC_URL` constant today; no listing-derived URL reaches it. Worth a `# nosec` comment if this keeps tripping future scans. |
| B105 hardcoded-password-string (Low) | `decision_policy.py:68` | False positive — `DECISION_PASS = "PASS"` is a verdict constant, not a credential. |
| B105 hardcoded-password-string (Low) | `ebay_sell.py:225` | False positive — an empty-string placeholder in a generated *config template file* (`CLIENT_SECRET: ""`), not a real secret. |
| B110 try/except/pass (Low) | `auth.py:503` | Intentional — `_record_visit_once()` is a best-effort visit counter; a failure here must never break login. |
| B110 try/except/pass (Low) ×2 | `telemetry.py:54,71` | Intentional — logging failures are never allowed to surface to the caller (documented in-line). |
| B112 try/except/continue (Low) | `mail.py:122` | Intentional — skips one undecodable MIME part while parsing an email body, not a security-relevant swallow. |
| B110 try/except/pass (Low) | `mail.py:195` | Intentional — best-effort IMAP logout in a `finally` block; a logout failure must not mask the real result. |

**pip-audit**: `requirements.txt` → no known vulnerabilities.
`requirements-webhook.txt` → no known vulnerabilities. Both re-run fresh
for this write-up, not copied from an earlier pass.

## 4. `mail.py` — dormant module, not a live attack surface

`mail.py` (Gmail inbox reader for shipment-tracking/invoice detection) is
fully built — `imaplib.IMAP4_SSL`, read-only `INBOX` select, Gmail App
Password from Streamlit secrets (never a real account password) — but is
**not wired into any page** (`app.py` has zero references to it). It's
not a current attack surface. If it's ever wired in, re-review at that
point: it already does the right things (encrypted transport, read-only,
App Password not primary credential, credential from secrets not
hardcoded), but that should be re-confirmed against whatever UI ends up
calling it.

## 5. Auth / session / API boundaries

- **IDOR class of bug (the one this whole engagement's hardening work
  centers on):** every Apps Script action that decides *whose* data to
  touch or whether admin-tier quota applies re-derives that from the
  `Users` sheet by username (`resolveOwnerKey_`, `findUser_`), never from
  a client-supplied `is_admin` parameter. Verified directly in
  `handleSaveData_`, `handleLoadData_`, `handleReserveAiUsage_`,
  `handleGetAiUsage_`, `handleAdminClearAbuseLockout_`. Any *new* Apps
  Script action must follow this same rule before merging — this is the
  exact bug class a naive implementation would reintroduce.
- **Needs human review — the API's actual trust boundary:** the Apps
  Script endpoint is gated by one shared `TOKEN` (Streamlit secret
  `APPS_SCRIPT_TOKEN`), not per-request session auth. Anyone holding that
  token can call any action for any `username` they choose to pass —
  including another tester's. Real login (password check) only happens
  once, client-side, to obtain the session; every subsequent
  `save_data`/`load_data` call trusts whatever `username` the Streamlit
  session state holds, not a re-verified credential or signed session
  token. This is an accepted, already-documented tradeoff for a small
  trusted beta (5-10 known testers), not something fixed this session —
  flagging it here explicitly as a human decision point before a wider
  public beta (Stage C/D in `LAUNCH_BLOCKERS.md`): either move to
  per-request signed session tokens, or keep the beta small enough that
  the shared-token model's blast radius stays acceptable.
- **Brute-force lockout** (`auth.py`): 5 failed attempts locks a username
  out for 15 minutes, covering Admin, tester, and beta-account login. This
  is in-process (module-level dict) state — resets on app
  restart/redeploy, doesn't share state across multiple instances.
  Correctly documented as a known limitation, not durable multi-instance
  rate limiting; acceptable for Streamlit Community Cloud's single-instance
  free tier at current beta scale.
- **Escalating abuse-detection lockout** (`AppsScript_Code.gs`,
  `checkAndRecordAbuseAttempt_`): durable, server-side (Sheet-backed,
  survives restarts), gates AI-usage call *rate* — more than 6 calls in a
  rolling 60s window trips a 5-minute cooldown; 3 separate bursts trip a
  permanent, admin-only-clearable lockout. See `.agent/HANDOFF.md` for
  full detail and its 24-scenario verification.
- **Timing-safe comparisons**: `TOKEN` and `ADMIN_SETUP_CODE` checks use
  a constant-time comparison (`timingSafeEqual_`) rather than `!==`, which
  would otherwise leak a character-position timing signal.
- **Password hashing**: bcrypt (salted, deliberately slow) is the
  recommended path for new/rotated Admin credentials; legacy SHA-256 hex
  digests are still accepted for backward compatibility with an
  already-configured production secret, auto-detected by hash shape
  (`_BCRYPT_HASH_RE`). The Apps-Script-side tester/beta signup path
  (`handleSignup_`) still stores a SHA-256 hash — migrating that to
  bcrypt needs Apps-Script-side changes that can't be live-tested against
  a real deployed Sheet from this environment; documented as an open gap
  rather than pushed unverified.

## 6. Stripe webhook security

Covered in detail in `.agent/HANDOFF.md` and `LAUNCH_BLOCKERS.md`; not
re-derived here. Summary: timestamp-tolerance replay protection, any
valid v1 signature accepted during secret rotation (not just the last
one), malformed/non-ASCII input produces a controlled rejection, refund
accounting uses the actual `amount_refunded` field (not the `refunded`
boolean), out-of-order webhook delivery can't downgrade a more-final
status (`STATUS_RANK`/`SALES_LOG_STATUS_RANK_`, kept in sync across the
Python and Apps Script copies), and a `RedeemedStripeSessions` sheet with
atomic `LockService` locking stops one real payment being replayed across
multiple accounts via a browser-editable `?session_id=`.

## 7. Secrets in source control

- `.gitignore` covers `.streamlit/secrets.toml`, `.env`, and
  `.ebay_tokens.json`.
- `git ls-files` grep for any tracked `secrets.toml`/`.env`/
  `.ebay_tokens.json`/`.pem`/`.p12`/`.keystore` file: **zero matches** —
  re-verified for this write-up, not assumed.
- `AppsScript_Code.gs`'s `SHEET_ID`/`TOKEN`/`ADMIN_SETUP_CODE` are
  placeholders in source control by design (see the file's own header
  comment); if this repo's history ever had real values committed, treat
  them as compromised and rotate regardless of the placeholder now being
  in place.

## 8. What was NOT done in this pass (explicitly deferred, needs a human)

- No live penetration test / dynamic scanning (`bandit`/`pip-audit` are
  static analysis only).
- No dependency deep-audit beyond `pip-audit`'s known-CVE database (e.g.
  no manual review of each dependency's own security posture/maintenance
  status).
- The API's shared-TOKEN trust model (§5) is a real architectural
  decision point for anything past a small trusted beta — needs a human
  call, not a silent code change.
- Mobile/iOS/Windows build-toolchain security review (signing, secure
  storage, permissions) — out of scope for this Python-repo-focused pass;
  see `LAUNCH_BLOCKERS.md` Stage D.
- No live Apps Script deployment was available in this environment to
  test any `.gs` change against a real Google Sheet — every `.gs`
  security fix mentioned above (timing-safe comparisons, folder
  allowlist, sanitization, abuse lockout, replay lock) is verified by
  standalone Node.js algorithm harnesses only. This is the single largest
  gap between "verified" and "production-trusted" for this repo's backend.

## Test commands

```
python3 -m pytest -q                                   # -> 497 passed, 0 failed
flake8 --select=E9,F63,F7,F82 .                         # -> 0 findings
bandit -r . -x ./tests,./.git -q                        # -> 9 findings, 0 High, all reviewed above
pip-audit -r requirements.txt                            # -> no known vulnerabilities
pip-audit -r requirements-webhook.txt                     # -> no known vulnerabilities
```
