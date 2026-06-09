# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
{
  name,
  workspaceDir,
  outputDir,
  repoName,
  repoUrl,
  commit,
  fileCommand ? "${pkgs.fd}/bin/fd -t f -e rs",
  postExtractExtra ? "",
  contextFile ? null,
  backend ? null,
  model ? "gemini-3.5-flash",
}:
import ../../../nix/orchestration/default_job.nix { inherit pkgs; } {
  inherit name workspaceDir outputDir backend model contextFile;
  agentDir = ../../../agents/rust_auditor;

  target = {
    inherit repoName repoUrl commit fileCommand;
  };

  postExtract = ''
    echo "${name}: Deleting non-Rust files..."
    cd "$CODE_DIR" && ${pkgs.fd}/bin/fd -t f -H -I -E '*.rs' -x rm {}
    ${postExtractExtra}
  '';
}
