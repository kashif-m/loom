# Local Troubleshooting Guide

## App doesn't start
- verify python dependencies: `pip install -e '.[dev,integrations]'`
- verify DB path: `echo $LOOM_DATABASE_URL`
- run `python3 -m loom.app.main --health`

## GUI actions fail with 403
- if `LOOM_UI_AUTH_MODE=token`, fetch CSRF first via `/api/auth/csrf`
- verify bearer token and role permissions
- in local mode set `LOOM_UI_AUTH_MODE=none`

## Missing connector tools
- run `./scripts/verify_connectors.sh`
- use `nix develop` or Docker image to get full toolchain

## Integration checks fail
- open GUI and inspect `Integration Status` and `Integrations Health`
- verify required env vars for enabled integrations

## Workflow publish fails
- use `Validate` button first in GUI
- check required sections in markdown template
