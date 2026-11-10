"""Convert one supplied answer column to the existing generic evaluator schema.

This is format conversion only: no inference, verification or approval is performed.
"""
import argparse
import json
from pathlib import Path

from canadianness_eval.dataset import EvaluationCase, load_dataset
from canadianness_eval.hpc_ingestion import BenchmarkRow, read_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--answer-column', required=True)
    parser.add_argument('--model-variant', required=True)
    parser.add_argument('--provenance', required=True)
    args = parser.parse_args()
    path = Path(args.output)
    if path.exists():
        raise ValueError('Output already exists; choose a new version')
    converted = []
    for row in read_records(args.input):
        context = row.get('reference_context')
        if context is None:
            context = [row['context_text']] if row.get('context_text') else []
        case = EvaluationCase(
            question_id=row['question_id'], question=row['question'],
            model_answer=row[args.answer_column], reference_answer=row.get('reference_answer'),
            reference_context=context,
            applicable_metrics=BenchmarkRow.parse_labels(row['applicable_metrics']),
            model_variant=args.model_variant, provenance=args.provenance,
            source_urls=row.get('source_urls', []), reference_ids=row.get('reference_ids', []),
        )
        if not case.model_answer.strip() or not case.question.strip() or not case.applicable_metrics:
            raise ValueError('Nonempty question, answer and applicability required')
        converted.append(case)
    # Validate all records and paired-ID invariants before publishing.
    if len({(r.question_id, r.model_variant) for r in converted}) != len(converted) or not converted:
        raise ValueError('Empty input or duplicate question/model pair')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf8') as handle:
        handle.write(''.join(json.dumps(r.model_dump(), ensure_ascii=False) + '\n' for r in converted))
    load_dataset(path)
    print(f'Converted {len(converted)} answers; no judge calls. Original source remains unchanged.')


if __name__ == '__main__':
    main()
