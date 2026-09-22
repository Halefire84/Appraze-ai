# CRTC Local Development — Standard Operating Procedure

One repeatable process for working on CRTC locally in VS Code, whether
you're testing a change from a Claude Code session, doing manual QA before
a release, or just poking at a feature. `DEPLOY.md` covers getting the app
live on Streamlit Cloud; this doc covers your own machine.

## 0. One-time machine setup

Pick ONE of these two paths.

### Path A — Dev Container (recommended)

Gives you the exact same environment every time, matching what GitHub
Codespaces already uses (`.devcontainer/devcontainer.json` is already
configured in this repo) — no local Python version conflicts, ever.

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   and keep it running.
2. Install VS Code's **Dev Containers** extension
   (`ms-vscode-remote.remote-containers` — already in this repo's
   `.vscode/extensions.json` recommendations, VS Code will offer to
   install it when you open the folder).
3. Open this repo folder in VS Code. Click **Reopen in Container** when
   prompted (or `Ctrl/Cmd+Shift+P` → "Dev Containers: Reopen in
   Container").
4. First build takes a few minutes; `requirements.txt` installs
   automatically. Every reopen after that is fast.

### Path B — Local virtual environment

Faster to start if you don't want Docker running.

```bash
# from the repo root
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pytest fastapi "uvicorn[standard]" httpx stripe  # dev/test extras
```

In VS Code: `Ctrl/Cmd+Shift+P` → "Python: Select Interpreter" → pick
`.venv`.

## 1. Secrets (do this once, every machine)

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Fill in only the keys for whatever you're actually testing — every
integration in this app fails safe with a "not configured" message when
its secrets are blank, nothing crashes. `.streamlit/secrets.toml` is
already in `.gitignore`; it will never be committed. **Never** put real
values in the `.example` file or in this doc.

## 2. Standard commands

```bash
# Run the app
streamlit run app.py

# Run the full test suite (do this before every push, no exceptions)
python -m pytest tests/ -q

# Run one file/module while iterating
python -m pytest tests/test_listing_bridge.py -q

# Dependency sanity check
python -m pip check

# Syntax-check a file you just edited without running it
python -m py_compile app.py
```

VS Code shortcuts for the same things:
- **Testing** sidebar (flask icon) discovers and runs `tests/` automatically
  once `python.testing.pytestEnabled` picks up `.vscode/settings.json`.
- **Run and Debug** (`F5`) → "Streamlit: run app.py" launches the app with
  the debugger attached, breakpoints included.
- Same panel → "FastAPI: stripe_webhook_server (local)" launches the
  webhook service standalone on port 8000, if you're testing Stripe
  reconciliation.

## 3. Before you push — the release gate

This is the same gate a production-hardening pass runs; treat it as
non-negotiable for any change, not just big ones:

1. `python -m pytest tests/ -q` — must show `N passed`, zero failed, zero
   errored. If you touched a file, run its specific test file first, then
   the full suite to catch regressions elsewhere.
2. `python -m pip check` — must show "No broken requirements found."
3. `python -m py_compile <every file you edited>` — catches syntax errors
   pytest's import step might not exercise.
4. If you touched anything UI-facing (`app.py`, `pages/*.py`, PWA
   manifest/icons): actually open the app in a browser and click through
   it. Tests can't see the screen.
5. If you touched `auth.py`, `stripe_webhooks.py`,
   `stripe_webhook_server.py`, or anything reading `st.secrets`/
   `os.environ`: re-read the diff once specifically looking for a
   credential, token, or password that could leak into a log line, an
   error message, or a comment.

Never claim a test passed or a build succeeded without having just run it
in this session — paste the real command output, not a summary from
memory.

## 4. Browser / mobile QA checklist (things automated tests can't cover)

Run this whenever you touch navigation, `auth.py`, session state, or PWA
assets:

- [ ] Login → dashboard → each sidebar page loads without error
- [ ] Browser refresh mid-session doesn't lose authentication unexpectedly
- [ ] Logout actually clears session and re-shows the login gate
- [ ] Direct URL to a `pages/*.py` file without logging in first is blocked
- [ ] Chrome DevTools → Application → Manifest shows `manifest.json`
      loaded with no errors, and the install icon appears in the address
      bar (confirms the PWA `<head>` injection is working)
- [ ] Chrome's mobile device emulator (`Ctrl/Cmd+Shift+M`) — no horizontal
      scroll, tables/forms usable on a narrow screen
- [ ] A real Android/iOS phone against the deployed HTTPS URL (install
      prompts don't fire on `localhost`)

## 5. Branching / commit convention

- One feature/fix per branch, branched from `main`.
- Small, logical commits (`feat:`, `fix:`, `security:`, `test:`, `docs:`
  prefixes match this repo's existing history — check `git log --oneline`
  before naming a new kind).
- Run the full gate in §3 before every push, not just the final one.
- Push with `git push -u origin <branch>`, open a PR into `main`.
- Never force-push a branch other people might have pulled; never skip
  hooks with `--no-verify` to get a commit through.

## 6. If something in this doc goes stale

Update this file in the same commit as whatever changed (a new secret key,
a new required extension, a new standard command) — the goal is that this
one document is always the accurate answer to "how do I work on this repo
locally," not a snapshot that rots.
