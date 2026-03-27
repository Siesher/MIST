"""Fix GSPO diploma figures: recover full metrics + regenerate all plots.

Paste this ENTIRE cell into Colab and run it. It will:
1. Recover Stage 1 (300 steps) from trainer_state.json
2. Recover Stage 2 (300 steps) from loguru log (with format/socratic detail)
3. Merge into a single clean CSV
4. Regenerate all 6 figures with correct labels

Usage (Colab cell — just paste and run):
    exec(open("training/scripts/fix_diploma_figures.py").read())

Or copy the code below directly into a Colab cell.
"""

# ============================================================
# 0. Imports and paths
# ============================================================
import glob
import json
import os
import re

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

# Use OUTPUT_DIR from the notebook (already defined in config cell)
# If running standalone, set it manually:
if "OUTPUT_DIR" not in dir():
    OUTPUT_DIR = "/content/drive/MyDrive/MITS/checkpoints/gspo_qwen3.5_9b_v2"

METRICS_DIR = os.path.join(OUTPUT_DIR, "metrics")
FIGURES_DIR = os.path.join(METRICS_DIR, "figures")
os.makedirs(FIGURES_DIR, exist_ok=True)

FULL_CSV = os.path.join(METRICS_DIR, "training_metrics_full.csv")
LOG_FILE = os.path.join(OUTPUT_DIR, "gspo_training.log")

# Actual config values (from notebook config cell)
STAGE1_WEIGHTS = [0.4, 0.15, 0.45]  # correctness, format, socratic
STAGE2_WEIGHTS = [0.7, 0.1, 0.2]  # correctness-focused for Stage 2
STAGE1_OPTIMIZER = "AdamW"
STAGE2_OPTIMIZER = "AdamW"  # NOT Lion — changed based on research
STAGE1_LR = "5e-7"
STAGE2_LR = "2e-6"

print("=" * 70)
print("STEP 1: Recovering Stage 1 from trainer_state.json")
print("=" * 70)

# ============================================================
# 1. Recover Stage 1 from trainer_state.json (full 300 steps)
# ============================================================
stage1_records = []
state_files = sorted(
    glob.glob(os.path.join(OUTPUT_DIR, "stage1", "checkpoint-*", "trainer_state.json"))
)
print(f"  Found {len(state_files)} Stage 1 checkpoint files")

for f in state_files:
    with open(f, "r") as fh:
        state = json.load(fh)
    if "log_history" not in state:
        continue
    for entry in state["log_history"]:
        step = entry.get("step", 0)
        if step == 0 or "loss" not in entry:
            continue
        stage1_records.append(
            {
                "stage": "stage1",
                "step": step,
                "loss": entry.get("loss"),
                "reward_mean": entry.get("reward", entry.get("reward/mean")),
                "reward_std": entry.get("reward_std", entry.get("reward/std")),
                "correctness_mean": entry.get("rewards/difficulty_weighted_correctness_fn/mean"),
                "correctness_std": entry.get("rewards/difficulty_weighted_correctness_fn/std"),
                "format_mean": entry.get(
                    "rewards/_base_format_fn/mean", entry.get("rewards/format_fn/mean")
                ),
                "format_std": entry.get(
                    "rewards/_base_format_fn/std", entry.get("rewards/format_fn/std")
                ),
                "socratic_mean": entry.get(
                    "rewards/_base_socratic_fn/mean", entry.get("rewards/socratic_fn/mean")
                ),
                "socratic_std": entry.get(
                    "rewards/_base_socratic_fn/std", entry.get("rewards/socratic_fn/std")
                ),
                "learning_rate": entry.get("learning_rate"),
                "grad_norm": entry.get("grad_norm"),
                "completion_length_mean": entry.get("completion_length/mean"),
            }
        )

# Deduplicate by step (keep last — most complete checkpoint)
seen_steps = {}
for r in stage1_records:
    seen_steps[r["step"]] = r
stage1_records = sorted(seen_steps.values(), key=lambda x: x["step"])
print(f"  Stage 1: {len(stage1_records)} unique steps recovered")
if stage1_records:
    print(f"  Steps: {stage1_records[0]['step']} → {stage1_records[-1]['step']}")

# ============================================================
# 2. Recover Stage 2 from loguru log (has format/socratic detail)
# ============================================================
print(f"\n{'=' * 70}")
print("STEP 2: Recovering Stage 2 from loguru log")
print("=" * 70)

STEP_RE = re.compile(
    r"step=(\d+)\s*\|\s*loss=([-\d.e+]+)\s*\|\s*"
    r"reward=([-\d.e+]+)±([-\d.e+]+)\s*\|\s*"
    r"lr=([-\d.e+]+)\s*\|\s*grad_norm=([-\d.e+]+)"
)
REWARD_RE = re.compile(r"rewards/([a-z_]+)/(mean|std):\s*([-\d.e+]+)")

stage2_records = []
current = None
in_stage2 = False

with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        clean = re.sub(r"\x1b\[[0-9;]*m", "", line)

        # Detect stage transitions
        if "STAGE 2" in clean or "Stage 2" in clean:
            in_stage2 = True
        if "STAGE 1" in clean and "SKIPPED" not in clean.upper():
            in_stage2 = False

        if not in_stage2:
            continue

        m = STEP_RE.search(clean)
        if m:
            if current:
                stage2_records.append(current)
            current = {
                "stage": "stage2",
                "step": int(m.group(1)),
                "loss": float(m.group(2)),
                "reward_mean": float(m.group(3)),
                "reward_std": float(m.group(4)),
                "learning_rate": float(m.group(5)),
                "grad_norm": float(m.group(6)),
            }
            continue

        if current:
            rm = REWARD_RE.search(clean)
            if rm:
                name = rm.group(1)
                key = (
                    "correctness"
                    if "correctness" in name
                    else "format"
                    if "format" in name
                    else "socratic"
                    if "socratic" in name
                    else None
                )
                if key:
                    current[f"{key}_{rm.group(2)}"] = float(rm.group(3))

if current:
    stage2_records.append(current)

# Deduplicate
seen_steps = {}
for r in stage2_records:
    seen_steps[r["step"]] = r
stage2_records = sorted(seen_steps.values(), key=lambda x: x["step"])
print(f"  Stage 2: {len(stage2_records)} unique steps recovered")
if stage2_records:
    print(f"  Steps: {stage2_records[0]['step']} → {stage2_records[-1]['step']}")
    n_fmt = sum(1 for r in stage2_records if r.get("format_mean") is not None)
    n_soc = sum(1 for r in stage2_records if r.get("socratic_mean") is not None)
    print(f"  format_mean filled: {n_fmt}/{len(stage2_records)}")
    print(f"  socratic_mean filled: {n_soc}/{len(stage2_records)}")

# ============================================================
# 3. Also try Stage 1 from loguru log (supplements trainer_state)
# ============================================================
stage1_from_log = []
current = None
in_stage1_section = True  # log starts in stage1

with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        clean = re.sub(r"\x1b\[[0-9;]*m", "", line)

        if "STAGE 2" in clean or "Stage 2" in clean:
            in_stage1_section = False
        if "STAGE 1" in clean and "SKIPPED" not in clean.upper():
            in_stage1_section = True

        if not in_stage1_section:
            if current:
                stage1_from_log.append(current)
                current = None
            continue

        m = STEP_RE.search(clean)
        if m:
            if current:
                stage1_from_log.append(current)
            current = {
                "stage": "stage1",
                "step": int(m.group(1)),
                "loss": float(m.group(2)),
                "reward_mean": float(m.group(3)),
                "reward_std": float(m.group(4)),
                "learning_rate": float(m.group(5)),
                "grad_norm": float(m.group(6)),
            }
            continue

        if current:
            rm = REWARD_RE.search(clean)
            if rm:
                name = rm.group(1)
                key = (
                    "correctness"
                    if "correctness" in name
                    else "format"
                    if "format" in name
                    else "socratic"
                    if "socratic" in name
                    else None
                )
                if key:
                    current[f"{key}_{rm.group(2)}"] = float(rm.group(3))

if current:
    stage1_from_log.append(current)

print(f"\n  Stage 1 from log: {len(stage1_from_log)} steps (supplements trainer_state)")

# Merge: trainer_state as base, log data fills format/socratic NaNs
stage1_by_step = {r["step"]: r for r in stage1_records}
for r in stage1_from_log:
    step = r["step"]
    if step in stage1_by_step:
        # Fill NaN fields from log
        for key in ["format_mean", "format_std", "socratic_mean", "socratic_std"]:
            if stage1_by_step[step].get(key) is None and r.get(key) is not None:
                stage1_by_step[step][key] = r[key]
    else:
        stage1_by_step[step] = r

stage1_records = sorted(stage1_by_step.values(), key=lambda x: x["step"])
print(f"  Stage 1 merged: {len(stage1_records)} steps")

# ============================================================
# 4. Build final DataFrame
# ============================================================
print(f"\n{'=' * 70}")
print("STEP 3: Building final DataFrame")
print("=" * 70)

all_records = stage1_records + stage2_records
df = pd.DataFrame(all_records)

expected_cols = [
    "stage",
    "step",
    "loss",
    "reward_mean",
    "reward_std",
    "correctness_mean",
    "correctness_std",
    "format_mean",
    "format_std",
    "socratic_mean",
    "socratic_std",
    "learning_rate",
    "grad_norm",
    "completion_length_mean",
]
for col in expected_cols:
    if col not in df.columns:
        df[col] = None
df = df[expected_cols].sort_values(["stage", "step"]).reset_index(drop=True)

df.to_csv(FULL_CSV, index=False)
print(f"  Saved: {FULL_CSV} ({len(df)} rows)")

for stage in df["stage"].unique():
    sdf = df[df["stage"] == stage]
    n_fmt = sdf["format_mean"].notna().sum()
    n_soc = sdf["socratic_mean"].notna().sum()
    n_cor = sdf["correctness_mean"].notna().sum()
    print(f"  {stage}: {len(sdf)} steps, correctness={n_cor}, format={n_fmt}, socratic={n_soc}")

# ============================================================
# 5. Generate all diploma figures (with CORRECT labels)
# ============================================================
print(f"\n{'=' * 70}")
print("STEP 4: Generating diploma figures")
print("=" * 70)

STAGE_COLORS = {"stage1": "#2196F3", "stage2": "#616161"}
STAGE_LABELS = {"stage1": "Stage 1", "stage2": "Stage 2"}


def save_fig(fig, name):
    """Save figure as PNG + PDF."""
    png_path = os.path.join(FIGURES_DIR, f"{name}.png")
    pdf_path = os.path.join(FIGURES_DIR, f"{name}.pdf")
    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    print(f"  Saved: {name}.png + .pdf")
    plt.close(fig)


# ---- Plot 01: Loss and Reward Dynamics ----
fig, ax1 = plt.subplots(figsize=(12, 5))
ax2 = ax1.twinx()

for stage, grp in df.groupby("stage"):
    color = STAGE_COLORS.get(stage, "gray")
    label = STAGE_LABELS.get(stage, stage)
    ax1.plot(
        grp["step"], grp["loss"], color=color, alpha=0.8, linewidth=1.2, label=f"Loss ({label})"
    )
    ax2.plot(
        grp["step"],
        grp["reward_mean"],
        color=color,
        alpha=0.6,
        linestyle="--",
        linewidth=1.2,
        label=f"Reward ({label})",
    )
    if grp["reward_std"].notna().any():
        ax2.fill_between(
            grp["step"],
            grp["reward_mean"] - grp["reward_std"],
            grp["reward_mean"] + grp["reward_std"],
            alpha=0.1,
            color=color,
        )

ax1.set_xlabel("Training Step")
ax1.set_ylabel("GRPO Loss", color="#2196F3")
ax2.set_ylabel("Mean Reward", color="#616161")
ax1.set_title("GSPO Training: Loss and Reward Dynamics")
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=8)
ax1.axhline(y=0, color="gray", linestyle=":", alpha=0.5)
save_fig(fig, "01_loss_reward")

# ---- Plot 02: Reward Decomposition (Correctness + Format) ----
fig, ax = plt.subplots(figsize=(12, 5))
for stage, grp in df.groupby("stage"):
    color = STAGE_COLORS.get(stage, "gray")
    label = STAGE_LABELS.get(stage, stage)
    if grp["correctness_mean"].notna().any():
        ax.plot(
            grp["step"],
            grp["correctness_mean"],
            color=color,
            linewidth=1.2,
            label=f"Correctness ({label})",
        )
        if grp["correctness_std"].notna().any():
            ax.fill_between(
                grp["step"],
                grp["correctness_mean"] - grp["correctness_std"],
                grp["correctness_mean"] + grp["correctness_std"],
                alpha=0.1,
                color=color,
            )
    if grp["format_mean"].notna().any():
        ax.plot(
            grp["step"],
            grp["format_mean"],
            color=color,
            linewidth=1.2,
            linestyle=":",
            label=f"Format ({label})",
        )

ax.set_xlabel("Training Step")
ax.set_ylabel("Reward Value")
ax.set_title("GSPO: Reward Decomposition (GDPO Decoupled)")
ax.set_ylim(0, 1.05)
ax.legend(fontsize=9)
save_fig(fig, "02_reward_decomposition")

# ---- Plot 03: Learning Rate Schedule ----
fig, ax = plt.subplots(figsize=(12, 4))
for stage, grp in df.groupby("stage"):
    color = STAGE_COLORS.get(stage, "gray")
    label = STAGE_LABELS.get(stage, stage)
    if grp["learning_rate"].notna().any():
        ax.plot(grp["step"], grp["learning_rate"], color=color, linewidth=1.5, label=label)

ax.set_xlabel("Training Step")
ax.set_ylabel("Learning Rate")
ax.set_title(
    f"Cosine LR Schedule (Stage 1: {STAGE1_OPTIMIZER} LR={STAGE1_LR}, "
    f"Stage 2: {STAGE2_OPTIMIZER} LR={STAGE2_LR})"
)
ax.yaxis.set_major_formatter(mticker.ScalarFormatter(useMathText=True))
ax.ticklabel_format(style="sci", axis="y", scilimits=(0, 0))
ax.legend(fontsize=9)
save_fig(fig, "03_learning_rate")

# ---- Plot 04: Gradient Norm ----
fig, ax = plt.subplots(figsize=(12, 4))
for stage, grp in df.groupby("stage"):
    color = STAGE_COLORS.get(stage, "gray")
    label = STAGE_LABELS.get(stage, stage)
    if grp["grad_norm"].notna().any():
        ax.plot(grp["step"], grp["grad_norm"], color=color, linewidth=1.2, label=label)

ax.set_xlabel("Training Step")
ax.set_ylabel("Gradient Norm")
ax.set_title("Gradient Norm During Training")
ax.legend(fontsize=9)
save_fig(fig, "04_gradient_norm")

# ---- Plot 05: Socratic vs Correctness ----
fig, ax = plt.subplots(figsize=(12, 5))
for stage, grp in df.groupby("stage"):
    color = STAGE_COLORS.get(stage, "gray")
    label = STAGE_LABELS.get(stage, stage)
    if grp["socratic_mean"].notna().any():
        ax.plot(
            grp["step"],
            grp["socratic_mean"],
            color=color,
            linewidth=1.2,
            label=f"Socratic ({label})",
        )
        if grp["socratic_std"].notna().any():
            ax.fill_between(
                grp["step"],
                grp["socratic_mean"] - grp["socratic_std"],
                grp["socratic_mean"] + grp["socratic_std"],
                alpha=0.1,
                color=color,
            )
    if grp["correctness_mean"].notna().any():
        ax.plot(
            grp["step"],
            grp["correctness_mean"],
            color=color,
            linewidth=1.2,
            linestyle="--",
            label=f"Correctness ({label})",
        )

ax.set_xlabel("Training Step")
ax.set_ylabel("Reward Value")
ax.set_title("GSPO: Socratic vs Correctness Reward Dynamics")
ax.set_ylim(0, 1.05)
ax.legend(fontsize=9)
save_fig(fig, "05_socratic_reward")

# ---- Plot 06: Triple GDPO Reward Decomposition (3 subplots) ----
reward_configs = [
    ("correctness_mean", "correctness_std", "#2196F3"),
    ("format_mean", "format_std", "#4CAF50"),
    ("socratic_mean", "socratic_std", "#FF5722"),
]

# Per-stage weights for titles
stage_weights = {
    "stage1": {"correctness": 0.4, "format": 0.15, "socratic": 0.45},
    "stage2": {"correctness": 0.7, "format": 0.1, "socratic": 0.2},
}

reward_names = ["correctness", "format", "socratic"]
fig, axes = plt.subplots(1, 3, figsize=(16, 4.5), sharey=True)

for ax, (mean_col, std_col, color), rname in zip(axes, reward_configs, reward_names):
    for stage, grp in df.groupby("stage"):
        label = STAGE_LABELS.get(stage, stage)
        w = stage_weights.get(stage, {}).get(rname, "?")
        if grp[mean_col].notna().any():
            ls = "-" if stage == "stage1" else "--"
            ax.plot(
                grp["step"], grp[mean_col], color=color, linestyle=ls, linewidth=1.2, label=label
            )
            if grp[std_col].notna().any():
                ax.fill_between(
                    grp["step"],
                    grp[mean_col] - grp[std_col],
                    grp[mean_col] + grp[std_col],
                    alpha=0.1,
                    color=color,
                )

    # Title shows both stage weights
    w1 = stage_weights["stage1"].get(rname, "?")
    w2 = stage_weights["stage2"].get(rname, "?")
    ax.set_title(f"{rname.capitalize()}\n(S1 w={w1}, S2 w={w2})", fontsize=10)
    ax.set_xlabel("Step")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8)

axes[0].set_ylabel("Reward Value")
fig.suptitle("GSPO Triple GDPO Reward Decomposition", fontsize=12)
fig.tight_layout()
save_fig(fig, "06_triple_reward_decomposition")

# ============================================================
# 6. LaTeX Summary Table
# ============================================================
print(f"\n{'=' * 70}")
print("STEP 5: Generating LaTeX summary table")
print("=" * 70)

tex_lines = [
    r"\begin{table}[h]",
    r"\centering",
    r"\caption{GSPO training results per stage}",
    r"\label{tab:gspo_results}",
    r"\begin{tabular}{lccccccc}",
    r"\toprule",
    r"Stage & Steps & Optimizer & Final Loss & Avg Correctness & Avg Format & Avg Socratic & Avg Reward \\",
    r"\midrule",
]

for stage in ["stage1", "stage2"]:
    sdf = df[df["stage"] == stage]
    if len(sdf) == 0:
        continue
    label = STAGE_LABELS[stage]
    opt = STAGE1_OPTIMIZER if stage == "stage1" else STAGE2_OPTIMIZER
    steps_range = f"{int(sdf['step'].min())}--{int(sdf['step'].max())}"
    final_loss = sdf["loss"].iloc[-1]
    avg_cor = sdf["correctness_mean"].mean()
    avg_fmt = sdf["format_mean"].mean()
    avg_soc = sdf["socratic_mean"].mean()
    avg_rew = sdf["reward_mean"].mean()

    cor_str = f"{avg_cor:.3f}" if pd.notna(avg_cor) else "---"
    fmt_str = f"{avg_fmt:.3f}" if pd.notna(avg_fmt) else "---"
    soc_str = f"{avg_soc:.3f}" if pd.notna(avg_soc) else "---"

    tex_lines.append(
        f"{label} & {steps_range} & {opt} & {final_loss:.4f} & "
        f"{cor_str} & {fmt_str} & {soc_str} & {avg_rew:.3f} \\\\"
    )

tex_lines += [
    r"\bottomrule",
    r"\end{tabular}",
    r"\end{table}",
]

tex_content = "\n".join(tex_lines)
tex_path = os.path.join(FIGURES_DIR, "training_summary.tex")
with open(tex_path, "w") as f:
    f.write(tex_content)
print(f"  Saved: {tex_path}")
print()
print(tex_content)

# ============================================================
# 7. Final summary
# ============================================================
print(f"\n{'=' * 70}")
print("DONE! All figures regenerated with correct labels.")
print(f"{'=' * 70}")
print(f"  CSV: {FULL_CSV}")
print(f"  Figures: {FIGURES_DIR}/")
print("  Files: 01-06_*.png + .pdf, training_summary.tex")
print(
    f"\n  Stage 1: {len(df[df['stage'] == 'stage1'])} steps, "
    f"weights={STAGE1_WEIGHTS}, {STAGE1_OPTIMIZER}"
)
print(
    f"  Stage 2: {len(df[df['stage'] == 'stage2'])} steps, "
    f"weights={STAGE2_WEIGHTS}, {STAGE2_OPTIMIZER}"
)
