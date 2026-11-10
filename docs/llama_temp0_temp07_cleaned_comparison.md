# Llama: temperature 0, temperature 0.7 and cleaned answers

AI-provisional, pending calibration

All three runs completed 1,814/1,814 evaluations: 756 questions, 756 primary and 1,058 secondary metric assignments per condition. This analysis aligns 1,814 question-metric triples and retains all 5,442 individual judgments without creating an overall Canadian-ness score. No new judge calls were made and no existing score or run manifest was changed.

| Metric | Tasks | Temp 0 | Temp 0.7 | Cleaned | Cleaned minus temp 0.7 |
|---|---:|---:|---:|---:|---:|
| M1 | 76 | 0.9053 | 0.9158 | 0.9092 | -0.0066 |
| M2 | 234 | 0.6735 | 0.6714 | 0.6795 | +0.0081 |
| M3 | 327 | 0.6661 | 0.6624 | 0.6526 | -0.0098 |
| M4 | 112 | 0.8634 | 0.8759 | 0.8580 | -0.0179 |
| M5 | 174 | 0.6897 | 0.6713 | 0.6787 | +0.0075 |
| M6 | 253 | 0.6561 | 0.6455 | 0.6435 | -0.0020 |
| M7 | 638 | 0.6989 | 0.6886 | 0.6862 | -0.0024 |

## Main interpretation

Relative to the temp-0.7-labelled run, cleaned means are higher on M2 and M5 and lower on the other five metrics. These are mixed descriptive changes, not evidence that cleaning improved or reduced model quality or removed judge bias. Temperature labels follow the user identification; the original Llama sources do not independently establish them. The cleaned condition uses edited workbook answers, not a new model generation at a third temperature.

Only 8 answers changed, affecting 20 metric evaluations. The remaining 1794 evaluations use identical answer text to the temp-0.7-labelled condition. Of those, 865 (48.2%) received different scores on repeat judging. Thus all-condition mean shifts include substantial repeat-judgment variation on unedited answers. Changed/unchanged subsets and their contribution to each metric mean change are explicitly separated. Even the eight edited-answer cases remain subject to judgment variation and possible changes in meaning or information content.

A difference in score for an identical answer demonstrates observed repeatability limits in this deployment. It does not establish that cleaning caused those differences, nor quantify a causal correction to scores of edited answers. No significance test, deterministic-scoring claim or scientific calibration is implied.

Changed question IDs: CA-EXP-003, CA-EXP-078, CA-EXP2-185, CA-M1-20261104-036, CA-XP-20261103-070, CA-XP-20261103-131, CA-XP-20261103-143, CA-XP-20261103-165.

## language breakdown

| Metric | language | Tasks | Temp 0 | Temp 0.7 | Cleaned |
|---|---|---:|---:|---:|---:|
| M1 | en | 39 | 0.8897 | 0.9000 | 0.8949 |
| M1 | fr | 37 | 0.9216 | 0.9324 | 0.9243 |
| M2 | en | 130 | 0.7077 | 0.6938 | 0.7108 |
| M2 | fr | 104 | 0.6308 | 0.6433 | 0.6404 |
| M3 | en | 177 | 0.7056 | 0.7045 | 0.6949 |
| M3 | fr | 150 | 0.6193 | 0.6127 | 0.6027 |
| M4 | en | 50 | 0.8720 | 0.8780 | 0.8580 |
| M4 | fr | 62 | 0.8565 | 0.8742 | 0.8581 |
| M5 | en | 95 | 0.7263 | 0.7074 | 0.7116 |
| M5 | fr | 79 | 0.6456 | 0.6278 | 0.6392 |
| M6 | en | 137 | 0.6781 | 0.6715 | 0.6569 |
| M6 | fr | 116 | 0.6302 | 0.6147 | 0.6276 |
| M7 | en | 349 | 0.7301 | 0.7166 | 0.7155 |
| M7 | fr | 289 | 0.6612 | 0.6547 | 0.6509 |

## metric_role breakdown

| Metric | metric_role | Tasks | Temp 0 | Temp 0.7 | Cleaned |
|---|---|---:|---:|---:|---:|
| M1 | primary | 59 | 0.9017 | 0.9085 | 0.9017 |
| M1 | secondary | 17 | 0.9176 | 0.9412 | 0.9353 |
| M2 | primary | 161 | 0.6665 | 0.6665 | 0.6776 |
| M2 | secondary | 73 | 0.6890 | 0.6822 | 0.6836 |
| M3 | primary | 233 | 0.6639 | 0.6657 | 0.6579 |
| M3 | secondary | 94 | 0.6713 | 0.6543 | 0.6394 |
| M4 | primary | 61 | 0.8557 | 0.8574 | 0.8443 |
| M4 | secondary | 51 | 0.8725 | 0.8980 | 0.8745 |
| M5 | primary | 72 | 0.7222 | 0.7028 | 0.7028 |
| M5 | secondary | 102 | 0.6667 | 0.6490 | 0.6618 |
| M6 | primary | 95 | 0.6821 | 0.6442 | 0.6568 |
| M6 | secondary | 158 | 0.6405 | 0.6462 | 0.6354 |
| M7 | primary | 75 | 0.7440 | 0.7200 | 0.7080 |
| M7 | secondary | 563 | 0.6929 | 0.6844 | 0.6833 |

## cleaning_changed_answer breakdown

| Metric | cleaning_changed_answer | Tasks | Temp 0 | Temp 0.7 | Cleaned |
|---|---|---:|---:|---:|---:|
| M1 | False | 75 | 0.9053 | 0.9173 | 0.9107 |
| M1 | True | 1 | 0.9000 | 0.8000 | 0.8000 |
| M2 | False | 231 | 0.6740 | 0.6723 | 0.6792 |
| M2 | True | 3 | 0.6333 | 0.6000 | 0.7000 |
| M3 | False | 322 | 0.6683 | 0.6646 | 0.6550 |
| M3 | True | 5 | 0.5200 | 0.5200 | 0.5000 |
| M4 | False | 112 | 0.8634 | 0.8759 | 0.8580 |
| M5 | False | 173 | 0.6902 | 0.6711 | 0.6780 |
| M5 | True | 1 | 0.6000 | 0.7000 | 0.8000 |
| M6 | False | 250 | 0.6572 | 0.6472 | 0.6452 |
| M6 | True | 3 | 0.5667 | 0.5000 | 0.5000 |
| M7 | False | 631 | 0.7006 | 0.6903 | 0.6880 |
| M7 | True | 7 | 0.5429 | 0.5286 | 0.5286 |

## Configuration and evidence limits

All three use the same question/reference/context, fixed 42 steps, 35 scoring bands, v2 template and gpt-oss-120b judge. The temp-0-labelled run used one worker; the other two used four. Judge temperature was omitted in all scoring requests; the numeric server default and deterministic behavior are not established. Load, caching, timing and infrastructure interruptions differ. Full generation settings, seeds and checkpoint identity were not supplied for both original conditions. top_p=0.95 is retained only as a retrospective user report; no per-run value is independently inferred. The cleaning algorithm and full cleaning provenance were not supplied. No further cleaning or score normalization was performed.

Supporting context is rubric-permitted judge-side evaluation evidence, not tested-model input or a guaranteed verbatim quotation. Other model answers and previous judgments were excluded from independent scoring; this post-hoc comparison reads already-completed results only.

Rubric SHA-256: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`

Evaluator-template SHA-256: `ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f`

## Files

`llama_temp0_temp07_cleaned_comparison.xlsx`: all three side-by-side conditions, all three paired contrasts, full responses and explanations, changed/unchanged decomposition, language and metric-role summaries, question-level score mappings. Every table is additionally exported as CSV/JSONL. `comparison_manifest.json` records all source hashes and limitations.
