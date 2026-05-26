"""Honest audit: KTO vs Base vs GSPO on the 29 KTO-evaluated indices.

Reads:
  evaluation/reports/kto_calc_preliminary.json (29 KTO points)
  evaluation/reports/compare_base_vs_gspo_20260331_115146.json (full benchmark)

Output:
  - confusion matrix (Base/GSPO/KTO correct flags)
  - 5 concrete examples where the verdicts disagree
  - Behavior breakdown: leak / no-visible / miss
  - Visible-leak audit on Base/GSPO themselves (do they also leak under CALC?)
"""

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path("C:/Work/MITS")
KTO = ROOT / "evaluation/reports/kto_calc_preliminary.json"
BENCH = ROOT / "evaluation/reports/compare_base_vs_gspo_20260331_115146.json"

with open(KTO, "r", encoding="utf-8") as f:
    kto = json.load(f)
with open(BENCH, "r", encoding="utf-8") as f:
    bench = json.load(f)

base_by_idx = bench["model_a"]["results"]["completions_by_idx"]
gspo_by_idx = bench["model_b"]["results"]["completions_by_idx"]

print("=== Bench labels ===")
print(f"  A = {bench['model_a']['label']}  acc={bench['model_a']['results']['overall_accuracy']:.3f}")
print(f"  B = {bench['model_b']['label']}  acc={bench['model_b']['results']['overall_accuracy']:.3f}")
print(f"  KTO (29/143) acc = {kto['overall']['accuracy']:.3f}")
print()

# Align KTO points by idx
kto_items = []
for d in kto["details"]:
    idx = str(d["idx"])
    if idx not in base_by_idx or idx not in gspo_by_idx:
        continue
    b = base_by_idx[idx]
    g = gspo_by_idx[idx]
    kto_items.append({
        "idx": int(idx),
        "domain": d["domain"],
        "difficulty": d["difficulty"],
        "kto_correct": d["acc"],
        "kto_beh": d["beh"],
        "base_correct": b.get("correct", False),
        "gspo_correct": g.get("correct", False),
        "prompt": b["prompt"][:120],
        "truth": b.get("truth"),
        "base_visible": b.get("visible", "")[:200],
        "gspo_visible": g.get("visible", "")[:200],
    })

n = len(kto_items)
print(f"=== Aligned: {n} indices common to all three ===\n")

# Counts
both_3_correct = sum(1 for r in kto_items if r["base_correct"] and r["gspo_correct"] and r["kto_correct"])
all_3_wrong = sum(1 for r in kto_items if not r["base_correct"] and not r["gspo_correct"] and not r["kto_correct"])
kto_better_than_gspo = sum(1 for r in kto_items if r["kto_correct"] and not r["gspo_correct"])
kto_worse_than_gspo = sum(1 for r in kto_items if not r["kto_correct"] and r["gspo_correct"])
kto_better_than_base = sum(1 for r in kto_items if r["kto_correct"] and not r["base_correct"])
kto_worse_than_base = sum(1 for r in kto_items if not r["kto_correct"] and r["base_correct"])

base_correct_n = sum(1 for r in kto_items if r["base_correct"])
gspo_correct_n = sum(1 for r in kto_items if r["gspo_correct"])
kto_correct_n = sum(1 for r in kto_items if r["kto_correct"])

print(f"Accuracy on the same 29 problems:")
print(f"  Base : {base_correct_n}/{n} = {100*base_correct_n/n:.1f}%")
print(f"  GSPO : {gspo_correct_n}/{n} = {100*gspo_correct_n/n:.1f}%")
print(f"  KTO  : {kto_correct_n}/{n} = {100*kto_correct_n/n:.1f}%")
print()

print("Pairwise flips (vs same problem set):")
print(f"  KTO right, GSPO wrong : {kto_better_than_gspo}  (KTO improvements)")
print(f"  KTO wrong, GSPO right : {kto_worse_than_gspo}  (KTO regressions)")
print(f"  KTO right, Base wrong : {kto_better_than_base}")
print(f"  KTO wrong, Base right : {kto_worse_than_base}")
print(f"  All 3 right           : {both_3_correct}")
print(f"  All 3 wrong           : {all_3_wrong}")
print()

# Audit visible-leak on Base/GSPO too: did they leak the answer?
def leaks_in_visible(visible: str, truth) -> bool:
    if not visible or truth is None:
        return False
    truth_str = str(truth).strip()
    if not truth_str:
        return False
    return truth_str in visible[:1000]

base_leak = sum(1 for r in kto_items if leaks_in_visible(base_by_idx[str(r['idx'])].get("visible",""), r["truth"]))
gspo_leak = sum(1 for r in kto_items if leaks_in_visible(gspo_by_idx[str(r['idx'])].get("visible",""), r["truth"]))
kto_leak = sum(1 for r in kto_items if r["kto_beh"] == "leak")
kto_no_vis = sum(1 for r in kto_items if r["kto_beh"] == "no-visible")

print("Visible-leak rate (does the answer appear in the visible/student-facing part?):")
print(f"  Base : {base_leak}/{n} = {100*base_leak/n:.0f}%  (CALC prompt -> expected behavior)")
print(f"  GSPO : {gspo_leak}/{n} = {100*gspo_leak/n:.0f}%")
print(f"  KTO  : {kto_leak}/{n} = {100*kto_leak/n:.0f}%   no-visible: {kto_no_vis}/{n} = {100*kto_no_vis/n:.0f}%")
print()

# Concrete examples
print("=" * 80)
print("CONCRETE EXAMPLES")
print("=" * 80)

# 1. KTO regression: Base+GSPO right, KTO wrong
print("\n--- 1. KTO regressions (Base+GSPO right, KTO wrong) ---")
for r in kto_items:
    if r["base_correct"] and r["gspo_correct"] and not r["kto_correct"]:
        print(f"  idx={r['idx']} [{r['domain']}/{r['difficulty']}] beh={r['kto_beh']}  truth={r['truth']!s:.50}")
        print(f"    prompt: {r['prompt']}")

# 2. KTO improvements (rare? if any)
print("\n--- 2. KTO unique wins (KTO right, GSPO wrong) ---")
hits = 0
for r in kto_items:
    if r["kto_correct"] and not r["gspo_correct"]:
        print(f"  idx={r['idx']} [{r['domain']}/{r['difficulty']}] beh={r['kto_beh']}  truth={r['truth']!s:.50}")
        hits += 1
if hits == 0:
    print("  (none)")

# 3. no-visible audit — these are KTO doing right thing under wrong prompt
print("\n--- 3. KTO 'no-visible' cases (model resisted CALC prompt — Socratic discipline) ---")
for r in kto_items:
    if r["kto_beh"] == "no-visible":
        print(f"  idx={r['idx']} [{r['domain']}/{r['difficulty']}]  kto_correct(full)={r['kto_correct']}  truth={r['truth']!s:.40}")

# Per-domain breakdown
print("\n=== Per-domain comparison on 29 problems ===")
print(f"{'domain':<12} {'n':>3} {'base':>6} {'gspo':>6} {'kto':>6}")
domains = {}
for r in kto_items:
    d = r["domain"]
    domains.setdefault(d, {"n": 0, "base": 0, "gspo": 0, "kto": 0})
    domains[d]["n"] += 1
    domains[d]["base"] += int(r["base_correct"])
    domains[d]["gspo"] += int(r["gspo_correct"])
    domains[d]["kto"] += int(r["kto_correct"])
for d in sorted(domains):
    s = domains[d]
    print(f"  {d:<10} {s['n']:>3} {s['base']:>3}/{s['n']:<2} {s['gspo']:>3}/{s['n']:<2} {s['kto']:>3}/{s['n']:<2}")

# Save audit JSON
out = ROOT / "evaluation/reports/kto_audit_29.json"
out.write_text(json.dumps({
    "n": n,
    "accuracy": {
        "base": base_correct_n / n,
        "gspo": gspo_correct_n / n,
        "kto": kto_correct_n / n,
    },
    "leak_rate": {
        "base": base_leak / n,
        "gspo": gspo_leak / n,
        "kto": kto_leak / n,
    },
    "kto_no_visible": kto_no_vis / n,
    "flips": {
        "kto_right_gspo_wrong": kto_better_than_gspo,
        "kto_wrong_gspo_right": kto_worse_than_gspo,
        "kto_right_base_wrong": kto_better_than_base,
        "kto_wrong_base_right": kto_worse_than_base,
    },
    "items": kto_items,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nAudit saved: {out}")
