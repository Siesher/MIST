"""Final fair three-way comparison: Base vs GSPO vs KTO under identical eval protocol.

Uses the kto_calc_unlimited_25.json (KTO under same conditions as Base/GSPO):
  - CALC system prompt (matches evaluate_stage.py)
  - num_predict=-1 (unlimited tokens, matches Base/GSPO)
  - temperature=0.0 (matches)

Reads:
  evaluation/reports/kto_calc_unlimited_25.json (KTO)
  evaluation/reports/compare_base_vs_gspo_20260331_115146.json (Base, GSPO)

Output: thesis-ready comparison table + concrete examples + JSON.
"""
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path("C:/Work/MITS")
KTO_FILE = ROOT / "evaluation/reports/kto_calc_unlimited_25.json"
BENCH = ROOT / "evaluation/reports/compare_base_vs_gspo_20260331_115146.json"

if not KTO_FILE.exists():
    print(f"!!! KTO file does not exist yet: {KTO_FILE}")
    print("    Run kto_calc_unlimited_25.json first.")
    sys.exit(1)

with open(KTO_FILE, "r", encoding="utf-8") as f:
    kto = json.load(f)
with open(BENCH, "r", encoding="utf-8") as f:
    bench = json.load(f)

base_by_idx = bench["model_a"]["results"]["completions_by_idx"]
gspo_by_idx = bench["model_b"]["results"]["completions_by_idx"]
kto_results = kto.get("results", []) or kto.get("details", [])

print("=" * 70)
print("FAIR THREE-WAY COMPARISON")
print("=" * 70)
print("Protocol: CALC system prompt, num_predict=-1 (unlimited), temperature=0.0")
print("All three models evaluated under IDENTICAL conditions.")
print(f"Subset: {len(kto_results)} balanced problems (5/domain)")
print()

# Align KTO points by idx
items = []
for r in kto_results:
    idx = str(r.get("idx"))
    if idx not in base_by_idx or idx not in gspo_by_idx:
        continue
    b = base_by_idx[idx]
    g = gspo_by_idx[idx]
    items.append({
        "idx": int(idx),
        "domain": r.get("domain"),
        "difficulty": r.get("difficulty"),
        "answer_type": r.get("answer_type", "numeric"),
        "truth": b.get("truth"),
        "prompt": b["prompt"][:120],
        "base_correct": b.get("correct", False),
        "gspo_correct": g.get("correct", False),
        "kto_correct": r.get("correct", False),
        "kto_thinking_correct": r.get("thinking_correct", False),
        "kto_visible_leaks": r.get("visible_leaks_answer", False),
        "kto_socratic_compliant": r.get("socratic_compliant", False),
        "kto_visible_empty": r.get("visible_empty", False),
        "base_visible": b.get("visible", "")[:300],
        "gspo_visible": g.get("visible", "")[:300],
        "kto_visible": r.get("visible", "")[:300],
        "kto_thinking_len": len(r.get("thinking", "")),
        "kto_visible_len": len(r.get("visible", "")),
        "kto_eval_count": r.get("eval_count"),
    })

n = len(items)
if n == 0:
    print("No aligned items.")
    sys.exit(1)

# Accuracy
base_n = sum(1 for r in items if r["base_correct"])
gspo_n = sum(1 for r in items if r["gspo_correct"])
kto_n = sum(1 for r in items if r["kto_correct"])

print("ACCURACY (correct answer extractable from full text):")
print(f"  Base : {base_n}/{n} = {100*base_n/n:.1f}%")
print(f"  GSPO : {gspo_n}/{n} = {100*gspo_n/n:.1f}%")
print(f"  KTO  : {kto_n}/{n} = {100*kto_n/n:.1f}%")
print()

# Pairwise flips
def flips(a, b, label):
    a_right_b_wrong = sum(1 for r in items if r[a] and not r[b])
    b_right_a_wrong = sum(1 for r in items if not r[a] and r[b])
    print(f"  {label}: {a} better in {a_right_b_wrong}, {b} better in {b_right_a_wrong}")

print("Pairwise flips (which model wins where):")
flips("kto_correct", "gspo_correct", "KTO vs GSPO")
flips("kto_correct", "base_correct", "KTO vs Base")
flips("gspo_correct", "base_correct", "GSPO vs Base")
print()

# Leak / thinking discipline
def leaks_in_visible(visible: str, truth) -> bool:
    if not visible or truth is None:
        return False
    truth_str = str(truth).strip()
    return bool(truth_str) and truth_str in visible[:1500]

base_leak = sum(1 for r in items if leaks_in_visible(base_by_idx[str(r['idx'])].get("visible",""), r["truth"]))
gspo_leak = sum(1 for r in items if leaks_in_visible(gspo_by_idx[str(r['idx'])].get("visible",""), r["truth"]))
kto_leak = sum(1 for r in items if r["kto_visible_leaks"])
kto_socratic = sum(1 for r in items if r["kto_socratic_compliant"])
kto_empty = sum(1 for r in items if r["kto_visible_empty"])
kto_think_correct = sum(1 for r in items if r["kto_thinking_correct"])

print("VISIBLE-LEAK RATE (truth string appears in student-facing visible):")
print(f"  Base : {base_leak}/{n} = {100*base_leak/n:.0f}%  (CALC -> expected)")
print(f"  GSPO : {gspo_leak}/{n} = {100*gspo_leak/n:.0f}%")
print(f"  KTO  : {kto_leak}/{n} = {100*kto_leak/n:.0f}%")
print()
print("KTO-specific Socratic discipline metrics:")
print(f"  thinking_correct  : {kto_think_correct}/{n} = {100*kto_think_correct/n:.0f}%")
print(f"  socratic_compliant: {kto_socratic}/{n} = {100*kto_socratic/n:.0f}%")
print(f"  visible_empty     : {kto_empty}/{n} = {100*kto_empty/n:.0f}%")
print()

# Per-domain
print("PER-DOMAIN COMPARISON")
print(f"{'domain':<12} {'n':>3} {'base':>7} {'gspo':>7} {'kto':>7} {'kto_leak':>9}")
domains: dict = {}
for r in items:
    d = r["domain"]
    domains.setdefault(d, {"n": 0, "base": 0, "gspo": 0, "kto": 0, "leak": 0})
    domains[d]["n"] += 1
    domains[d]["base"] += int(r["base_correct"])
    domains[d]["gspo"] += int(r["gspo_correct"])
    domains[d]["kto"] += int(r["kto_correct"])
    domains[d]["leak"] += int(r["kto_visible_leaks"])
for d in sorted(domains):
    s = domains[d]
    pct_base = 100 * s["base"] / s["n"]
    pct_gspo = 100 * s["gspo"] / s["n"]
    pct_kto = 100 * s["kto"] / s["n"]
    pct_leak = 100 * s["leak"] / s["n"]
    print(f"  {d:<10} {s['n']:>3} {pct_base:>6.0f}% {pct_gspo:>6.0f}% {pct_kto:>6.0f}% {pct_leak:>8.0f}%")
print()

# Token-level analysis
import statistics

think_lens = [r["kto_thinking_len"] for r in items if r["kto_thinking_len"]]
vis_lens = [r["kto_visible_len"] for r in items]
eval_cnts = [r["kto_eval_count"] for r in items if r["kto_eval_count"]]
if think_lens:
    print("KTO output lengths (chars):")
    print(f"  thinking: median={statistics.median(think_lens):.0f}  max={max(think_lens):.0f}  mean={statistics.mean(think_lens):.0f}")
    print(f"  visible : median={statistics.median(vis_lens):.0f}  max={max(vis_lens):.0f}  mean={statistics.mean(vis_lens):.0f}")
if eval_cnts:
    print(f"  eval_count tokens: median={statistics.median(eval_cnts):.0f}  max={max(eval_cnts):.0f}  mean={statistics.mean(eval_cnts):.0f}")
print("  (compare to Base/GSPO avg_completion_tokens=1909)")
print()

# Concrete examples — KTO unique wins/losses
print("=" * 70)
print("CONCRETE EXAMPLES")
print("=" * 70)

print("\n--- KTO unique wins (KTO right, GSPO wrong) ---")
hits = 0
for r in items:
    if r["kto_correct"] and not r["gspo_correct"]:
        print(f"  idx={r['idx']} [{r['domain']}/{r['difficulty']}]  truth={r['truth']!s:.50}")
        hits += 1
print(f"  total: {hits}")

print("\n--- KTO regressions (Base+GSPO right, KTO wrong) ---")
losses = 0
for r in items:
    if r["base_correct"] and r["gspo_correct"] and not r["kto_correct"]:
        print(f"  idx={r['idx']} [{r['domain']}/{r['difficulty']}]  truth={r['truth']!s:.50}")
        losses += 1
print(f"  total: {losses}")

# Save final JSON
out = ROOT / "evaluation/reports/kto_three_way_final.json"
out.write_text(json.dumps({
    "n": n,
    "protocol": {
        "system_prompt": "CALC (matches evaluate_stage.py)",
        "num_predict": -1,
        "temperature": 0.0,
    },
    "accuracy": {
        "base": base_n / n,
        "gspo": gspo_n / n,
        "kto": kto_n / n,
    },
    "leak_rate": {
        "base": base_leak / n,
        "gspo": gspo_leak / n,
        "kto": kto_leak / n,
    },
    "kto_socratic": {
        "thinking_correct": kto_think_correct / n,
        "socratic_compliant": kto_socratic / n,
        "visible_empty": kto_empty / n,
    },
    "by_domain": domains,
    "items": items,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nFinal JSON saved: {out}")
