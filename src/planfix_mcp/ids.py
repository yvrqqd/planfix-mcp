import json
from pathlib import Path
from typing import Any

_DEFAULT = Path(__file__).resolve().parent / 'data' / 'id_glossary.json'


def load_id_glossary(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or _DEFAULT).read_text(encoding='utf-8'))
