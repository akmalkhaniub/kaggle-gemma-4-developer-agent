# Token-Budgeted Declarative ADK Engineering for Gemma 4 Software Agents: Hybrid-Attention KV Roofline, 2×2 Factorial Static-Prefix Ablation, and Paired Leaderboard Identifiability

**Track:** Kaggle Gemma 4 Developer Agent Paper Track (`gemma-4-developer-agent-paper`)  
**Companion Reproducibility Kernel (CPU, Public, `v6` Verified):** [`akmalshahbaz/gemma-4-adk-kv-roofline-power-companion`](https://www.kaggle.com/code/akmalshahbaz/gemma-4-adk-kv-roofline-power-companion)  
**Competition Artifact Kernel (CPU + ADK Wheelhouse):** [`akmalshahbaz/gemma-4-developer-agent-baseline-harness`](https://www.kaggle.com/code/akmalshahbaz/gemma-4-developer-agent-baseline-harness)  
**Author:** Akmal Shahbaz  

---

## Abstract

Under Kaggle's Gemma 4 Developer Agent sandbox, participants cannot alter weights, inference engine, or the multi-turn loop outside a four-file Google ADK bundle (`agent.yaml`, `configs/sampling.yaml`, `eval_config.yaml`, `prompts/system.md`) plus optional LoRA weights. When runtime knobs are restricted to declared tools, budgets, prompts, and sampling config, modest changes collide with evaluation variance. Analyzing our `v2 -> v3` iteration on `gemma-4-31b-it-qat-w4a16-ct`, we: (1) derive the hybrid KV roofline across `50` sliding ($W=1024$) and `10` global layers, calibrated within `+4.3%` of single-L4 benchmarks (`17.99` vs `17.25 tok/s` at $T=4{,}096$); (2) audit `129` `tasks.jsonl` issues and `swegemma` tool schemas via a **2×2 factorial static-prefix ablation**, cutting Turn-1 context by **`1,004` tokens (`-36.28%`, `2,768 -> 1,764` tokens)** ahead of the `14,336`-token ADK compaction limit; and (3) derive a **paired correlation ($\rho$) & public/private ($N=58/62$) rank-reversal framework** (`22.6%` reversal risk at `+1` task), explaining why our `v2` (`0.18`) vs `v3` (`0.15`) delta (`-0.64σ`, $p=0.524$) sits inside single-draw noise.

---

## 1. Introduction & Fixed Competition Constraints

The **[Google — The Gemma 4 Developer Agent Competition](https://www.kaggle.com/competitions/gemma-4-developer-agent)** evaluates autonomous Python software-engineering agents on hidden repository issues (`N=58` public, `N=62` private). Rather than permitting external orchestration frameworks, frontier APIs, or live package installations, the competition enforces a strict declarative sandbox:

1. **Frozen Quantized Backbone:** Every submission declares one `google/gemma-4-*` QAT checkpoint (`gemma-4-31b-it-qat-w4a16-ct`), served by vLLM on `4 × NVIDIA L4` GPUs (`96 GiB` GDDR6, `TP=4`) inside an offline container.
2. **Declarative ADK Contract:** Agents are specified via `agent.yaml`, `configs/sampling.yaml`, `eval_config.yaml`, `prompts/system.md` (`{problem_description}`), and an optional LoRA adapter.
3. **Hard Execution Ceilings:** Tasks enforce tight tool caps (`28` calls; `swegemma` warns when `max_tool_calls >= 20` and `remaining <= 10`, i.e., call `18/28`), `240s` timeouts, `5,000`-char `run_command` truncation, `8`-minute task caps, and a `12`-hour run limit. Untracked `/workspace` files enter `git add -N . && git diff HEAD`, while test edits cause failure.

Because every improvement must operate within this strict budget envelope, wasted tool calls, verbose tool outputs, and static prompt/schema bloat degrade performance through two coupled bottlenecks: **context-window compaction** and **step-budget exhaustion**. Conversely, interpreting public leaderboard scores requires care: with $N = 58$ public tasks, a single solved issue shifts the displayed score by $1 / 58 \approx 0.01724$ (`1.72` percentage points).

---

## 2. Hybrid-Attention KV Cache & ADK Compaction Roofline

### 2.1 Analytical Memory Footprint of `gemma-4-31b-it-qat-w4a16-ct`

Unlike uniform global-attention transformers whose KV cache grows strictly linearly with context $T$ across all $L = 60$ layers, `gemma-4-31b-it-qat-w4a16-ct` uses a **5:1 hybrid attention topology**. Published Hugging Face `text_config` constants [5] specify `num_hidden_layers=60`, `sliding_window=1024`, `num_key_value_heads=16`, `head_dim=256`, `global_head_dim=512`, and `num_global_key_value_heads=4`, yielding a `50`/`10` sliding/global layer split:

- **Resident weights:** $M_{\text{weights}} \approx 18.24\text{ GiB}$ is an *assumed* resident-VRAM figure (INT4 weights plus embeddings and scales) used only for the single-L4 headroom column; it is not what is streamed per token.
- **50 Sliding-Window Attention Layers:** Local window $W = 1024$ tokens, $H_{kv,\text{slide}} = 16$, $d_{k,\text{slide}} = 256$. Storing FP16 keys and values ($2$ tensors $\times 2$ bytes) allocates:
  $$M_{\text{KV,slide}}(T) = 50 \times (2 \times 16 \times 256 \times 2) \times \min(T, 1024) = 819{,}200 \cdot \min(T, 1024)\text{ bytes}$$
  Once $T \ge 1024$, sliding-layer KV memory saturates at $838{,}860{,}800\text{ B} = 0.78125\text{ GiB}$.
- **10 Global Full-Attention Layers (every 6th layer):** $H_{kv,\text{global}} = 4$, $d_{k,\text{global}} = 512$, giving linear growth across full conversation depth $T$:
  $$M_{\text{KV,global}}(T) = 10 \times (2 \times 4 \times 512 \times 2) \times T = 81{,}920 \cdot T\text{ bytes} = 80.0\text{ KiB/token}$$

Table 1 reproduces our companion notebook's memory profile (`24 GiB` L4, $6\%$ PagedAttention overhead). Decode latency uses a bandwidth-bound roofline model, $\tau(T) = (15.5\text{ GB} + M_{\text{KV}}(T)) / 300\text{ GB/s}$, where $15.5\text{ GB} = 31\text{B} \times 0.5\text{ B}$ is the nominal 4-bit weight stream and $300\text{ GB/s}$ is the L4 datasheet peak. At $T = 4{,}096$ it predicts `17.99 tok/s`, within `+4.3%` of the `17.25 tok/s` measured independently on a single L4 (`vLLM 0.19`) by another Paper-Track study [6]. We treat absolute latencies as a roofline upper bound and relative growth with $T$ as the primary operational metric:

| Context $T$ (Tokens) | Sliding KV (GiB) | Global KV (GiB) | Total KV (GiB) | 1× L4 VRAM (GiB) | 1× L4 Headroom (GiB) | 1× L4 Decode (ms/tok) | Throughput (tok/s) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 512 | 0.3906 | 0.0391 | 0.4297 | 18.695 | 5.305 | 53.20 | 18.80 |
| 1,024 | 0.7812 | 0.0781 | 0.8594 | 19.151 | 4.849 | 54.74 | 18.27 |
| 4,096 | 0.7812 | 0.3125 | 1.0938 | 19.399 | 4.601 | 55.58 | 17.99 |
| 8,192 | 0.7812 | 0.6250 | 1.4062 | 19.731 | 4.269 | 56.70 | 17.64 |
| **14,336 (ADK Compaction)** | **0.7812** | **1.0938** | **1.8750** | **20.227** | **3.773** | **58.38** | **17.13** |
| 24,576 | 0.7812 | 1.8750 | 2.6562 | 21.056 | 2.944 | 61.17 | 16.35 |
| 32,768 | 0.7812 | 2.5000 | 3.2812 | 21.718 | 2.282 | 63.41 | 15.77 |

Expanding context from `8,192` to `24,576` tokens increases modeled single-L4 decode latency by **+7.88%** (`56.70 -> 61.17 ms/tok`), before prefill cost on multi-turn tool outputs.

### 2.2 The 14,336-Token ADK Compaction Wall and LoRA Headroom Trade-Off

In the official `4 × NVIDIA L4` runner (`TP=4`), two runtime boundaries govern multi-turn reliability:

1. **ADK `EventsCompactionConfig` (`14,336` tokens):** When cumulative prompt tokens surpass `14,336` tokens, the ADK harness triggers context compaction, summarizing older trajectory events while preserving only the `5` most recent events. Community write-ups report (not independently verified here) that crossing compaction ($\ge 1$ compaction) sharply degrades solve rates as exact line numbers, symbol names, and failed-edit constraints are lost in summary compression. Because Gemma 4's thinking trace (`thinking_budget: 4096`) and full tool JSON schemas are re-sent every turn, static prompt and schema overhead directly erode uncompacted trajectory capacity.
2. **Zero-LoRA Headroom Preservation:** Declaring a LoRA adapter triggers vLLM KV-block reservation—reported in community profiling to restrict practical KV allocation (~`7.6K` tokens with LoRA vs ~`46K` tokens without LoRA). Omitting `adapter` keys in `agent.yaml` preserves full sequence headroom.

---

## 3. Empirical Benchmark Audit & 2×2 Factorial `v2 -> v3` Ablation

### 3.1 Live `tasks.jsonl` Benchmark Audit (`N = 129` Public Dev Tasks)

Rather than assuming arbitrary issue lengths, Section 2.1 of our companion notebook directly audits `/kaggle/input/competitions/gemma-4-developer-agent/tasks.jsonl` (`129` public development tasks across `4` Python repositories). All `129` public rows omit `test_command` (`empty_test_cmd = 129`), confirming that hidden grading tests are withheld from the public metadata and reinforcing why agents must synthesize their own targeted `/tmp` reproduction and single-file pytest checks:

| Repository (`tasks.jsonl`) | Public Tasks ($N=129$) | Share (%) | Median Issue Bytes | P90 Issue Bytes | Max Issue Bytes |
|---|---:|---:|---:|---:|---:|
| `fastapi/fastapi` | 67 | 51.9% | 681 B | 2,535 B | 10,100 B |
| `Textualize/rich` | 48 | 37.2% | 138 B | 1,218 B | 3,112 B |
| `psf/requests` | 13 | 10.1% | 406 B | 677 B | 836 B |
| `encode/httpx` | 1 | 0.8% | 243 B | 243 B | 243 B |
| **All Public Dev Tasks** | **129** | **100.0%** | **420 B** | **1,806 B** | **10,100 B** |

### 3.2 2×2 Factorial Static-Prefix Ablation (`swegemma` Wheelhouse Inspection)

Our baseline **`v2`** (submission ref `58201114`) scored **`0.18`** on the public leaderboard (`~10/58` tasks) using a `9`-tool `gemma-4-31b-it-qat-w4a16-ct` bundle (`temperature=0.2`, `7m` / `28` calls, `5,351 B` prompt). Our **`v3`** candidate (submission ref `58250000`) modifies tool declarations (`9 -> 6`), prompt length (`5,351 -> 3,340 B`), call pacing, sampling temperature (`0.2 -> 0.4`), and time budget (`7 -> 8m`), scoring **`0.15`** (`-0.03` vs `v2`, well within $N=58$ single-draw noise as quantified in Section 4.1).

To decouple the static context savings of **Factor A (Tool-Surface Pruning)** from **Factor B (Prompt Compression)**, Section 2.2 of our companion notebook inspects `swegemma.tools` inside the attached Kaggle wheelhouse (`metric/gemma-4-developer-agent-wheelhouse`) and executes a **2×2 factorial compilation ablation** across all `129` real `tasks.jsonl` problem statements (`3.80` chars/token):

| Factorial Ablation Arm | Declared Tools | Prompt (`prompts/system.md`) | Tool Schema (`swegemma.tools`) | Turn-1 Median (`+420 B` Issue) | Turn-1 P90 (`+1,806 B` Issue) | Pre-Compaction Headroom (`14,336 - T1`) | Saved vs `v2` (Tokens / Turn) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **1. `v2` Baseline (`9` tools + `v2` prompt)** | 9 | 5,351 B | 4,746 B | 10,517 B (`2,768` tok) | 3,132 tok | 11,568 tok | — |
| **2. Tool-Pruned Only (`6` tools + `v2` prompt)** | 6 | 5,351 B | 2,942 B (`-38.0%`) | 8,713 B (`2,293` tok) | 2,658 tok | 12,043 tok | **`-475` tok (`-17.2%`)** |
| **3. Prompt-Compressed Only (`9` tools + `v3` prompt)** | 9 | 3,340 B (`-37.6%`) | 4,746 B | 8,506 B (`2,238` tok) | 2,603 tok | 12,098 tok | **`-530` tok (`-19.1%`)** |
| **4. `v3` Combined (`6` tools + `v3` prompt)** | **6** | **3,340 B (`-37.6%`)** | **2,942 B (`-38.0%`)** | **6,702 B (`1,764` tok)** | **2,128 tok** | **12,572 tok** | **`-1,004` tok (`-36.3%`)** |

This factorial decomposition reveals a key systems finding: in `v2`, the 9 `swegemma` tool declarations (`4,746 B`) nearly equaled the entire system prompt (`5,351 B`). Removing `get_code_neighbors` (`602 B`), `search_similar_code` (`584 B`), and `get_code_subgraph` (`618 B`) strips **`1,804 B` (`475` tokens/turn, `-38.0%`)** of static schema overhead while eliminating `async def` call-graph blind spots on async-heavy repositories (`fastapi/fastapi` and `encode/httpx` represent `68/129 = 52.7%` of public tasks). Simultaneously, section-by-section prompt compression trims **`2,011 B` (`530` tokens/turn, `-37.58%`)** across `WORKFLOW / PROCEDURE` (`2,513 -> 1,495 B`, `-40.5%`), `HARD LIMITS` (`1,578 -> 925 B`, `-41.4%`), `DECISION RULES` (`374 -> 226 B`, `-39.6%`), and `CALL PLAN` (`530 -> 445 B`, `-16.0%`). Together, `v3` cuts Turn-1 context by **`1,004` tokens (`-36.28%`)**, delaying ADK compaction by `4–5` full tool-call turns across the median-to-P90 task band (Figure 1B) so the agent stays uncompacted past `swegemma`'s Call `18/28` low-budget warning.

### 3.3 Finite-State Call Pacing & Deterministic Verification

Within the compressed `3,340 B` instruction budget, `v3` enforces four finite-state call phases:
- **Calls 1–8 (Locate):** Batch fixed-string `git grep -n -F` and `git ls-files | head -n 30` queries in `run_command`, inspect `40–120` line slices via `read_file`, and retain brief plain-text working notes between turns.
- **Calls 9–12 (Mandatory Edit):** Enforce at least one source edit by call `12` (`edit_file` verbatim short snippets; after 2 match failures, atomic Python replacement asserting `content.count(old) == 1`), propagating changes across parallel `sync`/`async`, `Client`/`AsyncClient`, typing overloads, `__all__`, and `docs_src/`.
- **Calls 13–20 (`/tmp` Repro & Tailing):** Redirect scratch scripts and test logs strictly to `/tmp` (`pytest ... -x -q -k kw > /tmp/t.log 2>&1; tail -n 35 /tmp/t.log`), respecting `run_command`'s `5,000`-character truncation while preventing untracked `/workspace` files from entering `git add -N . && git diff HEAD`.
- **Call 21+ (Clean Submit):** Run `git status --short && git diff` (catching untracked files hidden by bare `git diff`) and revert accidental non-source edits before calling `submit_patch`.

Both [`tests/test_agent_harness.py`](../tests/test_agent_harness.py) (`7/7` pytest tests passing) and our companion notebook verify all `4` payload files (`3,888` raw bytes -> `2,608`-byte deterministic `submission.zip`, SHA-256 `4029424ef9242aa53d0e32752b2f89c1064dd82b57d85b80145135426587496b`), pass `adk_submission.validate_directory` + `compile_submission`, and benchmark a sub-millisecond (`16.6–84.2 µs` on Kaggle CPU) pre-flight `compile(..., "exec")` AST gate across `6/6` valid/invalid patch archetypes.

---

## 4. Paired Task-Difficulty Correlation ($\rho$) & Public-to-Private Rank-Reversal Risk

### 4.1 Exact Wilson Intervals & Paired McNemar Discordance on Shared Tasks ($N = 58$)

On $N = 58$ binary tasks, each solved issue shifts the displayed score by $\Delta_1 = 1/58 \approx 1.724\text{ pp}$, with 95% Wilson confidence intervals [4] spanning `10.31–12.78` tasks (`[0.0964, 0.2891]` at $10/58 = 0.1724$). However, comparing two agent submissions evaluated on the **same** $N=58$ public tasks is a *paired* design, not two independent binomial draws. Let $\bar{p} = 10/58 \approx 0.1724$ be the marginal solve rate and $\rho \in [0, 0.85]$ be the cross-run task-outcome correlation induced by shared issue difficulty (easy tasks solved by both runs; hard tasks failed by both). Pairwise task discordance is:
$$d(\rho) = P(Y_{A,i} \ne Y_{B,i}) = 2\bar{p}(1-\bar{p})(1-\rho), \qquad \sigma_{\text{diff}}(\rho) = \sqrt{N_{\text{pub}} \, d(\rho)}\text{ tasks}$$

Section 3 of our companion notebook evaluates how task-difficulty correlation $\rho$ governs single-draw Minimum Detectable Effect ($\text{MDE}_{80\%} = Z_{0.80}\sigma_{\text{diff}}$ at two-sided $\alpha=0.05$, $Z_{0.80} \approx 2.8016$) and required repeated draws per arm:

| Task Correlation $\rho$ | Pairwise Discordance $d(\rho)$ | Equiv. Per-Draw SD ($\sigma_{\text{draw}}$) | Paired Diff SD ($\sigma_{\text{diff}}$ Tasks) | 1-Draw MDE (Tasks / pp) | Draws/Arm for `+1` Task (`+2` Tasks) | $P(\text{Win 1-Draw} \mid \delta = +1\text{ task})$ |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 (Indep. Binomial) | 0.2854 | 2.88 | 4.07 | 11.40 tasks (`19.65 pp`) | 130 (`33`) | 0.597 |
| 0.35 (Low Coupling) | 0.1855 | 2.32 | 3.28 | 9.19 tasks (`15.84 pp`) | 85 (`22`) | 0.620 |
| **0.55 (Empirical Baseline)** | **0.1284** | **1.93** | **2.73** | **7.65 tasks (`13.18 pp`)** | **59 (`15`)** | **0.643** |
| 0.70 (High Coupling) | 0.0856 | 1.58 | 2.23 | 6.24 tasks (`10.76 pp`) | 39 (`10`) | 0.673 |
| 0.82 (Near-Deterministic) | 0.0514 | 1.22 | 1.73 | 4.84 tasks (`8.34 pp`) | 24 (`6`) | 0.719 |

Even when shared task difficulty induces strong correlation ($\rho = 0.70, d = 0.0856$), a single public draw cannot resolve effects smaller than **`6.24` tasks (`10.76 pp`)** at 80% power, and a true `+1`-task (`+1.72 pp`) upgrade requires **`24–59` repeated evaluations per arm** across $\rho \in [0.55, 0.82]$. Our own live competition delta directly illustrates this bound: `v2` (`0.18`, ref `58201114`) vs `v3` (`0.15`, ref `58250000`) shows $\Delta = -3.00\text{ pp}$ (`-0.64σ` under paired SE `4.71 pp` at $\rho=0.55$, two-sided $p = 0.524$; unpaired $p = 0.663$)—statistically indistinguishable from zero and `4.4×` below the `13.18 pp` MDE, while also illustrating how raising `temperature` (`0.2 -> 0.4`) or adding a forced Call-12 edit alongside static prefix compression creates multi-factor confounding.

### 4.2 Decision-Theoretic Public ($N_{\text{pub}}=58$) to Private ($N_{\text{priv}}=62$) Split Rank-Reversal Risk

A distinct hazard arises when selecting final submissions: the `58` public tasks and `62` private tasks are **disjoint subsets** of the 120-task evaluation pool. Under baseline discordance $d = 0.127$ ($\sigma_{\text{pub}} = \sqrt{d / 58} \approx 4.68\text{ pp}$, $\sigma_{\text{priv}} = \sqrt{d / 62} \approx 4.53\text{ pp}$), Section 3 computes the joint probability that a candidate configuration **outscores control on the Public LB ($\Delta_{\text{pub}} > 0$) yet underperforms control on the Private LB ($\Delta_{\text{priv}} < 0$)**:

| True Underlying Effect ($\delta_{\text{true}}$) | True Gain (Tasks of 58) | $P(\Delta_{\text{pub}} > 0)$ | $P(\Delta_{\text{pub}} \ge +1\text{ task})$ | $P(\Delta_{\text{priv}} < 0)$ | Joint Reversal Risk $P(\text{Pub Win} \cap \text{Priv Loss})$ |
|---:|---:|---:|---:|---:|---:|
| `-1.72 pp` (Regression) | `-1.0` task | 0.357 | 0.231 | 0.648 | **0.231 (`23.1%`)** |
| `0.00 pp` (Null Change) | `0.0` task | 0.500 | 0.356 | 0.500 | **0.250 (`25.0%`)** |
| **`+1.72 pp` (`+1` Task Gain)** | **`+1.0` task** | **0.643** | **0.500** | **0.352** | **0.226 (`22.6%`)** |
| `+3.45 pp` (`+2` Task Gain) | `+2.0` tasks | 0.770 | 0.644 | 0.223 | **0.172 (`17.2%`)** |
| `+5.17 pp` (`+3` Task Gain) | `+3.0` tasks | 0.865 | 0.769 | 0.127 | **0.110 (`11.0%`)** |

Two operational conclusions follow immediately:
1. **False-Positive Hill-Climbing:** A deleterious edit that truly *hurts* solve rate by `-1` task (`-1.72 pp`) still scores `+1` task or higher on the Public LB **`23.1%` of the time**. Across 4–5 unprincipled prompt tweaks, at least one null or negative variant will appear to improve the public score by pure chance.
2. **True-Upgrade Reversal:** Even a genuine `+1`-task (`+1.72 pp`) improvement suffers a **`35.2%` chance of scoring below control on the 62-task Private LB** and a **`22.6%` joint probability of winning Public while losing Private** (Figure 2B). Consequently, submission selection must be anchored on **causal structural invariants**—verified `-36.3%` static token reduction, elimination of broken async graph tools, `/tmp` workspace isolation, and deterministic pre-flight validation—rather than single-draw leaderboard fluctuations.

---

## 5. Limitations, Honest Disclosure & Reproducibility

1. **Observed `v2` vs `v3` Competition Scores:** `v2` scored **`0.18`** (ref `58201114`) and `v3` scored **`0.15`** (ref `58250000`); we report this measured `-0.03` result transparently without post-hoc selection or extrapolation (`p = 0.524` paired / `0.663` unpaired under $N=58$).
2. **Static Prefix vs End-to-End Trajectory Ablation:** Section 3.2 decouples the *static Turn-1 byte/token overhead* of `v2 -> v3` via a 2×2 factorial compilation audit across all `129` `tasks.jsonl` issues (`-475` tokens from tool pruning, `-530` tokens from prompt compression). Because `v3` also changed temperature (`0.2 -> 0.4`), Call-12 edit forcing, and task time (`7 -> 8m`), isolating any single causal contributor to the `-0.03` delta would require single-factor controlled arms.
3. **Full CPU Reproducibility:** Every table, `tasks.jsonl` audit, `swegemma` schema measurement, SHA-256 digest check, `v2`/`v3` significance test, and figure executes in ~94s on Kaggle CPU from [`akmalshahbaz/gemma-4-adk-kv-roofline-power-companion`](https://www.kaggle.com/code/akmalshahbaz/gemma-4-adk-kv-roofline-power-companion) (`v6`) with internet disabled.

---

## References

1. Google DeepMind / Kaggle, *The Gemma 4 Developer Agent Competition* & *Official Harness (`swegemma` / `adk_submission`)* (2026).
2. M. Singatullin, *When Traceback Compression Lies: Verifiable Diagnostics for Gemma 4 SWE Agents* (`ast-guided-loops-verification-for-gemma-4`, Kaggle Gemma 4 Paper Track Reference, 2026).
3. S. M. Hossain (Mobassir), *Why Your Leaderboard Can't See a 3-Point Gain: Evaluation Validity for Gemma 4 Software-Engineering Agents* (Kaggle Gemma 4 Paper Track Reference, 2026).
4. E. Wilson, *Probable Inference, the Law of Succession, and Statistical Inference*, JASA (1927).
5. Google, *Gemma 4 31B model card and `config.json` (`text_config`)*, Hugging Face (accessed 2026-11-12).
6. pablodiegoo, *Hardware decode physics, the 12-call cliff, and operational contracts for autonomous software engineering with Gemma 4 31B* (Kaggle Paper-Track notebook, 2026): measured `17.25 tok/s` single-L4 decode.
