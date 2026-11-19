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

# Each world boss says his own taunts in his own voice (Nick picked per-boss voices, 2026-11-19).
# (Kokoro voice, speed, pitch factor (<1 = deeper, speed kept), extra ffmpeg filters)
BOSS_VOICES = {
    "sizzle":      ("am_onyx",   0.90, 0.72, "aecho=0.8:0.7:40:0.35,bass=g=6,volume=1.6"),           # lava growl
    "frostmaw":    ("bm_george", 0.85, 0.78, "aecho=0.8:0.8:180|320:0.45|0.3,highpass=f=120"),       # icy cave echo
    "thornback":   ("am_fenrir", 0.85, 0.76, "vibrato=f=6:d=0.12,bass=g=5,volume=1.5"),              # creaky beast
    "dunestinger": ("bm_lewis",  0.95, 0.88, "flanger=delay=3:depth=4,highpass=f=150,volume=1.3"),   # hissy scorpion
    "glimmerjaw":  ("am_santa",  1.00, 1.22, "chorus=0.6:0.9:50|60:0.4|0.32:0.25|0.4:2|2.3"),        # sparkly crab
    "stormbeak":   ("am_puck",   1.05, 1.12, "aecho=0.8:0.5:60:0.3"),                                # crackly bird
    "sporecap":    ("am_echo",   1.00, 1.30, ""),                                                    # squeaky mushroom
    "gloomhelm":   ("bm_fable",  0.85, 0.68, "aecho=0.8:0.85:250|500:0.5|0.3,bass=g=5,volume=1.5"),  # dark knight
}

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

def js_str(m):
    return m and json.loads('"' + m.group(1) + '"')

def read_bosses(src):
    """Boss names, intros, taunts and specials from LavaMonster's BOSSES list (+ the defaults)."""
    looks = dict(re.findall(r'^\s*(\w+):\s*\{ shape:.*?word: "([^"]+)"', src, re.M))
    s_mini = re.search(r'const SPECIAL = \{ mini: \[([^\]]*)\], super: "([^"]+)"', src)
    t_def = re.search(r'const TAUNTS = \{ 2: "((?:[^"\\]|\\.)*)", 3: "((?:[^"\\]|\\.)*)" \}', src)
    out = []
    for line in re.findall(r'^\s*\{ id: ".*?(?=^\s*\{ id: "|^\s*\];)', src, re.M | re.S):
        g = lambda pat: re.search(pat, line, re.S)
        b = {"id": g(r'id: "(\w+)"').group(1), "name": g(r'name: "([^"]+)"').group(1)}
        shot = g(r'shot: (?:"(\w+)"|\{.*?word: "([^"]+)")')
        b["shot"] = (shot.group(2) or looks.get(shot.group(1))) if shot else looks.get("fire")
        b["intro"] = js_str(g(r'intro: "((?:[^"\\]|\\.)*)"')) or ""
        tm = g(r'taunts: \{ 2: "((?:[^"\\]|\\.)*)", 3: "((?:[^"\\]|\\.)*)" \}') or t_def
        b["taunts"] = [js_str(re.match(r"(.*)", tm.group(i))) for i in (1, 2)]
        sp = g(r'special: \{ mini: \[([^\]]*)\], super: "([^"]+)"') or s_mini
        b["mini"] = re.findall(r'"([^"]+)"', sp.group(1)); b["super"] = sp.group(2)
        out.append(b)
    return out

def boss_narration(b):
    """Narrator (Heart) lines that have the boss's name, shot or special in them."""
    n, shot = b["name"], b["shot"]
    lines = [f"You beat {n}! Amazing spelling!", f"{n} got away. Practice and come back!",
             f"Your power is supercharged! Tap {b['super']}!", f"{b['super']}!"] + [f"{m}!" for m in b["mini"]]
    if b["id"] == "sizzle":
        lines += [f"Lava monster! Pick the right tricky part to block the {shot} and hit {n}.",
                  f"Lava monster! Pick the right tricky part to hit {n}."]
    else:
        lines += [b["intro"], f"Block the {shot} with the right tricky part!"]
    return [seg for l in lines for seg in segments(l)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    src = open(os.path.join(a.root, "index.html"), encoding="utf-8").read()
    words = read_words(src)

    jobs = {}  # key -> (text to speak, speed, voice, pitch, filters)
    def add(key, text, kind, voice=None):
        if key and key not in jobs:
            jobs[key] = (text, SPEED[kind], VOICE, 1.0, "") if not voice else (text, voice[1], voice[0], voice[2], voice[3])
    for w, s in words:
        add(norm(w), w + ".", "word"); add("slow:" + norm(w), w + ".", "slow_word")
        if s:
            for seg in segments(s):
                add(norm(seg), seg.strip(), "sentence"); add("slow:" + norm(seg), seg.strip(), "slow_sentence")
    for c in "abcdefghijklmnopqrstuvwxyz":
        add(c, c.upper() + ".", "letter")
    for p in sorted(read_phrases(src, words)):
        add(norm(p), p.strip(), "phrase")
    for b in read_bosses(src):
        for seg in boss_narration(b):
            add(norm(seg), seg.strip(), "phrase")
        v = BOSS_VOICES.get(b["id"], BOSS_VOICES["sizzle"])
        for t in b["taunts"] + [f"{b['name']} gets stronger!"]:
            for seg in segments(t):
                add(f"boss:{b['id']}:{norm(seg)}", seg.strip(), "phrase", v)

    audio = os.path.join(a.root, "audio"); clips = os.path.join(audio, "clips")
    os.makedirs(clips, exist_ok=True)
    plan = {}
    for key, (text, speed, voice, pitch, fx) in jobs.items():
        tag = f"{voice}|{speed}|{text}" if (voice, pitch, fx) == (VOICE, 1.0, "") else f"{voice}|{speed}|{pitch}|{fx}|{text}"
        h = hashlib.sha1(tag.encode()).hexdigest()[:12]   # Heart clips keep their old names
        plan[key] = (f"clips/{h}.mp3", text, speed, voice, pitch, fx)

    todo = [j for j in set(plan.values()) if not os.path.exists(os.path.join(audio, j[0]))]
    print(f"{len(plan)} clips needed, {len(todo)} new", file=sys.stderr)
    if todo:
        import numpy as np, soundfile as sf
        from kokoro_onnx import Kokoro
        k = Kokoro(os.path.join(a.model, "kokoro-v1.0.int8.onnx"), os.path.join(a.model, "voices-v1.0.bin"))
        with tempfile.TemporaryDirectory() as tmp:
            for f, text, speed, voice, pitch, fx in sorted(todo):
                pcm, sr = k.create(text, voice=voice, speed=speed, lang="en-us")
                pcm = np.trim_zeros(np.where(np.abs(pcm) < 0.003, 0, pcm)) if len(pcm) else pcm
                wav = os.path.join(tmp, "c.wav"); sf.write(wav, pcm, sr)
                af = [f"asetrate={sr}*{pitch},aresample={sr},atempo={1 / pitch:.4f}"] if pitch != 1.0 else []
                af += [fx] if fx else []
                af += ["alimiter=limit=0.95"] if af else []
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav] + (["-af", ",".join(af)] if af else [])
                               + ["-ac", "1", "-b:a", "48k", os.path.join(audio, f)], check=True)
                print("  made", f, repr(text), file=sys.stderr)

    used = {j[0] for j in plan.values()}
    for name in os.listdir(clips):
        if f"clips/{name}" not in used:
            os.remove(os.path.join(clips, name))
    with open(os.path.join(audio, "voice.json"), "w") as fh:
        json.dump({"voice": VOICE, "clips": {k: v[0] for k, v in sorted(plan.items())}}, fh, indent=0, sort_keys=True)
        fh.write("\n")

if __name__ == "__main__":
    main()
