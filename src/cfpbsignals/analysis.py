"""Charts + statistics for the README:  PYTHONPATH=src python -m cfpbsignals.analysis"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from . import config

plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.3, "font.size": 9})
NAVY, ORANGE, GREY = "#1B3A5C", "#E07B39", "#8A9099"
P = config.PROCESSED


def load():
    vol = pd.read_csv(P / "q_volume.csv", parse_dates=["quarter"])
    top = pd.read_csv(P / "q_topics.csv", parse_dates=["quarter"])
    tmpl = pd.read_csv(P / "q_templates.csv", parse_dates=["quarter"])
    panel = pd.read_csv(P / "signal_panel.csv", parse_dates=["quarter"])
    top["label"] = top["topic"].map(dict(enumerate(config.TOPIC_LABELS)))
    return vol, top, tmpl, panel


def fig_volume(vol: pd.DataFrame) -> None:
    tickers = vol.groupby("ticker").n_complaints.sum().sort_values(ascending=False).index
    fig, axes = plt.subplots(2, 5, figsize=(13, 5), sharex=True)
    for ax, t in zip(axes.flat, tickers):
        d = vol[vol.ticker == t]
        ax.bar(d.quarter, d.n_complaints / 1000, width=80, color=NAVY)
        ax.set_title(t, fontweight="bold")
        ax.tick_params(axis="x", rotation=45)
    for ax in axes[:, 0]:
        ax.set_ylabel("complaints per quarter (000s)")
    fig.suptitle("CFPB complaints per quarter, 2018 Q3 - 2026 Q2 (all complaints, archive full records)")
    fig.tight_layout()
    fig.savefig(config.FIGURES / "complaint_volume_by_company.png")
    plt.close(fig)


def fig_coverage(vol: pd.DataFrame) -> None:
    g = vol.groupby("quarter").agg(n=("n_complaints", "sum"), narr=("n_narratives", "sum"))
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(g.index, g.narr / g.n * 100, "-o", ms=3, color=ORANGE)
    ax.axvspan(pd.Timestamp(config.TOPIC_END), g.index.max() + pd.Timedelta(days=60), color=GREY, alpha=0.2)
    ax.text(pd.Timestamp(config.TOPIC_END) + pd.Timedelta(days=10), 5, "excluded from\ntopic analysis", fontsize=8)
    ax.set_ylabel("% of complaints with a public narrative")
    ax.set_ylim(0, 100)
    ax.set_title("Share of complaints with a published narrative, 10-company universe\n(falls in late 2025-2026; CFPB stopped publishing narratives on 2026-08-14)")
    fig.tight_layout()
    fig.savefig(config.FIGURES / "narrative_coverage.png")
    plt.close(fig)


def fig_topic_trends(top: pd.DataFrame) -> None:
    w = top.assign(wt=top.topic_share * top.n_docs).groupby(["quarter", "label"]).wt.sum().unstack()
    w = w.div(w.sum(axis=1), axis=0) * 100
    w = w[w.mean().sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.stackplot(w.index, w.T.values, labels=w.columns, colors=plt.cm.tab20.colors[: w.shape[1]], alpha=0.9)
    ax.set_xlim(w.index.min(), w.index.max())
    ax.set_ylim(0, 100)
    ax.set_ylabel("share of narrative topic weight (%)")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=8)
    ax.set_title("What are customers complaining about? NMF topic mix, 10 banks & fintechs, by quarter")
    fig.tight_layout()
    fig.savefig(config.FIGURES / "topic_trends.png")
    plt.close(fig)


def fig_topic_company(top: pd.DataFrame, start="2024-01-01", end="2025-12-31") -> pd.DataFrame:
    d = top[(top.quarter >= start) & (top.quarter <= end)]
    m = d.assign(wt=d.topic_share * d.n_docs).groupby(["ticker", "label"]).wt.sum().unstack()
    m = m.div(m.sum(axis=1), axis=0) * 100
    m = m[config.TOPIC_LABELS]
    fig, ax = plt.subplots(figsize=(11, 4.8))
    im = ax.imshow(m.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(m.shape[1]), m.columns, rotation=35, ha="right")
    ax.set_yticks(range(m.shape[0]), m.index)
    ax.grid(False)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.values[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7, color="white" if v > 25 else "black")
    fig.colorbar(im, ax=ax, label="% of company's narrative topic weight")
    ax.set_title("Topic mix by company, 2024-2025 (each row sums to 100%)")
    fig.tight_layout()
    fig.savefig(config.FIGURES / "topic_mix_by_company.png")
    plt.close(fig)
    return m


def quarterly_long_short(panel: pd.DataFrame, signal: str, outcome: str, k: int = 3) -> pd.DataFrame:
    """Each quarter: mean outcome of the k LOWEST-signal names minus the k HIGHEST-signal names."""
    rows = []
    for q, g in panel.dropna(subset=[signal, outcome]).groupby("quarter"):
        if len(g) < 2 * k:
            continue
        g = g.sort_values(signal)
        rows.append({"quarter": q, "spread": g[outcome].head(k).mean() - g[outcome].tail(k).mean(), "n": len(g)})
    return pd.DataFrame(rows)


def signal_tests(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sig, slab in (("vol_yoy_log", "Complaint volume, YoY log growth"),
                      ("vol_qoq_log", "Complaint volume, QoQ log growth"),
                      ("untimely_share", "Share of untimely company responses")):
        for out, olab in (("xret_same_q", "same quarter"), ("xret_next_q", "next quarter"),
                          ("xret_q_plus_2", "quarter after next")):
            d = panel.dropna(subset=[sig, out]).copy()
            rho, p = stats.spearmanr(d[sig], d[out])
            d["rs"] = d.groupby("quarter")[sig].rank(pct=True)
            d["ro"] = d.groupby("quarter")[out].rank(pct=True)
            rho_q, p_q = stats.spearmanr(d.rs, d.ro)
            ls = quarterly_long_short(panel, sig, out)
            t, p_ls = stats.ttest_1samp(ls.spread, 0) if len(ls) > 2 else (np.nan, np.nan)
            rows.append({"signal": slab, "excess return (vs XLF)": olab, "n_obs": len(d),
                         "spearman": rho, "p": p, "spearman_within_quarter": rho_q, "p_within_q": p_q,
                         "long_low_short_high_mean_spread": ls.spread.mean(), "spread_t": t, "spread_p": p_ls,
                         "hit_rate": (ls.spread > 0).mean(), "quarters": len(ls)})
    return pd.DataFrame(rows)


def fig_signal(panel: pd.DataFrame) -> None:
    ls = quarterly_long_short(panel, "vol_yoy_log", "xret_next_q")
    d = panel.dropna(subset=["vol_yoy_log", "xret_next_q"]).copy()
    d["tercile"] = d.groupby("quarter").vol_yoy_log.transform(lambda x: pd.qcut(x.rank(method="first"), 3, labels=False) + 1)
    g = d.groupby("tercile").xret_next_q.agg(["mean", "sem", "count"])
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    ax[0].bar(range(3), g["mean"] * 100, yerr=g["sem"] * 100, capsize=4, color=[NAVY, GREY, ORANGE])
    ax[0].axhline(0, color="black", lw=0.8)
    ax[0].set_xticks(range(3), [f"Slowest complaint\ngrowth (n={g['count'].iloc[0]})", f"Middle\n(n={g['count'].iloc[1]})",
                                f"Fastest complaint\ngrowth (n={g['count'].iloc[2]})"])
    ax[0].set_ylabel("mean next-quarter return minus XLF (%)")
    ax[0].set_title("Next-quarter excess return by complaint-growth tercile\n(ranked within quarter; bars = ±1 s.e.)")
    cum = (1 + ls.set_index("quarter").spread).cumprod()
    ax[1].plot(cum.index, cum.values, color=NAVY)
    ax[1].axhline(1, color="black", lw=0.8)
    ax[1].set_title("Toy long-short: long 3 slowest, short 3 fastest\ncomplaint growers, held one quarter (no costs)")
    ax[1].set_ylabel("growth of $1")
    fig.tight_layout()
    fig.savefig(config.FIGURES / "complaint_signal_vs_returns.png")
    plt.close(fig)


def fig_templates(tmpl: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 3.4))
    for t, g in tmpl.groupby("ticker"):
        if g.template_share.max() > 0.08:
            ax.plot(g.quarter, g.template_share * 100, "-o", ms=3, label=t)
    all_ = tmpl.assign(w=tmpl.template_share * tmpl.n_docs).groupby("quarter")[["w", "n_docs"]].sum()
    ax.plot(all_.index, all_.w / all_.n_docs * 100, "k--", lw=1.5, label="all 10")
    ax.set_ylabel("% of narratives that are copy-paste")
    ax.set_title(f"Template / copy-paste complaints (opening shared by >= {config.TEMPLATE_MIN_COPIES} narratives)")
    ax.legend(frameon=False, fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(config.FIGURES / "template_share.png")
    plt.close(fig)


def fig_block_case(start="2024-10-01", end="2025-06-30") -> pd.DataFrame:
    """Case study: Block (Cash App) weekly complaints around the CFPB consent order of 2025-01-16."""
    w = pd.read_csv(P / "weekly_volume.csv", parse_dates=["week"])
    d = w[(w.ticker == "XYZ") & (w.week >= start) & (w.week <= end)].copy()
    d["other"] = d.n_complaints - d.n_template
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(d.week, d.other, width=6, color=NAVY, label="other complaints")
    ax.bar(d.week, d.n_template, width=6, bottom=d.other, color=ORANGE, label="copy-paste template narratives")
    ax.axvline(pd.Timestamp("2025-01-16"), color="black", ls="--", lw=1)
    ax.text(pd.Timestamp("2025-01-20"), d.n_complaints.max() * 0.9,
            "CFPB consent order vs Block\n(Jan 16, 2025)", fontsize=8)
    ax.set_yscale("log")
    ax.set_ylabel("complaints per week (log scale)")
    ax.set_title("Block / Cash App: a complaint 'spike' that is mostly one copy-paste template")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(config.FIGURES / "block_case_study.png")
    plt.close(fig)
    return d


def main() -> None:
    config.FIGURES.mkdir(parents=True, exist_ok=True)
    vol, top, tmpl, panel = load()
    fig_volume(vol)
    fig_coverage(vol)
    fig_topic_trends(top)
    mix = fig_topic_company(top)
    fig_signal(panel)
    fig_templates(tmpl)
    block = fig_block_case()
    tests = signal_tests(panel)
    tests.to_csv(P / "signal_tests.csv", index=False)
    yearly = vol.assign(year=vol.quarter.dt.year).groupby(["year", "ticker"]).n_complaints.sum().unstack()
    terms = json.loads((P / "topics_top_terms.json").read_text())
    tw = top.assign(wt=top.topic_share * top.n_docs, year=top.quarter.dt.year)
    topic_year = tw.groupby(["year", "label"]).wt.sum().unstack()
    topic_year = (topic_year.div(topic_year.sum(axis=1), axis=0) * 100).T
    with open(config.REPORTS / "results.md", "w") as f:
        f.write("# Results (generated by `python -m cfpbsignals.analysis`)\n\n")
        f.write(f"Universe complaints {config.VOLUME_START} to {config.VOLUME_END}: {int(vol.n_complaints.sum()):,}; "
                f"narratives used for topics ({config.TOPIC_START} to {config.TOPIC_END}): "
                f"{int(tmpl.n_docs.sum()):,}\n\n")
        f.write("## Validation: archive vs live CFPB API counts\n\n"
                + pd.read_csv(P / "validation_vs_api.csv").to_markdown(index=False) + "\n\n")
        f.write("## Complaints per calendar year\n\n" + yearly.fillna(0).astype(int).to_markdown() + "\n\n")
        f.write("## Topics (NMF top terms)\n\n")
        for i, (lab, t) in enumerate(zip(config.TOPIC_LABELS, terms)):
            f.write(f"{i}. **{lab}**: {', '.join(t[:10])}\n")
        f.write("\n## Topic share by year (% of narrative topic weight)\n\n" + topic_year.round(1).to_markdown() + "\n\n")
        f.write("## Topic mix by company, 2024-2025 (%)\n\n" + mix.round(1).T.to_markdown() + "\n\n")
        f.write("## Case study: Block (XYZ) weekly complaints around the 2025-01-16 CFPB order\n\n"
                + block[["week", "n_complaints", "n_template"]].to_markdown(index=False) + "\n\n")
        f.write("## Signal tests vs excess returns (XLF)\n\n" + tests.round(3).to_markdown(index=False) + "\n")
    print(open(config.REPORTS / "results.md").read())


if __name__ == "__main__":
    main()
