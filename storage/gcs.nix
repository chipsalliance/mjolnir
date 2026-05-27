# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs,
  path ? null,
}:
{
  name = "gcs";
  upload =
    { runDir }:
    ''
      RUN_DIR_NAME=$(basename "${runDir}")
      
      GCS_BUCKET="$MJOLNIR_GCS_BUCKET"

      if [ -z "$GCS_BUCKET" ]; then
        echo "Error: GCS upload enabled but no GCS bucket is configured." >&2
        exit 1
      fi

      GCS_DEST="gs://$GCS_BUCKET/v0${if path != null && path != "" then "/${path}" else ""}/$RUN_DIR_NAME"
      echo "Uploading run directory to $GCS_DEST..."

      # Use gcloud storage to copy the contents of the directory
      ${pkgs.google-cloud-sdk}/bin/gcloud storage cp -r "${runDir}/." "$GCS_DEST/"
      echo "Uploaded to $GCS_DEST"
    '';
}
