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

        mkPoetryEnvAttrs = {
          projectDir = ./.;
          overrides = poetry2nixOverrides;
          python = pkgs.python310;
          extraPackages = ps: with pkgs; [python310Packages.pip];
          preferWheels = false;
          groups = [
            "test"
          ];
          checkGroups = ["test"];
          extras = [];
        };

        poetryEnv = pkgs.poetry2nix.mkPoetryEnv (
          mkPoetryEnvAttrs
        );

        mkPoetryEnvWithSource = src: pkgs.poetry2nix.mkPoetryEnv (
          mkPoetryEnvAttrs // {
            editablePackageSources = {
              flytezen = src;
            };
          }
        );

        sysPackages = with pkgs; [
          fakeNss
          bashInteractive
          coreutils
          cacert
          nix
          direnv
        ];

        mkRootNss = pkgs.runCommand "mkRootNss" {} ''
          mkdir -p $out/etc

          cat > $out/etc/passwd <<EOF
          root:x:0:0:root user:/var/empty:/bin/sh
          nobody:x:65534:65534:nobody:/var/empty:/bin/sh
          EOF

          cat > $out/etc/group <<EOF
          root:x:0:root
          nobody:x:65534:
          nixbld:x:30000:nobody
          EOF

          echo "hosts: files dns" > $out/etc/nsswitch.conf

          mkdir -p $out/tmp
          mkdir -p $out/root
        '';

        rcRoot = pkgs.runCommand "rcRoot" {} ''
          mkdir -p $out/root

          cat > $out/root/.zshrc <<EOF
          eval "\$(direnv hook zsh)"
          eval "\$(starship init zsh)"
          eval "\$(atuin init zsh)"
          EOF
        '';

        devPackages = with pkgs; [
          poetry
          neovim
          atuin
          bat
          gh
          git
          gnumake
          lazygit
          man-db
          man-pages
          poethepoet
          ripgrep
          starship
          tree
          yq-go
          zsh
        ];

        packageGitRepo = builtins.fetchGit {
          url = "https://github.com/sciexp/flytezen.git";
          # the ref is not strictly required when specifying a rev
          # but it should be included whenever possible
          # ref = "main";
          ref = "20-nixci";
          # the rev can be omitted transiently in development 
          # to track the HEAD of a ref but doing so requires 
          # `--impure` image builds
          rev = "fc833e1b08364b268f2a857330009b899dcbab2f";
        };

        packageGitRepoInContainer = pkgs.runCommand "copy-package-git-repo" {} ''
          mkdir -p $out/root
          cp -r ${packageGitRepo} $out/root/flytezen
        '';

        pythonPackages = [
          (mkPoetryEnvWithSource /root/flytezen/src)
        ];
      in {
        formatter = pkgs.alejandra;

        devShells = {
          default = pkgs.mkShell {
            name = "flytezen";
            buildInputs = with pkgs;
              [
                (mkPoetryEnvWithSource ./src)
              ]
              ++ devPackages;
          };
        };
        packages = {
          devcontainer = nix2container.buildImage {
            name = "flytezendev";
            # generally prefer the default image hash to manual tagging
            # tag = "latest";
            initializeNixDatabase = true;
            copyToRoot = [
              # similar to pkgs.fakeNss
              mkRootNss
              (pkgs.buildEnv {
                name = "root";
                paths = sysPackages;
                pathsToLink = "/bin";
              })
              rcRoot
              packageGitRepoInContainer
            ];
            # Setting maxLayers <=127 
            # maxLayers = 123;
            # can be used instead of the manual layer specification below
            layers = let
              layerDefs = [
                {
                  deps = sysPackages;
                }
                {
                  deps = devPackages;
                }
                {
                  deps = pythonPackages;
                }
              ];
            in
              foldImageLayers layerDefs;
            config = {
              Env = [
                (let
                  path = with pkgs; lib.makeBinPath (sysPackages ++ devPackages ++ pythonPackages);
                in "PATH=${path}")
                "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
                "NIX_PAGER=cat"
                "USER=root"
                "HOME=/root"
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
