# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
let
  # Generate a minimal, immutable git repository locally in the Nix store
  dummyRepo = pkgs.runCommand "dummy-git-repo" { buildInputs = [ pkgs.git ]; } ''
    mkdir -p $out
    cd $out
    git init --initial-branch=main
    git config user.name "Test Automaton"
    git config user.email "test@localhost"
    
    mkdir -p api/src
    echo '// Dummy target for postprocessing resilience evaluation' > api/src/lib.rs
    
    git add .
    git commit -m "init"
  '';
in
import ../default_job.nix { inherit pkgs; } {
  name = "Malformed Postprocessing Handling Test";
  workspaceDir = "/tmp/postprocessing-test-workspace";
  outputDir = "./postprocessing-test-output";
  backend = "gemini"; 

  contextFile = null;
  agentDir = ../../agents/postprocessing_test;

  target = {
    # Point the git target directly to our local Nix store derivation
    repoUrl = "file://${dummyRepo}";
    repoName = "dummy-sw";
    commit = "main";
    fileCommand = "echo 'api/src/lib.rs'"; 
  };

  postExtract = ''
    echo "Running AI with instructions to generate malformed output..."
  '';
}
