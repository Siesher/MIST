"""Phase 0a eval via llama-server (OpenAI-compatible API).

Migration from Ollama: leverages user's existing TurboQuant turbo3 KV cache stack
(C:\\OpenCode\\llama.cpp + llama-swap routing). Production-eval alignment — same
quantization regime as deployed system.

Pipeline per problem:
  1. Adaptive routing: easy/medium → enable_thinking=False (2-3x faster);
                       hard → enable_thinking=True (full chain-of-reasoning).
  2. Self-consistency N=3..5 trajectories at temp=0.7, seed offsets.
  3. llama-server processes batch via --parallel 3 (concurrent slots).
  4. Each sample: stream until first \\boxed{...} (early stop) or max_tokens cap.
  5. Multi-pattern extraction: \\boxed{} > "Final Answer:" > "Magnitude:" > last numeric.
  6. Vote (canonical-grouped mode) → final answer.

Key differences from Ollama version:
  - Endpoint: /v1/chat/completions (OpenAI streaming SSE)
  - Thinking control: chat_template_kwargs.enable_thinking (vs Modelfile template)
  - DRY sampler: server-side, no client-side penalty params
  - Reasoning content: choices[0].delta.reasoning_content (parallel to .content)
  - Slot save path: server-side KV reuse across same-prefix requests

Usage:
  uv run python scripts/eval_local_llamaserver.py
  uv run python scripts/eval_local_llamaserver.py --max-problems 3  # smoke
  uv run python scripts/eval_local_llamaserver.py --stages base gspo  # subset
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
EVAL_PATH = ROOT / "training/data/eval_dataset.jsonl"
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# llama-swap endpoint (OpenAI-compatible, routes к llama-server по `model` field)
LLAMA_SERVER_BASE = "http://127.0.0.1:8081/v1"
LLAMA_CHAT_URL = f"{LLAMA_SERVER_BASE}/chat/completions"
LLAMA_MODELS_URL = f"{LLAMA_SERVER_BASE}/models"

SYSTEM_PROMPT_CALC = (
    "Ты — репетитор по STEM. Реши задачу пошагово и запиши ОДИН финальный ответ в \\boxed{}."
)

# Adaptive sampling configs — temperature/top_k/etc. mirror llama-swap.yaml server defaults.
# Server's DRY sampler handles anti-repetition; client only specifies sampling diversity.
#
# THINK mode: NO max_tokens — production-aligned. Model self-terminates via <|im_end|>
# after </think> + final answer. DRY sampler prevents pathological loops.
# Effective ceiling = --ctx-size 32768 (set in llama-swap.yaml).
DECODING_CONFIG_THINK = {
    # max_tokens intentionally omitted — let model self-terminate (production parity)
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0,
}

# NOTHINK mode: keep cap — purpose is fast direct answer, 4K plenty для commit.
DECODING_CONFIG_NOTHINK = {
    "max_tokens": 4096,
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0,
}

PER_TOKEN_TIMEOUT_S = 60
# Wallclock cap = absolute safety net. At ~80 tok/s on RTX 5070 Ti, 32K tokens ≈ 400s.
# 1200s (20 min) catches pathological cases без resorting к max_tokens cap.
WALLCLOCK_CAP_S = 1200
MAX_CONSECUTIVE_ERRORS = 2

MIN_SAMPLES = 3
MAX_SAMPLES = 5
BASE_SEED = 42

EARLY_STOP_BOXED_RE = re.compile(r"\\boxed\{[^{}]*[^.\s{}][^{}]*\}")

# llama-swap model names (must match llama-swap.yaml entries)
STAGES = {
    "base": "mits-eval-base",
    "gspo": "mits-eval-gspo",
    "kto": "mits-eval-kto",
}


def select_mode(difficulty: str) -> tuple[str, bool]:
    """Adaptive routing — returns (mode_label, enable_thinking)."""
    if difficulty in ("easy", "medium"):
        return "nothink", False
    return "think", True


# ─── Service health check ──────────────────────────────────────────────


def check_llama_server_alive(timeout_s: float = 5.0) -> bool:
    """Probe /v1/models endpoint. False if llama-swap не отвечает."""
    try:
        r = requests.get(LLAMA_MODELS_URL, timeout=timeout_s)
        return r.ok
    except requests.exceptions.RequestException:
        return False


def setup_logger() -> Path:
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"eval_llamaserver_{timestamp}.log"
    logger.add(
        log_file,
        level="DEBUG",
        encoding="utf-8",
        rotation="500 MB",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    )
    logger.info(f"Log file: {log_file}")
    return log_file


# ─── Answer extraction (same logic as Ollama version) ──────────────────

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


def _clean_boxed(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\\text\s*\{[^}]*\}?", "", s)
    s = re.sub(r"\\mathrm\s*\{[^}]*\}?", "", s)
    s = re.sub(r"\\dots|\\ldots|\\cdots", "", s)
    cleaned = s.strip()
    if cleaned in _PLACEHOLDER_TOKENS:
        return ""
    return cleaned


def extract_all_candidates(text: str) -> list[str]:
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    if not text:
        return []
    candidates: list[str] = []

    def _add(s: str) -> None:
        if not s:
            return
        cleaned = s.strip()
        if cleaned and cleaned not in _PLACEHOLDER_TOKENS:
            candidates.append(cleaned)

    last5 = "\n".join(text.split("\n")[-5:])
    cleaned5 = re.sub(r"(\d),(\d{3})\b", r"\1\2", last5)
    nums = re.findall(r"[-+]?\d*\.?\d+", cleaned5)
    if nums:
        _add(nums[-1])

    last30 = "\n".join(text.split("\n")[-30:])
    answer_patterns = [
        r"(?:Final\s+Answer|Финальный\s+ответ|Ответ)\s*[:=]\s*\$?\s*\\?boxed?\{?([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?:\s*[A-Za-zА-Яа-я/^_]+)?)",
        r"(?:Magnitude|Модуль|Величина)\s*[:=]\s*([+-]?\d+(?:\.\d+)?)",
        r"\$\s*[a-zA-Zа-яА-Я]\w*\s*=\s*([+-]?\d+(?:\.\d+)?)",
    ]
    for pattern in answer_patterns:
        for m in re.finditer(pattern, last30, re.IGNORECASE):
            _add(m.group(1))

    for m in re.finditer(r"\\boxed\{([^{}]+)\}", text):
        _add(_clean_boxed(m.group(1)))

    return candidates


# ─── Numeric comparison + voting (same as Ollama version) ──────────────


def _normalize_for_compare(s) -> str:
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
    m = re.match(r"^[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", s)
    if m:
        return m.group(0)
    return s


def is_numeric_correct(extracted, ground_truth, tolerance: float = 0.02):
    e = _normalize_for_compare(extracted)
    g = _normalize_for_compare(ground_truth)
    if not e or not g:
        return None
    try:
        ef, gf = float(e), float(g)
        if abs(gf) < 1e-9:
            return abs(ef) < 0.001
        return abs(ef - gf) / abs(gf) < tolerance
    except ValueError:
        return e.lower() == g.lower()


def _canonical_form(s: str) -> str:
    n = _normalize_for_compare(s)
    if not n:
        return ""
    try:
        f = float(n)
        return f"{f:.4f}".rstrip("0").rstrip(".")
    except ValueError:
        return n


def _consensus_reached(samples: list[str]) -> bool:
    if len(samples) < MIN_SAMPLES:
        return False
    canonical = [_canonical_form(s) for s in samples if s and s.strip()]
    canonical = [c for c in canonical if c]
    if not canonical:
        return False
    from collections import Counter

    most_common_freq = Counter(canonical).most_common(1)[0][1]
    return most_common_freq > len(samples) / 2


def vote(samples: list[str]) -> str:
    from collections import Counter

    valid = [s for s in samples if s and s.strip()]
    if not valid:
        return ""
    canonical_to_first: dict[str, str] = {}
    canonical_seq: list[str] = []
    for s in valid:
        c = _canonical_form(s)
        if not c:
            continue
        if c not in canonical_to_first:
            canonical_to_first[c] = s
        canonical_seq.append(c)
    if not canonical_seq:
        return ""
    most_common_canonical, _ = Counter(canonical_seq).most_common(1)[0]
    return canonical_to_first[most_common_canonical]


# ─── llama-server streaming call ───────────────────────────────────────


def call_llama_server_stream(
    model: str,
    prompt: str,
    seed: int = BASE_SEED,
    enable_thinking: bool = True,
) -> dict:
    """Streaming call к llama-server OpenAI-compatible endpoint.

    Args:
        model: llama-swap model name (e.g. mits-eval-base)
        prompt: user prompt
        seed: per-sample seed для self-consistency diversity
        enable_thinking: Qwen3.5 chat_template_kwarg — True for hard, False for easy

    Returns dict с elapsed_s, tokens, done_reason, thinking, content.
    """
    config = DECODING_CONFIG_NOTHINK if not enable_thinking else DECODING_CONFIG_THINK

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_CALC},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "stream_options": {"include_usage": True},  # emit usage в final chunk (token count)
        "seed": seed,
        "stop": ["<|im_end|>", "<|endoftext|>"],
        # llama-server-specific: chat_template_kwargs passes through to Jinja template
        "chat_template_kwargs": {"enable_thinking": enable_thinking},
        **config,
    }

    full_thinking = ""
    full_content = ""
    n_tokens = 0
    t0 = time.time()
    early_stopped = False
    done_reason = "stop"

    try:
        # connect 30s, read timeout 120s (если no chunk arrives within 2 min → likely
        # llama-swap stuck on model load OR llama-server hung. Without this, hangs forever.)
        with requests.post(
            LLAMA_CHAT_URL,
            json=body,
            stream=True,
            timeout=(30, 120),
        ) as r:
            r.raise_for_status()
            for raw_line in r.iter_lines(decode_unicode=False):
                if not raw_line:
                    continue
                line_str = raw_line.decode("utf-8", errors="replace").strip()
                # OpenAI SSE format: "data: {json}"
                if not line_str.startswith("data: "):
                    continue
                payload = line_str[6:]  # strip "data: "
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError as e:
                    logger.warning(f"Bad SSE chunk: {e} | line: {line_str[:200]}")
                    continue

                # Extract delta — choices[0].delta может содержать .content и/или .reasoning_content
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})

                if delta.get("reasoning_content"):
                    full_thinking += delta["reasoning_content"]
                if delta.get("content"):
                    full_content += delta["content"]

                # Token count — usage может быть только в final chunk
                if "usage" in chunk and chunk["usage"]:
                    n_tokens = chunk["usage"].get("completion_tokens", n_tokens)

                # Early-stop on first complete \boxed{...} в content (post-thinking)
                if not early_stopped and EARLY_STOP_BOXED_RE.search(full_content):
                    early_stopped = True
                    return {
                        "elapsed_s": time.time() - t0,
                        "tokens": n_tokens,
                        "done_reason": "early_boxed",
                        "thinking": full_thinking,
                        "content": full_content,
                    }

                # Wall-clock cap
                total = time.time() - t0
                if total > WALLCLOCK_CAP_S:
                    logger.warning(f"Wall-clock cap hit ({WALLCLOCK_CAP_S}s) — aborting")
                    return {
                        "elapsed_s": total,
                        "tokens": n_tokens,
                        "done_reason": "wallclock_cap",
                        "thinking": full_thinking,
                        "content": full_content,
                    }

                # Finish reason — final chunk has non-null finish_reason
                fr = choices[0].get("finish_reason")
                if fr:
                    done_reason = fr  # 'stop' / 'length' / 'tool_calls'
    except requests.exceptions.RequestException as e:
        logger.error(f"llama-server request failed: {e}")
        return {
            "elapsed_s": time.time() - t0,
            "tokens": n_tokens,
            "done_reason": "error",
            "thinking": full_thinking,
            "content": full_content,
        }

    return {
        "elapsed_s": time.time() - t0,
        "tokens": n_tokens,
        "done_reason": done_reason,
        "thinking": full_thinking,
        "content": full_content,
    }


# ─── Dataset ───────────────────────────────────────────────────────────


def load_calc_problems() -> list[dict]:
    problems = []
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            p = json.loads(line)
            if p.get("answer_type") in ("numeric", "latex_boxed"):
                problems.append(p)
    return problems


# ─── Eval loop ─────────────────────────────────────────────────────────


def eval_stage(stage_name: str, problems: list[dict]) -> dict:
    """Self-consistency eval — N=3..5 parallel trajectories per problem via llama-server."""
    model_tag = STAGES[stage_name]
    logger.info(f"=== Stage: {stage_name} ({model_tag}) ===")
    completions = []
    t_stage = time.time()
    consecutive_errors = 0

    for i, p in enumerate(problems):
        difficulty = p.get("difficulty", "?")
        truth = p["ground_truth"]
        prompt = p["prompt"]

        mode, enable_thinking = select_mode(difficulty)

        logger.info(
            f"--- Problem {i + 1}/{len(problems)} [{difficulty}] truth={truth} mode={mode} ---"
        )
        logger.debug(f"Q: {prompt}")

        t0_problem = time.time()

        sample_answers: list[str] = []
        sample_records: list[dict] = []
        consensus_at: int | None = None

        def _process_batch(indices: list[int]) -> None:
            nonlocal consecutive_errors
            with ThreadPoolExecutor(max_workers=len(indices)) as ex:
                futures = {
                    ex.submit(
                        call_llama_server_stream,
                        model_tag,
                        prompt,
                        BASE_SEED + idx,
                        enable_thinking,
                    ): idx
                    for idx in indices
                }
                results = {futures[f]: f.result() for f in futures}

            for idx in sorted(results.keys()):
                r = results[idx]
                seed_i = BASE_SEED + idx

                if r["done_reason"] == "error" and r["tokens"] == 0 and r["elapsed_s"] < 10:
                    consecutive_errors += 1
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(
                            f"llama-server unreachable: {consecutive_errors} consecutive errors. "
                            f"Check llama-swap status: {LLAMA_SERVER_BASE}. Aborting."
                        )
                        raise RuntimeError("llama-server unavailable — aborting eval cleanly")
                else:
                    consecutive_errors = 0

                full_text = (r["thinking"] + "\n" + r["content"]).strip()
                candidates = extract_all_candidates(full_text)
                sample_answer = candidates[-1] if candidates else ""
                sample_answers.append(sample_answer)

                sample_records.append(
                    {
                        "sample_idx": idx,
                        "seed": seed_i,
                        "answer": sample_answer,
                        "candidates": candidates,
                        "n_tokens": r["tokens"],
                        "elapsed_s": r["elapsed_s"],
                        "done_reason": r["done_reason"],
                        "thinking_text": r["thinking"],
                        "content_text": r["content"],
                    }
                )
                logger.debug(
                    f"  sample[{idx}] seed={seed_i} | tokens={r['tokens']} | "
                    f"done={r['done_reason']} | answer={sample_answer!r}"
                )

        # Phase 1: parallel MIN_SAMPLES
        _process_batch(list(range(MIN_SAMPLES)))

        if _consensus_reached(sample_answers):
            consensus_at = MIN_SAMPLES
            logger.debug(f"  consensus reached at N={consensus_at} (phase 1)")
        elif MAX_SAMPLES > MIN_SAMPLES:
            _process_batch(list(range(MIN_SAMPLES, MAX_SAMPLES)))
            if _consensus_reached(sample_answers):
                consensus_at = MAX_SAMPLES
                logger.debug(f"  consensus reached at N={consensus_at} (phase 2)")

        final_answer = vote(sample_answers)
        correct = is_numeric_correct(final_answer, truth)

        total_tokens = sum(r["n_tokens"] for r in sample_records)
        total_elapsed = sum(r["elapsed_s"] for r in sample_records)
        wall_clock_s = time.time() - t0_problem
        any_natural_stop = any(r["done_reason"] in ("stop", "early_boxed") for r in sample_records)
        any_timeout = any(
            r["done_reason"] in ("wallclock_cap", "stale", "error", "length")
            for r in sample_records
        )
        any_think_close = any(
            r["thinking_text"] and len(r["thinking_text"]) > 0 for r in sample_records
        )

        completions.append(
            {
                "idx": i,
                "domain": p.get("domain"),
                "difficulty": difficulty,
                "mode": mode,
                "model_tag": model_tag,
                "truth": truth,
                "extracted": final_answer,
                "correct": correct,
                "n_samples": len(sample_records),
                "consensus_at": consensus_at,
                "sample_answers": sample_answers,
                "n_tokens_total": total_tokens,
                "elapsed_s_total": total_elapsed,
                "wall_clock_s": wall_clock_s,
                "any_natural_stop": any_natural_stop,
                "any_timeout": any_timeout,
                "any_think_close": any_think_close,
                "samples": sample_records,
            }
        )

        valid = [c for c in completions if c["correct"] is not None]
        acc = sum(1 for c in valid if c["correct"]) / max(len(valid), 1)
        par_factor = total_elapsed / max(wall_clock_s, 0.01)
        logger.info(
            f"  N={len(sample_records)} (consensus@{consensus_at}) | "
            f"tok={total_tokens} | wall={wall_clock_s:.1f}s (Σ={total_elapsed:.1f}s, par={par_factor:.1f}x) | "
            f"votes={sample_answers} | final={final_answer!r} | correct={correct} | "
            f"acc={acc:.3f} ({len(valid)} judged)"
        )

        for sr in sample_records:
            logger.debug(
                f"\n=== SAMPLE {sr['sample_idx']} (seed={sr['seed']}, "
                f"tokens={sr['n_tokens']}, done={sr['done_reason']}) ==="
            )
            logger.debug(
                f"--- THINKING ({len(sr['thinking_text'])} chars) ---\n{sr['thinking_text']}"
            )
            logger.debug(f"--- CONTENT ({len(sr['content_text'])} chars) ---\n{sr['content_text']}")
        logger.debug(f"=== END Problem {i + 1} ===\n")

    # Aggregate
    valid = [c for c in completions if c["correct"] is not None]
    accuracy = sum(1 for c in valid if c["correct"]) / max(len(valid), 1)
    n = len(completions)
    natural_stop_rate = sum(1 for c in completions if c["any_natural_stop"]) / max(n, 1)
    timeout_rate = sum(1 for c in completions if c["any_timeout"]) / max(n, 1)
    think_close_rate = sum(1 for c in completions if c["any_think_close"]) / max(n, 1)
    nothink_rate = sum(1 for c in completions if c["mode"] == "nothink") / max(n, 1)
    mean_samples = sum(c["n_samples"] for c in completions) / max(n, 1)
    mean_tokens = sum(c["n_tokens_total"] for c in completions) / max(n, 1)
    mean_elapsed = sum(c["elapsed_s_total"] for c in completions) / max(n, 1)
    mean_wall = sum(c["wall_clock_s"] for c in completions) / max(n, 1)
    consensus_rate = sum(1 for c in completions if c["consensus_at"] is not None) / max(n, 1)
    sum_elapsed = sum(c["elapsed_s_total"] for c in completions)
    sum_wall = sum(c["wall_clock_s"] for c in completions)
    parallel_factor = sum_elapsed / max(sum_wall, 0.01)

    return {
        "stage": stage_name,
        "model": model_tag,
        "n": n,
        "n_judged": len(valid),
        "accuracy": accuracy,
        "natural_stop_rate": natural_stop_rate,
        "timeout_rate": timeout_rate,
        "think_close_rate": think_close_rate,
        "consensus_rate": consensus_rate,
        "nothink_rate": nothink_rate,
        "mean_samples": mean_samples,
        "mean_tokens": mean_tokens,
        "mean_elapsed_s": mean_elapsed,
        "mean_wall_clock_s": mean_wall,
        "parallel_factor": parallel_factor,
        "elapsed_total_s": time.time() - t_stage,
        "completions": completions,
    }


# ─── Main ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stages", nargs="+", default=list(STAGES.keys()), choices=list(STAGES.keys())
    )
    parser.add_argument("--max-problems", type=int, default=None)
    args = parser.parse_args()

    log_file = setup_logger()

    if not check_llama_server_alive():
        logger.error(
            f"llama-server не отвечает на {LLAMA_SERVER_BASE}. "
            f"Start: launch llama-swap.exe С C:/OpenCode/llama-swap/. Aborting."
        )
        sys.exit(1)
    logger.info(f"llama-server alive ✓ ({LLAMA_SERVER_BASE})")

    problems = load_calc_problems()
    logger.info(f"Loaded {len(problems)} calc problems из {EVAL_PATH}")
    if args.max_problems:
        problems = problems[: args.max_problems]
        logger.info(f"Limited to {len(problems)} problems")

    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_dir = ROOT / f"evaluation/reports/honest_phase0a_llamaserver_{date_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output dir: {out_dir}")

    results = {}
    for stage_name in args.stages:
        stage_file = out_dir / f"{stage_name}.json"

        if stage_file.exists():
            logger.info(f"[RESUME] {stage_name} loaded from {stage_file.name}")
            results[stage_name] = json.loads(stage_file.read_text(encoding="utf-8"))
            continue

        r = eval_stage(stage_name, problems)
        results[stage_name] = r

        stage_file.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        sz = stage_file.stat().st_size / 1024
        logger.info(f"[SAVED] {stage_file.name} ({sz:.1f} KB)")

    logger.info("")
    logger.info(
        "=== Phase 0a (llama-server turbo3, self-consistency N=3..5, adaptive routing) — Summary ==="
    )
    logger.info(
        f"{'Stage':<6} {'acc':<7} {'cons%':<7} {'meanN':<6} "
        f"{'tok':<7} {'wall':<7} {'par':<5} {'nat%':<6} {'nt%':<6} n"
    )
    for stage in args.stages:
        r = results[stage]
        logger.info(
            f"{stage:<6} {r['accuracy']:<7.3f} "
            f"{r['consensus_rate'] * 100:<7.1f} {r['mean_samples']:<6.2f} "
            f"{int(r['mean_tokens']):<7} {r['mean_wall_clock_s']:<7.1f} "
            f"{r['parallel_factor']:<5.1f} "
            f"{r['natural_stop_rate'] * 100:<6.1f} {r['nothink_rate'] * 100:<6.1f} "
            f"{r['n_judged']}/{r['n']}"
        )
    logger.info(f"\nFull transcripts: {log_file}")


if __name__ == "__main__":
    main()
