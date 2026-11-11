import re
import sys

import requests

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import build_video as bv

TEXT = ("Wrzesień, rok dwa tysiące dwudziesty czwarty. Ulewa w Sudetach. Woda zabiera trzysta metrów nasypu pod Kłodzkiem. "
        "RailSentinel ostrzegł przed tym odcinkiem pięćdziesiąt dwie godziny wcześniej.")


def main():
    if not bv.EL_KEY:
        sys.exit("Brak ELEVENLABS_API_KEY w pliku .env")
    h = {"xi-api-key": bv.EL_KEY}
    r = requests.get("https://api.elevenlabs.io/v1/voices", headers=h, timeout=60)
    r.raise_for_status()
    voices = {v["voice_id"]: v for v in r.json()["voices"]}
    ids = sys.argv[1:] or [k for k, v in voices.items() if v.get("category") != "premade"]
    if not ids:
        print("W „My Voices” nie ma jeszcze dodanych głosów. Głosy wbudowane:")
        for k, v in voices.items():
            print(f"  {v['name']:<28} {k}")
        return
    out = bv.V / "probki"
    out.mkdir(exist_ok=True)
    for vid in ids:
        name = re.sub(r"[^\w-]+", "_", voices.get(vid, {}).get("name", vid))[:40]
        f = out / f"el_{name}.mp3"
        bv.el_tts(TEXT, f, voice=vid)
        print(f"{name:<40} {vid}  ->  {f}")


if __name__ == "__main__":
    main()
