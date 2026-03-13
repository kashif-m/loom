# Toolchain Conformance Checks

## flake shell
- enter shell with `nix develop`
- run `./scripts/verify_connectors.sh`

## docker local stack
- run `docker compose -f deploy/docker-compose.local.yml --profile minimal up --build`
- verify `/health` and `/ui`

## bootstrap scripts
- run `./scripts/bootstrap_local_stack.sh`
- ensure idempotent reruns do not fail
