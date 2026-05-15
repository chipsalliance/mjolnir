{ pkgs }:

let
  aggregate-results = pkgs.writeScriptBin "aggregate-results" ''
    #!${pkgs.python3}/bin/python3
    import sys
    import os
    
    # Add scripts directory to sys.path to find dashboard_builder
    sys.path.append("${./.}")
    
    import aggregate_results
    if __name__ == "__main__":
        sys.argv.insert(1, "--dashboards-dir")
        sys.argv.insert(2, "${../dashboards}")
        aggregate_results.main()
  '';

  aggregate-gcs-results = pkgs.writeScriptBin "aggregate-gcs-results" ''
    #!${pkgs.python3}/bin/python3
    import sys
    import os
    
    # Add gcloud to PATH
    os.environ["PATH"] = "${pkgs.google-cloud-sdk}/bin" + os.pathsep + os.environ.get("PATH", "")
    
    # Add scripts directory to sys.path to find dashboard_builder
    sys.path.append("${./.}")
    
    import aggregate_gcs_results
    if __name__ == "__main__":
        sys.argv.insert(1, "--dashboards-dir")
        sys.argv.insert(2, "${../dashboards}")
        aggregate_gcs_results.main()
  '';
in
{
  inherit aggregate-results aggregate-gcs-results;
}
