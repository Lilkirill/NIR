from __future__ import annotations

import json
from pathlib import Path

REQUIRED_OUTPUT_FIELDS = {'risk_score', 'risk_level', 'predicted_failure_kind', 'confidence', 'key_factors', 'explanation', 'recommendations'}


def validate(path: Path) -> None:
    total = 0
    for line_no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        total += 1
        item = json.loads(line)
        messages = item.get('messages')
        assert isinstance(messages, list) and len(messages) == 3, f'{path}:{line_no} invalid messages'
        assert messages[0]['role'] == 'system'
        assert messages[1]['role'] == 'user'
        assert messages[2]['role'] == 'assistant'
        output = json.loads(messages[2]['content'])
        missing = REQUIRED_OUTPUT_FIELDS - set(output)
        assert not missing, f'{path}:{line_no} missing output fields {missing}'
        assert 0 <= float(output['risk_score']) <= 1
        assert 0 <= float(output['confidence']) <= 1
    print(f'{path}: {total} examples OK')


if __name__ == '__main__':
    validate(Path('data/llm_training/configguard_qwen_train.jsonl'))
    validate(Path('data/llm_training/configguard_qwen_validation.jsonl'))
