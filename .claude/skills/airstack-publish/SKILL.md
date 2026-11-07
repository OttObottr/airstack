---
name: airstack-publish
description: Use when asked to open-source AirStack or make a repository public. Covers what is safe, what is not, and the exact procedure. Never make anything public without the owner's explicit go-ahead.
---
# Publish

Making a repository public is outward-facing and hard to reverse: **ask first, every time**, and name the license and its copyright holder.

1. Standard tools only: `gitleaks git . --redact` over the full history (and the pre-commit hook and CI job already enforce it); GitHub secret scanning and push protection are repository settings for the owner.
2. The public repository is the working repository (`origin`); the private one is an archive whose history is never pushed. Every commit goes live, so run the pre-commit hook and read the CI secrets job. To publish something new elsewhere, use a NEW repository with one clean commit, never the old history.
3. Needs a decision, not code: the license and holder (add `LICENSE`), the hackathon's and Meta's terms for model output and credits, whether personal names stay in docs, and the data license for the published facts.
4. Never include `.env`, `.wrangler/`, the account ledger, raw vendor pages, or a screenshot showing a key or a private path.
See the Publishing section of `docs/OWNER.md`.
