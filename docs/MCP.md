# MCP

A dependency-free, read-only MCP server over stdio, reading the published datasets.

```bash
tools/data_pull.sh
PYTHONPATH=backend python3 -m airstack.mcp_server data/site
```

Tools: `search_products`, `get_product`, `get_evidence`, `changes_since`, `review_stack`. Every fact carries its verbatim quote, the
page it is on, the source class and the date the page was read. A product with no published fact says "Not observed".
The server reads files only: no network, no database, no model, no writes and no recommendation.
