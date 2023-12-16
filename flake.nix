{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.11";
    # nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    systems.url = "github:nix-systems/default";
    # flake-utils.url = github:numtide/flake-utils;
    devenv.url = "github:cachix/devenv";
    poetry2nix = {
      url = github:nix-community/poetry2nix;
      inputs = {
        nixpkgs.follows = "nixpkgs";
        # flake-utils.follows = "flake-utils";
      };
    };
  };

  nixConfig = {
    extra-trusted-public-keys = [
      "sciexp.cachix.org-1:HaliIGqJrFN7CDrzYVHqWS4uSISorWAY1bWNmNl8T08="
      "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw="
    ];
    extra-substituters = [
      "https://sciexp.cachix.org"
      "https://devenv.cachix.org"
    ];
  };

  outputs = {
    self,
    nixpkgs,
    devenv,
    systems,
    poetry2nix,
    ...
  } @ inputs: let
    forEachSystem = nixpkgs.lib.genAttrs (import systems);
  in {
    packages = forEachSystem (system: let
      pkgs = import nixpkgs {
        inherit system;
        overlays = [poetry2nix.overlays.default];
      };
    in {
      devenv-up = self.devShells.${system}.default.config.procfileScript;
    });

    devShells =
      forEachSystem
      (system: let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [poetry2nix.overlays.default];
        };

        pyPkgsBuildRequirements = {
          cloudpickle = ["flit-core"];
          feather-format = ["setuptools"];
          flytekit = ["setuptools"];
          flyteidl = ["setuptools"];
          hydra-core = ["setuptools"];
          hydra-joblib-launcher = ["setuptools"];
          hydra-zen = ["setuptools"];
          marshmallow-jsonschema = ["setuptools"];
          xdoctest = ["setuptools"];
        };

        poetry2nixOverrides = pkgs.poetry2nix.overrides.withDefaults (
          self: super: let
            buildInputsOverrides =
              builtins.mapAttrs (
                package: buildRequirements:
                  (builtins.getAttr package super).overridePythonAttrs (old: {
                    buildInputs =
                      (old.buildInputs or [])
                      ++ (builtins.map (pkg:
                        if builtins.isString pkg
                        then builtins.getAttr pkg super
                        else pkg)
                      buildRequirements);
                  })
              )
              pyPkgsBuildRequirements;
          in
            buildInputsOverrides
            // {
              hydra-core = super.hydra-core.override {preferWheel = true;};
              hydra-joblib-launcher = super.hydra-joblib-launcher.override {preferWheel = true;};
              scipy = super.scipy.override {preferWheel = true;};
              yarl = super.yarl.override {preferWheel = true;};
            }
        );

        poetryEnv = pkgs.poetry2nix.mkPoetryEnv {
          projectDir = ./.;
          python = pkgs.python310;
          preferWheels = false;
          editablePackageSources = {
            flytezen = ./src;
          };
          groups = [
            "test"
          ];
          checkGroups = ["test"];
          extras = [];
          overrides = poetry2nixOverrides;
        };
      in {
        default = devenv.lib.mkShell {
          inherit inputs pkgs;
          modules = [
            {
              packages = with pkgs; [
                poetryEnv
                poetry

                atuin
                bat
                gh
                git
                gnumake
                lazygit
                poethepoet
                ripgrep
                starship
                tree
                yq-go
                zsh
              ];

              dotenv = {
                enable = true;
                filename = ".env";
                # disableHint = true;
              };

              pre-commit.hooks = {
                alejandra.enable = true;
                ruff.enable = true;
                # pyright.enable = true;
              };

              difftastic.enable = true;
            }
          ];
        };
      });
  };
}
