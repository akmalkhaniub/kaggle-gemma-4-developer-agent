# Smaller Prompts Are Not Enough: A Reproducible Negative Result for a Gemma 4 Developer Agent

**Subtitle:** Configuration compression, public-score regression, and limits of causal attribution

**Author:** Akmal Shahbaz

**Public reproducibility notebook:** https://www.kaggle.com/code/akmalshahbaz/gemma-4-adk-kv-roofline-power-companion

## Abstract

We compare two declarative Gemma 4 developer-agent configurations evaluated by Kaggle. The baseline v2 scored 0.18; the revised v3 scored 0.15. Both results were verified as COMPLETE through the authenticated Kaggle CLI on November 12, 2026. The revision shortened the system-prompt template from 5,351 to 3,340 UTF-8 bytes and reduced declared tools from nine to six, while also changing sampling temperature and time budget. Despite a 37.58% reduction in prompt-template bytes, the observed public score fell by 0.03. We release the configuration artifacts and a CPU notebook that audits official development data, measures expanded prompt bytes, and validates the v3 bundle with the official compiler. This is a negative configuration result, not evidence that prompt compression itself reduces repair quality. Our contribution is an auditable account of why smaller configuration artifacts should not be mistaken for improved software-engineering performance.

## 1. Introduction

Software repair requires more than locating a relevant symbol. An agent must interpret a behavioral contract, inspect related implementations, produce a patch, and verify it within a limited execution budget. Reducing instruction length and tool declarations is attractive because it may leave more context for repository evidence. However, smaller prompts can also omit useful instructions, and removing tools can discard useful capabilities.

The Gemma 4 Developer Agent competition evaluates submitted patches against validation tests [1]. Our experiment asks a narrow question: did our combined configuration simplification improve the observed competition score? The answer for these two runs is no. This report distinguishes directly measured artifact properties from model-runtime hypotheses and avoids inferring hidden task outcomes from rounded aggregate scores.

## 2. Methods and artifacts

Both configurations declare the Gemma 4 31B quantized instruction model and use no LoRA adapter. The submitted agent is a declarative ADK bundle containing a root agent configuration, sampling configuration, evaluation configuration and system prompt. Local Python diagnostic helpers are not the competition's executing agent and do not demonstrate autonomous repair.

| Property | v2 | v3 |
|---|---:|---:|
| Submission reference | 58201114 | 58250000 |
| Public score | 0.18 | 0.15 |
| Status verified November 12 | COMPLETE | COMPLETE |
| System-prompt template bytes | 5,351 | 3,340 |
| Declared tools | 9 | 6 |
| Temperature | 0.2 | 0.4 |
| Task time budget | 7 minutes | 8 minutes |
| Tool-call budget | 28 | 28 |

The v3 tool list retains command execution, file reading, file editing, file writing, status inspection and patch submission. The prompt emphasizes source-only changes, temporary scratch files, targeted checks, and an early transition from inspection to editing. These are instructions to the model, not mechanically enforced state transitions.

Several variables changed together. Accordingly, this is a comparison of two complete configurations, not a controlled factorial solve-rate experiment. The archived v2 ZIP and embedded v2/v3 file dictionaries preserve the configurations for subsequent controlled studies.

## 3. Reproducibility protocol

The public CPU companion requires the official development-task file and wheelhouse. It fails if the task file is absent or ambiguous; it does not substitute synthetic tasks or hard-coded summary rows. It records the input SHA-256, task count, problem-length quantiles, prompt-template byte counts and expanded-prompt byte quantiles in an output JSON report.

Prompt sizes are computed with UTF-8 encoding. Expanded prompts replace the problem-description placeholder with each official problem statement. These measurements exclude serialized tool schemas, chat-template overhead, reasoning traces and tool outputs. They are therefore not measurements of complete runtime context occupancy. We make no token-count claim and use no fixed characters-per-token conversion.

The notebook also constructs the v3 bundle, validates its directory with the official submission package, compiles the configuration and emits a deterministic files-only ZIP with its SHA-256. Compilation uses tool signature stubs and a non-serving model endpoint. It checks compatibility without executing inference; it cannot certify patch quality or reproduce a leaderboard score.

The historical score snapshot was collected through the authenticated competition-submissions API. The offline notebook labels those scores as historical observations rather than pretending to retrieve fresh results. The compiler run and development-data audit are separate from the competition's hidden evaluation.

## 4. Results

The revised companion completed on Kaggle CPU as version 7 on November 12, 2026. It audited 129 official development tasks (median problem length 420 bytes; P90 1,806.2 bytes). Expanded system prompts had medians of 5,750 bytes for v2 and 3,739 bytes for v3. Both official directory validation and compilation passed for v3. The emitted ZIP was 2,608 bytes, SHA-256 `4029424ef9242aa53d0e32752b2f89c1064dd82b57d85b80145135426587496b`. This rerun performed no model inference.


The v3 prompt template is 2,011 bytes smaller, a 37.58% reduction relative to v2. Three tool declarations were removed. The public evaluation nevertheless decreased from 0.18 to 0.15, an absolute difference of -0.03. We retain v2 as the best observed configuration in this comparison.

The result does not establish that the removed tools were necessary, that temperature caused the decrease, or that prompt compression is harmful. Those explanations require controlled interventions. Nor does the absence of repeated runs establish that the configurations are equivalent. We do not present a significance test: paired per-task outcomes and a justified variance model are unavailable.

An earlier analysis estimated schema tokens, compaction delays and rank-reversal probabilities. Those claims are withdrawn from this report because approximated schema sizes, assumed output growth and assumed task correlation do not constitute runtime measurements. A single-GPU bandwidth model is also omitted because it does not directly measure the competition runner's behavior.

## 5. Related work and context

The official competition defines the declarative submission interface and pass/fail patch evaluation [1]. The companion uses its supplied submission packages for configuration validation. SWE-bench introduced evaluation of language models on repository-level software issues [3]; its distinction between plausible patches and test-validated resolutions motivates our separation of compilation checks from repair outcomes. The Gemma 4 paper track permits reports describing competition approaches and related research [2]. Our contribution is limited to an auditable configuration case study rather than a new model, training method or benchmark.

## 6. Limitations and next experiments

Only one public evaluation is available for each configuration. Multiple settings changed together, private scores are unavailable, and the public development-task distribution need not represent hidden evaluation tasks. Byte reductions cannot establish reduced GPU latency, delayed compaction or increased task success.

A next experiment should hold the v2 sampling, time budget and prompt fixed while changing only the tool set, followed by a separate prompt-only intervention. Such experiments should preserve artifact hashes and all available per-task outcomes. Repeated measurements should be reported when evaluation budget permits. Until those results exist, replacing v2 with v3 would trade a better observed public result for an unverified hypothesis.

## 6a. Prospective controlled follow-up (November 12, 2026)

To separate tool-declaration overhead from the earlier bundled changes, we submitted v4 (reference 58271330). It differs from the archived v2 only in agent.yaml: three graph-tool declarations are removed. The full v2 prompt, temperature 0.2, seven-minute limit and 28-call budget are retained byte-for-byte. The prompt already prohibits use of those three tools in v2; this intervention tests the effect of their declarations while retaining that instruction. The candidate ZIP SHA-256 is da33053fc47c61c1208c9b03f168ee4f65766d8a29d805dcf85020db4e1a2be6.

The comparison uses the historical v2 evaluation, not a fresh randomized paired control. A single score difference cannot distinguish an intervention effect from run variability. We predefine success operationally as exceeding the observed v2 score of 0.18; ties do not justify replacing the baseline. The result remains pending and is not counted as an improvement.

A second independently prepared variant changes only v2 temperature from 0.2 to 0.0. Kaggle rejected its submission after reporting zero remaining daily submissions, so it has no evaluation result. Neither the rejected variant nor compilation checks are counted as performance experiments.

<!-- latest-controlled-status -->
Latest authenticated status check (2026-11-12T17:10:01+05:00): v4 remains PENDING with no public score; v2 remains 0.18. The quota endpoint reports one submission today and zero remaining, so v5 has not been resubmitted. No controlled performance conclusion is available.
<!-- /latest-controlled-status -->

## 7. Conclusion

Our compressed configuration was smaller but scored lower in its observed evaluation. Reliable submission engineering requires recording that result plainly. The released audit separates artifact measurements, official configuration checks and actual repair outcomes so that future improvements can be assessed against evidence.

## References

1. Google DeepMind and Kaggle. The Gemma 4 Developer Agent Competition. https://www.kaggle.com/competitions/gemma-4-developer-agent
2. Google DeepMind and Kaggle. The Gemma 4 Developer Agent Paper Track. https://www.kaggle.com/competitions/gemma-4-developer-agent-paper
3. Jimenez et al. SWE-bench: Can Language Models Resolve Real-World GitHub Issues? ICLR 2024. https://arxiv.org/abs/2310.06770
