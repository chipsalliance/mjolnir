# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs,
  model,
  googleCloudProject ? null,
  geminiBin ? "${pkgs.gemini-cli}/bin/gemini",
  silentMissing ? false,
  parallel ? 10,
  timeout ? null,
}:
{
  name = "gemini";

  # Batch Mode: Analyzes multiple files in parallel
  run =
    {
      systemPrompt,
      src,
      files,
      output,
    }:
    ''
      echo "Running Gemini backend (${model}) in Batch Mode..."

      # Set PYTHONPATH to backends/ directory so that gemini/gemini.py
      # can import the shared common.py module.
      PYTHONPATH="${../.}" \
      ${pkgs.python3}/bin/python3 ${./gemini.py} \
        --src "${src}" \
        --files "${files}" \
        --output "${output}" \
        --prompt "${systemPrompt}" \
        --model "${model}" \
        --gemini-bin "${geminiBin}" \
        --parallel "''${PARALLEL:-${toString parallel}}" \
        ${if silentMissing then "--silent-missing" else ""} \
        ${if googleCloudProject != null then "--project \"\${GOOGLE_CLOUD_PROJECT:-${googleCloudProject}}\"" else "\${GOOGLE_CLOUD_PROJECT:+--project $GOOGLE_CLOUD_PROJECT}"} \
        ${if timeout != null then "--timeout ${toString timeout}" else ""}
    '';

  # Single-File Mode: Analyzes or processes a single file
  runSingle =
    {
      systemPrompt,
      input,
      output,
    }:
    ''
      echo "Running Gemini backend (${model}) in Single-File Mode..."

      PYTHONPATH="${../.}" \
      ${pkgs.python3}/bin/python3 ${./gemini.py} \
        --input "${input}" \
        --output "${output}" \
        --prompt "${systemPrompt}" \
        --model "${model}" \
        --gemini-bin "${geminiBin}" \
        ${if googleCloudProject != null then "--project \"\${GOOGLE_CLOUD_PROJECT:-${googleCloudProject}}\"" else "\${GOOGLE_CLOUD_PROJECT:+--project $GOOGLE_CLOUD_PROJECT}"} \
        ${if timeout != null then "--timeout ${toString timeout}" else ""}
    '';
}
