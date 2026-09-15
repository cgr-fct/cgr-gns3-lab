#!/usr/bin/env python3
"""
apply_intent.py - intent-based configuration for the CGR labs.

    YAML intent --(validate: JSON Schema)--> data model --(Jinja2)--> device config --(SSH)--> device

Examples
    ./apply_intent.py intent/lab00.yml --dry-run        # show the generated configs, change nothing
    ./apply_intent.py intent/lab00.yml --diff           # show what would change on each device
    ./apply_intent.py intent/lab00.yml                  # push to every device in the file
    ./apply_intent.py intent/lab00.yml -d sw1           # only sw1
    ./apply_intent.py intent/lab00.yml --render out/    # write the generated files into out/<device>/

On each device the tool
  * replaces everything below the "# ---- your data-plane configuration" line of
    /etc/network/interfaces with the rendered interfaces and runs `ifreload -a`;
  * loads the rendered FRR configuration with `frr-reload.py` (only the differences are
    applied) and saves it with `write memory`.
"""
import argparse
import difflib
import ipaddress
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from cgrlib import Device, load_inventory

HERE = Path(__file__).resolve().parent
ENV = Environment(loader=FileSystemLoader(HERE / "templates"), undefined=StrictUndefined,
                  trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
MARKER = "# ---- your data-plane configuration goes below"


def validate(intent):
    import jsonschema
    schema = yaml.safe_load((HERE / "schema" / "intent.schema.yml").read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(intent),
                    key=lambda e: list(e.path))
    if errors:
        print("Intent file is NOT valid:")
        for e in errors:
            where = "/".join(str(p) for p in e.path) or "(top)"
            print(f"  - {where}: {e.message}")
        sys.exit(1)


def render(name, d):
    return (ENV.get_template("frr_interfaces.j2").render(name=name, d=d),
            ENV.get_template("frr.conf.j2").render(name=name, d=d))


def merged_interfaces(current, eni):
    head = current.split(MARKER)[0].rstrip() + "\n\n"
    return head + MARKER + " (managed by automation)\n" + eni


def normalise_frr(text):
    """Drop lines that differ only cosmetically between a template and `show running-config`."""
    skip = ("!", "exit", "end", "Building configuration", "Current configuration", "frr version",
            "log syslog", "service integrated-vtysh-config", "frr defaults")
    lines = [l.rstrip() for l in text.splitlines()
             if l.strip() and not l.strip().startswith(skip)]
    # FRR orders "neighbor" lines by address; sort each consecutive group the same way
    out, group = [], []

    def key(line):
        try:
            return (0, int(ipaddress.ip_address(line.split()[1])), "")
        except ValueError:
            return (1, 0, line.split()[1])

    for l in lines + [""]:
        if l.startswith(" neighbor "):
            group.append(l)
            continue
        out += sorted(group, key=key)
        group = []
        out.append(l)
    return "\n".join(out[:-1])


def show_diff(label, old, new):
    diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(),
                                     f"{label} (device)", f"{label} (intent)", lineterm=""))
    print("\n".join(diff) if diff else f"  {label}: no changes")


def push(dev, eni, frr, diff_only=False):
    with Device(dev) as d:
        current = d.read_file("/etc/network/interfaces")
        new_eni = merged_interfaces(current, eni)
        if diff_only:
            show_diff("/etc/network/interfaces", current, new_eni)
            show_diff("frr.conf", normalise_frr(d.run("sudo vtysh -c 'show running-config'")),
                      normalise_frr(frr))
            return
        d.write_file("/etc/network/interfaces", new_eni)
        rc, _, err = d.exec("sudo mkdir -p /run/network && sudo ifreload -a")
        if rc:
            print(f"\n  ifreload warnings:\n{err.strip()}")
        d.write_file("/etc/frr/frr.conf.new", frr)
        d.run("sudo /usr/lib/frr/frr-reload.py --reload /etc/frr/frr.conf.new")
        d.run("sudo vtysh -c 'write memory'")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("intent")
    ap.add_argument("-d", "--device", action="append", help="only this device (repeatable)")
    ap.add_argument("-i", "--inventory")
    ap.add_argument("--dry-run", action="store_true", help="print the generated configs")
    ap.add_argument("--diff", action="store_true", help="compare with what is on the devices")
    ap.add_argument("--render", metavar="DIR", help="write the generated configs into DIR")
    args = ap.parse_args()

    intent = yaml.safe_load(Path(args.intent).read_text(encoding="utf-8"))
    validate(intent)
    inv = load_inventory(args.inventory)
    devices = intent["devices"]
    if args.device:
        devices = {k: v for k, v in devices.items() if k in args.device}

    failed = []
    for name, d in devices.items():
        eni, frr = render(name, d)
        if args.render:
            out = Path(args.render) / name
            out.mkdir(parents=True, exist_ok=True)
            (out / "interfaces").write_text(eni, encoding="utf-8")
            (out / "frr.conf").write_text(frr, encoding="utf-8")
            print(f"{name}: rendered into {out}/")
            continue
        if args.dry_run:
            print(f"######## {name}: /etc/network/interfaces (data-plane part)\n{eni}")
            print(f"######## {name}: /etc/frr/frr.conf\n{frr}")
            continue
        if name not in inv:
            print(f"{name}: not in inventory - skipped")
            continue
        print(f"{name} ({inv[name]['host']}) ... ", end="", flush=True)
        try:
            if args.diff:
                print()
            push(inv[name], eni, frr, diff_only=args.diff)
            if not args.diff:
                print("applied")
        except Exception as e:  # noqa: BLE001 - report and continue with the next device
            print(f"FAILED\n   {type(e).__name__}: {e}")
            failed.append(name)
    if failed:
        sys.exit(f"Failed on: {', '.join(failed)}")


if __name__ == "__main__":
    main()
