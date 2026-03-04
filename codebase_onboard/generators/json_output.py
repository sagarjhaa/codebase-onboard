"""Generate JSON output for programmatic use."""

import json
import dataclasses
from ..models import RepoAnalysis


def generate_json(analysis: RepoAnalysis) -> str:
    """Generate JSON representation of the analysis."""
    data = _to_dict(analysis)
    return json.dumps(data, indent=2, default=str)


def _to_dict(obj):
    """Recursively convert dataclasses to dicts."""
    if dataclasses.is_dataclass(obj):
        result = {}
        for field in dataclasses.fields(obj):
            value = getattr(obj, field.name)
            result[field.name] = _to_dict(value)
        return result
    elif isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, tuple):
        return list(obj)
    return obj
