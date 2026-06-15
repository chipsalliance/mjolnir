{ pkgs }:
let
  dummyRepo = pkgs.runCommand "dummy-test-git-repo" { buildInputs = [ pkgs.git ]; } ''
    mkdir -p $out
    cd $out
    git init --initial-branch=main
    git config user.name "Test Automaton"
    git config user.email "test@localhost"

    mkdir -p src
    echo '// Mock security test file' > src/lib.rs
    echo '// Mock binary main file' > src/main.rs
    echo '// Mock file 3' > src/file3.rs
    echo '// Mock file 4' > src/file4.rs

    git add .
    git commit -m "init"
  '';
in
{
  name = "Integration Tests";
  repoUrl = "file://${dummyRepo}";
  repoName = "tests";
  commit = "main";
  srcExtensions = [ "rs" ];
  provider = "mock";
}
