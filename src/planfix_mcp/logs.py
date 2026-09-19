import logging
import sys

_SDK_LOGGER = 'mcp'


def configure_logging(level: str = 'INFO') -> None:
    normalized = level.upper()
    logging.basicConfig(
        level=normalized,
        format='%(levelname)s %(name)s %(message)s',
        stream=sys.stderr,
        force=True,
    )
    sdk = logging.getLogger(_SDK_LOGGER)
    if normalized == 'DEBUG':
        sdk.setLevel(logging.NOTSET)
    else:
        sdk.setLevel(logging.WARNING)
