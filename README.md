# AirStack.bot MCP server

A read-only [MCP](https://modelcontextprotocol.io) server over [AirStack.bot](https://airstack.bot)'s published data: facts about
software products, each with its quote, the page it is on and the day that page was read. It runs on your machine, reads local
files and calls nothing else. Python 3.10 or later, no dependencies.

```bash
git clone https://github.com/OttObottr/airstack.git && cd airstack
./pull.sh                                   # the published data into data/site
```

Add it to your MCP client, with the folder's full path:

```json
{"mcpServers": {"airstack": {"command": "python3", "args": ["-m", "airstack.mcp_server"], "env": {"PYTHONPATH": "/full/path/to/airstack"}}}}
```

Tools: `search_products`, `get_product`, `get_evidence`, `changes_since`, `review_stack`, `compare_products`. A product with no published fact says
"Not observed". Run `./pull.sh` again for newer data; the running server picks up updates automatically.

Tests: `python3 -m unittest discover tests`

## Security

Report a vulnerability privately through [GitHub](https://github.com/OttObottr/airstack/security/advisories/new). Anything else:
privacy@airstack.bot.

## Licences

The code is MIT. The data's terms are at [airstack.bot/open-data](https://airstack.bot/open-data/) and
[airstack.bot/legal/notices.txt](https://airstack.bot/legal/notices.txt).
