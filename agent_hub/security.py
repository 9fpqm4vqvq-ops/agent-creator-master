"""Local input controls. These are not an OS sandbox or identity service."""
import json
import re
from pathlib import Path

SECRET_KEYS = re.compile(r'^(?:password|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|credentials?)$', re.I)
HIDDEN_KEYS = {'chain_of_thought', 'private_reasoning', 'hidden_reasoning'}
PATTERNS = [
    re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk-ant-[A-Za-z0-9_-]{20,})'),
    re.compile(r'(?i)\bBearer\s+\S+'),
    re.compile(r'(?i)\b(password|api[_-]?key|secret|access[_-]?token)\s*[:=]\s*[^\s,;]+'),
    re.compile(r'(?i)[?&](?:token|key|api_key|access_token)=[^&#\s]+'),
    re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----', re.S),
]


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if SECRET_KEYS.search(str(k)) else redact(v)
                for k, v in value.items() if str(k).lower() not in HIDDEN_KEYS}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for pattern in PATTERNS:
            value = pattern.sub('[REDACTED]', value)
    return value


def safe_file(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Expected an existing file inside the project')
    return path


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
