# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs,
  agentDir,
  backendName,
  contextFile ? null,
}:

let
  manifestPath = "${agentDir}/manifest.json";
  manifest = builtins.fromJSON (builtins.readFile manifestPath);

  promptPath = "${agentDir}/prompt.txt";
  basePrompt = builtins.readFile promptPath;
  context = if contextFile != null then builtins.readFile contextFile else "";
  systemPromptContent = basePrompt + "\n\n" + context;

  isSupported = builtins.elem backendName manifest.supported_backends;

  systemPromptFile = pkgs.writeText "system-prompt" systemPromptContent;
in
{
  backendArgs = {
    systemPrompt = if isSupported
      then systemPromptFile
      else builtins.trace "Warning: Backend ${backendName} is not listed as supported for agent ${manifest.name}" systemPromptFile;
  };
}

