"""Shared chart helpers with a consistent, dashboard-like style."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from src.config import FIGURES_DIR

PALETTE = {
    "primary": "#1f4e79",
    "accent": "#e07b39",
    "good": "#2e8b57",
    "bad": "#c0392b",
    "grey": "#8a8d91",
}
SEGMENT_COLORS = {
    "Champions": "#1f4e79",
    "Loyal Customers": "#2e8b57",
    "Potential Loyalists": "#6aa84f",
    "Needs Attention": "#e07b39",
    "At Risk": "#c0392b",
    "High-Value Inactive": "#8e44ad",
    "Recent One-Time Buyers": "#4a86c8",
    "Other One-Time Buyers": "#95a5a6",
    "Inactive One-Time Buyers": "#bdc3c7",
}


def set_style() -> None:
    sns.set_theme(style="whitegrid", font_scale=1.0)
    plt.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "axes.edgecolor": "#cccccc",
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "font.family": "DejaVu Sans",
    })


def save_fig(fig: plt.Figure, name: str,
             directory: Path = FIGURES_DIR) -> Path:
    """Save a figure to outputs/figures and return the path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def cohort_heatmap(matrix: pd.DataFrame, ax=None,
                   annotate: bool = True) -> plt.Figure:
    """Classic cohort retention heatmap (rows=cohort, cols=months since)."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(14, 8))
    else:
        fig = ax.figure
    sns.heatmap(
        matrix, annot=annotate, fmt=".1f", cmap="Blues",
        vmin=0, vmax=max(10, float(matrix.max().max())),
        linewidths=0.4, cbar_kws={"label": "% of cohort active"},
        ax=ax,
    )
    ax.set_title("Cohort retention — % of customers ordering in month N")
    ax.set_xlabel("Months since first purchase")
    ax.set_ylabel("Acquisition cohort")
    return fig


def bar_labels(ax, fmt: str = "{:.1f}") -> None:
    for c in ax.containers:
        ax.bar_label(c, fmt=fmt, padding=2, fontsize=9)
