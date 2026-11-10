"""Krok 10: walidacja modułów fizycznych na udokumentowanych zdarzeniach (dane spoza treningu ML).

  Upał:  3.07.2025 - PKP PLK: 133 pociągi opóźnione przez ograniczenia prędkości z powodu upału
         (odpowiedź na interpelację poselską, sejm.gov.pl z02575)
  Wiatr: 18-19.02.2022 - orkan Eunice: PKP PLK - 400 zdarzeń na sieci związanych z pogodą do godz. 18
         (Polsat News, 19.02.2022)
Pytanie: czy moduł wskazuje te dni jako wyjątkowe na tle wszystkich innych dni w danych?
Miara: % sieci w alarmie (P >= 0.5) danego dnia i ranking dnia wśród wszystkich dni.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from features import cell_daily, heat_risk, rail_temp, static_frame, wind_risk

ROOT = Path(__file__).resolve().parents[1]
W = ROOT / "data" / "raw" / "weather"
P = ROOT / "data" / "processed"
FIG = ROOT / "docs" / "fig"


def daily(files):
    st = static_frame(json.load(open(P / "segments_static.json")))
    w = pd.concat([cell_daily(json.load(open(W / f))) for f in files], ignore_index=True)
    df = st[["id", "cell"]].merge(w, on="cell")
    df["heat"] = heat_risk(df.tmax.values, df.sw.values)
    df["wind"] = wind_risk(df.gust.values)
    df["trail"] = rail_temp(df.tmax.values, df.sw.values)
    return df.groupby("date").agg(heat_pct=("heat", lambda s: (s >= 0.5).mean() * 100),
                                  wind_pct=("wind", lambda s: (s >= 0.5).mean() * 100),
                                  trail_max=("trail", "max"), gust_max=("gust", "max"))


def rank(series, day):
    v = series.loc[pd.Timestamp(day)]
    return float(v), float((series > v).sum() + 1), int(series.notna().sum())


def main():
    summer = daily(["2021.json", "2022.json", "2023.json", "2024.json", "event_summer_2025.json"])
    summer = summer[summer.index.month.isin([6, 7, 8])]
    allw = daily(["2021.json", "2022.json", "2023.json", "2024.json", "event_eunice_2022.json",
                  "event_summer_2025.json"])
    res = {}
    v, r, n = rank(summer.heat_pct, "2025-07-03")
    res["heat_2025_07_03"] = {"network_alarm_pct": v, "rank": r, "of_days": n,
                              "rail_temp_max": float(summer.trail_max.loc["2025-07-03"]),
                              "median_day_alarm_pct": float(summer.heat_pct.median())}
    for d in ("2022-02-18", "2022-02-19"):
        v, r, n = rank(allw.wind_pct, d)
        res[f"wind_{d}"] = {"network_alarm_pct": v, "rank": r, "of_days": n,
                            "gust_max_kmh": float(allw.gust_max.loc[d]),
                            "median_day_alarm_pct": float(allw.wind_pct.median())}
    json.dump(res, open(P / "module_validation.json", "w"), indent=1)
    print(json.dumps(res, indent=1))

    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.6), dpi=200)
    for ax, s, day, title, col in (
            (axs[0], summer.heat_pct, "2025-07-03", "Moduł wyboczeń: lata 2021–2025 (VI–VIII)", "#ff8a00"),
            (axs[1], allw.wind_pct, "2022-02-19", "Moduł wiatru: wszystkie dni w danych", "#3b82f6")):
        vals = np.sort(s.dropna().values)[::-1]
        ax.plot(np.arange(1, len(vals) + 1), vals, color="#9aa5b4", lw=1.2)
        v, r, n = rank(s, day)
        ax.scatter([r], [v], color=col, zorder=3, s=36)
        ax.annotate(f"{pd.Timestamp(day):%d.%m.%Y}\n#{int(r)} z {n} dni", (r, v), xytext=(r + n * 0.12, v * 0.85),
                    fontsize=8, arrowprops=dict(arrowstyle="-", color="#5b6676", lw=0.6))
        ax.set_xscale("log")
        ax.set_xlabel("ranking dnia (log)", fontsize=8)
        ax.set_ylabel("% sieci w alarmie", fontsize=8)
        ax.set_title(title, fontsize=8.5, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(color="#e3e7ee", lw=0.6)
    fig.tight_layout()
    fig.savefig(FIG / "module_validation.png")
    print("wykres ok")


if __name__ == "__main__":
    main()
