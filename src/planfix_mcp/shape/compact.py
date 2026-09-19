import re
from typing import Any

from planfix_mcp.limit import Profile, list_cap

_TAG = re.compile(
    r'<!--.*?-->|</?(?:'
    r'a|abbr|address|article|aside|audio|b|blockquote|body|br|button|center|code|'
    r'dd|del|div|dl|dt|em|figcaption|figure|font|footer|form|h[1-6]|header|hr|'
    r'html|i|iframe|img|input|ins|label|li|main|nav|ol|option|p|pre|s|script|'
    r'section|select|small|source|span|strike|strong|style|sub|sup|table|tbody|'
    r'td|textarea|th|thead|tr|u|ul|video'
    r')(?:\s[^<>]*)?\s*/?>',
    flags=re.IGNORECASE | re.DOTALL,
)
_SPACE = re.compile(r'\s+')
_KEY_NORMALIZE = re.compile(r'[^a-z0-9]+')
_NOISE = ('html', 'onclick', 'iconclass', 'cssclass', 'innerhtml')
_REF_KEYS = ('ID', 'Name', 'Title', 'Login', 'LoginID', 'GeneralID')
_SECRET_KEYS = frozenset(
    {
        'password',
        'passwordhash',
        'passwordsalt',
        'sessionkey',
        'sessionid',
        'sessiontoken',
        'adminkey',
        'phpsessid',
        'rtoken',
        'accesstoken',
        'refreshtoken',
        'csrftoken',
        'xcsrftoken',
        'xsrftoken',
        'token',
        'apikey',
        'secretkey',
        'clientsecret',
        'licensekey',
        'authorization',
        'cookie',
        'setcookie',
    }
)
_SECRET_SUFFIXES = ('password', 'token', 'apikey', 'secret', 'secretkey', 'privatekey', 'licensekey')
_LOGIN_RECORD_KEYS = ('Email', 'InnerEmail', 'IsActive', 'IsOnline')
_LOGIN_SUMMARY_KEYS = (
    'ID',
    'Name',
    'Login',
    'LoginID',
    'Email',
    'InnerEmail',
    'IsActive',
    'IsOnline',
    'GeneralID',
)
_LOGIN_DETAIL_KEYS = (
    *_LOGIN_SUMMARY_KEYS,
    'Lang',
    'Type',
    'TimeZoneName',
    'LastActivityDate',
    'formatedLastActivityDate',
)


def as_maps(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def is_scalar(value: Any) -> bool:
    return isinstance(value, str | int | float | bool) or value is None


def skip_key(key: str) -> bool:
    normalized = _KEY_NORMALIZE.sub('', key.lower())
    return (
        _noise_key(key) or normalized in _SECRET_KEYS or any(normalized.endswith(suffix) for suffix in _SECRET_SUFFIXES)
    )


def pick(item: dict[str, Any], fields: tuple[str, ...], profile: Profile) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for name in fields:
        if name in item and not skip_key(name):
            row[name] = compact(item[name], profile, depth=1)
    return row


def compact(value: Any, profile: Profile, depth: int) -> Any:
    if depth > 8:
        return None
    if isinstance(value, str):
        return _plain(value)
    if isinstance(value, list):
        cap = list_cap(profile)
        return [compact(item, profile, depth + 1) for item in value[:cap]]
    if not isinstance(value, dict):
        return value
    if profile != 'full':
        as_date = _datetime_text(value)
        if as_date is not None:
            return as_date
    if profile != 'full' and _looks_like_login_record(value):
        keys = _LOGIN_SUMMARY_KEYS if profile in {'schema', 'summary'} else _LOGIN_DETAIL_KEYS
        return {key: compact(value[key], profile, depth + 1) for key in keys if key in value and not skip_key(key)}
    if profile != 'full' and _looks_like_ref(value):
        return {key: compact(value[key], profile, depth + 1) for key in _REF_KEYS if key in value and not skip_key(key)}
    return {key: compact(item, profile, depth + 1) for key, item in value.items() if not skip_key(key)}


def _datetime_text(value: dict[str, Any]) -> str | None:
    if 'ID' in value:
        return None
    date = value.get('Date')
    if not isinstance(date, str) or not date:
        return None
    if 'Time' not in value and 'UnixTime' not in value:
        return None
    time_part = value.get('Time')
    if isinstance(time_part, str) and time_part:
        return f'{date} {time_part}'
    return date


def _looks_like_login_record(value: dict[str, Any]) -> bool:
    if 'ID' not in value:
        return False
    return any(key in value for key in _LOGIN_RECORD_KEYS)


def _looks_like_ref(value: dict[str, Any]) -> bool:
    if 'ID' not in value:
        return False
    if _looks_like_login_record(value):
        return False
    if not any(key in value for key in ('Name', 'Title')):
        return False
    return len(value) > 3


def _noise_key(key: str) -> bool:
    lower = key.lower()
    return any(token in lower for token in _NOISE)


def _plain(value: str) -> str:
    if '<' in value and '>' in value:
        value = _SPACE.sub(' ', _TAG.sub(' ', value)).strip()
    return value
