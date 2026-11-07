# Maintainer boundary

Provider and production account configuration belongs in the private operator record.

## Money and access

- Live research is off unless a person explicitly authorizes one bounded run.
- Scheduled refresh performs free, local work only. It never pulls code, spends, pushes, or deploys.
- Visitors never reach research, crawling, or model code.

## Release

1. Start from reviewed source and a clean tree.
2. Run the complete tests, secret scan, data validator, and clean-checkout review.
3. Confirm only the declared public-data allowlist is assembled.
4. Deploy the tested commit and verify its commit and manifest hashes.
5. Keep generated data, databases, saved responses, ledgers, logs, screenshots, and provider records outside Git.

The repository is the public code record. Private operating evidence is not a release artifact.
