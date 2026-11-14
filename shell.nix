{
  pkgs ? import <nixpkgs> { },
}:
let
  python = pkgs.python3Packages;
  pok3rtool = python.buildPythonApplication {
    pname = "pok3rtool";
    version = "2.0";
    src = pkgs.lib.cleanSource ../pok3rtool;
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
