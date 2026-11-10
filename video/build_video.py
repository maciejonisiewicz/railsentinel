"""Montaż filmu prezentacyjnego RailSentinel (MP4 1920x1080, ok. 4 min).

1. Lektor: polski głos systemowy macOS (say) + obróbka (EQ, kompresja, delikatny pogłos).
2. Sceny: animowane plansze (video/scenes.html) i nagrania PRAWDZIWEJ aplikacji (Playwright + Chrome).
3. Montaż: płynne przejścia (xfade), muzyka skomponowana algorytmicznie (bez praw autorskich osób trzecich),
   automatyczne ściszanie muzyki pod lektorem (ducking), normalizacja głośności (EBU R128).
Uruchomienie: .venv/bin/python video/build_video.py   (wymaga serwera: python -m http.server 8765 w katalogu projektu)
"""
import json
import re
import shutil
import subprocess
import time
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "video"
TMP = V / "build"
FF = imageio_ffmpeg.get_ffmpeg_exe()
BASE = "http://127.0.0.1:8765"
SR = 48000
XF = 0.7          # długość przejścia [s]
LEAD, TAIL = 0.6, 0.9


def ff(*a):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", *a], check=True)


def metrics():
    m = json.load(open(ROOT / "data" / "processed" / "metrics.json"))
    rm = json.load(open(ROOT / "data" / "processed" / "river_metrics.json"))
    t = (ROOT / "web" / "data" / "replay2024.js").read_text()
    rp = json.loads(re.search(r"\]=(\{.*\});\s*$", t, re.S).group(1))["summary"]
    k2 = rm["test2024_flood_k2"]
    segs = json.load(open(ROOT / "data" / "processed" / "segments_static.json"))
    return {"det": rp["detected"], "dam": rp["damaged_segments"], "lead": int(rp["median_lead_hours"]),
            "s97": m["test1997_sites_detected_system"], "pod_p": round(k2["pod_persist"] * 100),
            "pod_s": round(k2["pod_system"] * 100),
            "gain": round((k2["pod_system"] / k2["pod_persist"] - 1) * 100), "stations": rm["stations"],
            "nseg": len(segs)}


def script(v):
    """(id, typ, tekst lektora, podpis). Liczby z aktualnych wyników."""
    return [
        ("intro", "html", "Każdego dnia po polskich torach jeżdżą tysiące pociągów. Ale tor nie jest odporny na pogodę. "
                          "Oto RailSentinel: system, który mówi, który odcinek toru sprawdzić, zanim pogoda go uszkodzi.", None),
        ("y1997", "html", "Lipiec, rok tysiąc dziewięćset dziewięćdziesiąty siódmy. Powódź tysiąclecia. Fala na Odrze niszczy "
                          "mosty kolejowe w Kędzierzynie-Koźlu, Krapkowicach i Brzegu Dolnym. Część tych zniszczeń ogranicza ruch do dziś.", None),
        ("y2024", "html", "Wrzesień, rok dwa tysiące dwudziesty czwarty. Ulewa w Sudetach. Woda zabiera trzysta metrów nasypu pod Kłodzkiem "
                          "i niszczy tory pod Nysą i Głuchołazami. Wstępne straty infrastruktury: osiemset osiemdziesiąt milionów złotych. "
                          "A prognozy pokazywały tę ulewę trzy dni wcześniej.", None),
        ("problem", "html", "Problem nie polega na braku danych. Ostrzeżenia pogodowe wydaje się dla powiatów, a stany rzek dla wodowskazów. "
                            "Nikt nie mówi dyżurnemu: jutro wieczorem zagrożony jest ten konkretny odcinek linii.", None),
        ("live", "app", f"RailSentinel robi to automatycznie, dla całej Polski. Ponad {v['nseg']} odcinków sieci, na siedemdziesiąt dwie godziny "
                        "do przodu: podmycie toru, fala na rzece, wyboczenie w upale, wichura i oblodzenie sieci.",
         "Cała Polska · prognoza na 72 h"),
        ("how", "html", "Pod spodem pracują dwa modele uczenia maszynowego. Pierwszy ocenia, czy ulewa podmyje tor: opad, nasycenie gruntu, "
                        f"położenie w dolinie, mosty i nasypy. Drugi prognozuje stany rzek z {v['stations']} wodowskazów IMGW i sam odkrywa, "
                        "które wodowskazy w górnym biegu zapowiadają nadchodzącą falę.", None),
        ("replay", "app", "Sprawdźmy to na prawdziwej powodzi. System dostaje tylko to, co było wiadomo wtedy: archiwalne prognozy ECMWF. "
                          "Wieczorem jedenastego września zapala alarmy dokładnie tam, gdzie dwa dni później woda zniszczyła tory. "
                          f"{v['det']} z {v['dam']} odcinków, ponad dwie doby wcześniej.", "Backtest: powódź 09.2024 na archiwalnych prognozach"),
        ("popup", "app", "Każdy alarm ma wyjaśnienie. Dyżurny widzi, dlaczego właśnie ten odcinek, i co zrobić: obchód przed pierwszym pociągiem, "
                         "ograniczenie prędkości, gotowość sprzętu.", "Wyjaśnialna AI: dlaczego ten odcinek?"),
        ("t1997", "app", "A najtrudniejszy test? Powódź z tysiąc dziewięćset dziewięćdziesiątego siódmego roku, której model nigdy nie widział. "
                         f"System wskazuje {'wszystkie trzy' if v['s97'] == 3 else 'dwa z trzech'} udokumentowane miejsca zniszczeń.",
         "Niezależny test: powódź 1997"),
        ("river", "html", f"Nowa prognoza rzek daje dodatkowy czas. Z dwudniowym wyprzedzeniem wykrywa o {v['gain']} procent więcej "
                          "przekroczeń stanu wody niż założenie, że rzeka się nie zmieni.", None),
        ("sim", "app", "W symulatorze można przećwiczyć każdy scenariusz. Stawiam ulewę w Karkonoszach. Podnoszę stan Odry. "
                       "I włączam scenariusz klimatyczny: opady mocniejsze o dwadzieścia procent to ponad dwa razy więcej kilometrów toru do sprawdzenia.",
         "Symulator: model ML działa w przeglądarce"),
        ("phone", "phone", "Dla ludzi w terenie jest Moja linia. Instalujesz aplikację na telefonie, wybierasz swoją linię albo klikasz "
                           "Gdzie jestem, i widzisz każdy odcinek na trzy dni. Działa także bez zasięgu.", None),
        ("whom", "html", "RailSentinel rozwiązuje problemy dyżurnych ruchu, zakładów linii kolejowych, sztabów kryzysowych i planistów inwestycji. "
                         "Wszystko na otwartych danych, bez montowania czegokolwiek w torze.", None),
        ("outro", "html", "RailSentinel. Wiesz, który tor sprawdzić, zanim pogoda go uszkodzi.", None),
    ]


# ---------------------------------------------------------------- lektor
def tts(i, text):
    aiff, wav = TMP / f"v{i:02d}.aiff", TMP / f"v{i:02d}.wav"
    subprocess.run(["say", "-v", "Zosia", "-r", "168", "-o", str(aiff), text], check=True)
    # obróbka: filtr dolnoprzepustowy szumu, ocieplenie, obecność, kompresja, delikatny pogłos
    ff("-i", str(aiff), "-af",
       "highpass=f=90,equalizer=f=180:t=q:w=1:g=2.5,equalizer=f=3200:t=q:w=1.2:g=3,"
       "acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=4,"
       "aecho=0.85:0.6:38|71:0.10|0.06,aresample=48000", "-ac", "1", str(wav))
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def read_wav(p):
    with wave.open(str(p)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return x


# ---------------------------------------------------------------- muzyka (synteza)
def music(dur):
    """Ambient/elektronika ~92 BPM: pad (detuned saw + filtr), arpeggio, miękki kick, hi-hat. Am-F-C-G."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    bpm, beat = 92, 60 / 92
    bar = 4 * beat
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]   # Am F C G (MIDI)
    f = lambda m: 440 * 2 ** ((m - 69) / 12)
    rng = np.random.default_rng(3)
    # pad
    for ci in range(int(dur / bar) + 2):
        s, e = int(ci * bar * SR), min(n, int((ci + 1) * bar * SR + 0.4 * SR))
        if s >= n:
            break
        tt = np.arange(e - s) / SR
        env = np.minimum(1, tt / 0.8) * np.minimum(1, (e - s) / SR - tt + 0.05)
        sig = np.zeros(e - s)
        for m in chords[ci % 4]:
            for det in (-0.08, 0.08):
                ph = 2 * np.pi * f(m - 12) * (1 + det / 100) * tt
                sig += 0.5 * np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph)
        out[s:e] += 0.035 * sig * env
    # arpeggio (od 8. s), ósemki
    step = beat / 2
    for k in range(int(dur / step)):
        st0 = k * step
        if st0 < 8 or st0 > dur - 6:
            continue
        ch = chords[int(st0 / bar) % 4]
        m = ch[k % 3] + (12 if (k // 3) % 2 else 0)
        s = int(st0 * SR); L = int(0.45 * SR)
        if s + L >= n:
            break
        tt = np.arange(L) / SR
        out[s:s + L] += 0.03 * np.sin(2 * np.pi * f(m) * tt) * np.exp(-tt * 7)
    # kick + hat (od 16. s do końca - 8 s)
    for k in range(int(dur / beat)):
        st0 = k * beat
        if st0 < 16 or st0 > dur - 8:
            continue
        s = int(st0 * SR); L = int(0.35 * SR)
        tt = np.arange(L) / SR
        out[s:s + L] += 0.09 * np.sin(2 * np.pi * (50 + 70 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 9)
        h = int((st0 + beat / 2) * SR); HL = int(0.06 * SR)
        if h + HL < n:
            out[h:h + HL] += 0.012 * rng.standard_normal(HL) * np.exp(-np.arange(HL) / SR * 60)
    # wygładzenie i fade in/out
    out = np.convolve(out, np.ones(3) / 3, mode="same").astype(np.float32)
    fade = np.ones(n, np.float32)
    fi, fo = int(2.5 * SR), int(4 * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    return out * fade


# ---------------------------------------------------------------- nagrania scen
CAPTION_JS = """(txt) => { const d = document.createElement('div'); d.id='rsCap'; d.textContent = txt;
  Object.assign(d.style, {position:'fixed', left:'40px', bottom:'40px', zIndex: 99999, background:'rgba(7,10,15,.82)',
  color:'#fff', font:'700 30px Inter, sans-serif', padding:'16px 26px', borderRadius:'16px', borderLeft:'8px solid #ffb020',
  boxShadow:'0 20px 60px rgba(0,0,0,.5)', opacity: 0, transform:'translateY(20px)', transition:'all .7s cubic-bezier(.2,.8,.2,1)'});
  document.body.appendChild(d); setTimeout(() => { d.style.opacity = 1; d.style.transform = 'none'; }, 300); }"""


def record(sid, kind, dur, caption, v):
    from playwright.sync_api import sync_playwright
    done = TMP / f"s_{sid}.mp4"
    if done.exists() and abs(float(subprocess.run([FF, "-i", str(done)], capture_output=True, text=True).stderr
                                     .split("Duration: ")[1].split(",")[0].split(":")[2]) - dur) < 0.15:
        return done   # scena już nagrana (ten sam czas trwania)
    out = TMP / f"rec_{sid}"
    shutil.rmtree(out, ignore_errors=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--force-color-profile=srgb"])
        ctx = b.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
                            record_video_dir=str(out), record_video_size={"width": 1920, "height": 1080},
                            color_scheme="dark")
        t0 = time.time()
        pg = ctx.new_page()
        q = "&v=" + json.dumps(v).replace(" ", "")
        if kind == "html":
            pg.goto(f"{BASE}/video/scenes.html?scene={sid}{q}")
            pg.wait_for_timeout(900)
            start = time.time() - t0
            pg.reload()   # restart animacji od zera w nagraniu
            start = time.time() - t0
            pg.wait_for_timeout(int(dur * 1000) + 200)
        elif kind == "phone":
            pg.goto(f"{BASE}/video/phone.html")
            pg.wait_for_timeout(2500)
            start = time.time() - t0 - 1.6
            fr = pg.frame_locator("#f")
            pg.wait_for_timeout(int(dur * 400))
            pg.evaluate("document.getElementById('f').contentWindow.scrollTo({top: 560, behavior: 'smooth'})")
            pg.wait_for_timeout(int(dur * 600) + 300)
        else:
            urls = {"live": "#mode=live&theme=dark&hz=total",
                    "replay": "#mode=replay2024&theme=dark&issue=0&day=1&lat=50.45&lon=16.95&z=9",
                    "popup": "#mode=replay2024&theme=dark&issue=4&day=1&lat=50.40&lon=16.75&z=11&popup=1",
                    "t1997": "#mode=y1997&theme=dark&day=0&lat=50.75&lon=17.2&z=8",
                    "sim": "#mode=sim&theme=dark&preset=clear&lat=50.95&lon=16.4&z=8"}
            pg.goto(f"{BASE}/web/index.html{urls[sid]}")
            pg.wait_for_timeout(2600)
            if caption:
                pg.evaluate(CAPTION_JS, caption)
            start = time.time() - t0
            ms = int(dur * 1000)
            if sid == "live":
                pg.evaluate("void RS_MAP.setView([52.0, 19.2], 6, {animate:false})")
                pg.wait_for_timeout(int(ms * 0.35))
                pg.evaluate("void RS_MAP.flyTo([50.5, 16.8], 9, {duration: 5})")
                pg.wait_for_timeout(int(ms * 0.65))
            elif sid == "replay":
                pg.click("#play")
                pg.wait_for_timeout(ms)
            elif sid == "popup":
                pg.wait_for_timeout(ms)
            elif sid == "t1997":
                for d in (0, 1, 2):
                    pg.click(f"#days button[data-d='{d}']")
                    pg.wait_for_timeout(int(ms / 3))
            elif sid == "sim":
                third = ms / 3
                pg.click("#presets button[data-p='storm']")
                pg.wait_for_timeout(int(third * 0.5))
                for val in (120, 150, 180):
                    pg.evaluate(f"(()=>{{const e=document.querySelector('#sRain'); e.value={val}; e.dispatchEvent(new Event('input'));}})()")
                    pg.wait_for_timeout(int(third * 0.17))
                pg.click("#presets button[data-p='odra']")
                pg.wait_for_timeout(int(third))
                pg.click("#presets button[data-p='storm']")
                pg.wait_for_timeout(300)
                for val in (5, 10, 15, 20):
                    pg.evaluate(f"(()=>{{const e=document.querySelector('#sClim'); e.value={val}; e.dispatchEvent(new Event('input'));}})()")
                    pg.wait_for_timeout(int(third * 0.22))
                pg.wait_for_timeout(400)
        pg.wait_for_timeout(400)
        ctx.close()
        b.close()
    webm = next(out.glob("*.webm"))
    mp4 = TMP / f"s_{sid}.mp4"
    ff("-ss", f"{max(0, start):.2f}", "-i", str(webm), "-t", f"{dur:.2f}", "-vf", "fps=30,scale=1920:1080,setsar=1",
       "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-an", str(mp4))
    return mp4


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    (V / "img").mkdir(exist_ok=True)
    shutil.copy(ROOT / "docs" / "fig" / "screen_1997.png", V / "img" / "screen_1997.png")
    import qrcode
    qrcode.make("https://railsentinel.pl").save(V / "img" / "qr.png")
    v = metrics()
    print("liczby:", v)
    sc = script(v)
    durs, clips = [], []
    for i, (sid, kind, text, cap) in enumerate(sc):
        d = tts(i, text)
        dur = LEAD + d + TAIL
        durs.append(dur)
        print(f"scena {sid}: lektor {d:.1f} s -> {dur:.1f} s", flush=True)
        clips.append(record(sid, kind, dur, cap, v))
    # --- wideo z przejściami
    trans = ["fade", "smoothleft", "fadeblack", "circleopen", "slideleft", "fade", "smoothup", "fade",
             "wipeleft", "fade", "smoothleft", "circleopen", "fadeblack"]
    inputs = sum([["-i", str(c)] for c in clips], [])
    fc, last, acc = [], "[0:v]", durs[0]
    for i in range(1, len(clips)):
        off = acc - XF
        lab = f"[x{i}]"
        fc.append(f"{last}[{i}:v]xfade=transition={trans[(i - 1) % len(trans)]}:duration={XF}:offset={off:.3f}{lab}")
        last, acc = lab, acc + durs[i] - XF
    total = acc
    ff(*inputs, "-filter_complex", ";".join(fc), "-map", last, "-c:v", "libx264", "-preset", "medium", "-crf", "21",
       "-pix_fmt", "yuv420p", str(TMP / "video_noaudio.mp4"))
    # --- audio: lektor w miejscach scen + muzyka z duckingiem
    n = int(total * SR) + SR
    voice = np.zeros(n, np.float32)
    start = 0.0
    for i, d in enumerate(durs):
        x = read_wav(TMP / f"v{i:02d}.wav")
        s = int((start + LEAD) * SR)
        voice[s:s + len(x)] += x[: max(0, n - s)]
        start += d - XF
    mus = music(n / SR)
    env = np.convolve(np.abs(voice), np.ones(int(0.25 * SR)) / int(0.25 * SR), mode="same")
    env = np.clip(env / (env.max() + 1e-9) * 4, 0, 1)
    env = np.convolve(env, np.ones(int(0.4 * SR)) / int(0.4 * SR), mode="same")
    mix = voice * 0.95 + mus * (1.0 - 0.62 * env) * 2.4
    mix = np.clip(mix / max(1e-9, np.abs(mix).max()) * 0.9, -1, 1)
    with wave.open(str(TMP / "mix.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    ff("-i", str(TMP / "video_noaudio.mp4"), "-i", str(TMP / "mix.wav"), "-filter:a", "loudnorm=I=-16:TP=-1.5:LRA=11",
       "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-shortest", "-movflags", "+faststart",
       str(V / "RailSentinel_film.mp4"))
    ff("-ss", "3", "-i", str(V / "RailSentinel_film.mp4"), "-frames:v", "1", "-q:v", "3", str(V / "poster.jpg"))
    print(f"GOTOWE: {V / 'RailSentinel_film.mp4'}  ({total:.0f} s)")


if __name__ == "__main__":
    main()
