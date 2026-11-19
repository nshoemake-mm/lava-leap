#!/usr/bin/env python3
"""Make the game's spoken clips with Kokoro (free, open-source TTS, runs offline).

Reads index.html: the WORDS list (word + sentence) and every fixed phrase passed to
say()/speak(). Writes audio/clips/<hash>.mp3 and audio/voice.json (text -> file).
Only new phrases are generated; clips no longer used are deleted.

Usage: python3 tools/voice/make_voice.py --model DIR [--root .]
DIR holds kokoro-v1.0.int8.onnx and voices-v1.0.bin
(https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0).
"""
import argparse, hashlib, json, os, re, subprocess, sys, tempfile

VOICE = "af_heart"          # Nick picked "Heart" (warm female), 2026-11-19
SPEED = {"word": 0.85, "slow_word": 0.6, "sentence": 0.95, "slow_sentence": 0.75, "phrase": 1.0, "letter": 0.9}
WORD_VARS = {"S.word", "it.w", "w", "c.w", "want"}   # template vars that hold the current word

def norm(t):  # must match norm() in index.html
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", t.lower())).strip()

def segments(t):  # must match segs() in index.html
    return re.findall(r"[^.!?]+[.!?]*", t)

def read_words(src):
    m = re.search(r"const WORDS = \[(.*?)\];", src, re.S)
    out = []
    for line in re.findall(r'"([^"]*)"', m.group(1)):
        w, _, s = line.partition("|")
        if re.search(r"[a-z]", w.strip().lower()):
            out.append((w.strip().lower(), s.strip()))
    return out

def call_args(src):
    """Argument text of every say(...)/speak(...) call (balanced parens, strings skipped)."""
    for m in re.finditer(r"\b(?:say|speak)\(", src):
        i, depth, q = m.end(), 1, None
        while i < len(src) and depth:
            c = src[i]
            if q:
                if c == "\\": i += 1
                elif c == q: q = None
            elif c in "\"'`": q = c
            elif c == "(": depth += 1
            elif c == ")": depth -= 1
            i += 1
        yield src[m.end():i - 1]

def read_phrases(src, words):
    """Fixed bits of every say()/speak() call, plus 'word' templates expanded for each word."""
    found = set()
    for args in call_args(src):
        for lit in re.findall(r'"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`', args):
            text = lit[0] or lit[1]
            vars_ = re.findall(r"\$\{([^{}]*)\}", text)
            tok = re.sub(r"\$\{[^{}]*\}", lambda m, n=iter(range(99)): f"\x00{next(n)}\x00", text)
            for seg in segments(tok):
                ids = [int(x) for x in re.findall(r"\x00(\d+)\x00", seg)]
                if not ids:
                    found.add(seg)
                elif len(ids) == 1 and vars_[ids[0]].strip() in WORD_VARS and norm(re.sub(r"\x00\d+\x00", "", seg)):
                    for w, _ in words:
                        found.add(re.sub(r"\x00\d+\x00", w, seg))
    return {p for p in found if len(norm(p)) > 2 and " " in p.strip() or re.search(r"[!?.]$", p.strip())}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    src = open(os.path.join(a.root, "index.html"), encoding="utf-8").read()
    words = read_words(src)

    jobs = {}  # key -> (text to speak, speed)
    def add(key, text, kind):
        if key and key not in jobs:
            jobs[key] = (text, SPEED[kind])
    for w, s in words:
        add(norm(w), w + ".", "word"); add("slow:" + norm(w), w + ".", "slow_word")
        if s:
            for seg in segments(s):
                add(norm(seg), seg.strip(), "sentence"); add("slow:" + norm(seg), seg.strip(), "slow_sentence")
    for c in "abcdefghijklmnopqrstuvwxyz":
        add(c, c.upper() + ".", "letter")
    for p in sorted(read_phrases(src, words)):
        add(norm(p), p.strip(), "phrase")

    audio = os.path.join(a.root, "audio"); clips = os.path.join(audio, "clips")
    os.makedirs(clips, exist_ok=True)
    plan = {}
    for key, (text, speed) in jobs.items():
        h = hashlib.sha1(f"{VOICE}|{speed}|{text}".encode()).hexdigest()[:12]
        plan[key] = (f"clips/{h}.mp3", text, speed)

    todo = [(f, t, s) for f, t, s in set(plan.values()) if not os.path.exists(os.path.join(audio, f))]
    print(f"{len(plan)} clips needed, {len(todo)} new", file=sys.stderr)
    if todo:
        import numpy as np, soundfile as sf
        from kokoro_onnx import Kokoro
        k = Kokoro(os.path.join(a.model, "kokoro-v1.0.int8.onnx"), os.path.join(a.model, "voices-v1.0.bin"))
        with tempfile.TemporaryDirectory() as tmp:
            for f, text, speed in sorted(todo):
                pcm, sr = k.create(text, voice=VOICE, speed=speed, lang="en-us")
                pcm = np.trim_zeros(np.where(np.abs(pcm) < 0.003, 0, pcm)) if len(pcm) else pcm
                wav = os.path.join(tmp, "c.wav"); sf.write(wav, pcm, sr)
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-ac", "1", "-b:a", "48k",
                                os.path.join(audio, f)], check=True)
                print("  made", f, repr(text), file=sys.stderr)

    used = {f for f, _, _ in plan.values()}
    for name in os.listdir(clips):
        if f"clips/{name}" not in used:
            os.remove(os.path.join(clips, name))
    with open(os.path.join(audio, "voice.json"), "w") as fh:
        json.dump({"voice": VOICE, "clips": {k: v[0] for k, v in sorted(plan.items())}}, fh, indent=0, sort_keys=True)
        fh.write("\n")

if __name__ == "__main__":
    main()
