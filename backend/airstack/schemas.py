# spec: AS-022 AS-030 AS-137 AS-250 AS-327 AS-350
"""Tiny JSON-schema subset validator (no dependency) plus the FLAT schemas for every Spark role and public tool."""
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

SLUG = r"^[a-z0-9][a-z0-9._-]{0,63}$"
_S = {"type": "string"}
# what the market extractor may state, and the JSON shape of each value (code checks the shape and the quote)
CATALOG_METRICS = {
    "x.what_it_does": "string: the product's own one-line description",
    "x.joins_meeting_apps": "list of meeting apps it records or joins, e.g. Zoom, Google Meet, Microsoft Teams, Webex",
    "x.in_person_capture": "boolean: it can capture in-person (not online) meetings",
    "x.devices": "list from: Web, Windows, macOS, Linux, iPhone, iPad, Android, Chrome extension",
    "x.languages_count": "integer: number of transcription languages it states",
    "x.integrations": "list of other products it integrates with, names as written",
    "x.compliance": "list from: SOC 2, SOC 2 Type II, HIPAA, GDPR, ISO 27001, CCPA",
    "x.free_plan": "boolean: a free plan exists",
    "x.plan_names": "list of plan names as written",
    "x.notes_plans": "list of plan or license names that include AI meeting notes or summaries",
    "x.in_person_terms": "string: the plan or limit under which in-person capture is offered, as written",
    "x.store_users": "integer: users shown on a Chrome Web Store listing",
    "x.store_rating": "object {rating: number, count: string} shown on a store listing",
    "x.bot_free": "boolean: it records without a bot joining the meeting",
}
# the generic product profile: any software tool, from its own pages
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
_S1 = {"type": "string", "minLength": 1}

ROLE_SCHEMAS = {
    "extract": {"type": "object", "additionalProperties": False, "required": ["facts"], "properties": {
        "facts": {"type": "array", "maxItems": 50, "items": {
            "type": "object", "additionalProperties": False, "required": ["metric", "value_json", "source_url", "source_ts"],
            "properties": {"metric": _S1, "value_json": _S, "source_url": _S1, "source_ts": _S}}}}},     # "" = unknown (strict mode: every key required)
    "classify": {"type": "object", "additionalProperties": False, "required": ["label", "material", "rationale"], "properties": {
        "label": {"enum": ["breaking", "deprecation", "license_change", "pricing_change", "capability_shock", "minor"]},
        "material": {"type": "boolean"}, "rationale": _S1}},
    "search": {"type": "object", "additionalProperties": False, "required": ["results"], "properties": {
        "results": {"type": "array", "maxItems": 8, "items": {
            "type": "object", "additionalProperties": False, "required": ["url", "title", "snippet", "published"],
            "properties": {"url": _S1, "title": _S, "snippet": _S, "published": _S}}}}},             # "" = unknown, never an invented date
    "judge": {"type": "object", "additionalProperties": False, "required": ["action", "reason", "confidence", "citations"], "properties": {
        "action": {"enum": ["BUILD", "BUY", "KEEP", "RETIRE"]},
        "reason": {"type": "string", "minLength": 1, "maxLength": 600},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "citations": {"type": "array", "minItems": 1, "maxItems": 20, "items": {"type": "string", "pattern": r"^f[0-9]+$"}}}},
    # market research: facts about one product from ONE fetched page, each with the verbatim quote code will look for on that page
    "profile": {"type": "object", "additionalProperties": False, "required": ["facts"], "properties": {
        "facts": {"type": "array", "maxItems": 40, "items": {
            "type": "object", "additionalProperties": False, "required": ["metric", "value_json", "quote", "source_ts"],
            "properties": {"metric": {"enum": list(PROFILE_METRICS)}, "value_json": _S1, "quote": {"type": "string", "minLength": 3, "maxLength": 400},
                           "source_ts": _S}}}}},
    # the daily brief: a few plain sentences written ONLY from facts we computed, each citing the facts it uses (code checks every number)
    "brief": {"type": "object", "additionalProperties": False, "required": ["headline", "items"], "properties": {
        "headline": {"type": "string", "minLength": 1, "maxLength": 110},
        "items": {"type": "array", "minItems": 3, "maxItems": 5, "items": {
            "type": "object", "additionalProperties": False, "required": ["text", "cites"],
            "properties": {"text": {"type": "string", "minLength": 1, "maxLength": 240},
                           "cites": {"type": "array", "minItems": 1, "maxItems": 4, "items": {"type": "string", "pattern": r"^d[0-9]+$"}}}}}}},
    # list prices from one part of a pricing page: each as written, with a verbatim quote that contains it (code checks the quote is on the page)
    "pricing": {"type": "object", "additionalProperties": False, "required": ["plans"], "properties": {
        "plans": {"type": "array", "maxItems": 12, "items": {
            "type": "object", "additionalProperties": False, "required": ["plan", "price", "period", "unit", "quote"],
            "properties": {"plan": {"type": "string", "minLength": 1, "maxLength": 60}, "price": {"type": "string", "minLength": 2, "maxLength": 30},
                           "period": {"enum": ["month", "year", "one-time", "unknown"]}, "unit": {"enum": ["user", "flat", "usage", "unknown"]},
                           "quote": {"type": "string", "minLength": 3, "maxLength": 240}}}}}},
    # the taxonomy: one category for one product, from its own one-line description ("" = abstain); code checks the quote is in that description
    "place": {"type": "object", "additionalProperties": False, "required": ["node", "quote"], "properties": {
        "node": {"type": "string", "maxLength": 64}, "quote": {"type": "string", "maxLength": 300}}},
    "catalog": {"type": "object", "additionalProperties": False, "required": ["facts"], "properties": {
        "facts": {"type": "array", "maxItems": 40, "items": {
            "type": "object", "additionalProperties": False, "required": ["metric", "value_json", "quote", "source_ts"],
            "properties": {"metric": {"enum": list(CATALOG_METRICS)}, "value_json": _S1, "quote": {"type": "string", "minLength": 3, "maxLength": 400},
                           "source_ts": _S}}}}},
}

_COND = {"type": "object", "additionalProperties": False, "required": ["key", "op", "value"],
         "properties": {"key": _S1, "op": {"enum": ["eq", "ne", "includes", "gte"]}, "value": {}}}
_REQ = {"type": "object", "additionalProperties": False, "required": ["id", "text", "all"], "properties": {
    "id": _S1, "text": _S1, "all": {"type": "array", "minItems": 1, "maxItems": 6, "items": _COND}, "entitlement": {"type": "string", "maxLength": 80}}}

_UNDOCUMENTED = ("minLength", "maxLength", "pattern", "minimum", "maximum", "minItems", "maxItems", "format")

def strip_for_provider(schema):
    """dev.meta.ai documents only: every key in `required`, additionalProperties:false, anyOf below the root. It says nothing about
    length/range/pattern keywords, so the request omits them (a rejected request would still count against the account ledger).
    validate() keeps enforcing all of them on the response."""
    if isinstance(schema, dict):
        return {k: strip_for_provider(v) for k, v in schema.items() if k not in _UNDOCUMENTED}
    if isinstance(schema, list):
        return [strip_for_provider(v) for v in schema]
    return schema

TOOL_ARGS = {
    "get_verdict": {"type": "object", "additionalProperties": False, "required": ["tool"], "properties": {
        "tool": {"type": "string", "pattern": SLUG}, "seat": {"type": "string", "pattern": r"^[A-Za-z0-9_-]{1,32}$"},
        "as_of": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}}},
    "get_evidence": {"type": "object", "additionalProperties": False, "required": ["tool"], "properties": {
        "tool": {"type": "string", "pattern": SLUG}}},
    "changes_since": {"type": "object", "additionalProperties": False, "required": ["since"], "properties": {
        "since": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}(T[0-9:]{8}Z)?$"}}},
    "review_stack": {"type": "object", "additionalProperties": False, "required": ["tools"], "properties": {
        "tools": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["tool"], "properties": {
            "tool": {"type": "string", "pattern": SLUG}, "seat": {"type": "string", "pattern": r"^[A-Za-z0-9_-]{1,32}$"},
            "requirements": {"type": "array", "maxItems": 12, "items": _REQ},
            "entitlements": {"type": "array", "maxItems": 20, "items": {"type": "string", "maxLength": 80}}}}}}},
    "get_entity": {"type": "object", "additionalProperties": False, "required": ["tool"], "properties": {"tool": {"type": "string", "pattern": SLUG}}},
}
