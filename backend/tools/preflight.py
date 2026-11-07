# spec: AS-026 AS-027
"""Secret-free configuration check. Loads the environment ON PURPOSE (from ../.env if given), then prints only
whether each required setting is present and which spending limits are active. It never prints a secret and makes no call.
Usage: python backend/tools/preflight.py [--env PATH]"""
import os, sys
from pathlib import Path
from airstack import paths

ROOT = paths.ROOT
REQUIRED_SETTINGS = ("MODEL_API_KEY", "AIRSTACK_HARD_CEILING_USD", "AIRSTACK_ACCOUNT_CAP_USD")

def load_env(path):
    """Minimal KEY=VALUE loader. Existing environment variables win. Values are never echoed."""
    loaded = []
    if path and Path(path).exists():
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if v.strip() and k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip(); loaded.append(k.strip())
    return loaded

def main(env_file=str(ROOT / ".env")):
    loaded = load_env(env_file)
    from airstack import config as c                      # read AFTER the env is loaded
    print(f"env file: {env_file or '(none)'} · loaded {len(loaded)} setting(s)")
    present = {name for name in REQUIRED_SETTINGS if bool(os.environ.get(name))}
    for k in REQUIRED_SETTINGS:
        print(f"{k}: {'present' if k in present else 'MISSING'}")
    print(f"model: {c.MODEL} · base url: {c.BASE_URL}")
    from airstack.account_guard import AccountGuard, account_cap
    acct = AccountGuard()
    print(f"account authorization: {'enabled for this run' if account_cap() else 'OFF'} · {'STOPPED' if acct.stopped() else 'not stopped'}")
    print("Verify provider billing and usage in the private operator console before each authorized run.")
    print(f"per job: {c.TOOL_MAX_CALLS} calls · max output tokens {c.MAX_OUTPUT_TOKENS} · max input chars {c.MAX_INPUT_CHARS}")
    print(f"prices reserved ($/M tokens in/out): {c.PRICE_IN_PER_MTOK} / {c.PRICE_OUT_PER_MTOK}")
    print("paid model web search: DISABLED (no provider-guaranteed per-call query ceiling)")
    ok = all(k in present for k in REQUIRED_SETTINGS) and bool(account_cap()) and not acct.stopped()
    print("RESULT:", "ready for an authorized, bounded smoke test" if ok else "not ready (missing or invalid authorization, or stopped)")
    return 0 if ok else 1

if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(a[a.index("--env") + 1] if "--env" in a else str(ROOT / ".env")))
