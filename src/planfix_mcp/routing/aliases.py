ALIASES: dict[tuple[str, str], str] = {
    ('tasks', 'technical_log'): 'tech_log',
    ('tasks', 'comments'): 'actions',
    ('audit', 'system_log'): 'entity_log',
    ('audit', 'sys_log'): 'entity_log',
}


def normalize_aspect(block: str, aspect: str) -> str:
    return ALIASES.get((block, aspect), aspect)
