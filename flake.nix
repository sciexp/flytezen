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
    # nix-snapshotter = {
    #   url = "github:pdtpartners/nix-snapshotter";
    #   inputs.nixpkgs.follows = "nixpkgs";
    # };
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
    # nix-snapshotter,
    ...
  } @ inputs: let
    forEachSystem = nixpkgs.lib.genAttrs (import systems);

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

    makePoetry2nixOverrides = pkgs: pkgs.poetry2nix.overrides.withDefaults (
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

    makePoetryEnv = pkgs: pkgs.poetry2nix.mkPoetryEnv {
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
      overrides = makePoetry2nixOverrides pkgs;
    };

  in {

    # apps = nixpkgs.lib.mkMerge [ pushImages ];

    # apps = forEachSystem (system: let
    #   pkgs = import nixpkgs {
    #     inherit system;
    #     overlays = [poetry2nix.overlays.default nix-snapshotter.overlays.default];
    #   };
    # in {
    #   push-nixcontainertest = {
    #     type = "app";
    #     program = "${self.packages.${system}.nixcontainertest.copyToRegistry {}}/bin/copy-to-registry";
    #   };
    # });

    packages = forEachSystem (system: let
      pkgs = import nixpkgs {
        inherit system;
        overlays = [poetry2nix.overlays.default];
        # overlays = [poetry2nix.overlays.default nix-snapshotter.overlays.default];
      };
    in {
      devenv-up = self.devShells.${system}.default.config.procfileScript;
      # nixcontainertest = pkgs.nix-snapshotter.buildImage {
      #   name = "ghcr.io/sciexp/nixcontainertest";
      #   tag = "latest";
      #   config = {
      #     entrypoint = ["${pkgs.hello}/bin/hello"];
      #   };
      # };
    });

    devShells =
      forEachSystem
      (system: let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [poetry2nix.overlays.default];
        };
      in {
        default = devenv.lib.mkShell {
          inherit inputs pkgs;
          modules = [
            {
              packages = with pkgs; [
                # poetryEnv
                (makePoetryEnv pkgs)
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
                # alejandra.enable = true;
                # ruff.enable = true;
                # pyright.enable = true;
              };

              difftastic.enable = true;
            }
          ];
        };
      });
  };
}
