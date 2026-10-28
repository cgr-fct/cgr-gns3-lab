#!/usr/bin/env python3
"""
deliver.py - pack your project files on netauto into /root/delivery.tgz.

    ./deliver.py lab04        pack the Lab 04 files (intent files + scripts)
    ./deliver.py lab05        pack the Lab 05 files (fabric plan, templates, configs)
    ./deliver.py lab05 --list only list what would be packed

Packed (relative to /root/cgr), when they exist:
    intent/*.yml              your intent files (Lab 04)
    scripts/                  your scripts (Lab 04 check script, ...)
    fabric/fabric.yml, fabric/templates/, fabric/configs/      (Lab 05)
    notes.md                  optional: anything you want to point out
Then, on your computer, in the lab kit folder:
    python tools/cgr_lab.py fetch <lab-name>      -> delivery-<lab-name>.tgz
"""
import argparse
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path("/root/delivery.tgz")
SKIP_INTENT = {"lab00.yml"}


def collect(lab):
    files = []
    if lab in ("lab04", "all"):
        files += [p for p in sorted((HERE / "intent").glob("*.yml")) if p.name not in SKIP_INTENT]
    dirs = {"lab04": ["scripts"], "lab05": ["fabric/templates", "fabric/configs"],
            "all": ["scripts", "fabric/templates", "fabric/configs"]}[lab]
    for d in dirs:
        base = HERE / d
        if base.is_dir():
            files += [p for p in sorted(base.rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
    for f in (["fabric/fabric.yml"] if lab != "lab04" else []) + ["notes.md"]:
        if (HERE / f).is_file():
            files.append(HERE / f)
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lab", nargs="?", default="all", choices=["lab04", "lab05", "all"])
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    files = collect(args.lab)
    if not files:
        print("Nothing to deliver yet (no intent files, scripts or fabric files).")
        return 1
    for p in files:
        print("  " + str(p.relative_to(HERE)))
    if args.list:
        return 0
    with tarfile.open(OUT, "w:gz") as t:
        for p in files:
            t.add(p, arcname=str(p.relative_to(HERE)))
    print(f"{len(files)} files -> {OUT}. On your computer: python tools/cgr_lab.py fetch <lab-project-name>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
