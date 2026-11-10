import importlib.util
import json
import sys
from pathlib import Path

import pytest


def converter():
    path = Path(__file__).resolve().parents[1] / 'scripts/prepare_answered_dataset.py'
    spec = importlib.util.spec_from_file_location('prepare_answered_dataset', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_selected_answer_is_preserved_and_other_answers_excluded(tmp_path, monkeypatch):
    source = tmp_path / 'answered.jsonl'
    target = tmp_path / 'cases.jsonl'
    row = dict(question_id='q1', question='Question?', applicable_metrics='M2;M7',
               reference_answer='Independent reference', context_text='Evidence',
               selected_answer='  exact answer\nwith repetition repetition  ',
               other_model_answer='DO NOT SEND', prior_judge_reason='DO NOT SEND')
    original = json.dumps(row).encode()
    source.write_bytes(original)
    monkeypatch.setattr(sys, 'argv', ['convert', '--input', str(source), '--output', str(target),
                                     '--answer-column', 'selected_answer', '--model-variant', 'chosen',
                                     '--provenance', 'Actual source'])
    converter().main()
    result = json.loads(target.read_text(encoding='utf8'))
    assert result['model_answer'] == row['selected_answer']
    assert result['reference_context'] == ['Evidence']
    assert result['applicable_metrics'] == ['M2', 'M7']
    assert 'DO NOT SEND' not in target.read_text(encoding='utf8')
    assert source.read_bytes() == original
    with pytest.raises(ValueError, match='already exists'):
        converter().main()


def test_duplicate_ids_do_not_publish_output(tmp_path, monkeypatch):
    source, target = tmp_path / 'answered.jsonl', tmp_path / 'cases.jsonl'
    row = dict(question_id='q1', question='Question?', applicable_metrics=['M1'], answer='Answer')
    source.write_text(json.dumps(row) + '\n' + json.dumps(row), encoding='utf8')
    monkeypatch.setattr(sys, 'argv', ['convert', '--input', str(source), '--output', str(target),
                                     '--answer-column', 'answer', '--model-variant', 'chosen',
                                     '--provenance', 'Actual source'])
    with pytest.raises(ValueError, match='duplicate'):
        converter().main()
    assert not target.exists()
