import math

import numpy as np
import pandas as pd

STATIC = ["tpi", "relief", "river_dist_km", "river_size", "bridge_share", "embankment_share", "elev"]
DYNAMIC = ["p1", "p3", "p7", "p_ante30", "p3_extreme"]
HYDRO = ["h_idx", "h3"]
FLOOD_FEATURES = DYNAMIC + STATIC

MONOTONIC = {"p1": 1, "p3": 1, "p7": 1, "p_ante30": 1, "p3_extreme": 1,
             "river_dist_km": -1, "tpi": -1, "river_size": 1, "h_idx": 1, "h3": 1}

FEATURE_LABELS_PL = {
    "p1": "opad w dniu", "p3": "opad 3-dniowy", "p7": "opad 7-dniowy",
    "p_ante30": "uwilgotnienie gruntu (opad 30 dni)", "p3_extreme": "ekstremalność opadu vs klimat",
    "h_idx": "stan wody w rzece (IMGW)", "h3": "stan wody - maks. 3 dni",
    "elev": "wysokość n.p.m.", "tpi": "położenie w dolinie (TPI)", "relief": "stromość terenu",
    "river_dist_km": "odległość od rzeki", "river_size": "wielkość rzeki", "bridge_share": "udział mostów",
    "embankment_share": "udział nasypów", "cutting_share": "udział przekopów", "tunnel_share": "udział tuneli",
    "electrified": "elektryfikacja", "maxspeed": "prędkość szlakowa", "main_line": "linia magistralna",
}


def static_frame(segs):
    df = pd.DataFrame([{k: s[k] for k in ("id", "line", "lat", "lon", "elev", "tpi", "relief",
                                          "river_dist_km", "river_size", "electrified", "maxspeed",
                                          "main_line", "length_km", "bridge_km", "embankment_km",
                                          "cutting_km", "tunnel_km", "river_name")} for s in segs])
    for k in ("bridge", "embankment", "cutting", "tunnel"):
        df[f"{k}_share"] = (df[f"{k}_km"] / df["length_km"]).clip(0, 1)
    df["cell"] = [f"{round(a * 4) / 4},{round(b * 4) / 4}" for a, b in zip(df.lat, df.lon)]
    return df


def cell_daily(weather_by_cell):
    rows = []
    for cell, d in weather_by_cell.items():
        t = pd.DataFrame(d)
        t["cell"] = cell
        rows.append(t)
    w = pd.concat(rows, ignore_index=True).rename(columns={
        "time": "date", "precipitation_sum": "p1", "temperature_2m_max": "tmax",
        "temperature_2m_min": "tmin", "wind_gusts_10m_max": "gust", "shortwave_radiation_sum": "sw",
        "weather_code": "wcode"})
    w["date"] = pd.to_datetime(w["date"])
    w = w.sort_values(["cell", "date"])
    w["p1"] = w["p1"].fillna(0)
    g = w.groupby("cell")["p1"]
    w["p3"] = g.transform(lambda s: s.rolling(3, min_periods=1).sum())
    w["p7"] = g.transform(lambda s: s.rolling(7, min_periods=1).sum())
    w["p_ante30"] = g.transform(lambda s: s.shift(3).rolling(27, min_periods=1).sum())
    return w


def add_extreme(w, clim_q99):
    w["p3_extreme"] = w["p3"] / w["cell"].map(clim_q99).fillna(w["p3"].quantile(0.99))
    return w


def rail_temp(tmax, sw_mj):
    return tmax + 0.75 * np.nan_to_num(sw_mj)


def heat_risk(tmax, sw_mj):
    tr = rail_temp(tmax, sw_mj)
    return 1 / (1 + np.exp(-(tr - 54) / 2.5))


def wind_risk(gust_kmh):
    return 1 / (1 + np.exp(-(np.nan_to_num(gust_kmh) - 85) / 7))


FREEZING_CODES = (56, 57, 66, 67)


def ice_risk(p1, tmax, tmin, electrified, wcode=None):
    tmax, tmin = np.asarray(tmax, dtype=float), np.asarray(tmin, dtype=float)
    near_zero = np.exp(-((tmax + tmin) / 2) ** 2 / 3) * (tmin < 0.0) * (tmax > -2.0)
    wet = 1 - np.exp(-np.nan_to_num(p1) / 4)
    elec = 0.3 + 0.7 * np.asarray(electrified, dtype=float)
    proxy = np.minimum(0.15, near_zero * wet * elec)
    if wcode is not None:
        w = np.nan_to_num(np.asarray(wcode, dtype=float), nan=-1)
        frz = np.isin(w, FREEZING_CODES)
        return np.where(frz, 0.85 * elec / (0.3 + 0.7), proxy)
    return proxy


def river_risk(h3, exposure):
    h = np.nan_to_num(np.asarray(h3, dtype=float), nan=-9)
    e = np.nan_to_num(np.asarray(exposure, dtype=float), nan=0)
    return e / (1 + np.exp(-(h - 2.0) / 0.25))


def combine(*ps):
    q = np.ones_like(ps[0], dtype=float)
    for p in ps:
        q *= (1 - np.clip(p, 0, 1))
    return 1 - q


def hav_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def dist_to_polyline_km(lat, lon, pts):
    if len(pts) == 1:
        return hav_km(lat, lon, *pts[0])
    best = 1e9
    for (a, b), (c, d) in zip(pts[:-1], pts[1:]):
        n = max(2, int(hav_km(a, b, c, d) / 0.2))
        for t in np.linspace(0, 1, n):
            best = min(best, hav_km(lat, lon, a + t * (c - a), b + t * (d - b)))
    return best
