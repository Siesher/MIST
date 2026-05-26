"""Forensic analysis of KTO checkpoint-1400 trainer_state.json.

Verifies/refutes thesis claims about KTO stage by reading actual training history.
"""
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

with open("C:/Work/MITS/_tmp_ckpt/checkpoint-1400/trainer_state.json") as f:
    s = json.load(f)

lh = s["log_history"]
train = [e for e in lh if "loss" in e and "eval_loss" not in e]
evals = [e for e in lh if "eval_loss" in e]

print(f"=== Training run summary ===")
print(f"Step: {s['global_step']}/{s['max_steps']}  ({s['global_step']/s['max_steps']*100:.0f}%)")
print(f"Epoch: {s['epoch']:.3f}/{s['num_train_epochs']}")
print(f"Batch size: {s['train_batch_size']}")
print(f"Train log entries: {len(train)}  (every {s['logging_steps']} steps)")
print(f"Eval log entries:  {len(evals)}   (every {s['eval_steps']} steps)")
print()

print("=== Training loss trajectory (every ~100 steps) ===")
print(f"{'step':>6} {'loss':>8} {'kl':>8} {'rew_chosen':>11} {'rew_rejected':>13} {'margin':>8} {'lr':>10} {'grad':>7}")
for i, e in enumerate(train):
    if i % 10 == 0 or i == len(train) - 1:
        print(f"{e['step']:>6} {e['loss']:>8.4f} {e['kl']:>8.3f} {e['rewards/chosen']:>11.4f} "
              f"{e['rewards/rejected']:>13.4f} {e['rewards/margins']:>8.4f} {e['learning_rate']:>10.2e} {e['grad_norm']:>7.3f}")

print()
print("=== Eval trajectory ===")
print(f"{'step':>6} {'eval_loss':>10} {'eval_kl':>9} {'rew_ch':>9} {'rew_rj':>9} {'margin':>8}")
for e in evals:
    print(f"{e['step']:>6} {e['eval_loss']:>10.4f} {e['eval_kl']:>9.3f} "
          f"{e['eval_rewards/chosen']:>9.3f} {e['eval_rewards/rejected']:>9.3f} {e['eval_rewards/margins']:>8.3f}")

print()
print("=== Stability checks ===")
losses = [e["loss"] for e in train]
kls = [e["kl"] for e in train]
margins = [e["rewards/margins"] for e in train]
grads = [e["grad_norm"] for e in train]

import statistics
def stats(name, arr):
    mn, mx = min(arr), max(arr)
    print(f"  {name:>14}: min={mn:.4f}  max={mx:.4f}  mean={statistics.mean(arr):.4f}  "
          f"final={arr[-1]:.4f}")
stats("loss", losses)
stats("kl", kls)
stats("margins", margins)
stats("grad_norm", grads)

# Detect divergence/instability
print()
print("Late-stage trajectory (last 5 train logs):")
for e in train[-5:]:
    print(f"  step {e['step']}: loss={e['loss']:.4f}  kl={e['kl']:.3f}  margin={e['rewards/margins']:.3f}  grad={e['grad_norm']:.3f}")

# Check: does loss continue to fall, or plateau / diverge?
last_third = losses[len(losses) * 2 // 3:]
mid = losses[len(losses) // 3 : len(losses) * 2 // 3]
first = losses[: len(losses) // 3]
print()
print("Loss thirds (train):")
print(f"  First  third mean: {statistics.mean(first):.4f}")
print(f"  Middle third mean: {statistics.mean(mid):.4f}")
print(f"  Last   third mean: {statistics.mean(last_third):.4f}")
delta_mid = statistics.mean(mid) - statistics.mean(first)
delta_last = statistics.mean(last_third) - statistics.mean(mid)
print(f"  Δ (mid - first):  {delta_mid:+.4f}")
print(f"  Δ (last - mid):   {delta_last:+.4f}")

# Check eval loss trajectory
if len(evals) >= 2:
    print()
    print("Eval loss trajectory:")
    for e in evals:
        marker = ""
        if e == min(evals, key=lambda x: x["eval_loss"]):
            marker = " <-- BEST"
        print(f"  step {e['step']}: eval_loss={e['eval_loss']:.4f}  eval_kl={e['eval_kl']:.3f}{marker}")
