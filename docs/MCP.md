# MCP

AirStack includes a dependency-free, read-only MCP server for reviewed local data.

```bash
cd backend
python -m airstack.mcp_server ../data/airstack-demo.db
```

Local tools can read verdicts, evidence, recorded changes, entities and a supplied stack. They do not crawl, call a model, mutate the record or open a network listener. Unknown values remain unknown; an answer that needs another check is never presented as current.
