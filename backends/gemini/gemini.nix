# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs,
  silentMissing ? false,
}:
{
  name = "gemini";

  # Batch Mode: Analyzes multiple files in parallel
  runBatchAuditor =
    {
      systemPrompt,
      src,
      files,
      output,
    }:
    ''
      echo "Running Gemini backend ($MJOLNIR_MODEL) in Batch Mode..."

      # Set PYTHONPATH to backends/ directory so that gemini/gemini.py
      # can import the shared common.py module.
      # Still export GOOGLE_APPLICATION_CREDENTIALS so Google Auth library
      # can locate the ADC JSON file.
      PYTHONPATH="${../.}" \
      ${pkgs.python3}/bin/python3 ${./gemini.py} \
        --src "${src}" \
        --files "${files}" \
        --output "${output}" \
        --prompt "${systemPrompt}" \
        --model "$MJOLNIR_MODEL" \
        --parallel "$MJOLNIR_PARALLEL" \
        --api-key "$GEMINI_API_KEY" \
        --project "$GOOGLE_CLOUD_PROJECT" \
        --location "$GOOGLE_CLOUD_LOCATION" \
        ${if silentMissing then "--silent-missing" else ""}
    '';

  # Single-File Mode: Analyzes or processes a single file
  runAdversarialReviewer =
    {
      systemPrompt,
      input,
      output,
    }:
    ''
      echo "Running Gemini backend ($MJOLNIR_MODEL) in Single-File Mode..."

      PYTHONPATH="${../.}" \
      ${pkgs.python3}/bin/python3 ${./gemini.py} \
        --input "${input}" \
        --output "${output}" \
        --prompt "${systemPrompt}" \
        --model "$MJOLNIR_MODEL" \
        --api-key "$GEMINI_API_KEY" \
        --project "$GOOGLE_CLOUD_PROJECT" \
        --location "$GOOGLE_CLOUD_LOCATION"
    '';
}
