# Lava Leap

Spelling practice game: the floor is lava, hop across letter blocks to spell the word.
Installable PWA, works offline, hosted on GitHub Pages.

## Files
- `index.html` — the whole game (HTML, CSS, JS in one file). **Source of truth.**
- `sw.js` — offline cache. **Bump `VERSION` on every release** so phones pick up changes.
- `manifest.webmanifest`, `icons/` — home-screen app metadata.
- `port.py` — one-time script used to convert the original Claude artifact into `index.html`.

## Weekly words
Edit the `WORDS` array near the top of the script in `index.html` (`"word | sentence"`),
or use "Change this week's words" in the game (saved on the device only).

## Saving
Progress is stored in the browser's localStorage on the device. A cloud backend comes later with the parent view.

## Install on iPhone
Open the site in Safari → Share → Add to Home Screen.
