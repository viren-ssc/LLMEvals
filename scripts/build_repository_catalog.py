"""Build human-facing experiment indexes without moving frozen experiment paths."""
import csv
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ['llama', 'gc_llm', 'apertus']
GROUPS = [
    ('01_original_outputs', 'Original outputs (user-labelled temperature 0)',
     ['llama_full_20261106_v2', 'gc_llm_full_as_generated_20261106_v2', 'apertus_full_as_generated_c4_20261107_v2']),
    ('02_temperature_07_workbook', 'Mixed-temperature workbook (user-labelled temperature 0.7)',
     [f'{m}_mixed_temperature_workbook_c4_20261107_v2' for m in MODELS]),
    ('03_repetition_cleaned', 'Repetition-cleaned responses: M1–M7',
     [f'{m}_cleaned_responses_c4_20261107_v2' for m in MODELS]),
    ('04_correctness_completeness', 'Cleaned responses: correctness and completeness',
     [f'{m}_general_quality_cleaned_20261107_v1' for m in MODELS]),
]

def main():
    index = ['# Results: four experiments', '', '**AI-provisional, pending calibration.** All individual explanations and original answers are retained.', '',
             'These folders are the reading order. Large canonical workbooks, datasets and checkpoint files stay at the paths bound by their historical manifests; links below avoid duplicating them.', '']
    run_index = []
    for folder, title, runs in GROUPS:
        directory = ROOT / 'results' / folder
        directory.mkdir(parents=True, exist_ok=True)
        rows = []
        text = [f'# {title}', '', '**AI-provisional, pending calibration.**', '',
                '| Model | Questions | Successful evaluations | Workbook | Every score and explanation |',
                '|---|---:|---:|---|---|']
        for model, rid in zip(MODELS, runs):
            output = ROOT / 'outputs/evaluations' / rid
            records = [json.loads(x) for x in (output/'all_results.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
            expected = 1512 if folder.startswith('04') else 1814
            assert len(records) == expected and all(r['status']=='SUCCESS' for r in records)
            assert len({(r['question_id'], r['evaluation_metric']) for r in records}) == expected
            groups = defaultdict(list)
            for r in records:
                groups[r['evaluation_metric']].append(r['score'])
            rows.extend(dict(model=model, metric=m, evaluations=len(scores), mean_score=statistics.mean(scores), result_label='AI-provisional, pending calibration') for m,scores in sorted(groups.items()))
            base = '../../outputs/evaluations/' + rid
            text.append(f'| {model} | 756 | {expected} | [Excel]({base}/full_results.xlsx) | [JSONL]({base}/all_results.jsonl) · [CSV]({base}/all_results.csv) |')
            run_index.append(dict(experiment=folder, model=model, run_id=rid, evaluations=expected, canonical_output=f'outputs/evaluations/{rid}'))
        text += ['', '## Metric means (0–1)', '', '| Model | Metric | Evaluations | Mean |', '|---|---|---:|---:|']
        text += [f"| {r['model']} | {r['metric']} | {r['evaluations']} | {r['mean_score']:.4f} |" for r in rows]
        text += ['', 'Each run folder also contains reference/context-enriched question records, language breakdowns, execution manifests, failure/retry accounting and immutable per-metric checkpoints.', '']
        if folder.startswith('01'):
            text += ['## Source answers', '', '- [Llama](../../data/incoming/Canadian-ness_Llama_756_Generations.jsonl)', '- [GC LLM](../../data/incoming/gc_llm_as_generated/)', '- [Apertus](../../data/incoming/apertus_as_generated/)', '', 'Original temperature labels are user-supplied; generation controls and underlying checkpoint identity are not fully independently attested. Length-limited and repeated answers were retained.']
        elif folder.startswith('02'):
            text += ['## Source answers', '', '[Supplied workbook](../../data/incoming/mixed_temperature_three_model/canadianness_756_three_model_answers_MIXED_TEMPERATURE_COMPLETE.xlsx)', '', 'GC LLM has 755 temperature-0.7 answers and one reused temperature-0 answer. Apertus/Llama temperature metadata is not independently recorded in the workbook.']
        else:
            text += ['## Source answers', '', '[Supplied cleaned JSONL](../../data/incoming/cleaned_three_model/Canadian_ness_Three_Models_Cleaned_for_Evaluation.jsonl)', '', 'Cleaned strings are edited responses, not generations at a third temperature. References were not changed to favour a model.']
        if folder.startswith('04'):
            text += ['', '[Combined Excel and paired comparisons](../../outputs/queues/general_quality_cleaned_20261107_v1/)', '', '[Exact two-metric definitions](../../config/general_answer_quality/2026-11-07-user-v1/metrics_extracted.json)']
        else:
            text += ['', '[Three-condition model comparisons](../../outputs/comparisons/)', '', '[Exact seven-metric rubric](../../config/final/2026-11-03-v1/metrics_final.json)']
        (directory/'README.md').write_text('\n'.join(text)+'\n', encoding='utf8')
        with (directory/'metric_summary.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer=csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        index += [f'- [{title}]({folder}/README.md)']
    (ROOT/'results/README.md').write_text('\n'.join(index)+'\n', encoding='utf8')
    with (ROOT/'results/run_index.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=list(run_index[0])); writer.writeheader(); writer.writerows(run_index)
    source = ROOT/'data/incoming/cleaned_three_model/Canadian_ness_Three_Models_Cleaned_for_Evaluation.jsonl'
    original = [json.loads(x) for x in source.read_text(encoding='utf8').splitlines() if x.strip()]
    fields=['question_id','language','primary_metric','applicable_metrics','context_text','question','reference_answer']
    questions=[{k:r[k] for k in fields} for r in original]
    assert len(questions)==len({r['question_id'] for r in questions})==756
    destination=ROOT/'data/benchmarks/core_756'
    destination.mkdir(parents=True,exist_ok=True)
    target=destination/'questions_and_references.jsonl'
    target.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in questions),encoding='utf8')
    (destination/'provenance.json').write_text(json.dumps(dict(description='Answer-free projection of supplied benchmark fields; not a new independent original source or factual verification.',source=source.relative_to(ROOT).as_posix(),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),questions=756,fields=fields,output_sha256=hashlib.sha256(target.read_bytes()).hexdigest()),indent=2),encoding='utf8')
    print('Indexed 12 completed model runs across four experiments; created answer-free benchmark view.')

if __name__ == '__main__':
    main()
