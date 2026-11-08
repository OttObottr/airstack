"""A JSON-schema subset validator, the fact vocabulary and the MCP tool argument schemas."""
import re

class SchemaError(ValueError):
    pass

_T = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}

def _is(v, t):
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _T[t])

def validate(inst, schema, path="$"):
    t = schema.get("type")
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        if not any(_is(inst, x) for x in ts):
            raise SchemaError(f"{path}: expected {t}, got {type(inst).__name__}")
    if "enum" in schema and inst not in schema["enum"]:
        raise SchemaError(f"{path}: {inst!r} not in {schema['enum']}")
    if isinstance(inst, str):
        if len(inst) < schema.get("minLength", 0):
            raise SchemaError(f"{path}: shorter than {schema['minLength']}")
        if len(inst) > schema.get("maxLength", 10**9):
            raise SchemaError(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            raise SchemaError(f"{path}: does not match {schema['pattern']}")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in schema and inst < schema["minimum"]:
            raise SchemaError(f"{path}: below minimum")
        if "maximum" in schema and inst > schema["maximum"]:
            raise SchemaError(f"{path}: above maximum")
    if isinstance(inst, list):
        if len(inst) < schema.get("minItems", 0):
            raise SchemaError(f"{path}: fewer than {schema['minItems']} items")
        if len(inst) > schema.get("maxItems", 10**9):
            raise SchemaError(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, x in enumerate(inst):
                validate(x, schema["items"], f"{path}[{i}]")
    if isinstance(inst, dict):
        for k in schema.get("required", []):
            if k not in inst:
                raise SchemaError(f"{path}: missing required '{k}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in inst:
                if k not in props:
                    raise SchemaError(f"{path}: unexpected property '{k}'")
        for k, sub in props.items():
            if k in inst:
                validate(inst[k], sub, f"{path}.{k}")
    return inst

CATALOG_METRICS = {
    "x.what_it_does": "string: the product's own one-line description",
    "x.devices": "list of supported device or client names, as written",
    "x.languages_count": "integer: number of languages it states",
    "x.integrations": "list of other products it integrates with, names as written",
    "x.compliance": "list of compliance or certification claims, names as written",
    "x.free_plan": "boolean: a free plan exists",
    "x.plan_names": "list of plan names as written",
    "x.store_users": "integer: users shown on a Chrome Web Store listing",
    "x.store_rating": "object {rating: number, count: string} shown on a store listing",
}
PROFILE_METRICS = {
    "x.what_it_does": "string: the product's own one-line description",
    "x.open_source": "boolean: the product says it is open source",
    "x.license": "string: the license name as written, e.g. MIT, Apache-2.0",
    "x.deployment": "list from: Cloud, Self-hosted, On-premises, Local",
    "x.platforms": "list of platforms or surfaces as written, e.g. Web, macOS, Windows, Linux, iOS, Android, VS Code, JetBrains, CLI, API",
    "x.sdk_languages": "list of programming languages it offers SDKs or support for, names as written",
    "x.models_supported": "list of model providers or models it supports, names as written",
    "x.integrations": "list of other products it integrates with, names as written",
    "x.integrations_count": "integer: number of integrations it states",
    "x.compliance": "list from: SOC 2, SOC 2 Type II, HIPAA, GDPR, ISO 27001, CCPA",
    "x.free_plan": "boolean: a free plan or free tier exists",
    "x.plan_names": "list of plan names as written",
    "x.pricing_basis": "string: how it is priced, as written (per seat, usage-based, per token), never an amount",
    "x.customers_claimed": "string: the vendor's own claim about its users or customers, as written",
    "x.founded_year": "integer: the year the company says it was founded",
}
ID = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
_ID = {"type": "string", "pattern": ID}
_DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
MAX_STACK = 25

TOOL_ARGS = {
    "search_products": {"type": "object", "additionalProperties": False, "required": ["query"], "properties": {
        "query": {"type": "string", "minLength": 2, "maxLength": 80}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}}},
    "get_product": {"type": "object", "additionalProperties": False, "required": ["id"], "properties": {"id": _ID}},
    "get_evidence": {"type": "object", "additionalProperties": False, "required": ["id"], "properties": {"id": _ID}},
    "changes_since": {"type": "object", "additionalProperties": False, "required": ["since"], "properties": {"since": _DATE}},
    "review_stack": {"type": "object", "additionalProperties": False, "required": ["ids"], "properties": {
        "ids": {"type": "array", "minItems": 1, "maxItems": MAX_STACK, "items": _ID}}},
}
