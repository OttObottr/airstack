# spec: AS-210
"""Bidirectional audit of SPECS/ <-> code <-> tests <-> journeys. The ticket files in SPECS/*.md are the source of truth.
  python tools/spec_audit.py          check; exit 1 on any gap
  python tools/spec_audit.py --fix    also rewrite each code file's `spec:` marker to match the tickets that cite it
  python tools/spec_audit.py --table  print a traceability table (ticket, status, files, tests, journeys) instead of storing one"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "SPECS"
NOT_TICKETS = {"README.md"}
STATUSES = {"TODO", "IN PROGRESS", "DONE"}
CODE = ["backend/airstack/**/*.py", "backend/tools/**/*.py", "backend/tests/*.py", "JOURNEY/*.py", "tools/*.py", "tools/*.sh", "web/index.html",
        "web/public/legal/index.html", "web/public/404.html", "web/public/sw.js", "web/public/manifest.webmanifest", "web/public/robots.txt",
        "web/public/llms.txt", "web/src/**/*.js", "web/src/**/*.css", "wrangler.jsonc", ".github/workflows/*.yml"]
EXEMPT = {"backend/airstack/__init__.py", "backend/tests/__init__.py"}
COMMENT = {".py": "# {}", ".sh": "# {}", ".yml": "# {}", ".js": "// {}", ".mjs": "// {}", ".jsonc": "// {}", ".html": "<!-- {} -->", ".css": "/* {} */"}
ID = r"AS-[A-Z0-9]+"

def parse_tickets():
    tickets, journeys = [], {}
    for p in sorted(SPECS.glob("*.md")):
        if p.name in NOT_TICKETS:
            continue
        for sec in re.split(r"(?m)^(?=## AS-)", p.read_text())[1:]:
            main, *js = re.split(r"(?m)^(?=### J-)", sec)
            head = re.match(rf"## ({ID}) · (.+)\n(TODO|IN PROGRESS|DONE|\S.*?) · (P\d)( · user-facing)?\n", main)
            if not head:
                tickets.append({"id": main.split("\n")[0], "bad": True, "path": p}); continue
            line = lambda key: next((l[len(key) + 2:] for l in main.split("\n") if l.startswith(key + ": ")), "")
            tests = [(f, n.strip()) for part in line("Tests").split("; ") if part for f, _, ns in [part.partition("::")] for n in ns.split(", ")]
            tickets.append({"id": head.group(1), "title": head.group(2), "status": head.group(3), "ux": bool(head.group(5)), "path": p,
                            "checks": re.findall(r"^- \[( |x)\] (.+)$", main, re.M),
                            "files": [f for f in line("Files").split(", ") if f], "tests": tests,
                            "journeys": re.findall(r"J-[0-9a-z]+", line("Journeys")), "bad": False})
            for j in js:
                m = re.match(r"### (J-[0-9a-z]+) · (.+)\nWho: .*?Test: (\S+::\w+|none.*)", j)
                if m:
                    journeys.setdefault(m.group(1), []).append(m.group(3) if "::" in m.group(3) else None)
                else:
                    journeys.setdefault(j.split(" ")[1], []).append("bad")
    return tickets, journeys

DATA_NOT_IN_REPO = re.compile(r"data/")

def expand(pattern):
    return [p for p in ROOT.glob(pattern) if p.is_file()] if "*" in pattern else ([ROOT / pattern] if (ROOT / pattern).exists() else [])

def test_exists(file, name):
    p = ROOT / file
    return p.exists() and re.search(rf"^(?:async )?def {re.escape(name)}\b", p.read_text(), re.M) is not None

def marker_ids(p):
    m = re.search(r"spec:\s*((?:AS-[A-Z0-9]+\s*)+)", "\n".join(p.read_text(errors="ignore").splitlines()[:3]))
    return set(m.group(1).split()) if m else None

def write_marker(p, ids):
    line = COMMENT[p.suffix].format("spec: " + " ".join(sorted(ids)))
    lines = p.read_text().splitlines(keepends=True)
    for i, l in enumerate(lines[:3]):
        if re.search(r"spec:\s*AS-", l):
            lines[i] = line + "\n"; break
    else:
        lines.insert(1 if lines and (lines[0].startswith("#!") or lines[0].lower().startswith("<!doctype")) else 0, line + "\n")
    p.write_text("".join(lines))

def citing(path):
    """Ids of the tickets that list `path` (used by the generators that write their own marker)."""
    return sorted(t["id"] for t in parse_tickets()[0] if not t["bad"] and any(path == f or ROOT / path in expand(f) for f in t["files"]))

def main(fix=False, table=False):
    errors = []
    tickets, journeys = parse_tickets()
    by_id = {t["id"]: t for t in tickets}
    for t in tickets:
        if t["bad"]:
            errors.append(f"{t['path'].name}: malformed ticket header {t['id']!r}")
    tickets = [t for t in tickets if not t["bad"]]
    if len(by_id) != len(tickets):
        errors.append("duplicate ticket ids")
    for j, tests in journeys.items():
        if len(tests) > 1:
            errors.append(f"{j}: defined {len(tests)} times")
    proven = set()
    cites = {}                                                     # file -> ids of tickets that cite it
    for t in tickets:
        if t["status"] not in STATUSES:
            errors.append(f"{t['id']}: unknown status {t['status']!r}")
        if not t["checks"]:
            errors.append(f"{t['id']}: has no criteria")
        for pattern in t["files"]:
            found = expand(pattern)
            if not found and not DATA_NOT_IN_REPO.match(pattern):                  # data is not in the repository: a ticket may cite it
                errors.append(f"{t['id']}: cites missing file {pattern}")
            for p in found:
                cites.setdefault(p.relative_to(ROOT).as_posix(), set()).add(t["id"])
        for f, name in t["tests"]:
            if not test_exists(f, name):
                errors.append(f"{t['id']}: cites missing test {f}::{name}")
            cites.setdefault(f, set()).add(t["id"])
        for j in t["journeys"]:
            if j not in journeys:
                errors.append(f"{t['id']}: cites undefined journey {j}")
                continue
            test = journeys[j][0]
            if test and test != "bad":
                f, _, name = test.partition("::")
                if not test_exists(f, name):
                    errors.append(f"{j}: cites missing test {test}")
                cites.setdefault(f, set()).add(t["id"])
                proven.add(t["id"])
        if t["status"] == "DONE":
            if any(c == " " for c, _ in t["checks"]):
                errors.append(f"{t['id']}: DONE but has unticked criteria")
            if not t["tests"]:
                errors.append(f"{t['id']}: DONE but cites no test")
            if t["ux"] and t["id"] not in proven:
                errors.append(f"{t['id']}: user-facing and DONE but no automated journey proves it")
    files = sorted({p.relative_to(ROOT).as_posix() for g in CODE for p in ROOT.glob(g) if p.is_file()} - EXEMPT)
    for f in files:
        if f not in cites:
            errors.append(f"orphan: {f} is not described by any ticket")
            continue
        p = ROOT / f
        if p.suffix in COMMENT:
            if fix:
                write_marker(p, cites[f])
            have = marker_ids(p)
            if have is None:
                errors.append(f"{f}: no `spec:` marker")
            elif have != cites[f]:
                errors.append(f"{f}: marker {sorted(have)} != tickets citing it {sorted(cites[f])}")
    if table:
        print("| Ticket | Status | Files | Tests | Journeys |\n|---|---|---|---|---|")
        for t in tickets:
            print(f"| {t['id']} {t['title']} | {t['status']} | {len(t['files'])} | {len(t['tests'])} | {', '.join(t['journeys']) or '-'} |")
    for e in errors:
        print("GAP ", e)
    print(f"\n{len(tickets)} tickets, {len(journeys)} journeys, {len(files)} code files · " + ("OK" if not errors else f"{len(errors)} gap(s)"))
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main("--fix" in sys.argv, "--table" in sys.argv))
