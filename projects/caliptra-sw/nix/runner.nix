{ pkgs, rustToolchain }:

let
  caliptra-runner = pkgs.writeShellApplication {
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
      CODE_DIR="$WORKSPACE_DIR/caliptra-sw"

      # Isolate Cargo target directory
      export CARGO_TARGET_DIR="$WORKSPACE_DIR/target"
      echo "Isolated Cargo target directory to: $CARGO_TARGET_DIR"

      # Assert CODE_DIR exists
      if [ ! -d "$CODE_DIR" ]; then
        echo "Error: Code directory $CODE_DIR does not exist! Checkout must be performed first." >&2
        exit 1
      fi
      echo "Using Caliptra source in $CODE_DIR."

      cd "$CODE_DIR"

      # Default action
      ACTION="build"
      if [ $# -gt 0 ]; then
        ACTION="$1"
        shift
      fi

      case "$ACTION" in
        "build")
          echo "Building Caliptra firmware targets..."
          mkdir -p target
          if [ $# -eq 0 ]; then
            echo "No arguments provided, building default rom-with-log and fw..."
            cargo run -p caliptra-builder --bin image -- --rom-with-log target/rom.bin --fw target/fw.bin
          else
            echo "Passing arguments to caliptra-builder..."
            # shellcheck disable=SC2068
            cargo run -p caliptra-builder --bin image -- "$@"
          fi
          ;;
        "test")
          echo "Running Caliptra tests..."
          # shellcheck disable=SC2068
          cargo test "$@"
          ;;
        "run")
          echo "Preparing default ROM and FW bundle..."
          mkdir -p target
          cargo run -p caliptra-builder --bin image -- --rom-with-log target/rom.bin --fw target/fw.bin
          echo "Running Caliptra firmware emulator..."
          if [ $# -eq 0 ]; then
            echo "No arguments provided, running with default rom.bin..."
            cargo run -p caliptra-emu -- --rom target/rom.bin --pqc-key-type 1
          else
            # shellcheck disable=SC2068
            cargo run -p caliptra-emu -- "$@"
          fi
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
  caliptra-runner
