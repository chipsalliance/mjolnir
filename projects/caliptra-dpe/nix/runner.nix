# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs, rustToolchain }:

let
  dpe-runner = pkgs.writeShellApplication {
    name = "runner";
    
    runtimeInputs = [
      rustToolchain
      pkgs.git
      pkgs.pkg-config
      pkgs.openssl
      pkgs.libusb1
      pkgs.gcc
    ];

    text = ''
      # Enable pipefail and exit on error
      set -euo pipefail

      if [ -n "''${MJOLNIR_WORKSPACE:-}" ]; then
        echo "Running in Mjolnir isolated workspace: $MJOLNIR_WORKSPACE"
        WORKSPACE_DIR="$MJOLNIR_WORKSPACE"
      else
        echo "Running in local development mode at ./workspace"
        WORKSPACE_DIR="workspace"
      fi
      
      WORKSPACE_DIR=$(readlink -f "$WORKSPACE_DIR")
      CODE_DIR="$WORKSPACE_DIR/caliptra-dpe"

      export CARGO_TARGET_DIR="$WORKSPACE_DIR/target"
      echo "Isolated Cargo target directory to: $CARGO_TARGET_DIR"

      # Assert CODE_DIR exists
      if [ ! -d "$CODE_DIR" ]; then
        echo "Error: Code directory $CODE_DIR does not exist! Checkout must be performed first." >&2
        exit 1
      fi
      echo "Using Caliptra DPE source in $CODE_DIR."

      cd "$CODE_DIR"

      ACTION="build"
      if [ $# -gt 0 ]; then
        ACTION="$1"
        shift
      fi

      case "$ACTION" in
        "build")
          echo "Building DPE..."
          # shellcheck disable=SC2068
          cargo build "$@"
          ;;
        "test")
          echo "Running DPE tests..."
          # shellcheck disable=SC2068
          cargo test "$@"
          ;;
        *)
          echo "Executing: cargo $ACTION $*"
          # shellcheck disable=SC2068
          cargo "$ACTION" "$@"
          ;;
      esac
    '';
  };
in
  dpe-runner
