import json
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WYW = ROOT / "video" / "wywiady"
MODELE = ROOT / "video" / "modele"
OUT = WYW / "transkrypcje"


def fmt(t):
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:05.2f}"


def audio16k(f):
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(f), "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def run(model_name, files):
    from faster_whisper import WhisperModel
    model = WhisperModel(str(MODELE / f"faster-whisper-{model_name}"), device="cpu", compute_type="int8", cpu_threads=8)
    out = OUT / model_name
    out.mkdir(parents=True, exist_ok=True)
    for f in files:
        t0 = time.time()
        segs, info = model.transcribe(audio16k(f), language="pl", word_timestamps=True, beam_size=5, vad_filter=True,
                                      vad_parameters={"min_silence_duration_ms": 400}, condition_on_previous_text=False)
        rows = []
        for s in segs:
            rows.append({"od": round(s.start, 2), "do": round(s.end, 2), "tekst": s.text.strip(),
                         "slowa": [{"s": w.word.strip(), "od": round(w.start, 2), "do": round(w.end, 2),
                                    "p": round(w.probability, 2)} for w in (s.words or [])]})
        json.dump({"plik": f.name, "model": model_name, "dlugosc": round(info.duration, 2), "segmenty": rows},
                  open(out / f"{f.stem}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        with open(out / f"{f.stem}.txt", "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(f"[{fmt(r['od'])} - {fmt(r['do'])}] {r['tekst']}\n")
        print(f"{model_name} {f.name}: {len(rows)} segmentów, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    names = sys.argv[1].split(",") if len(sys.argv) > 1 else ["small"]
    files = sorted(WYW.glob("w*.mp4"))
    for n in names:
        run(n, files)
