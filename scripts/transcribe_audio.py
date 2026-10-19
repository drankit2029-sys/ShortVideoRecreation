#!/usr/bin/env python3
"""Transcribe the reference video's audio on a GitHub runner. Heavy work off-device."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import wave

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS = ROOT / "analysis"
ANALYSIS.mkdir(exist_ok=True)

WAV = ANALYSIS / "audio.wav"

# 1) extract audio (mono 16k for whisper)
subprocess.run(
    ["ffmpeg", "-y", "-i", str(ROOT / "reference" / "target.mp4"),
     "-vn", "-ac", "1", "-ar", "16000", str(WAV)],
    check=True,
)

# 2) RMS envelope via numpy (no librosa needed)
with wave.open(str(WAV), "rb") as w:
    sr = w.getframerate()
    frames = w.readframes(w.getnframes())
    data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
win = int(0.05 * sr)
n = len(data) // win
env = np.sqrt(np.mean(data[: n * win].reshape(n, win) ** 2, axis=1))
times = np.arange(n) * 0.05
envelope = [{"t": round(float(t), 3), "rms": round(float(v), 5)} for t, v in zip(times, env)]
(ANALYSIS / "envelope.json").write_text(json.dumps(envelope))

# 3) whisper transcription (word-level)
try:
    import whisper

    model = whisper.load_model("small.en")
    result = model.transcribe(str(WAV), word_timestamps=True, verbose=False,
                              language="en", condition_on_previous_text=False)
    words = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []) or []:
            words.append({"t": round(w["start"], 3), "end": round(w["end"], 3),
                          "word": w["word"].strip()})
    transcript = {
        "text": result.get("text", "").strip(),
        "language": result.get("language"),
        "segments": [
            {"start": round(s["start"], 3), "end": round(s["end"], 3),
             "text": s["text"].strip()}
            for s in result.get("segments", [])
        ],
        "words": words,
    }
except Exception as e:  # noqa: BLE001 - report and continue with envelope only
    transcript = {"error": str(e), "text": ""}

(ANALYSIS / "transcript.json").write_text(json.dumps(transcript, indent=2))
(ANALYSIS / "transcript.txt").write_text(transcript.get("text", ""))

print("segments:", len(transcript.get("segments", [])))
print("words:", len(transcript.get("words", [])))
print("text:", transcript.get("text", "")[:500])
sys.exit(0)

# push-trigger for ffmpeg fix
