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
or use "Change this week's words" in the game (saved on the device).
Words typed in the game need voice clips: Grown-ups shows which words have no voice yet and a
**Make the voice** button. It opens GitHub with a new `words/<date>.txt` filled in; tap
*Commit changes* and the clips are ready in about 5 minutes.

## Voice
Every spoken line is a pre-made clip in the free, open-source Kokoro voice "Heart" (`audio/`);
each world boss says his own taunts in his own voice. **There is no phone/robot voice**: a line
with no clip is skipped (its text is still on screen) and logged as `[voice] no clip:` in the
console (all of them: `window.LLVoiceMissing`).
When `index.html` or `words/` changes on `main`, the "Make voice clips" GitHub Action makes clips
for new words, sentences and phrases and commits them (no API key, no cost). It finds lines in
`say()` / `spoken()` calls, boss lines, world names and Word Workshop word parts, so keep spoken
text fixed (names and numbers belong on screen, not in the voice).
To run it locally: `python3 tools/voice/make_voice.py --model DIR` (see the script for the model files).

## Saving
Progress is stored in the browser's localStorage on the device. A cloud backend comes later with the parent view.

## Install on iPhone
Open the site in Safari → Share → Add to Home Screen.
