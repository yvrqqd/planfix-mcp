[ru](README.md) · **en**

# planfix-mcp

Unofficial MCP server for Planfix.  
This release exposes **93 read operations, grouped into 15 domain blocks**.

![Available data: 15 Planfix domain blocks](docs/images/readme-capabilities.svg)

Example prompts:

- “Investigate the incident on task #123: compare the card, comments, and technical log; build a timeline of status, assignee, and deadline changes.”
- “Prepare an overdue-task report: group by assignees and projects, highlight the most critical cases, and distinguish planned deadline from actual completion.”
- “Audit configuration changes for the past week: who changed what and when, which changes repeated, and which processes may have been affected.”
- “Build a client risk report: find related projects and open tasks, overdue items, dependencies, and recent notable events. Name the owners and the five main risks.”
- “Inventory integrations and incoming webhooks: flag disabled and suspiciously duplicated items, and state which details cannot be verified from the available data.”



## Notes

- The listed commands are treated as non-mutating, but they may still have side effects on the Planfix side — for example updating a viewed/read marker or session activity. The code is open — review it and assess the risks before use; you are responsible for how you use it.
- This is an unofficial project, not affiliated with Planfix. It uses the same interface as the web client, so behavior depends on PF's version.
- The default rate limit is one request per second; it is configurable via environment variables.
- Chromium is used only for login. Session data is kept in process memory only.
- Login is automatic and happens on the first request, so that request can take a while.



## How the server works

The MCP client starts a Python process and talks to it over stdio. The server:

1. logs into Planfix with Playwright Chromium;
2. takes the session data, then closes the browser;
3. fetches data over HTTP;
4. returns a cleaned, compacted response.



## Install

Python **3.14** and Chromium are required. From the project directory:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m playwright install chromium
cp .env.example .env
chmod 600 .env
```

Windows (PowerShell):

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install .
.\.venv\Scripts\python -m playwright install chromium
copy .env.example .env
```

The path to Playwright’s Chromium is detected automatically. For a different browser, set `PF_BROWSER_BIN` to the absolute path of its executable.

### Account setup

Open `.env` and set:

```dotenv
PF_DOMAIN=company.planfix.com
PF_USERNAME=user@example.com
PF_PASSWORD=secret
```

`PF_DOMAIN` is the host only, without `https://`. `PF_LANG` sets the Planfix response language and defaults to `Ru`.

### Connect Cursor or Claude Desktop

For a `.venv` install, use absolute paths:

```json
{
  "mcpServers": {
    "planfix": {
      "command": "/abs/path/to/planfix-mcp/.venv/bin/python",
      "args": ["/abs/path/to/planfix-mcp/run.py"]
    }
  }
}
```

On Windows, use these paths:

```json
{
  "command": "C:\\Users\\you\\planfix-mcp\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Users\\you\\planfix-mcp\\run.py"]
}
```

For `uv`:

```json
{
  "mcpServers": {
    "planfix": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/abs/path/to/planfix-mcp",
        "python",
        "run.py"
      ]
    }
  }
}
```

After adding the config, restart the MCP server. Do not also run `run.py` in a terminal.