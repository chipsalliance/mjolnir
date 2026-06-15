{ pkgs, pkgs-v4 }:

let
  openssl-static = pkgs.openssl.override { static = true; };

  opentitan-runner = pkgs.writeShellApplication {
    name = "runner";
    checkPhase = ""; # Disable shellcheck to ignore SC2016 on python inline scripts
    
    runtimeInputs = with pkgs; [
      bazelisk
      pkgs-v4.verilator
      git
      python3
      gcc
      gnumake
      pkg-config
      binutils
      diffutils
      patch
      rsync
      gnutar
      gzip
      srecord
      udev
      libftdi1
      openssl-static
      ncurses5
      zlib
      llvmPackages.libclang.lib
      llvmPackages.libcxx
      libusb1
    ];

    text = ''
      # Enable pipefail and exit on error
      set -euo pipefail

      # Isolate pip
      export PIP_CONFIG_FILE=/dev/null
      echo "Isolated pip from host configuration (PIP_CONFIG_FILE=/dev/null)"

      # Set PKG_CONFIG_PATH
      export PKG_CONFIG_PATH="${pkgs.udev.dev}/lib/pkgconfig:${pkgs.libftdi1}/lib/pkgconfig:${pkgs.zlib.dev}/lib/pkgconfig:${pkgs.libusb1.dev}/lib/pkgconfig"
      echo "Set PKG_CONFIG_PATH=$PKG_CONFIG_PATH"

      # Set OpenSSL env
      export OPENSSL_LIB_DIR="${openssl-static.out}/lib"
      export OPENSSL_INCLUDE_DIR="${openssl-static.dev}/include"
      echo "Set OPENSSL_LIB_DIR=$OPENSSL_LIB_DIR"
      echo "Set OPENSSL_INCLUDE_DIR=$OPENSSL_INCLUDE_DIR"

      # Expose ncurses5 for libclang
      export LD_LIBRARY_PATH="${pkgs.ncurses5}/lib"
      echo "Set LD_LIBRARY_PATH=$LD_LIBRARY_PATH"

      # Expose CPATH and LIBRARY_PATH
      export CPATH="${pkgs.zlib.dev}/include:${pkgs.udev.dev}/include:${pkgs.libftdi1}/include:${openssl-static.dev}/include:${pkgs.libusb1.dev}/include"
      export LIBRARY_PATH="${pkgs.zlib}/lib:${pkgs.udev}/lib:${pkgs.libftdi1}/lib:${openssl-static.out}/lib:${pkgs.libusb1}/lib"
      echo "Set CPATH=$CPATH"
      echo "Set LIBRARY_PATH=$LIBRARY_PATH"

      echo "========================================================"
      echo " OpenTitan Nix Runner (Static)"
      echo " Verilator version: $(verilator --version)"
      echo " Bazel version: $(bazel --version 2>/dev/null || echo 'managed by bazelisk')"
      echo "========================================================"

      # Establish workspace directory
      if [ -n "''${MJOLNIR_WORKSPACE:-}" ]; then
        echo "Running in Mjolnir isolated workspace: $MJOLNIR_WORKSPACE"
        WORKSPACE_DIR="$MJOLNIR_WORKSPACE"
      else
        echo "Running in local development mode at ./workspace"
        WORKSPACE_DIR="workspace"
      fi
      
      WORKSPACE_DIR=$(readlink -f "$WORKSPACE_DIR")
      CODE_DIR="$WORKSPACE_DIR/opentitan"
      BAZEL_OUT_BASE="$WORKSPACE_DIR/bazel-out-base"

      # Setup shared cache
      SHARED_DISK_CACHE="/tmp/opentitan-bazel-shared-disk"
      SHARED_REPO_CACHE="/tmp/opentitan-bazel-shared-repo"
      mkdir -p "$SHARED_DISK_CACHE" "$SHARED_REPO_CACHE"
      echo "Using shared Bazel disk cache: $SHARED_DISK_CACHE"
      echo "Using shared Bazel repo cache: $SHARED_REPO_CACHE"

      # Assert CODE_DIR exists (Checkout must be done beforehand by the job wrapper)
      if [ ! -d "$CODE_DIR" ]; then
        echo "Error: Code directory $CODE_DIR does not exist! Checkout must be performed first." >&2
        exit 1
      fi
      echo "Using OpenTitan source in $CODE_DIR."

      # Initialize git if missing (required by Bazel workspace status script)
      if [ ! -d "$CODE_DIR/.git" ]; then
        echo "Initializing dummy git repository in $CODE_DIR..."
        cd "$CODE_DIR"
        git init
        git config user.name "Nix Builder"
        git config user.email "nix@builder.local"
        git add -A
        git commit -m "Mock commit for Nix Bazel workspace status"
        cd -
      fi

      cd "$CODE_DIR"

      # Patching scripts (Idempotent)
      echo "Patching third_party/system_libs/extensions.bzl..."
      python3 -c '
path = "third_party/system_libs/extensions.bzl"
with open(path, "r") as f:
    content = f.read()
target = "url = \"https://sourceware.org/elfutils/ftp/0.193/elfutils-0.193.tar.bz2\","
replacement = """urls = [
            "https://tarballs.nixos.org/sha256/7857f44b624f4d8d421df851aaae7b1402cfe6bcdd2d8049f15fc07d3dde7635",
            "https://mirror.bazel.build/sourceware.org/elfutils/ftp/0.193/elfutils-0.193.tar.bz2",
            "https://sourceware.org/elfutils/ftp/0.193/elfutils-0.193.tar.bz2",
        ],
        type = "tar.bz2","""
if target in content:
    content = content.replace(target, replacement)
    with open(path, "w") as f:
        f.write(content)
'

      echo "Patching third_party/system_libs/BUILD.libelf.bazel..."
      python3 -c '
path = "third_party/system_libs/BUILD.libelf.bazel"
with open(path, "r") as f:
    content = f.read()
target = """configure_make(
    name = "libelf",
    args = ["-j"],
    configure_in_place = True,
    lib_source = ":all_srcs",
    out_static_libs = ["libelf.a"],
)"""
replacement = """configure_make(
    name = "libelf",
    args = ["-j"],
    configure_in_place = True,
    configure_options = [
        "CFLAGS=-I${pkgs.zlib.dev}/include",
        "LDFLAGS=-L${pkgs.zlib}/lib",
        "CXX=g++",
    ],
    lib_source = ":all_srcs",
    out_static_libs = ["libelf.a"],
)"""
if target in content:
    content = content.replace(target, replacement)
    with open(path, "w") as f:
        f.write(content)
'

      echo "Creating symlinks for Nix native libclang and libc++..."
      ln -sf "${pkgs.llvmPackages.libclang.lib}/lib/libclang.so" "third_party/rust/libclang.so"
      ln -sf "${pkgs.llvmPackages.libcxx.out}/lib/libc++.so" "third_party/rust/libc++.so"

      echo "Patching third_party/rust/BUILD..."
      python3 -c '
path = "third_party/rust/BUILD"
with open(path, "r") as f:
    content = f.read()
target_libclang = "shared_library = \"@llvm_toolchain_llvm//:lib/libclang.so\","
repl_libclang = "shared_library = \":libclang.so\","
target_libcxx = "shared_library = \"@llvm_toolchain_llvm//:lib/libc++.so\","
repl_libcxx = "shared_library = \":libc++.so\","
patched = False
if target_libclang in content:
    content = content.replace(target_libclang, repl_libclang)
    patched = True
if target_libcxx in content:
    content = content.replace(target_libcxx, repl_libcxx)
    patched = True
if patched:
    with open(path, "w") as f:
        f.write(content)
'

      echo "Patching hw/BUILD..."
      python3 -c '
path = "hw/BUILD"
with open(path, "r") as f:
    content = f.read()
target = "\"LDFLAGS_FOR_BUILD\": \"-static ../../../../../../$(location @libelf//:gen_dir)/lib/libelf.a\","
replacement = "\"LDFLAGS_FOR_BUILD\": \"-static -L../../../../../../$(location @libelf//:gen_dir)/lib\","
if target in content:
    content = content.replace(target, replacement)
    with open(path, "w") as f:
        f.write(content)
'

      echo "Patching rules/nonhermetic.bzl..."
      python3 -c '
path = "rules/nonhermetic.bzl"
with open(path, "r") as f:
    content = f.read()
target = "environ = NONHERMETIC_ENV_VARS,"
replacement = "environ = NONHERMETIC_ENV_VARS + [\"PATH\"],"
if target in content:
    content = content.replace(target, replacement)
    with open(path, "w") as f:
        f.write(content)
'

      # Default action and target
      ACTION="test"
      TARGET="//sw/device/tests:uart_smoketest_sim_verilator"

      if [ $# -gt 0 ]; then
        ACTION="$1"
        shift
      fi

      if [ $# -gt 0 ]; then
        TARGET="$1"
        shift
      fi

      echo "Running Bazel $ACTION $TARGET with remaining args: $*"

      # shellcheck disable=SC2068
      bazel --output_base="$BAZEL_OUT_BASE" "$ACTION" \
        --disk_cache="$SHARED_DISK_CACHE" \
        --repository_cache="$SHARED_REPO_CACHE" \
        --noincompatible_strict_action_env \
        --action_env=PATH \
        --action_env=PKG_CONFIG_PATH \
        --action_env=OPENSSL_LIB_DIR \
        --action_env=OPENSSL_INCLUDE_DIR \
        --action_env=LD_LIBRARY_PATH \
        --action_env=CPATH \
        --action_env=LIBRARY_PATH \
        --sandbox_add_mount_pair=/nix \
        "$@" \
        "$TARGET"
    '';
  };
in
  opentitan-runner
