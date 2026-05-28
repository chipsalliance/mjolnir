# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs,
  repoUrl,
  repoName,
  commit ? "latest",
  fileCommand ? "${pkgs.fd}/bin/fd -t f -H -I",
}:
{
  inherit repoUrl repoName commit;

  checkout =
    { checkoutDir }:
    ''
      echo "Extracting code from ${repoUrl} at ${commit}..."

      # Ensure checkout directory exists
      mkdir -p "${checkoutDir}"

      # Clone the repository
      echo "Cloning into ${checkoutDir}..."
      ${pkgs.git}/bin/git clone "${repoUrl}" "${checkoutDir}"

      pushd "${checkoutDir}" > /dev/null
      if [ "${commit}" != "latest" ]; then
          echo "Checking out ${commit}..."
          ${pkgs.git}/bin/git checkout "${commit}"
      fi
      popd > /dev/null
    '';

  # New function to generate the list of files to analyze
  findFiles =
    { checkoutDir, output }:
    ''
      echo "Identifying files for analysis in ${checkoutDir}..."
      pushd "${checkoutDir}" > /dev/null
      # Run the provided file command and save to the output file
      ${fileCommand} > "${output}"
      popd > /dev/null
      echo "Found $(wc -l < "${output}") files to analyze."
    '';

  writeMetadata =
    { checkoutDir, metadataFile }:
    ''
      echo "Writing target metadata to ${metadataFile}..."
      if [ -d "${checkoutDir}/.git" ]; then
        TARGET_COMMIT=$(${pkgs.git}/bin/git -C "${checkoutDir}" rev-parse HEAD)
      else
        TARGET_COMMIT="unknown"
      fi
      
      # Strip closing brace from metadata.json, append new properties, and close the JSON block
      ${pkgs.gnused}/bin/sed -i '$d' "${metadataFile}"
      echo "  ,\"target_repo\": \"${repoUrl}\"," >> "${metadataFile}"
      echo "  \"target_commit\": \"$TARGET_COMMIT\"" >> "${metadataFile}"
      echo "}" >> "${metadataFile}"
    '';
}
