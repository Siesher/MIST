# Research Knowledge Base — MITS

## 2026-04-30 — RLVR, Inference Scaling, Tutoring RL (mid-2025 → Apr 2026)

**DAPO (arXiv:2503.14476):** 4 fixes on GRPO: Token-Level PG loss, Clip-Higher, Dynamic Sampling, Overlong Reward Shaping. 50pt AIME 2024 on 32B. Drop-in for any GSPO pipeline.

**VAPO (arXiv:2504.05118):** Reintroduces critic with 3 fixes (value bias, length normalization, GAE). 60.4 AIME 2024, no crashes. High VRAM cost (~+25%). Best for stability-constrained training.

**RL Pedagogy (arXiv:2505.15607, EMNLP 2025 oral):** RL reward for "withholding answers"; 7B matches LearnLM without human annotations. Add "no-spoiler" negative reward to any Socratic RL pipeline.

**MathTutorBench (arXiv:2502.18940, EMNLP 2025):** 3 skills x 7 tasks benchmark for tutoring LLMs. Finding: solving ability and pedagogical quality are Pareto trade-off. Use for MITS eval.

**rStar-Math (arXiv:2501.04519, ICML 2025):** MCTS + self-evolved PRM; 7B → 90% MATH without distillation from 70B+. Expensive offline, applicable for hard-problem data augmentation.

**ThinkDial (arXiv:2508.18773):** End-to-end training for discrete reasoning modes (High/Med/Low). Trains budget compliance into the model vs. external LogitsProcessor forcing.

**Budget Scheduling (arXiv:2604.19780, Apr 2026):** Curriculum-aware budget per difficulty level. Fixes overthinking/underthinking degenerate modes in fixed-budget training.

**DeepSeek-R1 distillation (arXiv:2501.12948):** Long-CoT traces from 671B → SFT on 7B/8B achieves 55.5 AIME 2024. Upgrade Cold-Start SFT using API-generated traces from R1 or Qwen3.5-72B.
