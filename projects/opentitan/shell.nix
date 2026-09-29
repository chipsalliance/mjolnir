# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs ? import <nixpkgs> {} }:
let
  openssl-static = pkgs.openssl.override { static = true; };
in
pkgs.mkShell {
  name = "opentitan-shell";
  nativeBuildInputs = with pkgs; [
    bazelisk
    verilator
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
    llvmPackages.llvm.out
    llvmPackages.libclang.lib
    llvmPackages.libcxx
    libusb1
  ];

  PKG_CONFIG_PATH = "${pkgs.udev.dev}/lib/pkgconfig:${pkgs.libftdi1}/lib/pkgconfig:${pkgs.zlib.dev}/lib/pkgconfig:${pkgs.libusb1.dev}/lib/pkgconfig";
  OPENSSL_LIB_DIR = "${openssl-static.out}/lib";
  OPENSSL_INCLUDE_DIR = "${openssl-static.dev}/include";
  LD_LIBRARY_PATH = "${pkgs.ncurses5}/lib";
  CPATH = "${pkgs.zlib.dev}/include:${pkgs.udev.dev}/include:${pkgs.libftdi1}/include:${openssl-static.dev}/include:${pkgs.libusb1.dev}/include";
  LIBRARY_PATH = "${pkgs.zlib}/lib:${pkgs.udev}/lib:${pkgs.libftdi1}/lib:${openssl-static.out}/lib:${pkgs.libusb1}/lib";
  PIP_CONFIG_FILE = "/dev/null";

  shellHook = ''
    export PKG_CONFIG_PATH="${pkgs.udev.dev}/lib/pkgconfig:${pkgs.libftdi1}/lib/pkgconfig:${pkgs.zlib.dev}/lib/pkgconfig:${pkgs.libusb1.dev}/lib/pkgconfig"
    export OPENSSL_LIB_DIR="${openssl-static.out}/lib"
    export OPENSSL_INCLUDE_DIR="${openssl-static.dev}/include"
    export LD_LIBRARY_PATH="${pkgs.ncurses5}/lib''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export CPATH="${pkgs.zlib.dev}/include:${pkgs.udev.dev}/include:${pkgs.libftdi1}/include:${openssl-static.dev}/include:${pkgs.libusb1.dev}/include"
    export LIBRARY_PATH="${pkgs.zlib}/lib:${pkgs.udev}/lib:${pkgs.libftdi1}/lib:${openssl-static.out}/lib:${pkgs.libusb1}/lib"
    export PIP_CONFIG_FILE="/dev/null"

    # Shared Bazel caches
    export SHARED_DISK_CACHE="/tmp/opentitan-bazel-shared-disk"
    export SHARED_REPO_CACHE="/tmp/opentitan-bazel-shared-repo"
    mkdir -p "$SHARED_DISK_CACHE" "$SHARED_REPO_CACHE"

    # If inside an OpenTitan source directory, configure .bazelrc-site and apply idempotent build patches
    if [ -f ".bazelrc" ] && [ -f "third_party/system_libs/extensions.bzl" ]; then
      cat > .bazelrc-site <<EOF
common --repository_cache=$SHARED_REPO_CACHE
build --disk_cache=$SHARED_DISK_CACHE
build --noincompatible_strict_action_env
build --action_env=PATH
build --action_env=PKG_CONFIG_PATH
build --action_env=OPENSSL_LIB_DIR
build --action_env=OPENSSL_INCLUDE_DIR
build --action_env=LD_LIBRARY_PATH
build --action_env=CPATH
build --action_env=LIBRARY_PATH
build --action_env=PIP_CONFIG_FILE
build --host_action_env=PATH
build --host_action_env=PKG_CONFIG_PATH
build --host_action_env=OPENSSL_LIB_DIR
build --host_action_env=OPENSSL_INCLUDE_DIR
build --host_action_env=LD_LIBRARY_PATH
build --host_action_env=CPATH
build --host_action_env=LIBRARY_PATH
build --host_action_env=PIP_CONFIG_FILE
build --sandbox_add_mount_pair=/nix
EOF
    fi

    if [ -f "third_party/system_libs/extensions.bzl" ]; then
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
    fi

    if [ -f "third_party/system_libs/BUILD.libelf.bazel" ]; then
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
    fi

    if [ -d "third_party/rust" ]; then
      ln -sf "${pkgs.llvmPackages.libclang.lib}/lib/libclang.so" "third_party/rust/libclang.so"
      ln -sf "${pkgs.llvmPackages.libcxx.out}/lib/libc++.so" "third_party/rust/libc++.so"
    fi

    if [ -f "third_party/rust/BUILD" ]; then
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
    fi

    if [ -f "hw/BUILD" ]; then
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
    fi

    if [ -f "rules/nonhermetic.bzl" ]; then
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
    fi
  '';
}
