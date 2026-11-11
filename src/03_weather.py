import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SEG = ROOT / "data" / "processed" / "segments_static.json"
CACHE = ROOT / "data" / "raw" / "weather"
UA = {"User-Agent": "RailSentinel/0.1 (student research prototype)"}
DAILY = ["precipitation_sum", "temperature_2m_max", "temperature_2m_min",
         "wind_gusts_10m_max", "shortwave_radiation_sum"]


def cell_of(lat, lon):
    return round(lat * 4) / 4, round(lon * 4) / 4


def cells():
    segs = json.load(open(SEG))
    return sorted({cell_of(s["lat"], s["lon"]) for s in segs})


def get(url, params):
    wait = 30
    while True:
        r = requests.get(url, params=params, headers=UA, timeout=180)
        if r.status_code == 200:
            return r.json()
        msg = r.text
        if "Daily" in msg:
            raise SystemExit(f"Dzienny limit API wyczerpany: {msg}")
        print("  limit/błąd, czekam", wait, "s:", msg[:120])
        time.sleep(wait)
        wait = min(wait * 2, 900)


def fetch_period(start, end, out_file, url="https://archive-api.open-meteo.com/v1/archive", extra=None):
    if out_file.exists():
        print("cache:", out_file.name)
        return
    cs = cells()
    result = {}
    for i in range(0, len(cs), 25):
        chunk = cs[i:i + 25]
        params = {"latitude": ",".join(str(c[0]) for c in chunk),
                  "longitude": ",".join(str(c[1]) for c in chunk),
                  "start_date": start, "end_date": end,
                  "daily": ",".join(DAILY), "timezone": "Europe/Warsaw"}
        params.update(extra or {})
        data = get(url, params)
        data = data if isinstance(data, list) else [data]
        for c, d in zip(chunk, data):
            result[f"{c[0]},{c[1]}"] = d["daily"]
        print(f"  {out_file.stem}: {min(i + 25, len(cs))}/{len(cs)} komórek")
        time.sleep(50)
    CACHE.mkdir(parents=True, exist_ok=True)
    json.dump(result, open(out_file, "w"))


if __name__ == "__main__":
    for y in sys.argv[1:]:
        fetch_period(f"{y}-03-01", f"{y}-10-31", CACHE / f"{y}.json")
