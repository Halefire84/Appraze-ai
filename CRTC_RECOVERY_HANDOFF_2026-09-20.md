# CRTC — Recovery & Verification Handoff
## 2026-09-20

### Status
The CRTC (Cooper River Trading Co.) recovery phase is complete.

### Authoritative source
- Repository: Halefire84/Appraze-ai
- Branch: main
- Verified remote HEAD: 8ac23e328490724b6a474c12383f20848f76ebe2
- Product-facing name: CRTC

### Recovery findings
The phone checkout contained two misleading local commits, c364779 and d67974a. Inspection showed they were contaminated with unrelated Termux/home-directory material and are NOT CRTC recovery commits. Do not merge, cherry-pick, or recover them.

The legitimate CRTC work investigated from the phone is already represented on GitHub main, including listing/SKU fixes, category validation, the canonical decision engine and financial normalization, POS/billing reconciliation, radar improvements, tests, and documentation.

### Verification
A clean verification tree was created directly from origin/main without modifying the dirty phone checkout.

- python -m compileall -q . — PASS
- Selected CRTC test suite — 169 passed
- 5 failures were dependency/environment failures only:
  - requests unavailable
  - pandas unavailable
  - auth/billing/storage imports consequently unavailable
- Full-suite verification is still pending on a proper development environment with the declared dependencies installed.

Do NOT claim the complete test suite passes yet.

### Next environment
Use the proper development machine/CI for the next phase.

Primary tools:
1. GitHub — source of truth
2. Claude Code — hands-on implementation and QA
3. ChatGPT — independent architecture/review/QA
4. Git — safety branches, small commits, no destructive history operations

### Next commands on the proper development environment
```
git status
git branch --show-current
git log -5 --oneline
git fetch origin
git rev-parse origin/main
pip install -r requirements.txt
pip install -r requirements-webhook.txt
python -m compileall -q .
python -m pytest -q
```

### Development rules
- Preserve existing functionality.
- Prefer small, reversible changes.
- Never claim tests passed unless actually executed.
- Do not hide/suppress failures.
- Do not rewrite unrelated code.
- Do not reset --hard or force-push.
- Review payment, authentication, webhook, tenant-isolation, API-key, and data-security behavior.
- Keep documentation synchronized with implementation.

### Beta target
The current objective is a stable, demonstrable, production-grade CRTC beta.

Prioritize:
- crash prevention
- error handling
- regression protection
- security
- payment correctness
- persistence/concurrency
- failure/recovery
- observability
- performance/resource safety
- deployment readiness
- complete test coverage

Major new features remain secondary until the current beta is verified.

### Handoff rule
Start from current main. Inspect the current repository and recent commits before changing anything. Do not rebuild or merge the obsolete phone-local contamination.
