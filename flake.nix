{
  description = "Loom development shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python312;
      in {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            python
            python.pkgs.pip
            just
            git
            gh
            curl
            jq
            nodejs
            jre
            graphviz
            sqlite
            postgresql
            syft
            docker-compose
            ruff
            mypy
          ];

          shellHook = ''
            # Avoid zsh-style prompt expansions breaking when nix launches bash.
            if [ -n "''${BASH_VERSION:-}" ]; then
              unset PROMPT RPROMPT RPS1
              unset POWERLEVEL9K_CONFIG_FILE POWERLEVEL9K_INSTANT_PROMPT
              unset PROMPT_COMMAND
              export PS1="(loom-nix) \u@\h:\w\$ "
            fi

            export LOOM_ENV=dev
            export LOOM_DATABASE_URL="sqlite:///./loom.db"
            export LOOM_API_AUTH_ENABLED=false
            export LOOM_UI_AUTH_MODE=none
            export LOOM_INTEGRATION_PROFILE=local
            export LOOM_LITELLM_ENABLED=false
            export LOOM_LITELLM_DEFAULT_MODEL="openai/gpt-4.1-mini"
            venv_path="$PWD/.venv"
            recreate_venv=0
            if [ ! -f "$venv_path/bin/activate" ] || [ ! -x "$venv_path/bin/python" ]; then
              recreate_venv=1
            elif ! grep -q "VIRTUAL_ENV=$venv_path" "$venv_path/bin/activate"; then
              # Handle moved/copied repos where activate script points to a different path.
              recreate_venv=1
            fi
            if [ "$recreate_venv" -eq 1 ]; then
              rm -rf "$venv_path"
              python -m venv "$venv_path"
            fi
            . "$venv_path/bin/activate"
            echo "Loom dev shell ready"
            echo "Virtualenv: .venv (activated)"
            echo "Try: pip --python .venv/bin/python install -e '.[dev,integrations]' && just bootstrap && just run"
            if command -v git >/dev/null 2>&1; then echo "git: ok"; fi
            if command -v gh >/dev/null 2>&1; then echo "gh: ok"; fi
            if command -v node >/dev/null 2>&1; then echo "node: ok"; fi
            if command -v java >/dev/null 2>&1; then echo "java: ok"; fi
          '';
        };
      });
}
