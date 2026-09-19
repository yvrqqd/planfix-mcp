from typing import Any

LOG_ASPECTS = frozenset(
    {
        ('tasks', 'tech_log'),
        ('audit', 'entity_log'),
        ('audit', 'user_log'),
    }
)


def normalize_log_item(item: dict[str, Any]) -> dict[str, Any]:
    row = dict(item)
    if 'ID' not in row and 'id' in row:
        row['ID'] = row['id']
    if 'Type' not in row and 'type' in row:
        row['Type'] = row['type']
    if not row.get('DateTime'):
        stamp = row.get('ts')
        if isinstance(stamp, str) and stamp:
            row['DateTime'] = stamp
        else:
            date = row.get('logDate') or row.get('userLogDate') or row.get('Date')
            time = row.get('logTime') or row.get('userLogTime') or row.get('Time')
            if isinstance(date, str) and date and isinstance(time, str) and time:
                row['DateTime'] = f'{date} {time}'
            elif isinstance(date, str) and date:
                row['DateTime'] = date
    if 'User' not in row:
        login_id = row.get('loginId') or row.get('LoginID')
        name = row.get('loginName') or row.get('Login')
        if login_id is not None or name:
            user: dict[str, Any] = {}
            if login_id is not None:
                user['ID'] = login_id
            if name:
                user['Name'] = name
            row['User'] = user
    if not row.get('Description'):
        data = row.get('data', row.get('Data'))
        if isinstance(data, dict):
            text = data.get('Name') or data.get('Title')
            if text:
                row['Description'] = text
        elif isinstance(data, str) and data:
            row['Description'] = data
    if 'Data' not in row and isinstance(row.get('data'), dict):
        row['Data'] = row['data']
    return row
