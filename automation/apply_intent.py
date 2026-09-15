#!/usr/bin/env python3
"""
apply_intent.py - model-driven configuration for the CGR labs.

    YAML intent --(validate against the cgr-device YANG model)--> device data
        --ssh-->       Jinja2 templates --> device files --> ifreload / frr-reload / dhcp restart
        --restconf-->  PUT /restconf/data/cgr-device:device  (the device renders and applies it)

The intent file lists devices; each value is the content of the YANG container
`cgr-device:device` (see yang/cgr-device@2026-09-15.yang, `pyang -f tree` shows it as a tree).

Examples
    ./apply_intent.py intent/lab00.yml --check          # validate only
    ./apply_intent.py intent/lab00.yml --dry-run        # show the generated device files
    ./apply_intent.py intent/lab00.yml --diff           # show what would change on each device
    ./apply_intent.py intent/lab00.yml                  # push over SSH
    ./apply_intent.py intent/lab00.yml --restconf       # push with RESTCONF instead
    ./apply_intent.py intent/lab00.yml -d sw1           # only sw1
    ./apply_intent.py intent/lab00.yml --render out/    # write the generated files into out/<device>/
"""
import argparse
import difflib
import ipaddress
import json
import sys
from pathlib import Path

import yaml

from cgrlib import Device, load_inventory
from cgrmodel import TOP, merge_interfaces, render, short_error, validate


def normalise_frr(text):
    """Drop lines that differ only cosmetically between a template and `show running-config`."""
    skip = ("!", "exit", "end", "Building configuration", "Current configuration", "frr version",
            "log syslog", "service integrated-vtysh-config", "frr defaults")
    lines = [l.rstrip() for l in text.splitlines()
             if l.strip() and not l.strip().startswith(skip)]
    out, group = [], []

    def key(line):          # FRR orders "neighbor" lines by address
        try:
            return (0, int(ipaddress.ip_address(line.split()[1])), "")
        except ValueError:
            return (1, 0, line.split()[1])

    for l in lines + [""]:
        if l.lstrip().startswith("neighbor ") and l.startswith((" neighbor", "  neighbor")):
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


def push_ssh(dev, data, diff_only=False):
    files, commands = render(data)
    with Device(dev) as d:
        current = d.read_file("/etc/network/interfaces")
        eni = merge_interfaces(current, files.pop("interfaces-dataplane"))
        if diff_only:
            show_diff("/etc/network/interfaces", current, eni)
            show_diff("frr.conf", normalise_frr(d.run("sudo vtysh -c 'show running-config'")),
                      normalise_frr(files.pop("/etc/frr/frr.conf.new")))
            for path, content in files.items():
                rc, old, _ = d.exec(f"sudo cat {path}")
                show_diff(path, old if rc == 0 else "", content)
            return
        d.write_file("/etc/network/interfaces", eni)
        for path, content in files.items():
            d.write_file(path, content)
        for cmd in commands:
            rc, out, err = d.exec(f"sudo sh -c \"{cmd}\"")
            if rc:
                raise RuntimeError(f"'{cmd}' failed:\n{short_error(err or out)}")
        # keep the device's RESTCONF datastore in sync with what was pushed
        d.write_file("/etc/cgr/running.json", json.dumps(data, indent=2) + "\n")


def push_restconf(dev, data, diff_only=False):
    from restconf import Restconf
    rc = Restconf(dev["host"], dev.get("user", "cgr"), dev.get("password", "cgrlab"))
    if diff_only:
        current = rc.get("", content="config").get(TOP, {})
        show_diff("cgr-device:device", json.dumps(current, indent=2, sort_keys=True),
                  json.dumps(data, indent=2, sort_keys=True))
        return
    rc.put("", {TOP: data})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("intent")
    ap.add_argument("-d", "--device", action="append", help="only this device (repeatable)")
    ap.add_argument("-i", "--inventory")
    ap.add_argument("--check", action="store_true", help="only validate the intent file")
    ap.add_argument("--dry-run", action="store_true", help="print the generated device files")
    ap.add_argument("--diff", action="store_true", help="compare with what is on the devices")
    ap.add_argument("--render", metavar="DIR", help="write the generated files into DIR")
    ap.add_argument("--restconf", action="store_true", help="push with RESTCONF instead of SSH")
    args = ap.parse_args()

    intent = yaml.safe_load(Path(args.intent).read_text(encoding="utf-8")) or {}
    devices = intent.get("devices") or {}
    if args.device:
        devices = {k: v for k, v in devices.items() if k in args.device}

    bad = False
    for name, data in devices.items():
        errors = validate(data)
        if errors:
            bad = True
            print(f"{name}: NOT valid against the cgr-device YANG model")
            for e in errors:
                print(f"   {e}")
    if bad:
        sys.exit(1)
    if args.check:
        print(f"{len(devices)} device(s) valid")
        return

    inv = load_inventory(args.inventory) if not (args.dry_run or args.render) else {}
    failed = []
    for name, data in devices.items():
        if args.render or args.dry_run:
            files, commands = render(data)
            files["/etc/network/interfaces (data-plane part)"] = files.pop("interfaces-dataplane")
            files["/etc/frr/frr.conf"] = files.pop("/etc/frr/frr.conf.new")
            if args.render:
                out = Path(args.render) / name
                out.mkdir(parents=True, exist_ok=True)
                for path, content in files.items():
                    (out / Path(path.split(" ")[0]).name).write_text(content, encoding="utf-8")
                (out / "restconf-body.json").write_text(json.dumps({TOP: data}, indent=2), encoding="utf-8")
                print(f"{name}: rendered into {out}/")
            else:
                for path, content in files.items():
                    print(f"######## {name}: {path}\n{content}")
                print(f"######## {name}: then run\n" + "\n".join(commands) + "\n")
            continue
        if name not in inv:
            print(f"{name}: not in inventory - skipped")
            continue
        print(f"{name} ({inv[name]['host']}) ... ", end="", flush=True)
        try:
            if args.diff:
                print()
            push = push_restconf if args.restconf else push_ssh
            push(inv[name], data, diff_only=args.diff)
            if not args.diff:
                print("applied")
        except Exception as e:  # noqa: BLE001 - report and continue with the next device
            print(f"FAILED\n   {type(e).__name__}: {e}")
            failed.append(name)
    if failed:
        sys.exit(f"Failed on: {', '.join(failed)}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
