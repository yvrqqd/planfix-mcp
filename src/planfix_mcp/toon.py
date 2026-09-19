"""Encode JSON-shaped values as TOON (Token-Oriented Object Notation).

Used only at the MCP tool boundary so the model sees compact text. JSON-RPC is unchanged.
"""

import math
import re
from decimal import Decimal
from typing import Any

_KEY_OK = re.compile(r'^[A-Za-z_][A-Za-z0-9_.]*$')
_NUMERIC = re.compile(r'^[+-]?[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?$', re.IGNORECASE)

type Field = str | tuple[str, list[Field]]


def encode(value: Any) -> str:
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            _field(lines, str(key), item, line=0, child=1)
    elif isinstance(value, list):
        _array(lines, value, key=None, line=0, child=1, hyphen=False)
    else:
        lines.append(_primitive(value))
    return '\n'.join(lines)


def _is_primitive(value: Any) -> bool:
    return value is None or isinstance(value, bool | int | float | str)


def _field(lines: list[str], key: str, value: Any, *, line: int, child: int, hyphen: bool = False) -> None:
    start = _start(line, hyphen)
    if isinstance(value, dict):
        lines.append(f'{start}{_key(key)}:')
        for nested_key, nested in value.items():
            _field(lines, str(nested_key), nested, line=child, child=child + 1)
        return
    if isinstance(value, list):
        _array(lines, value, key=key, line=line, child=child, hyphen=hyphen)
        return
    lines.append(f'{start}{_key(key)}: {_primitive(value)}')


def _array(
    lines: list[str],
    value: list[Any],
    *,
    key: str | None,
    line: int,
    child: int,
    hyphen: bool,
) -> None:
    start = _start(line, hyphen)
    prefix = '' if key is None else _key(key)
    if not value:
        if hyphen and key is None:
            lines.append(f'{"  " * line}- [0]:')
        elif key is None:
            lines.append(f'{start}[]')
        else:
            lines.append(f'{start}{prefix}: []')
        return
    shape = _table_shape(value)
    if shape is not None and (key is not None or not hyphen):
        header = f'{prefix}[{len(value)}]{{{_fields(shape)}}}:'
        lines.append(f'{start}{header}')
        pad = '  ' * child
        for row in value:
            lines.append(pad + ','.join(_cells(row, shape)))
        return
    if all(_is_primitive(item) for item in value):
        header = f'{prefix}[{len(value)}]: {",".join(_primitive(item) for item in value)}'
        lines.append(f'{start}{header}')
        return
    lines.append(f'{start}{prefix}[{len(value)}]:')
    for item in value:
        _item(lines, item, child)


def _item(lines: list[str], value: Any, depth: int) -> None:
    pad = '  ' * depth
    if isinstance(value, list):
        _array(lines, value, key=None, line=depth, child=depth + 1, hyphen=True)
        return
    if not isinstance(value, dict):
        lines.append(f'{pad}- {_primitive(value)}')
        return
    if not value:
        lines.append(f'{pad}-')
        return
    keys = list(value)
    _field(lines, keys[0], value[keys[0]], line=depth, child=depth + 2, hyphen=True)
    for key in keys[1:]:
        _field(lines, key, value[key], line=depth + 1, child=depth + 2)


def _table_shape(rows: list[Any]) -> list[Field] | None:
    if not rows or not all(isinstance(row, dict) and row for row in rows):
        return None
    keys = list(rows[0])
    wanted = set(keys)
    if any(set(row) != wanted for row in rows):
        return None
    shape: list[Field] = []
    for key in keys:
        column = [row[key] for row in rows]
        if all(_is_primitive(item) for item in column):
            shape.append(key)
            continue
        if all(isinstance(item, dict) and item for item in column):
            nested = _table_shape(column)
            if nested is None:
                return None
            shape.append((key, nested))
            continue
        return None
    return shape


def _fields(shape: list[Field]) -> str:
    parts: list[str] = []
    for item in shape:
        if isinstance(item, str):
            parts.append(_key(item))
        else:
            name, nested = item
            parts.append(f'{_key(name)}{{{_fields(nested)}}}')
    return ','.join(parts)


def _cells(row: dict[str, Any], shape: list[Field]) -> list[str]:
    cells: list[str] = []
    for item in shape:
        if isinstance(item, str):
            cells.append(_primitive(row[item]))
        else:
            name, nested = item
            cells.extend(_cells(row[name], nested))
    return cells


def _start(depth: int, hyphen: bool) -> str:
    pad = '  ' * depth
    return f'{pad}- ' if hyphen else pad


def _key(name: str) -> str:
    if _KEY_OK.match(name):
        return name
    return f'"{_escape(name)}"'


def _primitive(value: Any) -> str:
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _number(value)
    text = value if isinstance(value, str) else str(value)
    if _quoted(text):
        return f'"{_escape(text)}"'
    return text


def _number(value: float) -> str:
    if not math.isfinite(value):
        return 'null'
    if value == 0:
        return '0'
    text = repr(value).lower()
    magnitude = abs(value)
    if 1e-6 <= magnitude < 1e21:
        if 'e' in text:
            return format(Decimal(text), 'f')
        return text.removesuffix('.0')
    mantissa, separator, exponent = text.partition('e')
    if not separator:
        return mantissa.removesuffix('.0')
    normalized_exponent = int(exponent)
    sign = '+' if normalized_exponent >= 0 else ''
    return f'{mantissa.removesuffix(".0")}e{sign}{normalized_exponent}'


def _quoted(text: str) -> bool:
    if not text:
        return True
    if text[0] in '-#' or text[0] in ' \t' or text[-1] in ' \t':
        return True
    if text in {'true', 'false', 'null'} or _NUMERIC.match(text):
        return True
    return any(ch in text for ch in ':,\\"[]{}') or any(ord(ch) < 32 for ch in text)


def _escape(text: str) -> str:
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        elif code < 32:
            out.append(f'\\u{code:04x}')
        else:
            out.append(ch)
    return ''.join(out)
