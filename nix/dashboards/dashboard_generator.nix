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

      PYTHONPATH="${../../app/tools}" \
      ${pkgs.python3}/bin/python3 ${../../app/dashboard_generator/generate_dashboard.py} "${src}" "${output}" --template ${../../app/dashboard_generator/dashboards/vuln_report_dashboard.html.tpl} --css ${../../app/dashboard_generator/dashboards/dashboard.css}

      echo "Dashboard generated at: ${output}"
    '';
}
