# spec: AS-248
"""What AirStack does not list or publish (config/excluded.json): piracy, adult content, illegal markets, malware. build_directory.py applies
the rules to every Wikidata listing and records the ids it dropped; every builder that publishes research for an id asks here first."""
import json

from . import paths


def display_name(pid, name):
    """The listed name: Wikidata labels that carry vandalism are published under their real name (config/excluded.json)."""
    return paths.config("excluded")["renames"].get(pid, name)


def blocked_ids():
    return set(json.loads(paths.EXCLUDED.read_text())) if paths.EXCLUDED.exists() else set()
