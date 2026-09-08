# Voice Job Log

A dead-simple voice-note job log. One HTML file, no build step, no
backend, no signup — open it and start dictating job notes.

## Use it

Just open `index.html` in a browser (or host the folder anywhere static —
GitHub Pages, Netlify, a plain file server). On mobile, add it to your
home screen for one-tap access on a job site.

- Set the **current job** field to tag notes (e.g. "42 Oak St — roof
  repair"). It sticks until you change it.
- Tap the mic, talk, tap it again to stop — the note saves automatically
  using your browser's built-in speech recognition.
- No mic support (or don't want to talk)? Type into the text box instead.
- Edit or delete any note inline.
- Search across all notes and job tags.
- Export everything as CSV or JSON at any time.

## How it works

- Voice-to-text uses the browser's native `SpeechRecognition` API (Chrome,
  Edge, Safari). No audio is uploaded anywhere — recognition happens
  on-device/in-browser, and only the resulting text is stored.
- All notes live in `localStorage` in your browser. Nothing is sent to a
  server. That also means notes don't sync across devices — export/import
  is manual (export CSV/JSON as a backup).
- No dependencies, no framework, no build tooling. It's one file.

## Browser support

Speech recognition requires Chrome, Edge, or Safari (desktop or mobile).
Firefox doesn't implement the Web Speech API — the app still works there,
just falls back to manual typing.
