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
    flocken = {
      url = "github:mirkolenz/flocken/v2";
      inputs.nixpkgs.follows = "nixpkgs";
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

  outputs = inputs @ {
    self,
    flake-parts,
    ...
  }:
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
            conditionalOverrides =
              if pkgs.stdenv.isDarwin
              then {
                grpcio = super.grpcio.override {preferWheel = false;};
              }
              else {};
          in
            buildInputsOverrides
            // {
              hydra-core = super.hydra-core.override {preferWheel = true;};
              hydra-joblib-launcher = super.hydra-joblib-launcher.override {preferWheel = true;};
              mkdocs-material = super.mkdocs-material.override {preferWheel = false;};
              scipy = super.scipy.override {preferWheel = true;};
              yarl = super.yarl.override {preferWheel = true;};
            }
            // conditionalOverrides
        );

        mkPoetryAttrs = {
          projectDir = ./.;
          overrides = poetry2nixOverrides;
          python = pkgs.python310;
          # aarch64 cross-compilation on x86_64 may be intolerably slow if
          # preferWheels is disabled. If all of the individual contributors to
          # this are identified, it may be possible to use the library-specific
          # overrides above and disable the global usage of wheels
          preferWheels = true;
          groups = [
            "test"
          ];
          checkGroups = ["test"];
          extras = [];
        };

        poetryEnv = pkgs.poetry2nix.mkPoetryEnv (
          mkPoetryAttrs
          // {
            extraPackages = ps:
              with pkgs; [
                python310Packages.pip
              ];
          }
        );

        gitHubOrg = "sciexp";
        packageName = "flytezen";
        packageSrcPath = "/root/${packageName}/src";

        mkPoetryEnvWithSource = packageName: src:
          pkgs.poetry2nix.mkPoetryEnv (
            mkPoetryAttrs
            // {
              groups = ["test" "docs"];
              extraPackages = ps:
                with pkgs; [
                  python310Packages.pip
                ];
              editablePackageSources = {
                ${packageName} = src;
              };
            }
          );

        sysPackages = with pkgs;
          [
            bashInteractive
            coreutils
            cacert
            gnutar
            gzip
            nix
            direnv
          ]
          ++ lib.optional (lib.elem system pkgs.shadow.meta.platforms) shadow;

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

        customNixConf = pkgs.runCommand "custom-nix-conf" {} ''
          mkdir -p $out/etc/nix
          cat > $out/etc/nix/nix.conf <<EOF
          build-users-group = nixbld
          experimental-features = nix-command flakes repl-flake
          bash-prompt-prefix = (nix:\$name)\040
          max-jobs = auto
          extra-nix-path = nixpkgs=flake:nixpkgs
          trusted-users = root
          EOF
        '';

        devPackages = with pkgs; [
          atuin
          bat
          gawk
          gh
          git
          gnugrep
          gnumake
          lazygit
          man-db
          man-pages
          neovim
          poetry
          poethepoet
          ripgrep
          starship
          tree
          yq-go
          zsh
        ];

        # The local path can be used instead of `builtins.fetchGit` applied to
        # the repository source url to be used in `packageGitRepoToContainer` to
        # place a copy of the local source in the devcontainer if it does not
        # exist on a ref+rev:
        # packageGitRepo = ./.;
        # OR
        # packageGitRepo = builtins.fetchGit ./.;
        # should also work as an alternative to directly copying the local repo
        # path, see https://github.com/NixOS/nix/pull/7706/files; however, the
        # explicit ref+rev should likely be preferred outside of development
        # experimentation
        packageGitRepo = builtins.fetchGit {
          name = "${packageName}-source";
          url = "https://github.com/${gitHubOrg}/${packageName}.git";
          # the ref is not strictly required when specifying a rev but it should
          # be included whenever possible or it may be necessary to include
          ref = "main";
          # allRefs = true;
          # ref = "NN-feature";
          # the rev can be omitted transiently in development to track the HEAD
          # of a ref but doing so requires `--impure` image builds (this may
          # already be required for other reasons, e.g. `builtins.getEnv`)
          # rev = "b69ef531088f7a244104bc34f919619f15a8aa8d";
        };

        # The `chmod -R` command to make the root user's home directory writable
        # is only necessary to allow overwriting the source in the devcontainer
        # without rebuilding the image. Since it violates the intended
        # immutability of the image, it can be disabled in release images or
        # when image rebuilds are used to update the source during development.
        packageGitRepoToContainer = pkgs.runCommand "copy-package-git-repo" {} ''
          mkdir -p $out/root
          cp -r ${packageGitRepo} $out/root/${packageName}

          chmod -R 755 $out/root
        '';

        pythonPackages = [
          (mkPoetryEnvWithSource packageName packageSrcPath)
        ];

        devcontainerLayers = let
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

        devcontainerContents = [
          # similar to pkgs.fakeNss
          mkRootNss
          (pkgs.buildEnv {
            name = "root";
            paths = sysPackages;
            pathsToLink = "/bin";
          })
          customNixConf
          rcRoot
          packageGitRepoToContainer
        ];

        devcontainerConfig = {
          # Use default empty Entrypoint to completely defer to Cmd for flexible override
          Entrypoint = [];
          # but provide default Cmd to start zsh
          Cmd = [
            "${pkgs.bashInteractive}/bin/bash"
            "-c"
            "${pkgs.zsh}/bin/zsh"
          ];
          User = "root";
          WorkingDir = "/root";
          Env = [
            "PATH=${pkgs.lib.makeBinPath (sysPackages ++ devPackages ++ pythonPackages)}:/root/.nix-profile/bin"
            "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
            "NIX_PAGER=cat"
            "USER=root"
            "HOME=/root"
            "GIT_REPO_NAME=${builtins.getEnv "GIT_REPO_NAME"}"
            "GIT_REF=${builtins.getEnv "GIT_REF"}"
            "GIT_SHA=${builtins.getEnv "GIT_SHA"}"
            "GIT_SHA_SHORT=${builtins.getEnv "GIT_SHA_SHORT"}"
            "PYTHONPATH=${packageSrcPath}:${pkgs.lib.strings.makeSearchPathOutput "" "lib/python3.10/site-packages" pythonPackages}"
          ];
        };
      in {
        formatter = pkgs.alejandra;

        devShells = {
          default = pkgs.mkShell {
            name = packageName;
            buildInputs = with pkgs;
              [
                (mkPoetryEnvWithSource packageName ./src)
              ]
              ++ devPackages;
          };
        };

        packages = {
          default = pkgs.poetry2nix.mkPoetryApplication (
            mkPoetryAttrs
            // {
              checkPhase = ''
                pytest
              '';
            }
          );

          releaseEnv = pkgs.buildEnv {
            name = "release-env";
            paths = with pkgs; [poetry python310];
          };

          # Very similar devcontainer images can be constructed with either
          # nix2container or dockerTools
          devcontainerNix2Container = nix2container.buildImage {
            name = "${packageName}nixdev";
            # generally prefer the default image hash to manual tagging
            # tag = "latest";
            initializeNixDatabase = true;

            # Setting maxLayers <=127
            # maxLayers = 123;
            # can be used instead of the manual layer specification below
            layers = devcontainerLayers;

            copyToRoot = devcontainerContents;
            config = devcontainerConfig;
          };

          # Very similar devcontainer images can be constructed with either
          # nix2container or dockerTools
          devcontainerDockerTools = pkgs.dockerTools.buildLayeredImage {
            name = "${packageName}dev";
            # with mkDockerManifest, tags may be automatically generated from
            # git metadata
            tag = "latest";
            created = "now";

            # maxLayers <=127; defaults to 100
            maxLayers = 123;

            contents = devcontainerContents;
            config = devcontainerConfig;
          };
        };

        legacyPackages.devcontainerManifest = let
          includedSystems = let
            envVar = builtins.getEnv "NIX_IMAGE_SYSTEMS";
          in
            if envVar == ""
            then ["x86_64-linux" "aarch64-linux"]
            else builtins.filter (sys: sys != "") (builtins.split " " envVar);
        in
          inputs.flocken.legacyPackages.${system}.mkDockerManifest {
            github = {
              enable = true;
              enableRegistry = false;
              token = builtins.getEnv "GH_TOKEN";
            };
            autoTags = {
              branch = false;
            };
            registries = {
              "ghcr.io" = {
                enable = true;
                repo = "${gitHubOrg}/${packageName}dev";
                username = builtins.getEnv "GITHUB_ACTOR";
                password = builtins.getEnv "GH_TOKEN";
              };
            };
            version = builtins.getEnv "VERSION";
            # aarch64-linux may be disabled for more rapid image builds during
            # development. Note the usage of `preferWheels` above as well.
            # images = with self.packages; [x86_64-linux.devcontainerDockerTools aarch64-linux.devcontainerDockerTools];
            # images = with self.packages; [x86_64-linux.devcontainerDockerTools];
            images = builtins.map (sys: self.packages.${sys}.devcontainerDockerTools) includedSystems;
            tags = [(builtins.getEnv "GIT_SHA_SHORT") (builtins.getEnv "GIT_SHA") (builtins.getEnv "GIT_REF")];
          };
      };
    };
}
