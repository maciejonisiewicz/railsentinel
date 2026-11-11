import json
import pickle
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "docs" / "fig"
FIG.mkdir(parents=True, exist_ok=True)
INK, MUTED, GRID = "#121821", "#5b6676", "#e3e7ee"
RED, ORANGE, BLUE, GREEN = "#e5484d", "#ff8a00", "#3b82f6", "#1f9d55"
plt.rcParams.update({"font.family": "Helvetica", "font.size": 10, "axes.edgecolor": GRID,
                     "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": 0.6})


def load_js(name):
    t = (ROOT / "web" / "data" / f"{name}.js").read_text(encoding="utf-8")
    return json.loads(re.search(r"\]=([\[{].*[\]}]);\s*$", t, re.S).group(1))


def fig_backtest():
    rp = load_js("replay2024")
    seg = load_js("segments")
    ids = [s["id"] for s in seg]
    dmg = set(rp["damaged"])
    di = [i for i, s in enumerate(ids) if s in dmg]
    other = [i for i in range(len(ids)) if ids[i] not in dmg]
    issues, frac_d, frac_o, maxp = [], [], [], []
    for it in rp["issues"]:
        fl = np.max([it["risk"][d]["flood"] for d in it["days"]], axis=0)
        p3 = np.max([it["risk"][d]["p3"] for d in it["days"]], axis=0)
        issues.append(pd.Timestamp(it["issued"]) - pd.Timedelta(days=1))
        frac_d.append((fl[di] >= 0.5).mean() * 100)
        frac_o.append((fl[other] >= 0.5).mean() * 100)
        maxp.append(p3[di].max())
    fig, ax = plt.subplots(figsize=(7.2, 3.2), dpi=200)
    x = np.arange(len(issues))
    ax.bar(x - 0.2, frac_d, 0.4, color=RED, label="odcinki faktycznie zniszczone")
    ax.bar(x + 0.2, frac_o, 0.4, color="#9aa5b4", label="pozostałe odcinki sieci")
    ax.set_xticks(x, [d.strftime("%d.%m") for d in issues])
    ax.set_xlabel("prognoza wydana wieczorem dnia")
    ax.set_ylabel("% odcinków w alarmie (72 h)")
    ax.axvspan(len(x) - 2.5, len(x) - 0.5, color="#ffb020", alpha=0.12, lw=0)
    ax.text(len(x) - 1.5, max(frac_d) * 1.02 + 1, "szczyt powodzi", ha="center", color=MUTED, fontsize=8.5)
    ax.legend(frameon=False, loc="upper left")
    ax.set_title("Backtest: alarmy na archiwalnych prognozach ECMWF przed powodzią 09.2024",
                 loc="left", fontsize=10.5, color=INK, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG / "backtest.png")
    plt.close(fig)


def fig_metrics():
    m = json.load(open(ROOT / "data" / "processed" / "metrics.json"))
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.6), dpi=200)
    items = [("PR-AUC (całość)", m["pr_auc_model"], m["pr_auc_baseline_p3"], True),
             ("AUC w strefie ulewy\n(dni powodzi)", m["event_auc_model"], m["event_auc_baseline"], True),
             ("% pozostałej sieci w alarmie\n(dni powodzi, czułość 80%)", m["other_alarm_pct_model"],
              m["other_alarm_pct_baseline"], False)]
    for ax, (t, a, b, hi) in zip(axs, items):
        ax.bar([0, 1], [b, a], color=["#9aa5b4", BLUE], width=0.6)
        ax.set_xticks([0, 1], ["reguła\nopadowa", "RailSentinel"])
        for i, v in enumerate([b, a]):
            ax.text(i, v, f"{v:.3f}" if v <= 1 else f"{v:.0f}%", ha="center", va="bottom", fontsize=9, color=INK)
        ax.set_title(t + ("\n(więcej = lepiej)" if hi else "\n(mniej = lepiej)"), fontsize=8.5, color=INK)
        ax.set_ylim(0, max(a, b) * 1.25 + 1e-6)
        ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(FIG / "metrics.png")
    plt.close(fig)


def fig_importance():
    imp = json.load(open(ROOT / "data" / "processed" / "importance.json"))
    from features import FEATURE_LABELS_PL
    items = sorted(imp.items(), key=lambda x: x[1])[-10:]
    fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=200)
    ax.barh([FEATURE_LABELS_PL[k] for k, _ in items], [v for _, v in items], color=BLUE)
    ax.set_xlabel("spadek PR-AUC po losowym przemieszaniu cechy (permutation importance)")
    ax.set_title("Co decyduje o ryzyku podmycia odcinka", loc="left", fontsize=10.5, color=INK, fontweight="bold")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(FIG / "importance.png")
    plt.close(fig)


def fig_rain():
    w = json.load(open(ROOT / "data" / "raw" / "weather" / "prev_runs_2024_09.json"))
    obs = json.load(open(ROOT / "data" / "raw" / "weather" / "2024.json"))
    cell = "50.25,16.75"
    h = pd.DataFrame(w[cell]["hourly"])
    h["date"] = pd.to_datetime(h["time"]).dt.normalize()
    d = h.groupby("date").sum(numeric_only=True).loc["2024-09-10":"2024-09-17"]
    o = pd.DataFrame(obs[cell]).set_index("time")["precipitation_sum"]
    o.index = pd.to_datetime(o.index)
    o = o.loc["2024-09-10":"2024-09-17"]
    fig, ax = plt.subplots(figsize=(7.2, 2.8), dpi=200)
    x = np.arange(len(d))
    ax.bar(x - 0.3, d["precipitation_previous_day3"], 0.2, color="#c7d2fe", label="prognoza 3 dni wcześniej")
    ax.bar(x - 0.1, d["precipitation_previous_day2"], 0.2, color="#818cf8", label="prognoza 2 dni wcześniej")
    ax.bar(x + 0.1, d["precipitation_previous_day1"], 0.2, color="#4f46e5", label="prognoza 1 dzień wcześniej")
    ax.bar(x + 0.3, o.values, 0.2, color=INK, label="obserwacja (ERA5)")
    ax.set_xticks(x, [t.strftime("%d.%m") for t in d.index])
    ax.set_ylabel("opad dobowy [mm]")
    ax.legend(frameon=False, fontsize=8, ncol=2)
    ax.set_title("Kotlina Kłodzka: ulewa była widoczna w prognozach z 3-dniowym wyprzedzeniem",
                 loc="left", fontsize=10.5, color=INK, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG / "rain_forecast.png")
    plt.close(fig)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    fig_backtest(); fig_metrics(); fig_importance(); fig_rain()
    print("ok", sorted(p.name for p in FIG.glob("*.png")))
