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
    ./apply_intent.py intent/lab00.yml --diff           # what would change on each device
    ./apply_intent.py intent/lab00.yml                  # push over SSH
    ./apply_intent.py intent/lab00.yml --restconf       # push with RESTCONF instead
    ./apply_intent.py intent/lab00.yml -d sw1           # only sw1
    ./apply_intent.py intent/lab00.yml --render out/    # write the generated files into out/<device>/

Taking over devices that were configured by hand (CLI):
    ./apply_intent.py intent/mylab.yml --import R1 R2   # read R1, R2 into the intent file
    ./apply_intent.py intent/mylab.yml --import all     # ... or every device of the lab
    ./apply_intent.py intent/mylab.yml --diff           # check what a push would change
    ./apply_intent.py intent/mylab.yml                  # push (refused if it would remove
                                                        #  hand-made settings; see --force)

Safety: a push is refused when it would remove settings that were made by hand (not through
the model). The refusal lists them; add them to the intent, or use --force to drop them.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

from cgrimport import handmade_losses, import_snapshot, normalize, rendered_snapshot, snapshot_ssh
from cgrlib import Device, load_inventory
from cgrmodel import TOP, merge_interfaces, render, short_error, validate

RUNNING = "/etc/cgr/running.json"


class Refused(RuntimeError):
    pass


def refusal(name, losses):
    shown = "\n".join(f"      {l}" for l in losses[:12])
    more = f"\n      ... and {len(losses) - 12} more" if len(losses) > 12 else ""
    return Refused(
        f"{name} has {len(losses)} hand-made setting(s) that this push would remove:\n{shown}{more}\n"
        f"   -> add them to the intent (./apply_intent.py <file> --import {name} reads them), "
        f"or repeat with --force to remove them")


def read_running(d):
    rc, out, _ = d.exec(f"sudo cat {RUNNING} 2>/dev/null")
    try:
        return json.loads(out) if rc == 0 and out.strip() else {}
    except ValueError:
        return {}


def show_semantic_diff(snap, data):
    current = set(normalize(snap))
    wanted = set(normalize(rendered_snapshot(data)))
    removed, added = sorted(current - wanted), sorted(wanted - current)
    if not removed and not added:
        print("  no changes")
        return
    for l in removed:
        print(f"  - {l}")
    for l in added:
        print(f"  + {l}")


def push_ssh(dev, data, diff_only=False, force=False):
    files, commands = render(data)
    with Device(dev) as d:
        snap = snapshot_ssh(d)
        old = read_running(d)
        losses = handmade_losses(snap, old, data)
        if diff_only:
            show_semantic_diff(snap, data)
            if losses:
                print(f"  ! {len(losses)} of the '-' lines were made by hand (not through the model): "
                      "a push will be refused without --force")
            return
        if losses and not force:
            raise refusal(dev["name"], losses)
        eni = merge_interfaces(snap["interfaces"], files.pop("interfaces-dataplane"))
        d.write_file("/etc/network/interfaces", eni)
        for path, content in files.items():
            d.write_file(path, content)
        for cmd in commands:
            rc, out, err = d.exec(f"sudo sh -c \"{cmd}\"")
            if rc:
                raise RuntimeError(f"'{cmd}' failed:\n{short_error(err or out)}")
        # keep the device's RESTCONF datastore in sync with what was pushed
        d.write_file(RUNNING, json.dumps(data, indent=2) + "\n")


def push_restconf(dev, data, diff_only=False, force=False):
    from restconf import Restconf
    rc = Restconf(dev["host"], dev.get("user", "cgr"), dev.get("password", "cgrlab"))
    if diff_only:
        current = rc.get("", content="config").get(TOP, {})
        a = json.dumps(current, indent=2, sort_keys=True).splitlines()
        b = json.dumps(data, indent=2, sort_keys=True).splitlines()
        import difflib
        diff = list(difflib.unified_diff(a, b, "datastore", "intent", lineterm=""))
        print("\n".join("  " + l for l in diff) if diff else "  no changes (RESTCONF datastore)")
        return
    rc.put("", {TOP: data}, force=force)


# ------------------------------------------------------------------ import
def do_import(args, inv):
    path = Path(args.intent)
    intent = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    intent = intent or {}
    devices = intent.setdefault("devices", {}) or {}
    intent["devices"] = devices
    names = list(inv) if args.import_ == ["all"] else args.import_
    header = ["# Intent file - devices imported from their live configuration by apply_intent.py --import"]
    for name in names:
        if name not in inv:
            print(f"{name}: not in inventory - skipped")
            continue
        print(f"{name} ({inv[name]['host']}) ... ", end="", flush=True)
        try:
            with Device(inv[name]) as d:
                data, notes = import_snapshot(snapshot_ssh(d))
        except Exception as e:  # noqa: BLE001
            print(f"FAILED\n   {type(e).__name__}: {e}")
            continue
        errors = validate(data)
        devices[name] = data
        print("imported" + (f" ({len(notes)} note(s))" if notes else ""))
        for n in notes:
            print(f"   note: {n}")
        for e in errors:
            print(f"   INVALID: {e}")
        if notes or errors:
            header.append("#")
            header.append(f"# {name}: not imported / to check:")
            header += [f"#   - {n}" for n in notes] + [f"#   - INVALID: {e}" for e in errors]
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(intent, sort_keys=False, default_flow_style=None, width=110)
    path.write_text("\n".join(header) + "\n" + body, encoding="utf-8")
    print(f"\nWrote {path}. Next: review it, then  ./apply_intent.py {path} --diff")


# ------------------------------------------------------------------ main
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
    ap.add_argument("--import", dest="import_", nargs="+", metavar="DEVICE",
                    help="read the live configuration of these devices ('all' = every device) into the intent file")
    ap.add_argument("--force", action="store_true", help="push even if hand-made settings would be removed")
    args = ap.parse_args()

    if args.import_:
        return do_import(args, load_inventory(args.inventory))

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
            push(inv[name], data, diff_only=args.diff, force=args.force)
            if not args.diff:
                print("applied")
        except Exception as e:  # noqa: BLE001 - report and continue with the next device
            label = "REFUSED" if isinstance(e, Refused) or "resource-denied" in str(e) else "FAILED"
            print(f"{label}\n   {e if label == 'REFUSED' else type(e).__name__ + ': ' + str(e)}")
            failed.append(name)
    if failed:
        sys.stdout.flush()
        sys.exit(f"Not applied on: {', '.join(failed)}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
