# Appraze™ — Brand Record

**FINAL BRANDING DECISION (2026-09-21).** This document is the single
source of truth for product branding and supersedes `CRTC_NAME.md` and
`BUSINESS_OS_BRAND.md` (kept for history, marked superseded).

**Product name:** Appraze (spelled A-p-p-r-a-z-e — a coined word, **not**
"appraise")

**Tagline:** Complete Resale Business Suite

**One-line descriptor:** deal math, inventory, and listing for resellers

**Company (unchanged):** Cooper River Trading Co. (CRTC)

## Retired names — removed from all user-facing surfaces

- **"BUSINESS OS"** as a product name (from the 2026-09-21 overnight brand
  commits — that positioning is reverted). "business OS" may survive only
  as a lowercase generic descriptor if it reads naturally, never as the
  product name.
- **"LLAVE"** and **"TURNKEY"** — earlier working names from the same
  rebrand saga, fully retired.
- **"CRTC"** as the app/product name — CRTC now refers only to the
  company, Cooper River Trading Co.
- The **"-ai" suffix** in user-facing branding. The GitHub repo slug
  `Halefire84/Appraze-ai` stays as-is; everything the user sees just says
  Appraze.

## Where "Appraze" appears

App header/title, sidebar branding, login screen, README title, docs
headers, page `<title>` tags, PWA manifest name/short_name, footer text,
every `pages/*.py` page title.

## Trademark usage

`Appraze™` on the first/most prominent mention per screen (app header,
sidebar brand block, login screen, page titles, README title, manifest
description). Plain `Appraze` is fine in body copy after that.

## Internal identifiers left unchanged

Internal module names, database keys, package identifiers, historical
handoff filenames, existing deployment URLs, and secret/env var names
(e.g. `CRTC_ADMIN_USERNAME`, `CRTC_ADMIN_PASSWORD_HASH`) retain the legacy
`CRTC` identifier until separately migrated and tested — changing these
would break existing deployments without being visible to any user.

## Trademark clearance status

Working brand only. Exact-name and broader trademark clearance has not
been completed. Consider a comprehensive USPTO clearance search (exact
wording, similar wording, alternative spellings/pronunciations, related
goods/services, similar commercial impressions) before filing or relying
on the mark exclusively.

## Visual direction

Existing dark/gold-accented UI theme is kept. New wordmark + app icon
assets were referenced as "available and will be supplied" but were not
attached to this session — the PWA manifest/sidebar currently use the
pre-existing generic `icon-192.png` / `icon-512.png` / `icon-512-maskable.png`
files as placeholders. Wire in the real Appraze logo assets into
`static/` and `static/manifest.json` when they are provided.
