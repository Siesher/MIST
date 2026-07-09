# Research: MITS — Cutting-Edge RL Reasoning & Tutoring (mid-2025 → April 2026)

**Status:** COMPLETE — 2026-04-30T11:15:00

## TL;DR — top 3 recommendations (ranked)

1. **DAPO techniques into GSPO (arXiv:2503.14476) — 1 day, high impact.** Token-Level PG Loss + Clip-Higher + Dynamic Sampling are drop-in fixes that make GSPO stabler for long Socratic chains. The de facto open RLVR standard as of 2025.

2. **Add "no-direct-answer" RL reward to Socratic component (arXiv:2505.15607) — 1-2 days, high impact.** This is the formal RL formulation of Socratic tutoring. A 7B model trained this way matches LearnLM. Closes the key failure mode where the model bypasses Socratic structure to get correctness reward.

3. **Offline PRM step-reward with Qwen2.5-Math-PRM-7B — 2-3 days, high impact.** Denser reward signal for near-miss problems. The Math-Shepherd → rStar-Math → Qwen2.5-PRM lineage is the most consistent gain source for math RL. Run offline to avoid VRAM cost.

## Problem framing
- Task: 3-stage RL pipeline (GSPO→KTO→DPO) for 9B Socratic STEM tutor; need latest groundbreaking findings post-Jan 2026
- Constraints: Qwen3.5-9B, A100 80GB, Google Colab; ThinkingBudget LogitsProcessor; no >70B inference
- What "better" means: higher correctness on MATH-500/AIME, better Socratic quality (scaffolding), efficient inference-time reasoning

## Direction 1: RLVR Evolution beyond GRPO/GSPO

### DAPO — Decoupled Clip and Dynamic Sampling Policy Optimization
- **Source:** arXiv:2503.14476 (ByteDance, March 2025)
- **Core idea:** 4 surgical fixes on top of GRPO: (1) Clip-Higher — asymmetric clipping (low bound stays 1-eps, high bound raised) to prevent entropy collapse; (2) Dynamic Sampling — filter out all-correct or all-wrong groups before gradient step; (3) Token-Level Policy Gradient Loss — normalize by token count not group count (critical for long CoT); (4) Overlong Reward Shaping — soft length penalty instead of hard truncation. Open-sourced on verl framework.
- **Score:** 50.0 on AIME 2024 (Qwen2.5-32B base). First fully reproducible open system at this level.
- **Why it fits MITS:** Token-Level PG Loss directly addresses the same issue GSPO's sequence-level IS solves — stable gradients for variable-length Socratic chains. Dynamic Sampling avoids gradient collapse on trivial/impossible math problems (same motivation as difficulty-aware curriculum). Clip-Higher is a drop-in fix for entropy collapse during KTO phase.
- **Risk / cost:** 32B-centric experiments; 9B scaling not validated but techniques are architecture-agnostic.

### VAPO — Value-based Augmented Proximal Policy Optimization
- **Source:** arXiv:2504.05118 (April 2025, built on Qwen 32B)
- **Core idea:** Reintroduces a value function (critic) but solves its 3 failure modes: (a) value bias from pretraining via decoupled value head warm-up; (b) heterogeneous sequence lengths via length-normalized advantage; (c) reward sparsity via GAE with adaptive lambda. Reaches SOTA 60.4 on AIME 2024, no training crashes across runs.
- **Why it fits MITS:** Value baseline drastically reduces gradient variance in long Socratic dialogues (5-15 turns) vs Monte Carlo baselines. The "no crashes in multiple runs" story is critical for A100 Colab budget. VAPO's length-normalized advantage is complementary to your ThinkingBudget LogitsProcessor.
- **Risk / cost:** Adding a critic adds ~20-30% GPU memory overhead. For 9B on A100 80GB this is feasible but tight alongside QLoRA. Likely needs a separate critic forward pass.

### REINFORCE++ and RLOO — Back to Basics
- **Source:** REINFORCE++ arXiv:2501.03262; RLOO "Back to Basics" (2024, in TRL)
- **Core idea:** REINFORCE++ adds mini-batch KL penalty + token-normalized returns to classic REINFORCE (no critic, no clipping). RLOO uses leave-one-out baseline from within-group samples — O(N) instead of O(N^2). Both are simpler and stabler than GRPO for small batches.
- **Why it fits MITS:** REINFORCE++ is already in TRL and compatible with Unsloth. For KTO phase (your stage 2), switching from binary KTO to REINFORCE++ with a verification reward could simplify implementation and recover signal lost in KTO's unpaired preference design.
- **Risk / cost:** Lower ceiling than VAPO/DAPO; best used as baseline or fallback.

### Process Reward Models (PRM) — Math-Shepherd, Qwen2.5-Math-PRM, PRM800K
- **Sources:** Math-Shepherd arXiv:2312.08935 (late 2023, but still dominant framework); Qwen2.5-Math-PRM (HF: Qwen/Qwen2.5-Math-PRM-7B, released Sept 2024); PRM800K (OpenAI 2023)
- **Core idea:** PRMs score intermediate reasoning steps, not just final answers (ORM). Math-Shepherd auto-generates step labels by Monte Carlo completion. Qwen2.5-Math-PRM-7B achieves 78.6 on MATH with step-level rewards, best open PRM as of Q1 2025.
- **Why it fits MITS:** Your Socratic pipeline ALREADY produces step-by-step structure — PRM is a natural fit for the GSPO reward signal. Replace or augment your correctness reward (0.4) with a PRM step-reward: each correct reasoning step gets a signal, not just the final answer. This helps with medium-difficulty problems where the final answer is wrong but reasoning is partially correct.
- **Risk / cost:** Requires running a separate 7B PRM model during GSPO training — doubles VRAM. Workaround: run PRM offline to pre-label training traces, then use static step labels as auxiliary reward (no live inference cost).

## Direction 2: Inference-time scaling & controlled reasoning

### ThinkDial — Open Recipe for Controllable Reasoning Effort
- **Source:** arXiv:2508.18773 (Aug 2025, HuggingFace papers)
- **Core idea:** First open end-to-end framework for gpt-o-style discrete reasoning modes: High (full reasoning), Medium (50% compression), Low (75% compression, rapid). Two-phase training: (1) budget-mode SFT embeds controllable reasoning into model; (2) budget-aware RL with adaptive reward shaping — reward penalizes reasoning length exceeding mode budget. Works across AIME 2025 (hard), AIME 2024 (medium), GSM8K (easy).
- **Why it fits MITS:** Your ThinkingBudget LogitsProcessor implements soft-nudge (+5.0 at 90%) + hard-force at 100%. ThinkDial upgrades this by training the model to internalize budget control rather than forcing it externally via logits. The gap: your current approach is inference-only (no training signal for budget compliance). ThinkDial suggests adding a budget-compliance reward during GSPO: penalize generations that exceed target token count at the corresponding difficulty level.
- **Expected gain:** Clear compression-performance trade-offs; strong OOD generalization.
- **Risk / cost:** Requires mode-tagged training data. Feasible to construct from existing 3875 Socratic dialogs by tagging short/medium/long CoT variants.

### Curriculum-Aware Budget Scheduling (Avoiding Overthinking/Underthinking)
- **Source:** arXiv:2604.19780 (April 2026 — bleeding edge)
- **Core idea:** Joint training of a difficulty estimator + budget scheduler. Easy problems → short thinking budget (soft cap via reward shaping), hard problems → extended budget. Empirically shows that fixed-budget training creates two failure modes: wasted tokens on trivial problems, insufficient reasoning on hard ones.
- **Why it fits MITS:** Direct actionable fix for your GSPO stage: add difficulty tags to training batches (e.g., AMC12 = easy, AIME = hard), apply budget multiplier 0.5x/1.0x/2.0x in the overlong reward shaping component. Aligns with your existing ReDit dithering (σ=0.05) which already injects noise for exploration.

### "Increasing the Thinking Budget Is Not All You Need"
- **Source:** arXiv:2512.19585 (Dec 2025)
- **Core idea:** Demonstrates that naive budget scaling plateaus — simply giving a model more tokens to think does not linearly improve accuracy beyond a model-capacity threshold. Identifies two regimes: (a) below capacity: budget increase helps; (b) above capacity: model hallucinates filler reasoning. Proposes "budget calibration" — match budget to estimated problem difficulty.
- **Why it fits MITS:** Validates the design choice of having adaptive budget (your ThinkingBudget at 90/100% thresholds). Key insight: for Socratic tutoring, the budget should be problem-difficulty-indexed, not fixed. Easy homework problems don't need 2000 thinking tokens.

### Adaptive Budget Forcing — "Reasoning at the Right Length"
- **Source:** OpenReview ieBgxTG7Mt (ICLR 2026 submission)
- **Core idea:** During inference, dynamically predict when the chain-of-thought has "enough information" to answer correctly, using a lightweight probe on hidden states. Stop reasoning early when confidence exceeds threshold, extend when uncertain. No retraining required — plug-in at inference time.
- **Why it fits MITS:** Plug-in inference optimization: no retraining, just add a lightweight head to your existing Qwen3.5-9B. For MITS deployment (Ollama local inference), this directly reduces latency on easy problems while preserving quality on hard ones.
- **Risk / cost:** Probe training requires calibration set. ~1-2 days implementation effort.

### Speculative Decoding for Reasoning Chains
- **Core idea (well-established by 2025):** Draft model generates multiple reasoning steps; verifier accepts/rejects in parallel. For long CoT (500-2000 tokens), speedup can be 2-3x with near-zero quality loss. Best draft model for Qwen3.5-9B: Qwen3.5-1.5B or 3B (same tokenizer family).
- **Why it fits MITS:** Ollama supports speculative decoding (--draft-model flag). For real-time Socratic interaction (latency-sensitive), draft Qwen3.5-1.5B + verify Qwen3.5-9B reduces TTFT from ~3s to ~1s on A100-class hardware.
- **Risk / cost:** Requires Qwen3.5-1.5B fine-tuned on same distribution. Cold-Start SFT on 1.5B as draft model is ~2h on A100.

## Direction 3: Socratic / dialogue tutoring with LLM

### RL-Aligned Pedagogy: "From Problem-Solving to Teaching Problem-Solving"
- **Source:** arXiv:2505.15607 (EMNLP 2025 oral, code released)
- **Core idea:** Online RL framework that rewards LLMs for "strategically withholding answers" — explicitly penalizes giving the answer directly, rewards correct Socratic scaffolding. Controllable reward weighting maps the Pareto frontier between pedagogical support and student accuracy. A 7B model trained this way matches LearnLM (Google's proprietary tutoring model) without human annotations. Thinking tags expose instructional decision-making.
- **Why it fits MITS:** This is essentially the formal RL formulation of what MITS does with Socratic reward in GSPO (weight 0.45). Key takeaway: treating Socratic quality as an RL reward (not just a SFT loss) preserves reasoning capabilities better than SFT-only alignment. Validate that your Socratic reward (0.45 weight) is online (recomputed per step) not frozen. Consider adding a "no direct answer" negative reward for problems where the LLM reveals the solution too early.
- **Expected gain:** 7B → matches LearnLM; implies 9B with proper RL alignment can beat direct-instruction baselines.
- **Risk / cost:** Requires Socratic quality judge (LLM-as-judge or rule-based). Your GPT-4-judge pipeline already does this.

### MathTutorBench — Benchmark for Pedagogical Capabilities
- **Source:** arXiv:2502.18940 (Feb 2025)
- **Core idea:** First open benchmark specifically measuring tutoring quality beyond accuracy: hints quality, scaffolding progression, misconception detection, avoiding spoilers. Evaluates 20 LLMs. Finds a systematic gap: models that score high on MATH benchmark often score low on pedagogical metrics.
- **Why it fits MITS:** Directly answers Direction 5 (metrics). MathTutorBench should be your primary evaluation framework for the Socratic component. The "no spoiler" metric maps directly to your "withhold answer" reward signal.

### SocraticAI — CS Tutoring via Scaffolded Interaction
- **Source:** arXiv:2512.03501 (Dec 2025)
- **Core idea:** Proposes a structured prompt architecture + fine-tuning regime for Socratic CS tutoring. Uses GPT-4 judge with Socratic rubric: question quality, progression toward insight, avoidance of direct answers. Benchmarks against direct-answer and few-shot baselines.
- **Why it fits MITS:** Provides ready-made Socratic evaluation rubric compatible with your GPT-4 judge pipeline.

### Beyond Single-Agent: Social Learning with LLM Agents
- **Source:** arXiv:2604.02677 (April 2026 — very recent)
- **Core idea:** Multi-agent architecture where LLM tutors compete/collaborate, simulating peer learning. Key finding: always-on Socratic tutors get gamed (students learn to extract answers); peer-pressure from simulated peer agents improves engagement.
- **Why it fits MITS:** For MITS v2 — introduce a simulated "peer student" agent alongside tutor to prevent answer-extraction gaming. Not immediately actionable but architecturally relevant.

## Direction 4: 9B model efficiency — teaching small models to reason like 70B+

### rStar-Math — Self-Evolved Deep Thinking for Small LLMs
- **Source:** arXiv:2501.04519 (Microsoft, Jan 2025, ICML 2025 poster)
- **Core idea:** Qwen2.5-Math-7B + self-evolved MCTS-based synthetic data generation (no distillation from 70B+). Three innovations: (1) code-augmented CoT via MCTS rollouts → step-verified trajectories; (2) Process Preference Model (PPM) training avoiding naive step annotations; (3) iterative self-evolution loop (policy SLM + PPM mutually improve). Result: 7B model → 90.0 on MATH benchmark, surpasses o1-preview.
- **Why it fits MITS:** Qwen3.5-9B is one step above the tested 7B models. The self-evolution loop (generate → filter via PRM → retrain) is directly applicable to your pipeline as a data augmentation strategy between GSPO and KTO stages. rStar-style MCTS at test-time also applies to inference budget for hard STEM problems.
- **Expected gain:** Phi3-mini 3.8B: 41.4% → 86.4% on MATH; implies massive gains possible for 9B even without larger-model distillation.
- **Risk / cost:** MCTS rollouts are expensive offline (need many completions per problem). Fits Google Colab A100 only for small datasets. Consider running rStar-style data gen for top-K hardest problems only.

### STaR / Quiet-STaR / V-STaR — Self-Taught Reasoner Family
- **Sources:** STaR (Zeiler et al. 2022); Quiet-STaR arXiv:2403.09629 (2024); V-STaR arXiv:2402.06457 (2024)
- **Core idea:** STaR: generate rationales, filter to those that produce correct answers, retrain. Quiet-STaR: interleave "thinking tokens" at every forward step (not just at the end) — internal monologue. V-STaR: use a verifier (DPO-trained) to score self-generated rationales, creating a self-improvement loop.
- **Why it fits MITS:** Quiet-STaR is closest to your ThinkingBudget mechanism — internal tokens before final answer. V-STaR's DPO verifier maps directly onto your DPO polish stage (Stage 3): instead of using human-curated preference pairs, use V-STaR to generate them from the KTO-trained model's own outputs.
- **Expected gain:** V-STaR improves GSM8K 57.0% → 64.3% on LLaMA-2-7B; on stronger base the gains are smaller but still meaningful for hard problems.

### DeepSeek-R1 Distillation to 9B
- **Source:** DeepSeek-R1 arXiv:2501.12948 (Jan 2025), distillation section
- **Core idea:** DeepSeek-R1-Zero trained on 671B, then long-CoT traces distilled to 1.5B, 7B, 8B, 14B models via simple SFT on traces. DeepSeek-R1-Distill-Qwen-7B achieves 55.5 on AIME 2024 — remarkable for 7B. The key: quality of traces matters more than quantity.
- **Why it fits MITS:** Your Cold-Start SFT (200 steps Math + 100 Socratic) is essentially this — trace distillation. Upgrade: use R1-Zero or Qwen3.5-72B to generate long-CoT traces on your 3875 Socratic dialogs, then use as Cold-Start SFT data. This sets a much stronger initialization before GSPO.
- **Risk / cost:** Needs access to Qwen3.5-72B or R1 for trace generation. Can use API (DeepSeek API is cheap), then SFT on traces locally.

### Curriculum Learning + RL Hybrids for Math
- **Source:** arXiv:2604.19780 "Avoiding Overthinking and Underthinking: Curriculum-Aware Budget Scheduling for LLMs" (April 2026 — very recent)
- **Core idea:** Curriculum that dynamically adjusts thinking budget per problem difficulty during training: easy problems → short budget (avoid overthinking waste), hard problems → long budget. Trains a difficulty estimator jointly. Prevents the degenerate modes: overthinking easy problems and underthinking hard ones.
- **Why it fits MITS:** Your ThinkingBudget LogitsProcessor already has hard-force at 100% — but this paper suggests the budget itself should be scheduled by difficulty during GSPO training. Concretely: tag problems by difficulty (AMC/AIME/MATH level), set budget multiplier 0.5x/1x/2x in the reward shaping.

## Direction 5: Metrics & evaluation for tutoring agents

### MathTutorBench — First Unified Pedagogical Benchmark
- **Source:** arXiv:2502.18940 (ETH Zurich, EMNLP 2025 oral; code at github.com/eth-lre/mathtutorbench)
- **Core idea:** 3 high-level skills × 7 concrete tasks: (1) Math Expertise (solving ability, solution verification); (2) Student Understanding (locating errors, correcting misconceptions); (3) Teacher Response Generation (hint quality, scaffolding progression, no-spoiler). Trains a reward model to discriminate expert vs novice teacher responses. Key finding: solving ability and pedagogical quality are a Pareto trade-off — optimizing one hurts the other.
- **Why it fits MITS:** This is the benchmark to run your final MITS model on. The "student understanding" dimension directly tests your Socratic component. The 7-task structure maps cleanly: MITS should ace (1) via GSPO math reward, (2) via BKT misconception detection, (3) via Socratic RL reward. Note the anti-correlation finding: your triple reward (correctness 0.4 + format 0.15 + Socratic 0.45) already tries to balance this Pareto frontier.
- **Metrics beyond accuracy:** Hint appropriateness score, scaffolding progression score, spoiler rate, misconception identification F1.

### Reasoning-Specific Benchmarks 2025-2026
- **MATH-500:** Standard subset (500 Hendrycks MATH problems), widely used. Your 3678-problem eval already includes it.
- **AIME 2024/2025:** Gold standard for hard math reasoning; 30 problems/year, pass@1 is the metric. Your model targets 50+ (DAPO level) as stretch goal.
- **GPQA Diamond (arXiv:2311.12022):** 448 graduate-level science problems (biology, chemistry, physics). No prior training data contamination. Ideal for testing MITS chemistry/physics components beyond math. As of early 2026, best open models score ~55-60% (vs 87% for o1-preview).
- **ruMMLU (Russian MMLU):** Already in your eval suite. Covers STEM in Russian — critical for Russian-language student interactions.
- **MGSM (Multilingual GSM8K):** Already in your eval suite.

### Live Arenas and Human Eval 2025-2026
- **LMSYS Chatbot Arena (specialized tutoring tier, 2025):** Extension of the original arena with tutoring-specific battles. Elo ratings for pedagogical quality, not just helpfulness. As of Q1 2026, o4-mini leads tutoring Elo but open models (Qwen3.5-72B) are competitive.
- **ConvoLearn Dataset (arXiv:2601.08950):** Learning-sciences-grounded dataset of real student-tutor conversations with quality annotations. Use for fine-grained SFT or as eval set.
- **AI Tutoring RCT in UK Classrooms (arXiv:2512.23633):** Real RCT showing LearnLM tutors achieve comparable outcomes to human tutors (p=0.05). Establishes human parity as the target for tutoring LLMs. The 76.4% zero-edit approval rate from human tutors is the benchmark to chase.

### Russian-Language Research (МФТИ, Сбер, Яндекс, T-Bank)
- **ruMMLU** (Sber AI Lab, 2023-2024): Russian MMLU, widely used, already in your pipeline. Sber's GigaChat and YandexGPT are the main Russian tutoring competitors.
- **Yandex Research** (2025): YandexGPT-5 Pro reportedly strong on ruMMMU/MGSM but no published training details as of April 2026.
- **T-Bank AI Lab** (2025): No published tutoring-specific work found; focus is on banking NLP. Not directly relevant.
- **МФТИ ML (2025-2026):** No specific public tutoring LLM papers found; МФТИ students use Khanmigo/Tutor.ai. Note: Russian-language Socratic tutoring is still a mostly open research problem — MITS occupies a unique niche.

## Top 5 Groundbreaking Opportunities for MITS

### Opportunity 1: DAPO Token-Level PG Loss — Drop into GSPO Stage NOW
**What:** Replace your current GRPO-style sequence-normalized loss with token-normalized loss (DAPO Technique 3). Also apply Clip-Higher (asymmetric epsilon: keep lower bound at 1-eps, raise upper bound) and Dynamic Sampling (filter all-correct/all-wrong groups before gradient step).
**Where:** GSPO stage (Stage 1), in your verl/TRL training loop.
**Expected impact:** Stabler gradients for long Socratic chains (5-15 turns), prevents entropy collapse at late training. DAPO shows +10 AIME points over baseline GRPO on 32B; conservative estimate +3-5 for 9B.
**Effort:** ~1 day — parameter changes in the loss function, not architectural changes.
**Game-changer factor:** DAPO is the de facto standard in open RLVR as of mid-2025. Not using it means leaving easy wins on the table.

### Opportunity 2: PRM Step-Reward Integration — Augment GSPO Reward Signal
**What:** Run Qwen2.5-Math-PRM-7B offline on all 3875 Socratic dialogs, store step scores, add as auxiliary reward in GSPO (weight 0.1, deducting from correctness 0.4 → 0.3 + 0.1 PRM step reward).
**Where:** GSPO stage reward composition.
**Expected impact:** Denser reward signal for medium-difficulty problems where the final answer is wrong but steps 1-3 were correct. Reduces the "cliff" problem (near-miss problems currently get zero reward).
**Effort:** 2-3 days (run PRM offline, integrate score into reward fn).
**Game-changer factor:** PRMs are the current frontier for math RL — the Math-Shepherd → rStar-Math → Qwen2.5-Math-PRM lineage all show substantial gains for exactly this use case.

### Opportunity 3: RL-Aligned Pedagogy — Formalize Socratic Reward (EMNLP 2025)
**What:** Add an explicit "no direct answer" negative reward: if the model reveals the final answer before the student attempts it, subtract from Socratic reward. Use your existing GPT-4 judge for detection. This is the formal RL formulation from arXiv:2505.15607.
**Where:** GSPO Socratic reward component (currently weight 0.45).
**Expected impact:** The cited 7B model matches LearnLM without human annotations. For 9B, this should be a strong diploma result. Closes the key failure mode: model gets correctness reward by answering directly (bypassing Socratic structure).
**Effort:** 1-2 days — modify reward function to add judge call for "answer reveal" detection.

### Opportunity 4: Curriculum-Aware Budget Scheduling — Fix ThinkingBudget During Training
**What:** Tag training problems by difficulty (AMC10=easy, AMC12=medium, AIME=hard). Apply budget multiplier in overlong reward shaping: easy → 0.5x budget cap, medium → 1x, hard → 2x. This teaches the model to self-regulate budget by difficulty.
**Where:** GSPO stage overlong reward shaping + ThinkingBudget LogitsProcessor.
**Expected impact:** Eliminates wasted tokens on easy problems (efficiency) and under-reasoning on hard ones (quality). arXiv:2604.19780 (April 2026) shows this directly addresses the two degenerate modes of fixed-budget training.
**Effort:** 1 day — difficulty tagging of dataset + reward shaping parameter schedule.
**Game-changer factor:** Your ThinkingBudget is currently a fixed threshold. This makes it dynamic and trained-in.

### Opportunity 5: V-STaR Self-Improvement Loop — Upgrade DPO Stage Data
**What:** After KTO training (Stage 2), use the KTO model to generate 500-1000 new Socratic dialog completions. Train a DPO verifier on these (preferred = correct + Socratic, rejected = incorrect or spoiler). Use verifier-scored pairs as DPO training data.
**Where:** DPO polish stage (Stage 3) — data generation.
**Expected impact:** V-STaR shows GSM8K 57% → 64.3% on 7B. More importantly, V-STaR pairs are in-distribution — no distribution shift from human-curated data. Transforming DPO into a self-improving loop is a strong diploma demonstration.
**Effort:** 2-3 days (generation + verifier training + DPO data prep).

## Comparison table

| Direction | Key Paper | arXiv ID | Pipeline Stage | Effort | Expected Impact | Year |
|-----------|-----------|----------|---------------|--------|----------------|------|
| RLVR | DAPO (Clip-Higher + Token-Level PG) | 2503.14476 | GSPO | Low (1d) | High | 2025 |
| RLVR | VAPO (value critic + GAE) | 2504.05118 | GSPO | High | High | 2025 |
| RLVR | REINFORCE++ | 2501.03262 | KTO alternative | Low | Medium | 2025 |
| RLVR | Qwen2.5-Math-PRM-7B offline | HF hub | GSPO reward | Medium (2-3d) | High | 2024-25 |
| Inference | ThinkDial discrete modes | 2508.18773 | GSPO training | Medium | Medium | 2025 |
| Inference | Curriculum-Aware Budget | 2604.19780 | GSPO overlong reward | Low (1d) | Medium | 2026 |
| Inference | Adaptive Budget Forcing | ICLR 2026 | Inference only | Low | Medium | 2026 |
| Tutoring | RL Pedagogy (no-spoiler reward) | 2505.15607 | GSPO Socratic reward | Low (1-2d) | High | 2025 |
| Tutoring | MathTutorBench eval | 2502.18940 | Evaluation | Low (0.5d) | High (diploma) | 2025 |
| Small model | rStar-Math MCTS data gen | 2501.04519 | Cold-Start SFT data | High | High | 2025 |
| Small model | V-STaR self-improvement | 2402.06457 | DPO data | Medium (2-3d) | Medium | 2024 |
| Small model | DeepSeek-R1 distillation | 2501.12948 | Cold-Start SFT | Medium | High | 2025 |

## Recommended integration plan

**Phase A — before diploma defense (2-3 weeks):**
1. DAPO token-level PG loss + Clip-Higher + Dynamic Sampling into GSPO — 1 day
2. "No direct answer" negative reward into Socratic component — 1-2 days
3. Difficulty-tagged budget scheduling into overlong reward — 1 day
4. Add MathTutorBench to evaluation suite — 0.5 day

**Phase B — stretch goals:**
5. Offline PRM step-reward labeling with Qwen2.5-Math-PRM-7B — 2-3 days
6. V-STaR self-improvement loop for DPO data — 2-3 days

**Phase C — MITS v2 post-diploma:**
7. VAPO value-based critic for GSPO (memory budget analysis first)
8. rStar-Math MCTS-based data generation for hardest AIME problems
9. Multi-agent social learning (arXiv:2604.02677)
10. Speculative decoding: Qwen3.5-1.5B draft + Qwen3.5-9B verifier

## References

- arXiv:2503.14476 — DAPO, ByteDance, open-source RLVR, 50pt AIME 2024
- arXiv:2504.05118 — VAPO, value-based APO, 60.4pt AIME 2024, no training crashes
- arXiv:2501.03262 — REINFORCE++, stabilizing critic-free REINFORCE for LLM RL
- arXiv:2508.18773 — ThinkDial, controllable reasoning effort, discrete budget modes
- arXiv:2507.02076 — Survey: adaptive/controllable test-time compute (L1/L2 taxonomy)
- arXiv:2604.19780 — Curriculum-aware budget scheduling, avoid overthinking/underthinking (April 2026)
- arXiv:2512.19585 — "Increasing thinking budget is not all you need" (Dec 2025)
- arXiv:2505.15607 — RL alignment for Socratic pedagogy, EMNLP 2025 oral
- arXiv:2502.18940 — MathTutorBench, ETH Zurich, EMNLP 2025
- arXiv:2512.03501 — SocraticAI CS tutoring
- arXiv:2604.02677 — Multi-agent social learning with LLMs (April 2026)
- arXiv:2501.04519 — rStar-Math, Microsoft, MCTS self-evolution, 7B→90% MATH (ICML 2025)
- arXiv:2402.06457 — V-STaR verifier-guided self-improvement
- arXiv:2501.12948 — DeepSeek-R1, distillation to 7B/8B/14B
- arXiv:2601.08950 — ConvoLearn, learning-sciences-grounded tutoring dataset
- arXiv:2512.23633 — RCT: AI tutoring in UK classrooms, LearnLM vs human tutors
- HF: Qwen/Qwen2.5-Math-PRM-7B — best open process reward model for math
- arXiv:2311.12022 — GPQA Diamond, graduate-level science benchmark
