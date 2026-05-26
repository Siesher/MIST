"""V-STaR trajectory generation для DPO pair construction.

For each problem в vstar_subset.jsonl:
  - Generate N=4 trajectories с distinct seeds via llama-server
  - Extract answer per trajectory
  - Score correctness (SymPy/exact match)
  - Save full trajectory data для downstream DPO pair construction

Output: training/data/vstar_trajectories.jsonl — one line per problem с
all N trajectories embedded.

Resume safety: skips already-saved problems на restart (per-problem incremental save).

Source model: mits-eval-gspo (best raw capability, no alignment tax).

Usage:
  uv run python scripts/vstar_generate.py
  uv run python scripts/vstar_generate.py --model mits-eval-kto --n-samples 6
  uv run python scripts/vstar_generate.py --max-problems 10  # smoke test
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from loguru import logger

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
SUBSET_PATH = ROOT / "training/data/vstar_subset.jsonl"
OUT_PATH = ROOT / "training/data/vstar_trajectories.jsonl"
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LLAMA_SERVER_BASE = "http://127.0.0.1:8081/v1"
LLAMA_CHAT_URL = f"{LLAMA_SERVER_BASE}/chat/completions"
LLAMA_MODELS_URL = f"{LLAMA_SERVER_BASE}/models"

SYSTEM_PROMPT = (
    "Ты — репетитор по STEM. Реши задачу пошагово и запиши ОДИН финальный ответ в \\boxed{}."
)

DEFAULT_MODEL = "mits-eval-gspo"
N_SAMPLES_DEFAULT = 4
BASE_SEED = 42

# Sampling config — matches Phase 0a baseline (May 17 proven)
DECODING_CONFIG = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0,
    # max_tokens omitted — let model self-terminate (production parity)
}

WALLCLOCK_CAP_S = 1200
MAX_CONSECUTIVE_ERRORS = 3

EARLY_STOP_BOXED_RE = re.compile(r"\\boxed\{[^{}]*[^.\s{}][^{}]*\}")

_PLACEHOLDER_TOKENS = {
    "...",
    "…",
    "answer",
    "Answer",
    "ответ",
    "Ответ",
    "x",
    "X",
    "y",
    "Y",
    "z",
    "Z",
    "?",
    "??",
    "???",
    "ans",
    "Ans",
    "tbd",
    "TBD",
}


# ─── Helpers (reused from eval_local_llamaserver) ──────────────────────


def setup_logger() -> Path:
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
    )
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"vstar_generate_{ts}.log"
    logger.add(log_file, level="DEBUG", encoding="utf-8", rotation="500 MB")
    logger.info(f"Log file: {log_file}")
    return log_file


def check_llama_server_alive(timeout_s: float = 5.0) -> bool:
    try:
        r = requests.get(LLAMA_MODELS_URL, timeout=timeout_s)
        return r.ok
    except requests.exceptions.RequestException:
        return False


def _clean_boxed(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\\text\s*\{[^}]*\}?", "", s)
    s = re.sub(r"\\mathrm\s*\{[^}]*\}?", "", s)
    s = re.sub(r"\\dots|\\ldots|\\cdots", "", s)
    cleaned = s.strip()
    if cleaned in _PLACEHOLDER_TOKENS:
        return ""
    return cleaned


def extract_answer(text: str) -> str:
    """Returns best-effort extracted answer string (last \\boxed{} preferred)."""
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    if not text:
        return ""

    # Priority 1: all \boxed{} (last wins)
    boxed = []
    for m in re.finditer(r"\\boxed\{([^{}]+)\}", text):
        cleaned = _clean_boxed(m.group(1))
        if cleaned:
            boxed.append(cleaned)
    if boxed:
        return boxed[-1]

    # Priority 2: explicit answer patterns
    last30 = "\n".join(text.split("\n")[-30:])
    for pattern in [
        r"(?:Final\s+Answer|Финальный\s+ответ|Ответ)\s*[:=]\s*\$?\s*\\?boxed?\{?"
        r"([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?:\s*[A-Za-zА-Яа-я/^_]+)?|[A-D])",
        r"^\s*([A-D])\s*$",
    ]:
        m = re.search(pattern, last30, re.MULTILINE)
        if m:
            cand = m.group(1).strip()
            if cand and cand not in _PLACEHOLDER_TOKENS:
                return cand

    # Priority 3: last numeric in last 5 lines
    last5 = "\n".join(text.split("\n")[-5:])
    cleaned5 = re.sub(r"(\d),(\d{3})\b", r"\1\2", last5)
    nums = re.findall(r"[-+]?\d*\.?\d+", cleaned5)
    if nums:
        return nums[-1]
    return ""


def _normalize(s) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    if not s:
        return ""
    if s.startswith("$") and s.endswith("$"):
        s = s[1:-1].strip()
    s = re.sub(r"\\text\s*\{[^}]*\}?", "", s)
    s = re.sub(r"\\mathrm\s*\{[^}]*\}?", "", s)
    s = s.replace(" ", "").replace("\xa0", "").replace(",", ".")
    if "=" in s:
        s = s.split("=")[-1].strip()
    s = s.rstrip(".;,")
    return s


def is_correct(extracted, ground_truth, tolerance: float = 0.02) -> bool | None:
    e = _normalize(extracted)
    g = _normalize(ground_truth)
    if not e or not g:
        return None
    # Numeric path
    try:
        ef, gf = float(e), float(g)
        if abs(gf) < 1e-9:
            return abs(ef) < 0.001
        return abs(ef - gf) / abs(gf) < tolerance
    except ValueError:
        # Symbolic / categorical
        return e.lower() == g.lower()


# ─── llama-server streaming call ───────────────────────────────────────


def call_model_stream(model: str, prompt: str, seed: int) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "stream_options": {"include_usage": True},
        "seed": seed,
        "stop": ["<|im_end|>", "<|endoftext|>"],
        "chat_template_kwargs": {"enable_thinking": True},
        **DECODING_CONFIG,
    }

    full_thinking = ""
    full_content = ""
    n_tokens = 0
    t0 = time.time()
    done_reason = "stop"
    early_stopped = False

    try:
        with requests.post(LLAMA_CHAT_URL, json=body, stream=True, timeout=(30, 120)) as r:
            r.raise_for_status()
            for raw_line in r.iter_lines(decode_unicode=False):
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                if delta.get("reasoning_content"):
                    full_thinking += delta["reasoning_content"]
                if delta.get("content"):
                    full_content += delta["content"]

                if "usage" in chunk and chunk["usage"]:
                    n_tokens = chunk["usage"].get("completion_tokens", n_tokens)

                if not early_stopped and EARLY_STOP_BOXED_RE.search(full_content):
                    early_stopped = True
                    return {
                        "elapsed_s": time.time() - t0,
                        "tokens": n_tokens,
                        "done_reason": "early_boxed",
                        "thinking": full_thinking,
                        "content": full_content,
                    }

                if time.time() - t0 > WALLCLOCK_CAP_S:
                    return {
                        "elapsed_s": time.time() - t0,
                        "tokens": n_tokens,
                        "done_reason": "wallclock_cap",
                        "thinking": full_thinking,
                        "content": full_content,
                    }

                fr = choices[0].get("finish_reason")
                if fr:
                    done_reason = fr
    except requests.exceptions.RequestException as e:
        return {
            "elapsed_s": time.time() - t0,
            "tokens": n_tokens,
            "done_reason": "error",
            "thinking": full_thinking,
            "content": full_content,
            "error": str(e),
        }

    if n_tokens == 0 and (full_thinking or full_content):
        n_tokens = (len(full_thinking) + len(full_content)) // 4

    return {
        "elapsed_s": time.time() - t0,
        "tokens": n_tokens,
        "done_reason": done_reason,
        "thinking": full_thinking,
        "content": full_content,
    }


# ─── Generation loop ──────────────────────────────────────────────────


def generate_trajectories(model: str, prompt: str, n: int) -> list[dict]:
    """N parallel trajectories per problem via ThreadPoolExecutor."""
    seeds = [BASE_SEED + i for i in range(n)]
    with ThreadPoolExecutor(max_workers=n) as ex:
        futures = {ex.submit(call_model_stream, model, prompt, s): i for i, s in enumerate(seeds)}
        results = {futures[f]: f.result() for f in futures}

    trajectories = []
    for idx in sorted(results.keys()):
        r = results[idx]
        full_text = (r["thinking"] + "\n" + r["content"]).strip()
        extracted = extract_answer(full_text)
        trajectories.append(
            {
                "sample_idx": idx,
                "seed": BASE_SEED + idx,
                "thinking": r["thinking"],
                "content": r["content"],
                "extracted": extracted,
                "tokens": r["tokens"],
                "elapsed_s": r["elapsed_s"],
                "done_reason": r["done_reason"],
            }
        )
    return trajectories


def load_done_indices(out_path: Path) -> set[int]:
    """Resume safety — skip already-completed problems."""
    if not out_path.exists():
        return set()
    done = set()
    with open(out_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                done.add(obj["subset_idx"])
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--n-samples", type=int, default=N_SAMPLES_DEFAULT)
    parser.add_argument("--max-problems", type=int, default=None, help="Limit for smoke test")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument("--subset", type=Path, default=SUBSET_PATH, help="Path to subset JSONL")
    args = parser.parse_args()

    log_file = setup_logger()

    if not check_llama_server_alive():
        logger.error(f"llama-server unreachable: {LLAMA_SERVER_BASE}")
        sys.exit(1)
    logger.info(f"llama-server alive ✓ (model: {args.model})")

    # Load subset
    problems = []
    with open(args.subset, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            obj = json.loads(line)
            obj["subset_idx"] = i
            problems.append(obj)
    logger.info(f"Loaded {len(problems)} problems from {args.subset.name}")
    if args.max_problems:
        problems = problems[: args.max_problems]
        logger.info(f"Limited to {len(problems)} (smoke)")

    # Resume: skip already-done
    done_indices = load_done_indices(args.out)
    if done_indices:
        logger.info(f"[RESUME] Skipping {len(done_indices)} already-completed problems")
    problems = [p for p in problems if p["subset_idx"] not in done_indices]
    logger.info(
        f"To process: {len(problems)} problems × N={args.n_samples} = "
        f"{len(problems) * args.n_samples} trajectories"
    )

    # Generate
    t_start = time.time()
    consecutive_errors = 0
    correct_per_problem_counter = {}

    with open(args.out, "a", encoding="utf-8") as out_f:
        for i, p in enumerate(problems):
            t0 = time.time()
            try:
                trajectories = generate_trajectories(args.model, p["prompt"], args.n_samples)
            except Exception as e:
                logger.error(f"Generation failed for idx={p['subset_idx']}: {e}")
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error("Too many consecutive errors — aborting")
                    sys.exit(1)
                continue
            consecutive_errors = 0

            # Score each trajectory
            truth = p.get("answer", "")
            n_correct = 0
            for t in trajectories:
                t["correct"] = is_correct(t["extracted"], truth)
                if t["correct"]:
                    n_correct += 1

            # Save problem с all trajectories
            entry = {
                "subset_idx": p["subset_idx"],
                "prompt": p["prompt"],
                "answer": truth,
                "domain": p.get("domain"),
                "difficulty": p.get("difficulty"),
                "source": p.get("source"),
                "answer_type": p.get("answer_type"),
                "trajectories": trajectories,
                "n_correct": n_correct,
                "n_total": args.n_samples,
                "model": args.model,
            }
            out_f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            out_f.flush()

            # Progress logging
            wall = time.time() - t0
            elapsed_total = time.time() - t_start
            avg_per_problem = elapsed_total / (i + 1)
            eta_s = avg_per_problem * (len(problems) - i - 1)
            eta_str = f"{eta_s / 3600:.1f}h" if eta_s > 3600 else f"{eta_s / 60:.0f}m"

            correct_per_problem_counter[n_correct] = (
                correct_per_problem_counter.get(n_correct, 0) + 1
            )
            usable_pair_rate = sum(
                v for k, v in correct_per_problem_counter.items() if 0 < k < args.n_samples
            ) / max(sum(correct_per_problem_counter.values()), 1)

            logger.info(
                f"[{i + 1}/{len(problems)}] {p.get('domain'):<10} "
                f"{p.get('difficulty'):<7} | {n_correct}/{args.n_samples} ✓ | "
                f"wall={wall:.0f}s | usable={usable_pair_rate:.0%} | ETA {eta_str}"
            )

    # Final summary
    logger.info("")
    logger.info("=== V-STaR generation summary ===")
    logger.info(f"Total time: {(time.time() - t_start) / 3600:.1f}h")
    logger.info(f"Output: {args.out}")
    logger.info("Correct distribution per problem:")
    for k in sorted(correct_per_problem_counter.keys()):
        v = correct_per_problem_counter[k]
        logger.info(
            f"  {k}/{args.n_samples} correct: {v} problems "
            f"({100 * v / max(sum(correct_per_problem_counter.values()), 1):.1f}%)"
        )

    usable = sum(v for k, v in correct_per_problem_counter.items() if 0 < k < args.n_samples)
    total = sum(correct_per_problem_counter.values())
    logger.info(
        f"\nUsable for DPO pairs (0 < n_correct < {args.n_samples}): "
        f"{usable}/{total} = {usable / max(total, 1):.1%}"
    )
    logger.info(f"Full transcripts: {log_file}")


if __name__ == "__main__":
    main()
