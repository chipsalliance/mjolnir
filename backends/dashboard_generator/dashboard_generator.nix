# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
{
  name = "dashboard-generator";
  run =
    { src, output }:
    ''
      echo "Generating HTML dashboard from ${src}..."

      # Ensure output directory exists
      mkdir -p "$(dirname "${output}")"

      PYTHONPATH="${../.}" \
      ${pkgs.python3}/bin/python3 ${./generate_dashboard.py} "${src}" "${output}" --template ${../../dashboards/vuln_report_dashboard.html.tpl} --css ${../../dashboards/dashboard.css}

      echo "Dashboard generated at: ${output}"
    '';
}
