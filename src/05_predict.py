"""Krok 5: predykcje dla dashboardu.

  live    - prognoza na dziś + 2 dni (Open-Meteo Forecast API, ostatnie 30 dni dla uwilgotnienia)
  replay  - backtest powodzi 09.2024 z PRAWDZIWYMI archiwalnymi prognozami (Previous Runs API, ECMWF IFS):
            prognoza "wydana wieczorem D-1" widzi tylko obserwacje do D-1 i prognozę na D..D+2
  y1997   - kontrola jakościowa: powódź tysiąclecia, lipiec 1997 (reanaliza)
  heat    - najgorętszy dzień w danych (demo modułu wyboczeń)

Wynik: web/data/*.js (window.RS_DATA[...] = {...}) - dashboard działa bez serwera, z pliku.
"""
import json
import pickle
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from features import (FEATURE_LABELS_PL, add_extreme, cell_daily, combine, heat_risk, ice_risk,
                      rail_temp, river_risk, static_frame, wind_risk)

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
WEB = ROOT / "web" / "data"
UA = {"User-Agent": "RailSentinel/0.2 (student research prototype)"}

segs = json.load(open(P / "segments_static.json"))
ST = static_frame(segs)
M = pickle.load(open(P / "flood_model.pkl", "rb"))
CELLS = sorted(ST["cell"].unique())
_HYD = None


def hyd_hist():
    """Historyczne stany wód (duży plik, potrzebny tylko w trybach archiwalnych – nie w codziennej prognozie)."""
    global _HYD
    if _HYD is None:
        _HYD = pickle.load(open(P / "hydro_daily.pkl", "rb"))[["id", "date", "h3"]]
    return _HYD
HM = json.load(open(P / "hydro_mapping.json"))
ST["exposure"] = ST["id"].map(HM["exposure"]).astype(float)

# Klimatologia opadu (q99 sumy 3-dniowej) dla komórek spoza regionu treningowego:
# regresja liniowa q99 ~ wysokość komórki, dopasowana na komórkach Dolnego Śląska i Opolszczyzny
_cell_elev = ST.groupby("cell")["elev"].mean()
_known = {c: v for c, v in M["clim_q99"].items() if c in _cell_elev}
_a, _b = np.polyfit([_cell_elev[c] for c in _known], list(_known.values()), 1)
CLIM = {c: float(M["clim_q99"].get(c, _a * e + _b)) for c, e in _cell_elev.items()}
print(f"klimatologia: {len(_known)} komórek z danych, {len(CLIM) - len(_known)} z regresji q99 = {_a:.4f}*elev + {_b:.1f}")
STM = json.load(open(P / "station_meta.json"))["meta"]


def get(url, params):
    wait = 30
    for _ in range(12):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=180)
        except requests.exceptions.RequestException as e:
            print("  błąd sieci, ponawiam:", type(e).__name__)
            time.sleep(wait); continue
        if r.status_code == 200:
            return r.json()
        print("  czekam", wait, r.text[:100])
        time.sleep(wait)
        wait = min(wait * 2, 600)
    raise RuntimeError("Open-Meteo niedostępne")


def fetch_cells(url, params, chunk=25, pause=10):
    out = {}
    for i in range(0, len(CELLS), chunk):
        if i % 100 == 0:
            print(f"  komórki {i}/{len(CELLS)}", flush=True)
        ch = CELLS[i:i + chunk]
        q = dict(params, latitude=",".join(c.split(",")[0] for c in ch),
                 longitude=",".join(c.split(",")[1] for c in ch))
        d = get(url, q)
        d = d if isinstance(d, list) else [d]
        for c, x in zip(ch, d):
            out[c] = x
        time.sleep(pause)
    return out


# ---------------------------------------------------------------- scoring

def explain(model, X, feats, n=3):
    """Lokalne wyjaśnienie: wpływ cechy = zmiana P po podstawieniu wartości 'typowej' (mediana tła)."""
    base = model.predict_proba(X)[:, 1]
    contrib = {}
    for f in feats:
        Xb = X.copy()
        Xb[f] = REF[f]
        contrib[f] = base - model.predict_proba(Xb)[:, 1]
    C = pd.DataFrame(contrib)
    tops = []
    for i in range(len(X)):
        row = C.iloc[i].sort_values(ascending=False)
        tops.append([[FEATURE_LABELS_PL[k], round(float(v), 3)] for k, v in row.head(n).items() if v > 0.002])
    return tops


REF = None


def score(df, out_of_fold=False):
    """df: segment x dzień z cechami => kolumny ryzyka.
    out_of_fold=True: każdy odcinek oceniany modelem, który NIE widział jego linii w treningu
    (uczciwy backtest na zdarzeniu, z którego pochodzą etykiety)."""
    global REF
    X = df[M["features"]].astype(float)
    if REF is None:
        REF = {f: float(X[f].median()) for f in M["features"]}
        REF.update({"p1": 2.0, "p3": 6.0, "p7": 14.0, "p_ante30": 55.0, "p3_extreme": 0.15})
    df = df.copy()
    if out_of_fold:
        r = np.zeros(len(df))
        fold = df["line"].astype(str).map(M["line_fold"]).fillna(-1).astype(int).values
        for k, m in enumerate(M["fold_models"]):
            sel = fold == k
            if sel.any():
                r[sel] = m.predict_proba(X[sel])[:, 1]
        sel = fold == -1
        if sel.any():
            r[sel] = M["model"].predict_proba(X[sel])[:, 1]
        df["r_flood"] = r
    else:
        df["r_flood"] = M["model"].predict_proba(X)[:, 1]
    # kalibracja do skali "alarmu": próg modelu => 0.5
    thr = M["threshold"]
    df["s_flood"] = 1 / (1 + np.exp(-(np.log(df["r_flood"] + 1e-9) - np.log(thr)) * 1.6))
    df["s_heat"] = heat_risk(df["tmax"].values, df["sw"].values)
    df["s_wind"] = wind_risk(df["gust"].values)
    df["s_ice"] = ice_risk(df["p1"].values, df["tmax"].values, df["tmin"].values, df["electrified"].values,
                           df["wcode"].values if "wcode" in df else None)
    if "h3" not in df:
        df["h3"] = np.nan
    df["s_river"] = river_risk(df["h3"].values, df["exposure"].values)
    df["s_water"] = combine(df["s_flood"].values, df["s_river"].values)  # podmycie (A) lub fala (B)
    df["s_total"] = combine(df["s_water"].values, df["s_heat"].values, df["s_wind"].values, df["s_ice"].values)
    df["t_rail"] = rail_temp(df["tmax"].values, df["sw"].values)
    hot = df["s_flood"] > 0.3
    df["why"] = None
    if hot.any():
        df.loc[hot, "why"] = pd.Series(explain(M["model"], X[hot.values], M["features"]), index=df.index[hot])
    riv = df["s_river"] > 0.3
    for i in df.index[riv]:
        w = df.at[i, "why"] if isinstance(df.at[i, "why"], list) else []
        df.at[i, "why"] = [["stan wody w rzece (IMGW) – fala wezbraniowa", round(float(df.at[i, "s_river"]), 3)]] + w
    return df


def pack(df, days, meta):
    """Kompaktowy JSON: dla każdego dnia lista wartości per odcinek (kolejność = segments)."""
    out = {"meta": meta, "days": [], "risk": {}}
    ids = ST["id"].tolist()
    for d in days:
        sub = df[df["date"] == pd.Timestamp(d)].set_index("id").reindex(ids)
        out["days"].append(str(d)[:10])
        out["risk"][str(d)[:10]] = {
            "total": sub["s_total"].round(3).fillna(0).tolist(),
            "flood": sub["s_water"].round(3).fillna(0).tolist(),
            "flash": sub["s_flood"].round(3).fillna(0).tolist(),
            "river": sub["s_river"].round(3).fillna(0).tolist(),
            "h3": sub["h3"].round(2).fillna(-9).tolist(),
            "heat": sub["s_heat"].round(3).fillna(0).tolist(),
            "wind": sub["s_wind"].round(3).fillna(0).tolist(),
            "ice": sub["s_ice"].round(3).fillna(0).tolist(),
            "p3": sub["p3"].round(1).fillna(0).tolist(),
            "p1": sub["p1"].round(1).fillna(0).tolist(),
            "gust": sub["gust"].round(0).fillna(0).tolist(),
            "trail": sub["t_rail"].round(1).fillna(0).tolist(),
            "why": [w if isinstance(w, list) else [] for w in sub["why"].tolist()],
        }
    return out


def frame_from_daily(daily_by_cell, hydro=None):
    """hydro: DataFrame (id, date, h3); domyślnie obserwacje IMGW z tego samego dnia (tryb archiwalny)."""
    w = cell_daily(daily_by_cell)
    w = add_extreme(w, CLIM)
    df = ST.merge(w, on="cell")
    return df.merge(hyd_hist() if hydro is None else hydro, on=["id", "date"], how="left")


def simplify(pts, tol=0.0006):
    """Douglas-Peucker (~60 m) - lżejsza mapa dla telefonów."""
    if len(pts) < 3:
        return pts
    a, b = np.array(pts[0]), np.array(pts[-1])
    P_ = np.array(pts)
    ab, ap = b - a, P_ - a
    d = np.abs(ab[0] * ap[:, 1] - ab[1] * ap[:, 0]) / (np.linalg.norm(ab) + 1e-12)
    i = int(np.argmax(d))
    if d[i] > tol:
        return simplify(pts[:i + 1], tol)[:-1] + simplify(pts[i:], tol)
    return [pts[0], pts[-1]]


def write_js(name, obj):
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / f"{name}.js").write_text(
        f"window.RS_DATA=window.RS_DATA||{{}};window.RS_DATA[{json.dumps(name)}]=" +
        json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print("zapisano", name)


# ---------------------------------------------------------------- tryby

DAILY = "precipitation_sum,temperature_2m_max,temperature_2m_min,wind_gusts_10m_max,shortwave_radiation_sum,weather_code"


def live():
    cache = RAW / "weather" / f"live_{date.today()}.json"
    if cache.exists():
        raw = json.load(open(cache))
    else:
        raw = fetch_cells("https://api.open-meteo.com/v1/forecast",
                          {"daily": DAILY, "past_days": 31, "forecast_days": 3, "timezone": "Europe/Warsaw"})
        json.dump(raw, open(cache, "w"))
    today = date.today()
    # bieżące stany wód z API IMGW (wodowskazy przypisane do odcinków), utrwalone na 3 dni
    hyd = pd.DataFrame(columns=["id", "date", "h3"])
    try:
        import river_fc
        api = {x["id_stacji"]: x for x in requests.get("https://danepubliczne.imgw.pl/api/data/hydro/",
                                                         headers=UA, timeout=60).json()}
        t = pd.Timestamp(today) - pd.Timedelta(days=1)
        cur, suspect = {}, []
        for code, m in STM.items():
            x = api.get(code)
            if not (x and x.get("stan_wody")):
                continue
            if x.get("stan_wody_data_pomiaru") and pd.Timestamp(x["stan_wody_data_pomiaru"]) < pd.Timestamp(today) - pd.Timedelta(days=2):
                continue  # pomiar nieaktualny
            h = (float(x["stan_wody"]) - m["q50"]) / (m["q99"] - m["q50"])
            ostrz = float(x["stan_ostrzegawczy"]) if x.get("stan_ostrzegawczy") else None
            # kontrola jakości: poniżej oficjalnego stanu ostrzegawczego IMGW - bez alarmu o fali;
            # bez stanów ostrzegawczych i skrajnie poza historią (np. nowe zero wodowskazu po odbudowie) - niepewne
            if (ostrz is not None and float(x["stan_wody"]) < ostrz) or (ostrz is None and h > 2.5):
                if h > 1.5:
                    suspect.append(x["stacja"])
                h = min(h, 1.5)
            cur[code] = h
        if suspect:
            print("kontrola jakości – odczyty ograniczone:", ", ".join(sorted(set(suspect))[:12]))
        # brak historii z ostatnich dni w API -> stan bieżący jako h(t), h(t-1), h(t-2) (trend = 0)
        W = pd.DataFrame([cur] * 3, index=pd.date_range(t - pd.Timedelta(days=2), t))
        cellp = {c: pd.DataFrame(x["daily"]).set_index("time")["precipitation_sum"] for c, x in raw.items()}
        rh, rf = {}, {1: {}, 2: {}, 3: {}}
        for code, m in STM.items():
            cell = f"{round(m['lat'] * 4) / 4},{round(m['lon'] * 4) / 4}"
            if cell in cellp:
                ser = cellp[cell]
                rh[code] = ser.reindex([d.strftime("%Y-%m-%d") for d in W.index]).values
                for k in (1, 2, 3):
                    rf[k][code] = float(np.nansum(ser.reindex([(today + timedelta(days=j)).strftime("%Y-%m-%d")
                                                               for j in range(k)]).values))
        RH = pd.DataFrame(rh, index=W.index)
        fcst = river_fc.forecast(W, RH, {k: pd.Series(v, dtype=float) for k, v in rf.items()}, t)
        cur_seg = {sid: cur.get(code, np.nan) for sid, code in HM["segment_station"].items()}
        hyd = river_fc.segments_h3(fcst, HM["segment_station"], t, cur_seg)
        print(f"rzeki: {len(cur)} wodowskazów z API, {hyd.id.nunique()} odcinków z prognozą fali")
    except Exception as e:  # brak API nie blokuje prognozy opadowej
        print("IMGW hydro / prognoza rzek niedostępne:", e)
    df = score(frame_from_daily({c: x["daily"] for c, x in raw.items()}, hydro=hyd))
    days = [today + timedelta(days=k) for k in range(3)]
    write_js("live", pack(df, days, {"title": "Prognoza bieżąca – cała Polska", "issued": str(today),
                                      "source": "Open-Meteo Forecast API (ECMWF/ICON/GFS) + IMGW hydro API + prognoza rzek ML"}))


def replay():
    """Backtest z archiwalnymi prognozami. Opad z Previous Runs API (ECMWF IFS 0.25°)."""
    cache = RAW / "weather" / "prev_runs_2024_09.json"
    if not cache.exists():
        raw = fetch_cells("https://previous-runs-api.open-meteo.com/v1/forecast",
                          {"hourly": "precipitation_previous_day1,precipitation_previous_day2,"
                                     "precipitation_previous_day3,temperature_2m_previous_day1",
                           "models": "ecmwf_ifs025", "start_date": "2024-09-05", "end_date": "2024-09-18",
                           "timezone": "Europe/Warsaw"}, pause=20)
        json.dump(raw, open(cache, "w"))
    raw = json.load(open(cache))
    obs = json.load(open(RAW / "weather" / "2024.json"))
    # prognozy dobowe sum opadu dla wyprzedzenia k dni
    fc = {}
    for c, x in raw.items():
        h = pd.DataFrame(x["hourly"])
        h["date"] = pd.to_datetime(h["time"]).dt.normalize()
        fc[c] = h.groupby("date").sum(numeric_only=True)

    issues = pd.date_range("2024-09-09", "2024-09-15")
    frames, timeline = [], []
    cells_r = [c for c in CELLS if c in obs and c in fc]
    # prognoza rzek (ML): historia stanów IMGW + opad z posterunków; opad przyszły z prognozy ECMWF
    import river_fc
    hist = pickle.load(open(P / "station_hidx.pkl", "rb"))
    srain = pickle.load(open(P / "station_rain.pkl", "rb"))
    st_cell = {c: f"{round(m['lat'] * 4) / 4},{round(m['lon'] * 4) / 4}" for c, m in STM.items()}
    for D in issues:
        # obserwacje do D-1, prognoza wydana wieczorem D-1 na D, D+1, D+2 (wyprzedzenie 1..3 dni)
        daily = {}
        for c in cells_r:
            o = pd.DataFrame(obs[c])
            o["time"] = pd.to_datetime(o["time"])
            o = o[o["time"] < D].copy()
            fut = []
            for k in range(3):
                T = D + pd.Timedelta(days=k)
                col = f"precipitation_previous_day{k + 1}"
                p = float(fc[c].loc[T, col]) if T in fc[c].index else 0.0
                base = pd.DataFrame(obs[c])
                base["time"] = pd.to_datetime(base["time"])
                rowT = base[base["time"] == T].iloc[0].to_dict()
                rowT["precipitation_sum"] = p  # opad WYŁĄCZNIE z prognozy (temperatury nieistotne dla modelu)
                fut.append(rowT)
            o = pd.concat([o, pd.DataFrame(fut)], ignore_index=True)
            o["time"] = o["time"].dt.strftime("%Y-%m-%d")
            daily[c] = o.to_dict(orient="list")
        # hydrologia: obserwacje IMGW do D-1, dalej utrwalenie stanu z D-1 (bez prognozy hydrologicznej)
        HYD = hyd_hist()
        past = HYD[HYD["date"] < D]
        t = D - pd.Timedelta(days=1)
        rf = {}
        for k in (1, 2, 3):
            ser = {}
            for code, cell in st_cell.items():
                if cell in fc:
                    ser[code] = sum(float(fc[cell].loc[D + pd.Timedelta(days=j), f"precipitation_previous_day{j + 1}"])
                                    for j in range(k) if (D + pd.Timedelta(days=j)) in fc[cell].index)
            rf[k] = pd.Series(ser, dtype=float)
        fcst = river_fc.forecast(hist, srain, rf, t)
        hp_seg = HYD[HYD["date"] == t].set_index("id")["h3"].to_dict()
        fut = river_fc.segments_h3(fcst, HM["segment_station"], t, hp_seg)
        df = score(frame_from_daily(daily, hydro=pd.concat([past, fut])), out_of_fold=True)
        df = df[df["date"] >= D]
        df["issued"] = D
        frames.append(df)
    allf = pd.concat(frames)
    pos = json.load(open(P / "positive_segments.json"))
    # które odcinki faktycznie zniszczone przekraczają alarm i z jakim wyprzedzeniem
    # wyprzedzenie = od wydania prognozy (wieczór D-1, ~20:00) do początku pierwszego dnia zniszczeń (14.09 00:00)
    first_damage = pd.Timestamp("2024-09-14 00:00")
    lead = {}
    for sid in pos:
        s = allf[(allf["id"] == sid) & (allf["date"].isin(pd.to_datetime(["2024-09-14", "2024-09-15", "2024-09-16"])))]
        hit = s[s["s_water"] >= 0.5]
        if len(hit):
            first = hit.sort_values("issued").iloc[0]
            released = first["issued"] - pd.Timedelta(hours=4)  # D 00:00 - 4 h = D-1 20:00
            lead[sid] = round((first_damage - released).total_seconds() / 3600)
    out = {"meta": {"title": "Powódź 09.2024 - backtest na archiwalnych prognozach ECMWF",
                    "note": "Prognoza wydana wieczorem dnia poprzedniego; opad wyłącznie z prognozy na D..D+2. "
                            "Model out-of-fold: odcinek oceniany modelem, który nie widział jego linii."},
           "issues": [], "lead_hours_by_segment": lead, "damaged": list(pos.keys())}
    for D in issues:
        sub = allf[allf["issued"] == D]
        days = [D + pd.Timedelta(days=k) for k in range(3)]
        out["issues"].append({"issued": str(D)[:10], **pack(sub, days, {})})
    # odsetek pozostałych (nieoznaczonych) odcinków w alarmie w dniach 14-15.09 wg prognozy z wieczora 13.09
    peak = allf[(allf["issued"] == pd.Timestamp("2024-09-14")) & (allf["date"].isin(pd.to_datetime(["2024-09-14", "2024-09-15"])))]
    mx = peak.groupby("id")["s_water"].max()
    mx_ml = peak.groupby("id")["s_flood"].max()
    ev = allf[allf["date"].isin(pd.to_datetime(["2024-09-14", "2024-09-15", "2024-09-16"]))]
    det_ml = set(ev[ev["s_flood"] >= 0.5]["id"]) & set(pos)
    out["summary"] = {
        "detected_ml_only": len(det_ml),
        "other_in_alarm_pct_ml_only": float((mx_ml[~mx_ml.index.isin(list(pos))] >= 0.5).mean() * 100),
        "damaged_segments": len(pos), "detected": len(lead),
        "median_lead_hours": float(np.median(list(lead.values()))) if lead else None,
        "max_lead_hours": max(lead.values()) if lead else None,
        "other_in_alarm_pct": float((mx[~mx.index.isin(list(pos))] >= 0.5).mean() * 100),
        "damaged_in_alarm_pct": float((mx[mx.index.isin(list(pos))] >= 0.5).mean() * 100),
    }
    write_js("replay2024", out)
    print(json.dumps(out["summary"]))


def from_archive(name, start, end, show_days, title):
    yr = start[:4]
    f = RAW / "weather" / f"{yr}.json"
    w = json.load(open(f))
    df = score(frame_from_daily(w))
    write_js(name, pack(df, pd.to_datetime(show_days), {"title": title, "source": "ERA5 (Open-Meteo Archive)"}))


def heat_demo():
    """Fala upałów lata 2025 dla CAŁEJ Polski (562 komórki, ERA5): najgorętszy dzień sieci +/- 1 dzień."""
    f = RAW / "weather" / "heat_pl_2025.json"
    if f.exists():
        raw = json.load(open(f))
    else:
        raw = fetch_cells("https://archive-api.open-meteo.com/v1/archive",
                          {"start_date": "2025-06-01", "end_date": "2025-07-15", "timezone": "Europe/Warsaw",
                           "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,wind_gusts_10m_max,"
                                    "shortwave_radiation_sum"}, chunk=10, pause=8)
        raw = {c: x["daily"] for c, x in raw.items()}
        json.dump(raw, open(f, "w"))
    w = cell_daily(raw)
    w["tr"] = rail_temp(w["tmax"], w["sw"])
    tr = w[w["date"] >= "2025-06-20"].groupby("date")["tr"].mean()
    d = pd.Timestamp(tr.idxmax())
    print("najgorętszy dzień sieci:", d.date(), round(tr.max(), 1), "°C szyny (średnio)")
    df = score(frame_from_daily(raw))
    write_js("heat", pack(df, [d - pd.Timedelta(days=1), d, d + pd.Timedelta(days=1)],
                          {"title": f"Fala upałów {d:%d.%m.%Y} – ryzyko wyboczeń toru, cała Polska",
                           "source": "ERA5 (Open-Meteo Archive)"}))


if __name__ == "__main__":
    modes = sys.argv[1:] or ["live", "replay", "y1997", "heat"]
    if "replay" in modes:
        replay()
    if "y1997" in modes and (RAW / "weather" / "1997.json").exists():
        from_archive("y1997", "1997-06-01", None, ["1997-07-07", "1997-07-09", "1997-07-13"],
                     "Powódź tysiąclecia 07.1997 – niezależny test")
    if "heat" in modes:
        heat_demo()
    if "live" in modes:
        live()
    # geometria odcinków dla mapy
    geo = [{"id": s["id"], "line": s["line"], "g": [simplify(l) for l in s["geometry"]], "river": s["river_name"],
            "place": s.get("place", ""), "cell": f"{round(s['lat'] * 4) / 4},{round(s['lon'] * 4) / 4}",
            "elev": round(s["elev"]), "len": s["length_km"]} for s in segs]
    write_js("segments", geo)
    json.dump(json.load(open(P / "metrics.json")), open(WEB / "metrics.json", "w"), indent=1)
    write_js("metrics", json.load(open(P / "metrics.json")))
