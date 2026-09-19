from typing import Any, Literal

Profile = Literal['schema', 'summary', 'detail', 'full']

SCHEMA_LIST_LIMIT = 5
SUMMARY_LIST_LIMIT = 20
DETAIL_LIST_LIMIT = 50
MAX_STRING = 4000


def _trim_string(value: str) -> str:
    if len(value) <= MAX_STRING:
        return value
    return value[: MAX_STRING - 1] + '…'


def list_cap(profile: Profile) -> int:
    if profile == 'schema':
        return SCHEMA_LIST_LIMIT
    if profile == 'summary':
        return SUMMARY_LIST_LIMIT
    return DETAIL_LIST_LIMIT


def limit_payload(payload: Any, profile: Profile) -> Any:
    return _limit(payload, profile, list_cap(profile), depth=0, types=profile == 'schema')


def cap_payload(payload: Any, profile: Profile) -> Any:
    return _limit(payload, profile, list_cap(profile), depth=0, types=False)


def _limit(value: Any, profile: Profile, cap: int, depth: int, *, types: bool) -> Any:
    if depth > 8:
        return None
    if isinstance(value, str):
        return _trim_string(value)
    if isinstance(value, list):
        return [_limit(item, profile, cap, depth + 1, types=types) for item in value[:cap]]
    if isinstance(value, dict):
        if types:
            return {key: _type_leaf(item) for key, item in value.items()}
        return {key: _limit(item, profile, cap, depth + 1, types=types) for key, item in value.items()}
    return value


def _type_leaf(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: type(item).__name__ for key, item in value.items()}
    if isinstance(value, list):
        return f'list[{len(value)}]'
    if isinstance(value, str):
        return 'str'
    if value is None:
        return 'null'
    return type(value).__name__
