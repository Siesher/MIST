"""Local Phase 0a eval через Ollama — self-consistency + adaptive routing.

Pipeline per problem:
  1. Adaptive routing: easy/medium → nothink variant (2K budget, 2-3x faster);
                       hard → think variant (8K budget, full chain-of-reasoning)
  2. Sample N=3 trajectories at temp=0.7 with seed offsets (BASE_SEED + i)
  3. Each sample: stream until first \\boxed{...} (early stop) или num_predict cap
  4. Multi-pattern extraction: \\boxed{} > "Final Answer:" > "Magnitude:" > last numeric
  5. If majority of N=3 agree → consensus, terminate sampling
  6. Else expand to N=5, then vote() aggregates final answer

Why self-consistency:
  - Anti-commitment patho (Qwen3.5 enumerates "if A else B" trained-in) is SEMANTIC,
    не token-level — penalty defenses (presence/repeat/freq) backfired (5800+ tokens).
  - Mode-of-N samples concentrates on correct answer (Wang et al. 2022, arXiv 2203.11171):
    different seeds traverse different reasoning paths; correct answer most-frequent.

Loguru logging:
  - Console: INFO level (running acc, votes per problem)
  - File logs/eval_local_<timestamp>.log: DEBUG level (per-sample thinking + content)

Resumable per-stage saves к evaluation/reports/honest_phase0a_local_<date>/{stage}.json.

Usage:
  uv run python scripts/eval_local_ollama.py
  uv run python scripts/eval_local_ollama.py --max-problems 3  # smoke
  uv run python scripts/eval_local_ollama.py --stages base gspo  # subset
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from loguru import logger

# UTF-8 stdout — Windows default cp1251 ломает Russian Cyrillic
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
EVAL_PATH = ROOT / "training/data/eval_dataset.jsonl"
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/chat"

SYSTEM_PROMPT_CALC = (
    "Ты — репетитор по STEM. Реши задачу пошагово и запиши ОДИН финальный ответ в \\boxed{}.\n"
    "ПРАВИЛА:\n"
    '1. НЕ перечисляй альтернативы (не пиши "если бы было так...", "в случае X — иначе Y").\n'
    "2. НЕ оговаривай несколько случаев. Прими стандартные допущения и реши ОДИН раз.\n"
    "3. Стандартные допущения для физики: g=9.8 м/с², кинетическое трение если упоминается μ, "
    "движение по умолчанию (если задача даёт ускорение, тело движется).\n"
    "4. Сразу после \\boxed{...} заверши решение. Не пересчитывай и не сомневайся."
)

# Adaptive decoding configs — routed по problem difficulty в `select_model()`.
# Думающий variant (для hard problems): full thinking budget for chain-of-reasoning.
# No-thinking variant (для easy/medium): direct answer phase, 2-3x faster.

_BASE_DECODING = {
    "temperature": 0.7,  # diverse sampling for self-consistency
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0,
    "presence_penalty": 1.5,  # Qwen rec only — keep token-level uniqueness baseline
    "num_keep": 256,  # cache system prompt KV across same-prompt re-samples (~5% win)
    # Removed repeat_penalty + frequency_penalty — they backfired (5800+ tokens, no commit).
    # Sampling diversity comes from temperature + per-sample seed offset.
}

DECODING_CONFIG_THINK = {
    **_BASE_DECODING,
    "num_predict": 8192,  # ~5K thinking + ~1K commit, early-stop fires post-commit
}

DECODING_CONFIG_NOTHINK = {
    **_BASE_DECODING,
    "num_predict": 2048,  # answer phase only — \boxed{} fits comfortably в 2K
}

PER_TOKEN_TIMEOUT_S = 60  # max gap между tokens (Ollama backend stuck)
# WALLCLOCK_CAP_S must scale with num_predict. At 14 tok/s, 8192 tokens = ~585s;
# plus warmup + safety margin. Formula: num_predict / 10 tok/s + 80s overhead.
WALLCLOCK_CAP_S = 900  # absolute upper bound per sample (15 min, fits 8192 budget)
MAX_CONSECUTIVE_ERRORS = 2  # fail-fast: abort если N samples в ряд получают connection error

# Self-consistency voting params
MIN_SAMPLES = 3  # минимальное число trajectories перед consensus check
MAX_SAMPLES = 5  # абсолютный потолок per problem
BASE_SEED = 42  # seed[i] = BASE_SEED + i — same across stages для fair comparison

# Early-stop pattern: \boxed{...} where content has at least one non-dot non-whitespace char.
# Rejects placeholders like \boxed{...}, \boxed{ }, \boxed{...} that fire premature stops
# когда модель планирует format в thinking phase ("Я запишу ответ в \boxed{...}").
EARLY_STOP_BOXED_RE = re.compile(r"\\boxed\{[^{}]*[^.\s{}][^{}]*\}")

# Adaptive routing: each stage exposes both think + nothink variants.
# `select_model()` picks based on problem difficulty (easy/medium → nothink, hard → think).
STAGES: dict[str, dict[str, str]] = {
    "base": {"think": "mits-eval-base", "nothink": "mits-eval-base-nothink"},
    "gspo": {"think": "mits-eval-gspo", "nothink": "mits-eval-gspo-nothink"},
    "kto": {"think": "mits-eval-kto", "nothink": "mits-eval-kto-nothink"},
}


def select_model(stage_name: str, difficulty: str) -> tuple[str, str]:
    """Adaptive routing по problem difficulty.

    Easy/medium problems → nothink variant (2-3x faster, no reasoning depth needed).
    Hard / unknown difficulty → think variant (preserves chain-of-reasoning capability).

    Returns:
        (model_tag, mode) where mode ∈ {"think", "nothink"}
    """
    mode = "nothink" if difficulty in ("easy", "medium") else "think"
    return STAGES[stage_name][mode], mode


def check_ollama_alive(timeout_s: float = 5.0) -> bool:
    """Ping Ollama service before starting eval. False если down."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=timeout_s)
        return r.ok
    except requests.exceptions.RequestException:
        return False


def setup_logger() -> Path:
    """Setup loguru — console INFO + file DEBUG (full transcripts)."""
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"eval_local_{timestamp}.log"
    logger.add(
        log_file,
        level="DEBUG",
        encoding="utf-8",
        rotation="500 MB",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    )
    logger.info(f"Log file: {log_file}")
    return log_file


# ─── Answer extraction ─────────────────────────────────────────────────


def extract_answer(text: str) -> str:
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    if not text:
        return ""

    boxed = re.findall(r"\\boxed\{([^}]+)\}", text)
    if boxed:
        return _clean_boxed(boxed[-1])

    m = re.search(
        r"(?:правильный\s+)?(?:ответ|answer)\s*[:=—–\-]\s*\*{0,2}\s*([A-DА-Гa-dа-г])\b",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()

    m = re.search(
        r"(?:правильный\s+)?(?:ответ|answer|вариант(?:\s+ответа)?)\s*[:=—–\-]\s*(.+?)(?:\.\s|$)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()

    cleaned = re.sub(r"(\d),(\d{3})\b", r"\1\2", text)
    numbers = re.findall(r"[-+]?\d*\.?\d+", cleaned)
    return numbers[-1] if numbers else ""


# Known placeholder/junk extractions to filter — model writes these когда не commit к real answer
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
    """Clean LaTeX wrappers + filter placeholder tokens."""
    s = s.strip()
    s = re.sub(r"\\text\s*\{[^}]*\}?", "", s)
    s = re.sub(r"\\mathrm\s*\{[^}]*\}?", "", s)
    s = re.sub(r"\\dots|\\ldots|\\cdots", "", s)
    cleaned = s.strip()
    if cleaned in _PLACEHOLDER_TOKENS:
        return ""
    return cleaned


def extract_all_candidates(text: str) -> list[str]:
    """Multi-pattern extraction — returns ordered candidates from a single trajectory.

    Priority (later in list = stronger signal — `candidates[-1]` is final pick):
      1. Last numeric в последних 5 lines (weakest, fallback for free-form text)
      2. "Final Answer:" / "Magnitude:" / "$a = N$" patterns в last 30 lines
      3. All \\boxed{} occurrences (strongest signal — model committed)

    Filters: placeholders ("...", "answer", "X" etc.) discarded via `_clean_boxed`.
    Returns: list of non-empty candidates (last = best). [] if nothing found.
    """
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    if not text:
        return []

    candidates: list[str] = []

    def _add(s: str) -> None:
        """Append after stripping + placeholder filter."""
        if not s:
            return
        cleaned = s.strip()
        if cleaned and cleaned not in _PLACEHOLDER_TOKENS:
            candidates.append(cleaned)

    # Priority 1 (weakest): last numeric в последних 5 lines
    last5 = "\n".join(text.split("\n")[-5:])
    cleaned5 = re.sub(r"(\d),(\d{3})\b", r"\1\2", last5)
    nums = re.findall(r"[-+]?\d*\.?\d+", cleaned5)
    if nums:
        _add(nums[-1])

    # Priority 2: explicit answer patterns в last 30 lines
    last30 = "\n".join(text.split("\n")[-30:])
    answer_patterns = [
        # Russian "Ответ: ..." or English "Final Answer: ..." — strict numeric/symbolic capture
        r"(?:Final\s+Answer|Финальный\s+ответ|Ответ)\s*[:=]\s*\$?\s*\\?boxed?\{?([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?:\s*[A-Za-zА-Яа-я/^_]+)?)",
        # Magnitude / модуль — pure numeric
        r"(?:Magnitude|Модуль|Величина)\s*[:=]\s*([+-]?\d+(?:\.\d+)?)",
        # "$a = N$" / "$v = N$" inline-math assignment
        r"\$\s*[a-zA-Zа-яА-Я]\w*\s*=\s*([+-]?\d+(?:\.\d+)?)",
    ]
    for pattern in answer_patterns:
        for m in re.finditer(pattern, last30, re.IGNORECASE):
            _add(m.group(1))

    # Priority 3 (strongest): все \boxed{} — order preserved, last wins
    for m in re.finditer(r"\\boxed\{([^{}]+)\}", text):
        _add(_clean_boxed(m.group(1)))

    return candidates


def _canonical_form(s: str) -> str:
    """Canonical form for grouping equivalent answers (used by both consensus + vote).

    Strategy: numeric → float-roundtrip с rounding to 4 decimals → strip trailing zeros.
    This groups "1.56" / "1.560" / "1.5600" together (same value, different surface form).
    Non-numeric → fall back to plain `_normalize_for_compare` (string equality).
    """
    n = _normalize_for_compare(s)
    if not n:
        return ""
    try:
        f = float(n)
        return f"{f:.4f}".rstrip("0").rstrip(".")
    except ValueError:
        return n


def _consensus_reached(samples: list[str]) -> bool:
    """Strict majority of canonical samples agree (> N/2)."""
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
    """Self-consistency voting — mode of canonical-grouped answers.

    Algorithm:
      1. Filter empty samples (no-vote)
      2. Compute `_canonical_form` per sample (groups "1.56" / "1.560" together)
      3. Mode via `Counter.most_common(1)` — ties broken by insertion order (deterministic)
      4. Return ORIGINAL form of the first sample in the winning group (preserves UI surface)

    Args:
        samples: N trajectory answers (may include "" for failed trajectories)

    Returns:
        Final voted answer in original form. Empty string if all samples invalid.
    """
    from collections import Counter

    valid = [s for s in samples if s and s.strip()]
    if not valid:
        return ""

    # Map canonical → first original (Python 3.7+ dict preserves insertion order
    # → ties resolve to earliest-encountered original surface form).
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

    # Counter.most_common: ties broken by insertion order → earliest occurrence wins
    most_common_canonical, _ = Counter(canonical_seq).most_common(1)[0]
    return canonical_to_first[most_common_canonical]


# ─── Numeric comparison ────────────────────────────────────────────────


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


# ─── Streaming Ollama wrapper ──────────────────────────────────────────


def call_ollama_stream(model: str, prompt: str, seed: int = BASE_SEED, mode: str = "think") -> dict:
    """Streaming call — accumulates tokens incrementally with early-stop on \\boxed{...}.

    Args:
        model: Ollama model tag (e.g. mits-eval-base)
        prompt: user prompt
        seed: per-sample seed for self-consistency diversity (BASE_SEED + sample_idx)
        mode: "think" (8192 budget, для hard) or "nothink" (2048 budget, для easy/medium)

    Returns dict с elapsed_s, tokens, done_reason ('stop'/'length'/'early_boxed'/'stale'/'error'),
    thinking (full), content (full).
    """
    config = DECODING_CONFIG_NOTHINK if mode == "nothink" else DECODING_CONFIG_THINK
    options = dict(config)
    options["seed"] = seed

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_CALC},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "options": options,
    }

    full_thinking = ""
    full_content = ""
    n_tokens = 0
    t0 = time.time()
    last_token_time = t0
    early_stopped = False

    try:
        with requests.post(
            OLLAMA_URL,
            json=body,
            stream=True,
            timeout=(30, None),  # connect 30s, read None (we manage stale ourselves)
        ) as r:
            r.raise_for_status()
            for raw_line in r.iter_lines(decode_unicode=False):
                if not raw_line:
                    continue
                try:
                    chunk = json.loads(raw_line.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"Bad chunk skipped: {e}")
                    continue

                msg = chunk.get("message", {})
                if msg.get("thinking"):
                    full_thinking += msg["thinking"]
                if msg.get("content"):
                    full_content += msg["content"]
                if "eval_count" in chunk:
                    n_tokens = chunk["eval_count"]

                # Early stop on first complete \boxed{...} в content (visible answer phase).
                # Saves ~3-5K wasted tokens of post-answer rambling.
                if not early_stopped and EARLY_STOP_BOXED_RE.search(full_content):
                    early_stopped = True
                    return {
                        "elapsed_s": time.time() - t0,
                        "tokens": n_tokens,
                        "done_reason": "early_boxed",
                        "thinking": full_thinking,
                        "content": full_content,
                    }

                # Stale detection — no new chunk in PER_TOKEN_TIMEOUT_S
                now = time.time()
                last_token_time = now

                # Wall-clock cap
                total = now - t0
                if total > WALLCLOCK_CAP_S:
                    logger.warning(f"Wall-clock cap hit ({WALLCLOCK_CAP_S}s) — aborting")
                    return {
                        "elapsed_s": total,
                        "tokens": n_tokens,
                        "done_reason": "wallclock_cap",
                        "thinking": full_thinking,
                        "content": full_content,
                    }

                if chunk.get("done"):
                    return {
                        "elapsed_s": now - t0,
                        "tokens": n_tokens,
                        "done_reason": chunk.get("done_reason", "stop"),
                        "thinking": full_thinking,
                        "content": full_content,
                    }
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        return {
            "elapsed_s": time.time() - t0,
            "tokens": n_tokens,
            "done_reason": "error",
            "thinking": full_thinking,
            "content": full_content,
        }

    # Stream ended без `done` — partial response
    return {
        "elapsed_s": time.time() - t0,
        "tokens": n_tokens,
        "done_reason": "stale",
        "thinking": full_thinking,
        "content": full_content,
    }


# ─── Dataset loading ──────────────────────────────────────────────────


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


# ─── Eval loop ────────────────────────────────────────────────────────


def eval_stage(stage_name: str, problems: list[dict]) -> dict:
    """Self-consistency eval — N=3..5 trajectories per problem, vote() aggregates.

    Adaptive routing per-problem: model picked в `select_model()` based on difficulty.
    Easy/medium problems use nothink variant (2-3x faster), hard use full thinking.
    """
    think_tag = STAGES[stage_name]["think"]
    nothink_tag = STAGES[stage_name]["nothink"]
    logger.info(f"=== Stage: {stage_name} (think={think_tag}, nothink={nothink_tag}) ===")
    completions = []
    t_stage = time.time()
    consecutive_errors = 0  # fail-fast on Ollama service crash mid-run

    for i, p in enumerate(problems):
        difficulty = p.get("difficulty", "?")
        truth = p["ground_truth"]
        prompt = p["prompt"]

        # Adaptive routing — picks think vs nothink variant
        model_tag, mode = select_model(stage_name, difficulty)

        logger.info(
            f"--- Problem {i + 1}/{len(problems)} [{difficulty}] truth={truth} mode={mode} ---"
        )
        logger.debug(f"Q: {prompt}")

        t0_problem = time.time()  # wall-clock start for problem (parallel-aware)

        # Self-consistency sampling — parallel batches via ThreadPoolExecutor.
        # Phase 1: MIN_SAMPLES в parallel (3 concurrent Ollama requests). Ollama c
        # OLLAMA_NUM_PARALLEL=3+ обрабатывает их одновременно на GPU (batched weight reads,
        # 3-5x throughput на decode phase). Phase 2: parallel expansion если no consensus.
        sample_answers: list[str] = []
        sample_records: list[dict] = []
        consensus_at: int | None = None

        def _process_batch(indices: list[int]) -> bool:
            """Запускает batch sample indices в parallel, populates lists in order.

            Returns False если fail-fast triggered (caller raises).
            """
            nonlocal consecutive_errors

            # Submit all в parallel
            with ThreadPoolExecutor(max_workers=len(indices)) as ex:
                futures = {
                    ex.submit(
                        call_ollama_stream,
                        model_tag,
                        prompt,
                        BASE_SEED + idx,
                        mode,
                    ): idx
                    for idx in indices
                }
                results = {futures[f]: f.result() for f in futures}

            # Process in submission order (preserves sample_idx semantics)
            for idx in sorted(results.keys()):
                r = results[idx]
                seed_i = BASE_SEED + idx

                # Fail-fast: connection error signature
                if r["done_reason"] == "error" and r["tokens"] == 0 and r["elapsed_s"] < 10:
                    consecutive_errors += 1
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(
                            f"Ollama unreachable: {consecutive_errors} consecutive errors. "
                            f"Service likely crashed. Restart: 'ollama serve' or Ollama Desktop. "
                            f"Per-stage incremental save preserved для resume."
                        )
                        raise RuntimeError("Ollama service unavailable — aborting eval cleanly")
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
            return True

        # Phase 1: parallel batch of MIN_SAMPLES
        _process_batch(list(range(MIN_SAMPLES)))

        # Consensus check после phase 1
        if _consensus_reached(sample_answers):
            consensus_at = MIN_SAMPLES
            logger.debug(f"  consensus reached at N={consensus_at} (phase 1)")
        elif MAX_SAMPLES > MIN_SAMPLES:
            # Phase 2: parallel expansion (remaining samples)
            _process_batch(list(range(MIN_SAMPLES, MAX_SAMPLES)))
            if _consensus_reached(sample_answers):
                consensus_at = MAX_SAMPLES
                logger.debug(f"  consensus reached at N={consensus_at} (phase 2)")

        # Voting (TODO(human) implementation)
        try:
            final_answer = vote(sample_answers)
        except NotImplementedError as e:
            logger.error(f"vote() not implemented yet: {e}")
            raise

        correct = is_numeric_correct(final_answer, truth)

        # Aggregate per-problem metrics across samples
        total_tokens = sum(r["n_tokens"] for r in sample_records)
        total_elapsed = sum(r["elapsed_s"] for r in sample_records)
        any_natural_stop = any(r["done_reason"] in ("stop", "early_boxed") for r in sample_records)
        any_timeout = any(
            r["done_reason"] in ("wallclock_cap", "stale", "error") for r in sample_records
        )
        any_think_close = any("</think>" in r["content_text"] for r in sample_records)
        wall_clock_s = time.time() - t0_problem  # actual experienced latency (parallel-aware)

        completions.append(
            {
                "idx": i,
                "domain": p.get("domain"),
                "difficulty": difficulty,
                "mode": mode,  # think / nothink — adaptive routing decision
                "model_tag": model_tag,  # actual Ollama model used
                "truth": truth,
                "extracted": final_answer,
                "correct": correct,
                "n_samples": len(sample_records),
                "consensus_at": consensus_at,
                "sample_answers": sample_answers,
                "n_tokens_total": total_tokens,
                "elapsed_s_total": total_elapsed,  # sum of per-sample elapsed (parallel: > wall)
                "wall_clock_s": wall_clock_s,  # actual wall-clock — reflects parallelism
                "any_natural_stop": any_natural_stop,
                "any_timeout": any_timeout,
                "any_think_close": any_think_close,
                "samples": sample_records,
            }
        )

        # Running accuracy
        valid = [c for c in completions if c["correct"] is not None]
        acc = sum(1 for c in valid if c["correct"]) / max(len(valid), 1)
        # Parallelism factor: ratio of cumulative time / wall — shows effective speedup
        par_factor = total_elapsed / max(wall_clock_s, 0.01)
        logger.info(
            f"  N={len(sample_records)} (consensus@{consensus_at}) | "
            f"tok={total_tokens} | wall={wall_clock_s:.1f}s (Σelapsed={total_elapsed:.1f}s, par={par_factor:.1f}x) | "
            f"votes={sample_answers} | final={final_answer!r} | correct={correct} | "
            f"acc={acc:.3f} ({len(valid)} judged)"
        )

        # File-level full transcript per sample
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
    # Parallelism factor: ratio Σelapsed / wall — shows effective speedup
    sum_elapsed = sum(c["elapsed_s_total"] for c in completions)
    sum_wall = sum(c["wall_clock_s"] for c in completions)
    parallel_factor = sum_elapsed / max(sum_wall, 0.01)

    return {
        "stage": stage_name,
        "models": STAGES[stage_name],  # both think + nothink tags
        "n": n,
        "n_judged": len(valid),
        "accuracy": accuracy,
        "natural_stop_rate": natural_stop_rate,
        "timeout_rate": timeout_rate,
        "think_close_rate": think_close_rate,
        "consensus_rate": consensus_rate,
        "nothink_rate": nothink_rate,  # share routed к fast variant
        "mean_samples": mean_samples,
        "mean_tokens": mean_tokens,
        "mean_elapsed_s": mean_elapsed,  # sum-of-per-sample (parallel: > wall)
        "mean_wall_clock_s": mean_wall,  # wall-clock — reflects parallelism gains
        "parallel_factor": parallel_factor,  # effective speedup from OLLAMA_NUM_PARALLEL
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

    # Pre-flight: verify Ollama service alive перед starting eval
    if not check_ollama_alive():
        logger.error(
            "Ollama service не отвечает на http://localhost:11434. "
            "Start: 'ollama serve' OR open Ollama Desktop app. Aborting."
        )
        sys.exit(1)
    logger.info("Ollama service alive ✓")

    problems = load_calc_problems()
    logger.info(f"Loaded {len(problems)} calc problems из {EVAL_PATH}")
    if args.max_problems:
        problems = problems[: args.max_problems]
        logger.info(f"Limited to {len(problems)} problems")

    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_dir = ROOT / f"evaluation/reports/honest_phase0a_local_{date_tag}"
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

    # Final summary
    logger.info("")
    logger.info(
        "=== Phase 0a (local Q4_K_M, self-consistency N=3..5, adaptive routing) — Summary ==="
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
