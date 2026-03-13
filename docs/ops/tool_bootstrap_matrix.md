# External Tool Bootstrap Matrix

| Tool | Acquisition | Version Strategy | Bootstrap Path | Runtime Check |
|---|---|---|---|---|
| git/gh | nix package / apt in Docker | pinned via flake.lock + base image tag | flake shell + Dockerfile | connector health command probe |
| OpenCode CLI | system command in shell or cloned repo | pin via bootstrap script revision tag | `scripts/bootstrap_tools.sh` | opencode command probe |
| OpenClaw | API contract + optional repo clone | pin via bootstrap script revision tag | `scripts/bootstrap_tools.sh` | signed ingress handshake |
| Graphiti | HTTP endpoint + optional SDK | pinned py dependency and endpoint version | env config + pip deps | HTTP probe |
| OpenAI SDK | pip dependency | pinned version range in pyproject | pip install extras | API key presence + execution path |
| LangSmith SDK | pip dependency | pinned version range in pyproject | pip install extras | API key presence + emission path |
| PlantUML/Node/Java | nix package / apt in Docker | pin through lock/image | flake shell + Dockerfile | command probe |

## Upgrade policy

- Bump one integration at a time.
- Run connector health + smoke tests before merging.
- Record compatibility notes in release docs.
