BLOCK_LEADS: dict[str, str] = {
    'tasks': (
        'Tasks (runtime work records). Prefer global_search when a query is known; '
        'list browses a filter id without persisting UI state. '
        'List pages with offset + page_size (has_more / next_offset). Search ignores page_size '
        '(step 20). Comments: actions uses last_action (0 then last_action from the result) '
        'for newer feed items; older pages are card_data with offset. '
        'Task-card technical log (UI «Технический лог»): aspect=tech_log with task=. '
        'That is not the account system journal (audit entity_log). '
        'tech_log summary includes DateTime, User, Type, Description (the event). '
        'This tool is read-only and cannot comment or change status.'
    ),
    'projects': 'Projects. Prefer global_search when a query is known; list browses a filter id.',
    'contacts': (
        'Contacts and companies. Prefer global_search or client_search; templates are Contact/Company processes.'
    ),
    'employees': 'Employees and groups. is_admin requires a real user/login id (0 always returns false).',
    'handbooks': (
        'Handbooks (directories) and their data rows. '
        'expand=true on list with handbook=<id> loads one handbook info (second request).'
    ),
    'documents': 'Document library items and file search. items pages with offset, folder_offset, first_group_offset.',
    'planners': 'Planners (boards and calendars) — reads only.',
    'filters': 'Saved list filters. Resolve a filter id before browsing entity list.',
    'analytics': 'Analytic tags / data fields on tasks.',
    'reports': 'Saved report definitions only — this server cannot run report output.',
    'automation': (
        'Process/status-set configuration, automatic scenarios, rules, logs, and reusable operations. '
        'triggers are automatic scenarios. status_sets supports expand=true with status_set=<process id>; '
        'triggers supports expand=true with status_set=<process id> and trigger=<id>. '
        'triggers / macros / trigger_logs need status_set=, not object=. '
        'The unpublished, process-scoped macros route may represent process buttons; do not assume '
        'it covers every modern Object button type. custom_operations lists reusable scenario '
        'operations independent of Objects and has no detail expansion.'
    ),
    'account_config': (
        'Account setup reads: templates, custom fields, email filters, integrations, access. '
        'aspect=overview fans out six AJAX calls; prefer targeted aspects. '
        'expand=true on task_templates with object=<template id> loads template fields (second request). '
        'integrations reads conf:selectList; it is not an incoming-webhook inventory. '
        'incoming_webhooks lists incoming webhook names and status only; URL slugs and '
        'operations are never returned. This tool is read-only and cannot create or edit webhooks.'
    ),
    'workspace': (
        'Workspace reads (list may be empty while Current.workSpaceId still exists). get requires object=<workSpaceId>.'
    ),
    'audit': (
        'Account and employee logs, not a task-card log. '
        'entity_log = system journal of settings changes '
        '(UI «Системный журнал» / «Изменение настроек системы»; alias system_log). '
        'summary includes DateTime, User, Type, Description. '
        'Sends dataFrom/dataTo (default 2000-01-01 through now); narrow with data_from / data_to. '
        'user_log = employee Events tab (needs a real user id, never 0). '
        'work_summary = «Мои действия» / timesheet-style summary (needs user). '
        'chronicle_menu = Chronicle filter metadata only, not the feed. '
        'For a task technical log use tasks aspect=tech_log.'
    ),
    'session': (
        'Planfix login metadata (phone_types, notices). Do not call this to connect — '
        'any domain tool or ajax logs in automatically. '
        'aspect=status is diagnostic only; aspect=logout drops the in-memory session if the user asked.'
    ),
}


def block_description(block: str, aspects: tuple[str, ...]) -> str:
    lead = BLOCK_LEADS.get(block, f'Planfix {block} block.')
    listed = ', '.join(aspects)
    return (
        f'{lead} Required: aspect. '
        f'Aspects: {listed}. '
        f'response_profile: schema | summary (default, operational fields) | '
        f'detail (extra columns for analysis) | full (non-secret Planfix structure / debug). '
        f'Result is TOON text for the model, not the user.'
    )
