from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "ui" / "diagrams"


def _rounded_box(ax, x: float, y: float, w: float, h: float, title: str, subtitle: str = "") -> None:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.03",
        linewidth=1.3,
        edgecolor="#2B6CB0",
        facecolor="#F7FBFF",
    )
    ax.add_patch(patch)
    title_wrapped = "\n".join(textwrap.wrap(title, width=22))
    ax.text(
        x + w / 2,
        y + h * 0.66,
        title_wrapped,
        ha="center",
        va="center",
        fontsize=11.2,
        color="#1A365D",
        weight="bold",
        linespacing=1.2,
    )
    if subtitle:
        subtitle_wrapped = "\n".join(textwrap.wrap(subtitle, width=28))
        ax.text(
            x + w / 2,
            y + h * 0.32,
            subtitle_wrapped,
            ha="center",
            va="center",
            fontsize=9.0,
            color="#2D3748",
            linespacing=1.25,
        )


def _arrow(ax, x1: float, y1: float, x2: float, y2: float) -> None:
    arrow = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, linewidth=1.6, color="#2B6CB0")
    ax.add_patch(arrow)


def create_flow_diagram() -> None:
    fig, ax = plt.subplots(figsize=(16.5, 5.8), dpi=140)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    nodes = [
        (0.02, 0.27, "Incoming Email / Ticket", "User request intake"),
        (0.18, 0.27, "Task Selector", "task_1 / task_2 / task_3"),
        (0.34, 0.27, "Agent Action", "Manual or auto-step"),
        (0.50, 0.27, "Env Step + Tools", "Policy, Order DB, Inventory, HF Space"),
        (0.68, 0.27, "Reward + Grader", "0.0 to 1.0 with partial credit"),
        (0.84, 0.27, "Epoch Log + Policy Update", "Learning log and policy update"),
    ]

    w = 0.135
    h = 0.48
    for idx, (x, y, title, subtitle) in enumerate(nodes):
        _rounded_box(ax, x, y, w, h, title, subtitle)
        if idx < len(nodes) - 1:
            _arrow(ax, x + w, y + h * 0.5, nodes[idx + 1][0], y + h * 0.5)

    ax.text(0.02, 0.92, "Email Triage Workflow", fontsize=15, weight="bold", color="#1A365D")
    ax.text(0.02, 0.86, "HF Space-assisted support triage with deterministic reward feedback", fontsize=10, color="#2D3748")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "flow_diagram.svg", format="svg", bbox_inches="tight")
    plt.close(fig)


def create_feature_diagram() -> None:
    fig, ax = plt.subplots(figsize=(13.2, 7.6), dpi=140)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    cards = [
        (0.06, 0.52, 0.4, 0.28, "UI Layer", [
            "Task controls + action builder",
            "Timeline, metrics, and outcomes",
            "Epoch trainer and logs",
        ]),
        (0.54, 0.52, 0.4, 0.28, "API Layer", [
            "reset / step / state",
            "auto-step + support search",
            "training run + training logs",
        ]),
        (0.06, 0.14, 0.4, 0.28, "Environment Layer", [
            "Task 1: email classification",
            "Task 2: policy-safe response",
            "Task 3: multi-system resolution",
        ]),
        (0.54, 0.14, 0.4, 0.28, "Model/Data Layer", [
            "RL-style policy + epoch logs",
            "HF Space classifier integration",
            "Corpus index + recommendations",
        ]),
    ]

    for x, y, w, h, title, lines in cards:
        patch = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.015,rounding_size=0.03",
            linewidth=1.4,
            edgecolor="#2B6CB0",
            facecolor="#F8FBFF",
        )
        ax.add_patch(patch)
        ax.text(x + 0.02, y + h - 0.06, title, fontsize=12.5, color="#1A365D", weight="bold")
        for i, line in enumerate(lines):
            wrapped = "\n".join(textwrap.wrap(f"- {line}", width=34))
            ax.text(x + 0.03, y + h - 0.12 - i * 0.075, wrapped, fontsize=10, color="#2D3748", linespacing=1.2)

    _arrow(ax, 0.46, 0.66, 0.54, 0.66)
    _arrow(ax, 0.26, 0.52, 0.26, 0.42)
    _arrow(ax, 0.74, 0.52, 0.74, 0.42)
    _arrow(ax, 0.46, 0.28, 0.54, 0.28)

    ax.text(0.06, 0.94, "Feature Architecture", fontsize=16, weight="bold", color="#1A365D")
    ax.text(0.06, 0.89, "Layered system view for the OpenEnv email triage benchmark", fontsize=10.2, color="#2D3748")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "feature_architecture.svg", format="svg", bbox_inches="tight")
    plt.close(fig)


def create_training_lifecycle_diagram() -> None:
    fig, ax = plt.subplots(figsize=(13.8, 7.0), dpi=140)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    steps = [
        (0.07, 0.62, 0.24, 0.22, "Run Epoch", "Execute task_1, task_2, task_3"),
        (0.38, 0.62, 0.24, 0.22, "Collect Rewards", "Capture task scores + breakdown"),
        (0.69, 0.62, 0.24, 0.22, "Update Policy", "Apply RL-style weight updates"),
        (0.07, 0.31, 0.24, 0.22, "Write Logs", "Persist epoch_training_log.jsonl"),
        (0.38, 0.31, 0.24, 0.22, "Review in UI", "Epoch cards + trends + status"),
        (0.69, 0.31, 0.24, 0.22, "Train Again", "Repeat with N epochs"),
    ]

    for i, (x, y, w, h, title, subtitle) in enumerate(steps):
        _rounded_box(ax, x, y, w, h, title, subtitle)

    # Top row arrows
    _arrow(ax, 0.31, 0.73, 0.38, 0.73)
    _arrow(ax, 0.62, 0.73, 0.69, 0.73)
    # Down from top-right to bottom-right
    _arrow(ax, 0.81, 0.62, 0.81, 0.53)
    # Bottom row arrows (right to left)
    _arrow(ax, 0.69, 0.42, 0.62, 0.42)
    _arrow(ax, 0.38, 0.42, 0.31, 0.42)

    # Feedback loop path: Train Again -> Run Epoch using a clean bottom route.
    ax.plot([0.81, 0.81], [0.31, 0.16], color="#2B6CB0", linewidth=1.4)
    ax.plot([0.81, 0.18], [0.16, 0.16], color="#2B6CB0", linewidth=1.4)
    loop_head = FancyArrowPatch(
        (0.18, 0.16),
        (0.18, 0.31),
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=1.4,
        color="#2B6CB0",
    )
    ax.add_patch(loop_head)
    ax.text(0.50, 0.12, "continuous training loop", ha="center", va="center", fontsize=9.7, color="#2D3748")

    ax.text(0.03, 0.9, "Training Lifecycle", fontsize=15.5, weight="bold", color="#1A365D")
    ax.text(0.03, 0.84, "How epochs run, update policy, log outcomes, and feed the next training cycle", fontsize=10.2, color="#2D3748")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "training_lifecycle.svg", format="svg", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    create_flow_diagram()
    create_feature_diagram()
    create_training_lifecycle_diagram()
    print(f"Diagrams generated in {OUT_DIR}")


if __name__ == "__main__":
    main()
