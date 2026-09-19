from typing import Any

import orjson

from planfix_mcp.errors import PlanfixRequestError

WEBHOOK_SAFE_KEYS = (
    'id',
    'name',
    'requestType',
    'method',
    'isActive',
    'actionsLoginType',
    'actionsLoginId',
    'withoutNotices',
    'responseType',
    'deleted',
)
_INVALID_WEBHOOK_LIST = 'Planfix returned invalid webhook list'


def prepare_webhooks(payload: dict[str, Any]) -> dict[str, Any]:
    rows = _parse_webhook_list(payload.get('webhookList'))
    body: dict[str, Any] = {
        'Result': payload.get('Result'),
        'Items': [_project_webhook(item) for item in rows if isinstance(item, dict)],
    }
    if 'complexWebhooksVersion' in payload:
        body['complexWebhooksVersion'] = payload['complexWebhooksVersion']
    return body


def _parse_webhook_list(raw: Any) -> list[Any]:
    if isinstance(raw, str | bytes):
        try:
            parsed = orjson.loads(raw)
        except orjson.JSONDecodeError as exc:
            raise PlanfixRequestError(_INVALID_WEBHOOK_LIST) from exc
    elif isinstance(raw, list):
        parsed = raw
    else:
        raise PlanfixRequestError(_INVALID_WEBHOOK_LIST)
    if not isinstance(parsed, list):
        raise PlanfixRequestError(_INVALID_WEBHOOK_LIST)
    return parsed


def _project_webhook(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item[key] for key in WEBHOOK_SAFE_KEYS if key in item}
