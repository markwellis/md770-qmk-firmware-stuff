{
  pkgs ? import <nixpkgs> { },
}:
let
  python = pkgs.python3Packages;
  pok3rtool = python.buildPythonApplication {
    pname = "pok3rtool";
    version = "2.0";
    src = pkgs.fetchFromGitHub {
      owner = "pok3r-custom";
      repo = "pok3rtool";
      rev = "7da3d5169bd5d7218464d302024e97c0d109999a";
      hash = "sha256-zkXxwPM29LmhmPn7IfXogT7yeFkA/l/ad8uijBh/LKA=";
    };
    patches = [ ./patches/pok3rtool-md770.patch ];
    pyproject = true;
    build-system = [ python.setuptools ];
    dependencies = with python; [
      pyusb
      hid-parser
      typer
      tqdm
      rarfile
      pefile
      dissect-cstruct
    ];
    pythonImportsCheck = [ "pok3rtool.cli" ];
  };
in
pkgs.mkShell {
  packages = [
    pkgs.qmk
    pok3rtool
  ];
  QMK_HOME = toString ../qmk_firmware;
  QMK_USERSPACE = toString ./.;
}
