# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs,
  bucket ? "caliptra-github-ci-caliptra-reports",
  path ? "",
}:
{
  name = "gcs";
  upload =
    { runDir }:
    ''
      RUN_DIR_NAME=$(basename "${runDir}")
      GCSDEST="''${GCSDEST:-gs://${bucket}/v0/${path}/$RUN_DIR_NAME}"
      echo "Uploading run directory to $GCSDEST..."

      # Use gcloud storage to copy the contents of the directory
      ${pkgs.google-cloud-sdk}/bin/gcloud storage cp -r "${runDir}/." "$GCSDEST/"
      echo "Uploaded to $GCSDEST"
    '';
}
