Это приложение собирает в одном месте формулы функций потерь основных RL-алгоритмов (упомянутых в разделе 1.4) и сводную таблицу гиперпараметров всех четырёх стадий дообучения (детальные таблицы по стадиям — в разделах 3.5-3.8 основной части).

## Ж.1. Формулы функций потерь

### PPO (Proximal Policy Optimization)

$$
L^{\text{PPO}}(\theta) = \mathbb{E}_t\!\left[\min\!\left(r_t(\theta)\hat{A}_t,\; \text{clip}\!\left(r_t(\theta),\, 1{-}\varepsilon,\, 1{+}\varepsilon\right)\hat{A}_t\right)\right],
$$

где $r_t(\theta) = \pi_\theta(a_t\mid s_t)/\pi_{\theta_{\text{old}}}(a_t\mid s_t)$ — token-level importance ratio, $\hat{A}_t$ — оценка преимущества от critic-сети, $\varepsilon = 0{,}2$ — параметр клиппирования.

### GRPO (Group Relative Policy Optimization)

$$
L^{\text{GRPO}}(\theta) = -\mathbb{E}\!\left[\sum_{i=1}^{G}\sum_{t=1}^{|y_i|} \min\!\left(r_{i,t}(\theta)\hat{A}_i,\; \text{clip}(\cdots)\hat{A}_i\right)\right] + \beta\,\mathbb{D}_{\text{KL}}[\pi_\theta \,\|\, \pi_{\text{ref}}],
$$

где advantage вычисляется как нормированное отклонение от среднего по группе:

$$
\hat{A}_i = \frac{r_i - \mu_r}{\sigma_r + \varepsilon},\quad \mu_r = \frac{1}{G}\sum_{j=1}^{G} r_j,\quad \sigma_r = \sqrt{\frac{1}{G}\sum_{j=1}^{G}(r_j - \mu_r)^2}.
$$

### GSPO (Group Sequence Policy Optimization)

$$
L^{\text{GSPO}}(\theta) = -\mathbb{E}\!\left[\sum_{i=1}^{G} \rho_i(\theta) \cdot \hat{A}_i \cdot \text{clip}\!\left(\rho_i(\theta),\, 1{-}\varepsilon_{\text{seq}},\, 1{+}\varepsilon_{\text{seq}}\right)\right],
$$

где $\rho_i(\theta) = \pi_\theta(y_i\mid x) / \pi_{\theta_{\text{old}}}(y_i\mid x) = \prod_{t=1}^{|y_i|} \pi_\theta(y_{i,t}\mid x, y_{i,<t}) / \pi_{\theta_{\text{old}}}(y_{i,t}\mid x, y_{i,<t})$ — sequence-level importance ratio. Параметр $\varepsilon_{\text{seq}} = 3\cdot10^{-4}$ — на 2-3 порядка меньше token-level $\varepsilon$ из PPO.

### DPO (Direct Preference Optimization)

$$
L^{\text{DPO}}(\theta) = -\log\sigma\!\left(\beta\left(\log\frac{\pi_\theta(y^+\mid x)}{\pi_{\text{ref}}(y^+\mid x)} - \log\frac{\pi_\theta(y^-\mid x)}{\pi_{\text{ref}}(y^-\mid x)}\right)\right),
$$

где $(x, y^+, y^-)$ — пара предпочтений, $\sigma$ — логистическая функция, $\beta = 0{,}1$ — температура KL-регуляризации.

### KTO (Kahneman-Tversky Optimization)

$$
L^{\text{KTO}}(\theta) = \lambda_D \cdot \mathbb{E}_{(x,y)\sim\mathcal{D}_+}\!\left[1 - v\bigl(r_\theta(x,y) - z_0\bigr)\right] + \lambda_U \cdot \mathbb{E}_{(x,y)\sim\mathcal{D}_-}\!\left[1 - v\bigl(z_0 - r_\theta(x,y)\bigr)\right],
$$

где $r_\theta(x,y) = \beta\log(\pi_\theta(y\mid x)/\pi_{\text{ref}}(y\mid x))$ — неявная награда, $z_0$ — reference point (текущее KL-расстояние до референсной политики), $v(\cdot)$ — асимметричная функция полезности из Prospect Theory, $\lambda_D, \lambda_U$ — веса desirable/undesirable.

### LoRA (Low-Rank Adaptation)

$$
\Delta W = B A, \quad B \in \mathbb{R}^{d \times r},\; A \in \mathbb{R}^{r \times k},\; r \ll \min(d, k),
$$

где $W$ — исходные веса (заморожены), $\Delta W$ — обновление (обучается), $r$ — ранг. При $r = 16$ число обучаемых параметров составляет около $0{,}1$-$0{,}5\,\%$ от полного.

## Ж.2. Сводная таблица гиперпараметров 4 стадий

| Параметр | Stage 1 (GSPO) | Stage 2 (KTO) | Stage 3 (DPO) | Stage 4 (V-STaR-DPO) |
|---|---|---|---|---|
| Базовая модель | Qwen3.5-9B (Instruct) | mits-qwen3-9b-gspo | mits-qwen3-9b-kto | mits-qwen3-9b-final |
| Тип данных | groups of $G=8$ completions | unpaired desirable/undesirable | preference pairs $(y^+, y^-)$ | within-task pairs $(N=4)$ |
| Размер датасета | ~5 000 задач, групп ${\times}8$ | 12 597 примеров | ~3 000 пар | 84 пары (hard-only) |
| LoRA rank $r$ | 16 | 16 | 16 | 16 |
| LoRA $\alpha$ | 32 | 32 | 32 | 32 |
| LoRA target modules | `q_proj`, `k_proj`, `v_proj`, `o_proj` | то же | то же | то же |
| Learning rate | $5\cdot10^{-7}$ | $1\cdot10^{-6}$ | $5\cdot10^{-7}$ | $5\cdot10^{-7}$ |
| Batch size (effective) | 32 (4 × grad accum 8) | 16 | 16 | 8 |
| Эпохи | 2 | 3 | 2 | 4 |
| $\beta$ (KL-temp) | — | $0{,}1$ | $0{,}1$ | $0{,}1$ |
| $\varepsilon_{\text{seq}}$ (clip) | $3\cdot10^{-4}$ | — | — | — |
| max completion | 2048 | 4096 | 4096 | 4096 |
| thinking budget | 1500 | — | — | — |
| Reward components | $0{,}7\cdot r_{\text{корр}} + 0{,}15\cdot r_{\text{форм}} + 0{,}15\cdot r_{\text{сокр}}$ | binary desirable | implicit (pair-based) | composite: $0{,}5\cdot r_{\text{корр}} + 0{,}3\cdot \text{PRM} + 0{,}2\cdot r_{\text{no-spoiler}}$ |
| Особенности | ReDit ($\sigma=0{,}05$), GDPO-нормировка, Clip-Higher | $\lambda_D = \lambda_U = 1{,}0$ | стандартный | within-task pairing, hard-only |
| GPU/время обучения | A100 80GB / ~14 ч | A100 / ~8 ч | A100 / ~3 ч | A100 / ~1 ч |
| HuggingFace чекпойнт | `Siesher/mits-qwen3-9b-gspo` | `Siesher/mits-qwen3-9b-kto` | `Siesher/mits-qwen3-9b-final` | `Siesher/mits-qwen3-9b-vstar` |

## Ж.3. Параметры сэмплирования при инференсе

Параметры применяются как при обучении (rollout), так и при деплое (рекомендация Qwen Team для precise coding mode):

| Параметр | Значение | Назначение |
|---|---|---|
| temperature | $0{,}6$ | основной режим, баланс детерминизма и разнообразия |
| temperature (tool-loop) | $0{,}6$ | снижено с $1{,}0$ для устойчивости structured tool_calls |
| top_p | $0{,}95$ | nucleus sampling, отсечение хвостов распределения |
| top_k | $20$ | отсечение топ-20 кандидатов |
| min_p | $0{,}0$ | без минимального порога |
| presence_penalty | $0{,}0$ | без штрафа за повтор токенов |
| repeat_penalty | $1{,}05$ | мягкое подавление зацикливаний |

## Ж.4. Параметры инференс-стэка

| Параметр | Значение | Раздел |
|---|---|---|
| Inference-движок | llama.cpp (am17an/turboquant-kv-cache) | 3.10 |
| Маршрутизатор API | llama-swap | 3.10 |
| Формат весов | GGUF Q4_K_M | 3.10 |
| KV-cache quant | turbo3 (3-bit) | 3.10 |
| Длина контекста | 65 536 токенов | 3.10 |
| Параллельные слоты | 2 (`--parallel 2`) | 3.10 |
| Tool templates | `--jinja` | 2.8, 3.10 |
| TTL выгрузки модели | 1800 c (30 мин) | 3.10 |
| Порт llama-swap | 8090 | 3.10 |
| Размер базы (Q4_K_M) | ~5{,}7 ГБ | — |
| Размер контекста в VRAM (turbo3) | ~1{,}8 ГБ при 64K | — |
