"""Quick interim analysis of running KTO eval. Also saves preliminary JSON."""

import io
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

LOG = "C:/Work/MITS/evaluation/reports/kto_hybrid_log.txt"

with open(LOG, "r", encoding="utf-16-le") as f:
    text = f.read()

if text.startswith("﻿"):
    text = text[1:]

header_re = re.compile(r"\[(\d+)/143\]\s+(\w+)/(\w+)\s+idx=(\d+)")
# In log, accuracy marks appear as literal escape sequences:  acc=✓ / ✗
acc_re = re.compile(r"acc=\\u(2713|2717)\s+beh=(\S+)")

results = []
current = None
for line in text.split("\n"):
    h = header_re.search(line)
    if h:
        current = {
            "n": int(h.group(1)),
            "domain": h.group(2),
            "difficulty": h.group(3),
            "idx": int(h.group(4)),
        }
    a = acc_re.search(line)
    if a and current:
        current["acc"] = a.group(1) == "2713"
        current["beh"] = a.group(2)
        results.append(current)
        current = None

n = len(results)
print(f"=== ИНТЕРИМ: {n}/143 задач завершено ({100*n/143:.0f}%) ===")
print()

if n == 0:
    sys.exit(0)

correct = sum(1 for r in results if r["acc"])
print(f"KTO accuracy:    {correct}/{n} = {100*correct/n:.1f}%")
print("Base    (143):   90.2%")
print("GSPO    (143):   87.9%")
print()

print("Behavior distribution:")
behs = Counter(r["beh"] for r in results)
for k, v in behs.most_common():
    print(f"  {k:<12s}: {v:>3d}/{n} = {100*v/n:.0f}%")
print()

print("Per-domain accuracy:")
domains: dict[str, list[bool]] = {}
for r in results:
    domains.setdefault(r["domain"], []).append(r["acc"])
for d in sorted(domains):
    accs = domains[d]
    print(f"  {d:<10s}: {sum(accs)}/{len(accs)} = {100*sum(accs)/len(accs):.0f}%")
print()

print("Per-difficulty:")
diffs: dict[str, list[bool]] = {}
for r in results:
    diffs.setdefault(r["difficulty"], []).append(r["acc"])
for d in sorted(diffs):
    accs = diffs[d]
    print(f"  {d:<10s}: {sum(accs)}/{len(accs)} = {100*sum(accs)/len(accs):.0f}%")
print()

# Time analysis
ts = re.findall(r"(\d{2}:\d{2}:\d{2})", text)
if len(ts) >= 2:
    t0 = datetime.strptime(ts[0], "%H:%M:%S")
    tlast = datetime.strptime(ts[-1], "%H:%M:%S")
    if tlast < t0:
        tlast += timedelta(days=1)
    elapsed_min = (tlast - t0).total_seconds() / 60
    per_task = elapsed_min / n
    eta_min = (143 - n) * per_task
    print("Время:")
    print(f"  Прошло:        {elapsed_min:.0f} мин")
    print(f"  Среднее/зад:   {per_task:.1f} мин")
    print(f"  ETA до конца:  {eta_min:.0f} мин ({eta_min/60:.1f} ч)")
    print(f"  Финиш ~:       {(tlast + timedelta(minutes=eta_min)).strftime('%H:%M')}")

# Save preliminary JSON
out = Path("C:/Work/MITS/evaluation/reports/kto_calc_preliminary.json")
agg = {
    "model": "mits-tutor-9b-fast",
    "prompt_mode": "calc",
    "n_completed": n,
    "n_total": 143,
    "interrupted": True,
    "timestamp": datetime.now().isoformat(),
    "overall": {
        "accuracy": correct / n if n else 0,
        "behaviors": dict(Counter(r["beh"] for r in results)),
    },
    "by_domain": {
        d: {"n": len(domains[d]), "accuracy": sum(domains[d]) / len(domains[d])}
        for d in domains
    },
    "by_difficulty": {
        d: {"n": len(diffs[d]), "accuracy": sum(diffs[d]) / len(diffs[d])}
        for d in diffs
    },
    "details": results,
}
out.write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nPreliminary JSON saved to: {out}")
