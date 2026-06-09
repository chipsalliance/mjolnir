# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs, name, backends, backendName }:
let
  dashboardGenerator = import ../dashboards/dashboard_generator.nix { inherit pkgs; };

  # Load adversarial review prompt
  adversarialPrompt = import ./load.nix {
    inherit pkgs;
    agentDir = ../../agents/adversarial_reviewer;
    backendName = backendName;
  };

  # Filter backends that support runAdversarialReviewer
  adversarialReviewBackends = pkgs.lib.filterAttrs (name: backendModule:
    backendModule ? runAdversarialReviewer
  ) backends;
in
''
  echo "${name}: Adversarial security review ..."
  
  # Raw Agent Output
  RAW_REVIEW_TXT="$VULN_RUN_DIR/raw_ai_review.txt"
  
  # Final merged JSON
  REVIEWED_JSON="$VULN_RUN_DIR/reviewed_report.json"
  
  case "$MJOLNIR_BACKEND" in
    ${builtins.concatStringsSep "\n" (builtins.map (bName: ''
      "${bName}")
        ${adversarialReviewBackends.${bName}.runAdversarialReviewer {
          systemPrompt = adversarialPrompt.backendArgs.systemPrompt;
          input = "$REPORT_FILE";
          output = "$RAW_REVIEW_TXT";
        }}
        ;;
    '') (builtins.attrNames adversarialReviewBackends))}
    *)
      echo "Error: Backend $MJOLNIR_BACKEND does not support adversarial review." >&2
      exit 1
      ;;
  esac

  echo "${name}: Merging review with original findings..."
  ${pkgs.python3}/bin/python3 ${../../app/tools}/sanitize_report.py \
      --original "$REPORT_FILE" \
      --review "$RAW_REVIEW_TXT" \
      --output "$REVIEWED_JSON"

  echo "${name}: Generating Markdown report..."
  ${pkgs.python3}/bin/python3 ${../../app/tools}/generate_markdown.py --input "$REVIEWED_JSON" --output "$VULN_RUN_DIR/reviewed_report.md"

  echo "${name}: Generating consolidated dashboard..."
  ${dashboardGenerator.run {
    src = "$REVIEWED_JSON";
    output = "$VULN_RUN_DIR/dashboard.html";
  }}
''
