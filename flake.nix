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
            echo "Loom dev shell ready"
            echo "Try: pip install -e '.[dev,integrations]' && make bootstrap && make run"
            if command -v git >/dev/null 2>&1; then echo "git: ok"; fi
            if command -v gh >/dev/null 2>&1; then echo "gh: ok"; fi
            if command -v node >/dev/null 2>&1; then echo "node: ok"; fi
            if command -v java >/dev/null 2>&1; then echo "java: ok"; fi
          '';
        };
      });
}
