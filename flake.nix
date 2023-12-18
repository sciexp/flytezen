{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.11";
    # nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    systems.url = "github:nix-systems/default";
    flake-parts.url = "github:hercules-ci/flake-parts";
    # flake-utils.url = github:numtide/flake-utils;
    poetry2nix = {
      url = github:nix-community/poetry2nix;
      inputs = {
        nixpkgs.follows = "nixpkgs";
        # flake-utils.follows = "flake-utils";
      };
    };
    nix2container = {
      url = github:nlewo/nix2container;
      inputs = {
        nixpkgs.follows = "nixpkgs";
      };
    };
  };

  nixConfig = {
    extra-trusted-public-keys = [
      "sciexp.cachix.org-1:HaliIGqJrFN7CDrzYVHqWS4uSISorWAY1bWNmNl8T08="
    ];
    extra-substituters = [
      "https://sciexp.cachix.org"
    ];
  };

  outputs = inputs @ {flake-parts, ...}:
    flake-parts.lib.mkFlake {inherit inputs;} {
      systems = import inputs.systems;

      perSystem = {
        self',
        system,
        ...
      }: let
        pkgs = import inputs.nixpkgs {
          inherit system;
          overlays = [inputs.poetry2nix.overlays.default];
        };
        inherit (inputs.nix2container.packages.${system}) nix2container;

        # million thanks to @kolloch for the foldImageLayers function!
        # https://blog.eigenvalue.net/2023-nix2container-everything-once/
        foldImageLayers = let
          mergeToLayer = priorLayers: component:
            assert builtins.isList priorLayers;
            assert builtins.isAttrs component; let
              layer = nix2container.buildLayer (component
                // {
                  layers = priorLayers;
                });
            in
              priorLayers ++ [layer];
        in
          layers: pkgs.lib.foldl mergeToLayer [] layers;

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

        poetryEnvWithSource = pkgs.poetry2nix.mkPoetryEnv {
          projectDir = ./.;
          overrides = poetry2nixOverrides;
          python = pkgs.python310;
          editablePackageSources = {
            flytezen = ./src;
          };
          extraPackages = ps: with pkgs; [python310Packages.pip];
          preferWheels = false;
          groups = [
            "test"
          ];
          checkGroups = ["test"];
          extras = [];
        };

        poetryEnv = pkgs.poetry2nix.mkPoetryEnv {
          projectDir = ./.;
          overrides = poetry2nixOverrides;
          python = pkgs.python310;
          # leave blank to allow for separation of editable package source
          # from dependencies in devcontainer build
          editablePackageSources = {};
          extraPackages = ps: with pkgs; [python310Packages.pip];
          preferWheels = false;
          groups = [
            "test"
          ];
          checkGroups = ["test"];
          extras = [];
        };

        flytezenEditablePackage = pkgs.poetry2nix.mkPoetryEditablePackage {
          projectDir = ./.;
          python = pkgs.python310;
          editablePackageSources = {
            flytezen = ./src;
          };
        };

        devPackages = with pkgs; [
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
      in {
        formatter = pkgs.alejandra;

        devShells = {
          default = pkgs.mkShell {
            name = "flytezen";
            buildInputs = with pkgs;
              [
                poetryEnvWithSource
                # poetryEnv
                # flytezenEditablePackage
              ]
              ++ devPackages;
          };
        };
        packages = {
          devcontainer = nix2container.buildImage {
            name = "flytezendev";
            # prefer default image output hash to manual tag
            # tag = "latest";
            initializeNixDatabase = true;
            copyToRoot = [
              pkgs.dockerTools.fakeNss
              (pkgs.buildEnv {
                name = "root";
                paths = with pkgs; [coreutils nix bashInteractive];
                pathsToLink = "/bin";
              })
            ];
            layers = let
              layerDefs = [
                {
                  deps = with pkgs; [fakeNss coreutils nix bashInteractive];
                }
                {
                  deps = devPackages;
                }
                {
                  deps = with pkgs; [poetryEnvWithSource];
                }
                # {
                #   deps = with pkgs; [poetryEnv];
                # }
                # {
                #   deps = with pkgs; [flytezenEditablePackage];
                # }
              ];
            in
              foldImageLayers layerDefs;
            config = {
              Env = [
                (let
                  path = with pkgs; lib.makeBinPath ([coreutils nix bashInteractive poetryEnv flytezenEditablePackage] ++ devPackages);
                in "PATH=${path}")
                "NIX_PAGER=cat"
                "USER=root"
                "HOME=/"
              ];
              # Use default empty Entrypoint to completely defer to Cmd for flexible override
              Entrypoint = [];
              # but provide default Cmd to start zsh
              Cmd = [
                "${pkgs.bashInteractive}/bin/bash"
                "-c"
                "${pkgs.zsh}/bin/zsh"
              ];
            };
          };
        };
      };
    };
}
