import ipaddress
import re
from urllib.parse import urlsplit

_HOST_LABEL = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?')


def normalize_domain(value: str) -> str:
    candidate = value.strip()
    parsed = urlsplit(f'https://{candidate}')
    host = parsed.hostname
    if (
        not candidate
        or ':' in candidate
        or parsed.netloc != candidate
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
        or host is None
    ):
        raise ValueError('domain must contain only a hostname')
    try:
        ascii_host = host.encode('idna').decode('ascii').lower()
    except UnicodeError as exc:
        raise ValueError('invalid hostname') from exc
    if len(ascii_host) > 253 or any(_HOST_LABEL.fullmatch(label) is None for label in ascii_host.split('.')):
        raise ValueError('invalid hostname')
    try:
        ipaddress.ip_address(ascii_host)
    except ValueError:
        return ascii_host
    raise ValueError('IP addresses are not allowed')


def is_same_https_origin(url: str, domain: str) -> bool:
    try:
        parsed = urlsplit(url)
        port = parsed.port
        host = parsed.hostname
        actual = host.encode('idna').decode('ascii').lower() if host is not None else ''
        expected = normalize_domain(domain)
    except ValueError:
        return False
    return (
        parsed.scheme.lower() == 'https'
        and parsed.username is None
        and parsed.password is None
        and port in {None, 443}
        and actual == expected
    )


def https_origin(domain: str) -> str:
    return f'https://{normalize_domain(domain)}'


def absolute_https_url(domain: str, relative: str) -> str:
    host = normalize_domain(domain)
    if not relative.startswith('/') or relative.startswith('//') or '\\' in relative or '..' in relative:
        raise ValueError('path must be relative to the same origin')
    parsed = urlsplit(relative)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ValueError('path must be relative to the same origin')
    url = f'https://{host}{relative}'
    if not is_same_https_origin(url, host):
        raise ValueError('path must be relative to the same origin')
    return url
