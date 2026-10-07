#!/usr/bin/env python3
"""Aggregate HW1 experiment CSVs and render presentation charts."""

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATA_SIZE_BYTES = 256 * 1024
EXPECTED_SIZES = [1 << e for e in range(18)]
EXPECTED_PHASES = 256

COLOR_MAIN = "#1f77b4"
COLOR_ALT = "#ff7f0e"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 11.5,
        "axes.grid": True,
        "grid.linestyle": "--",
        "grid.alpha": 0.4,
        "axes.axisbelow": True,
        "legend.fontsize": 10,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    }
)


def human_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        kb = n / 1024
        return f"{kb:g} KB"
    return f"{n / (1024 * 1024):g} MB"


def load_experiment1(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"file": str})
    df["file"] = df["file"].str.zfill(2)
    sizes = sorted(df["block_size_bytes"].unique().tolist())
    if sizes != EXPECTED_SIZES:
        sys.exit(f"Unexpected block sizes in {path}: {sizes}")
    counts = df.groupby("block_size_bytes")["elapsed_ms"].count()
    bad = counts[counts != EXPECTED_PHASES]
    if not bad.empty:
        sys.exit(f"Expected {EXPECTED_PHASES} phases per size, got:\n{bad}")
    return df


def load_experiment2(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if set(df["test"]) != {"sequential", "random"}:
        sys.exit(f"Unexpected tests in {path}: {df['test'].tolist()}")
    return df


def summarize_experiment1(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["block_size_bytes", "file"])["elapsed_ms"]
    summary = g.agg(
        n="count",
        mean_ms="mean",
        median_ms="median",
        std_ms="std",
        min_ms="min",
        max_ms="max",
    )
    quantiles = (
        g.quantile([0.05, 0.95])
        .unstack(level=-1)
        .reset_index()
        .rename(columns={0.05: "p5_ms", 0.95: "p95_ms"})
    )
    summary = summary.reset_index().merge(
        quantiles, on=["block_size_bytes", "file"]
    )
    summary = summary.sort_values("block_size_bytes").reset_index(drop=True)
    summary["throughput_MB_s"] = (DATA_SIZE_BYTES / 1e6) / (summary["mean_ms"] / 1000)
    summary["speedup_vs_1B"] = summary["mean_ms"].iloc[0] / summary["mean_ms"]
    return summary[
        [
            "block_size_bytes",
            "file",
            "n",
            "mean_ms",
            "median_ms",
            "std_ms",
            "min_ms",
            "max_ms",
            "p5_ms",
            "p95_ms",
            "throughput_MB_s",
            "speedup_vs_1B",
        ]
    ]


def summarize_experiment2(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["throughput_MB_s"] = (out["total_bytes"] / 1e6) / (out["elapsed_ms"] / 1000)
    seq = out.loc[out["test"] == "sequential", "elapsed_ms"].iloc[0]
    out["slowdown_vs_sequential"] = out["elapsed_ms"] / seq
    return out


def block_size_axis(ax, sizes):
    ax.set_xscale("log", base=2)
    ax.set_xticks(sizes)
    ax.set_xticklabels([human_bytes(s) for s in sizes], rotation=45, ha="right", fontsize=8.5)
    ax.minorticks_off()


def plot_exp1_line(summary: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.4))
    x = summary["block_size_bytes"].to_numpy(float)
    y = summary["mean_ms"].to_numpy(float)
    e = summary["std_ms"].to_numpy(float)

    plateau_lo = 4096
    ax.axvspan(plateau_lo, x.max(), color=COLOR_ALT, alpha=0.10)
    ax.text(
        np.sqrt(plateau_lo * x.max()),
        0.93,
        "Plateau (4 KB – 128 KB)",
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="center",
        fontsize=10,
        color="#a0522d",
    )

    ax.errorbar(
        x,
        y,
        yerr=e,
        color=COLOR_MAIN,
        marker="o",
        markersize=5,
        linewidth=2,
        capsize=3,
        elinewidth=1,
        label="Mean of 256 phases (±1 std)",
    )
    ax.set_yscale("log")
    block_size_axis(ax, summary["block_size_bytes"].tolist())
    ax.set_xlabel("Write block size")
    ax.set_ylabel("Execution time per phase (ms, log scale)")
    ax.set_title("Experiment 1: Write Time vs Block Size")
    ax.legend(loc="lower left")
    fig.savefig(path)
    plt.close(fig)


def plot_exp1_bar(summary: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.4))
    labels = [human_bytes(s) for s in summary["block_size_bytes"]]
    ax.bar(
        labels,
        summary["mean_ms"],
        yerr=summary["std_ms"],
        color=COLOR_MAIN,
        ecolor="#555555",
        capsize=2.5,
        width=0.72,
    )
    ax.set_xlabel("Write block size")
    ax.set_ylabel("Execution time per phase (ms)")
    ax.set_title("Experiment 1: Mean Write Time by Block Size")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8.5)
    fig.savefig(path)
    plt.close(fig)


def plot_exp1_throughput(summary: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.plot(
        summary["block_size_bytes"],
        summary["throughput_MB_s"],
        color="#2ca02c",
        marker="s",
        markersize=5,
        linewidth=2,
        label="Mean throughput",
    )
    block_size_axis(ax, summary["block_size_bytes"].tolist())
    ax.set_xlabel("Write block size")
    ax.set_ylabel("Throughput (MB/s)")
    ax.set_title("Experiment 1: Write Throughput vs Block Size")
    ax.legend(loc="upper left")
    fig.savefig(path)
    plt.close(fig)


def plot_exp1_boxplot(df: pd.DataFrame, path: Path) -> None:
    sizes = sorted(df["block_size_bytes"].unique().tolist())
    data = [df.loc[df["block_size_bytes"] == s, "elapsed_ms"].to_numpy() for s in sizes]
    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.boxplot(
        data,
        tick_labels=[human_bytes(s) for s in sizes],
        showfliers=True,
        flierprops={"markersize": 3.5, "markerfacecolor": COLOR_ALT, "alpha": 0.6},
        medianprops={"color": COLOR_ALT, "linewidth": 1.6},
        patch_artist=True,
        boxprops={"facecolor": COLOR_MAIN, "alpha": 0.55},
    )
    ax.set_yscale("log")
    ax.set_xlabel("Write block size")
    ax.set_ylabel("Execution time per phase (ms, log scale)")
    ax.set_title("Experiment 1: Distribution of 256 Phases per Block Size")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8.5)
    fig.savefig(path)
    plt.close(fig)


def plot_exp2(summary: pd.DataFrame, path: Path) -> None:
    order = ["sequential", "random"]
    df = summary.set_index("test").loc[order].reset_index()
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    colors = [COLOR_MAIN, COLOR_ALT]
    bars = ax.bar(df["test"].str.title(), df["elapsed_ms"], color=colors, width=0.55)

    for bar, (_, row) in zip(bars, df.iterrows()):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{row['elapsed_ms']:.1f} ms\n{row['throughput_MB_s']:,.0f} MB/s",
            ha="center",
            va="bottom",
            fontsize=11,
        )

    seq = df.loc[df["test"] == "sequential", "elapsed_ms"].iloc[0]
    rnd = df.loc[df["test"] == "random", "elapsed_ms"].iloc[0]
    pct = (rnd / seq - 1) * 100
    ax.annotate(
        f"Random read is {pct:+.1f}% slower\n(same 1024 × 256 KB, lseek jumps)",
        xy=(0.5, 0.9),
        xycoords="axes fraction",
        ha="center",
        fontsize=11,
        color="#a0522d",
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "#fff6e5", "edgecolor": "#e0c090"},
    )

    ax.set_ylabel("Execution time (ms)")
    ax.set_title("Experiment 2: Sequential vs Random Read")
    ax.set_ylim(0, max(df["elapsed_ms"]) * 1.5)
    fig.savefig(path)
    plt.close(fig)


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=here / "run")
    parser.add_argument("--out-dir", type=Path, default=here / "run" / "figures")
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    exp1 = load_experiment1(data_dir / "experiment1_results.csv")
    exp2 = load_experiment2(data_dir / "experiment2_results.csv")

    exp1_summary = summarize_experiment1(exp1)
    exp2_summary = summarize_experiment2(exp2)

    exp1_csv = data_dir / "summary_experiment1.csv"
    exp2_csv = data_dir / "summary_experiment2.csv"
    exp1_summary.to_csv(exp1_csv, index=False, float_format="%.6f")
    exp2_summary.to_csv(exp2_csv, index=False, float_format="%.6f")

    figures = {
        "exp1_write_time_vs_block_size.png": plot_exp1_line,
        "exp1_write_time_bar.png": plot_exp1_bar,
        "exp1_throughput_vs_block_size.png": plot_exp1_throughput,
    }
    for name, fn in figures.items():
        fn(exp1_summary, out_dir / name)
    plot_exp1_boxplot(exp1, out_dir / "exp1_distribution_boxplot.png")
    plot_exp2(exp2_summary, out_dir / "exp2_sequential_vs_random.png")

    print(f"Experiment 1 summary -> {exp1_csv}")
    for _, row in exp1_summary.iterrows():
        print(
            f"  {human_bytes(int(row['block_size_bytes'])):>7}: "
            f"mean {row['mean_ms']:9.3f} ms  median {row['median_ms']:9.3f} ms  "
            f"{row['throughput_MB_s']:8.2f} MB/s  ({row['speedup_vs_1B']:7.1f}x vs 1 B)"
        )
    plateau = exp1_summary[exp1_summary["block_size_bytes"] >= 4096]
    print(
        f"  plateau (4 KB-128 KB): {plateau['mean_ms'].min():.3f}-"
        f"{plateau['mean_ms'].max():.3f} ms per 256 KB phase"
    )

    print(f"Experiment 2 summary -> {exp2_csv}")
    for _, row in exp2_summary.iterrows():
        print(
            f"  {row['test']:>10}: {row['elapsed_ms']:8.3f} ms  "
            f"{row['throughput_MB_s']:8.0f} MB/s  "
            f"(x{row['slowdown_vs_sequential']:.3f} vs sequential)"
        )

    print(f"Figures written to {out_dir}/")
    for p in sorted(out_dir.glob("*.png")):
        print(f"  {p.name}  ({p.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
