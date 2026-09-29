# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs ? import <nixpkgs> {} }:
pkgs.mkShell {
  name = "openprot-shell";
  nativeBuildInputs = with pkgs; [
    bazelisk
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
    openssl
    zlib
    llvmPackages.libclang.lib
    llvmPackages.libcxx
  ];

  PKG_CONFIG_PATH = "${pkgs.zlib.dev}/lib/pkgconfig:${pkgs.openssl.dev}/lib/pkgconfig";
  OPENSSL_LIB_DIR = "${pkgs.openssl.out}/lib";
  OPENSSL_INCLUDE_DIR = "${pkgs.openssl.dev}/include";
  CPATH = "${pkgs.zlib.dev}/include:${pkgs.openssl.dev}/include";
  LIBRARY_PATH = "${pkgs.zlib}/lib:${pkgs.openssl.out}/lib";
  PIP_CONFIG_FILE = "/dev/null";

  shellHook = ''
    # Shared Bazel caches across isolated PoC worktrees
    export SHARED_DISK_CACHE="/tmp/openprot-bazel-shared-disk"
    export SHARED_REPO_CACHE="/tmp/openprot-bazel-shared-repo"
    mkdir -p "$SHARED_DISK_CACHE" "$SHARED_REPO_CACHE"
  '';
}
