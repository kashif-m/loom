{
  description = "Loom MVP - Virtual organisation orchestration system";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    process-compose-flake.url = "github:Platonic-Systems/process-compose-flake";
    services-flake.url = "github:juspay/services-flake";
  };

  outputs = inputs: inputs.flake-parts.lib.mkFlake { inherit inputs; } {
    systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

    # Import the process-compose-flake module
    imports = [
      inputs.process-compose-flake.flakeModule
    ];

    perSystem = { config, self', inputs', pkgs, system, lib, ... }:
      let
        python = pkgs.python311;
        node = pkgs.nodejs_20;
      in
      {
        # Define development shell
        devShells.default = pkgs.mkShell {
          name = "loom-mvp-dev";

          packages = with pkgs; [
            python
            uv
            ruff
            pyright
            node
            nodePackages.pnpm
            postgresql_16
            curl
            git
            gnumake
            jq
          ];

          shellHook = ''
            echo ""
            echo "╔══════════════════════════════════════════════════════╗"
            echo "║            Loom MVP dev environment ready            ║"
            echo "╚══════════════════════════════════════════════════════╝"

            if [ ! -d ".venv" ]; then
              echo "→ Creating Python venv with uv..."
              uv venv --python ${python}/bin/python3.11
            fi

            source .venv/bin/activate
            echo "→ Python venv activated: $(which python)"

            if [ -f "pyproject.toml" ]; then
              echo "→ Syncing Python dependencies..."
              uv sync --quiet
            fi

            if [ -f "ui/package.json" ] && [ ! -d "ui/node_modules" ]; then
              echo "→ Installing Node dependencies..."
              (cd ui && pnpm install --silent)
            fi

            if [ ! -f ".env" ] && [ -f ".env.example" ]; then
              cp .env.example .env
              echo "→ Created .env from .env.example"
            fi

            echo ""
            echo "🔧 Service Management:"
            echo ""
            echo "  nix run .#ext-services  — start PostgreSQL"
            echo ""
            echo "  Services will be available at:"
            echo "    PostgreSQL: localhost:5432"
            echo "      Database: loom"
            echo "      Username: loom"
            echo "      Password: loom"
            echo ""

            alias services="nix run .#ext-services"
            alias migrate="uv run python -c 'from src.core.task_store.operations import TaskStore; import asyncio; asyncio.run(TaskStore().init_db())'"
            alias test="uv run pytest tests/ -v"
            alias test-unit="uv run pytest tests/unit/ -v"
            alias test-integration="uv run pytest tests/integration/ -v"
            alias lint="ruff check src/ && ruff format --check src/"
            alias fmt="ruff format src/ && ruff check --fix src/"
            alias typecheck="pyright src/"
            alias api="uv run uvicorn src.api.gateway:app --reload --port 8000"
            alias ui-dev="cd ui && pnpm dev"

            echo "Development commands:"
            echo "  api            — start FastAPI dev server (:8000)"
            echo "  ui-dev         — start Next.js dev server (:3000)"
            echo "  migrate        — initialize SQLite database"
            echo "  test           — run all tests"
            echo "  lint           — check code style"
            echo "  fmt            — auto-format code"
            echo ""
            echo "⚠️  Required External Services:"
            echo ""
            echo "  1. PostgreSQL (start with: nix run .#ext-services)"
            echo ""
            echo "  2. LiteLLM Proxy (start manually):"
            echo "     litellm --model anthropic/claude-3-5-sonnet-20241022 --port 4000"
            echo ""
            echo "  3. Graphiti (optional, for memory):"
            echo "     (Python library already installed via uv sync)"
            echo ""
          '';

          UV_PYTHON = "${python}/bin/python3.11";
          UV_SYSTEM_PYTHON = "0";
        };

        # Define external services using process-compose and services-flake
        process-compose.ext-services = {
          imports = [ inputs.services-flake.processComposeModules.default ];

          services.postgres."loom-db" = {
            enable = true;
            initialScript = {
              before = ''
                CREATE USER loom WITH PASSWORD 'loom' SUPERUSER CREATEDB CREATEROLE INHERIT LOGIN;
              '';
              after = ''
                GRANT ALL PRIVILEGES ON DATABASE loom TO loom;
                GRANT ALL PRIVILEGES ON DATABASE graphiti TO loom;
              '';
            };
            initialDatabases = [
              { name = "loom"; }
              { name = "graphiti"; }
            ];
          };
        };
      };
  };
}
