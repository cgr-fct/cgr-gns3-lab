#!/usr/bin/env python3
"""
collect.py - run commands on many devices / back up their configuration (SSH).

    ./collect.py all                                  # back up every reachable device -> backups/
    ./collect.py sw1 sw2                              # only these devices
    ./collect.py all -c "vtysh -c 'show ip route'"    # run a command everywhere and print the output
    ./collect.py all -c "ip -br addr" --json          # structured output (for further scripting)

A backup is one text file per device with /etc/network/interfaces and the FRR running config —
exactly what you hand in for the projects.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from cgrlib import HERE, Device, load_inventory


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("devices", nargs="+", help="device names or 'all'")
    ap.add_argument("-c", "--command", help="command to run instead of a backup")
    ap.add_argument("-i", "--inventory")
    ap.add_argument("-o", "--outdir", default=str(HERE / "backups"))
    ap.add_argument("--json", action="store_true", help="print results as JSON")
    args = ap.parse_args()

    inv = load_inventory(args.inventory)
    names = list(inv) if args.devices == ["all"] else args.devices
    results, stamp = {}, datetime.now().strftime("%Y%m%d-%H%M")
    for name in names:
        if name not in inv:
            print(f"{name}: not in inventory", file=sys.stderr)
            continue
        try:
            with Device(inv[name], timeout=3) as d:
                if args.command:
                    results[name] = d.run(args.command)
                else:
                    text = (f"### {name}  {stamp}\n### /etc/network/interfaces\n"
                            + d.read_file("/etc/network/interfaces")
                            + "\n### FRR running configuration\n"
                            + d.run("sudo vtysh -c 'show running-config'"))
                    out = Path(args.outdir)
                    out.mkdir(parents=True, exist_ok=True)
                    (out / f"{name}.txt").write_text(text, encoding="utf-8")
                    results[name] = f"saved {out / (name + '.txt')}"
        except Exception as e:  # noqa: BLE001 - devices of other labs are simply unreachable
            if args.devices != ["all"]:
                print(f"{name}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        if not args.json:
            print(f"==== {name}\n{results[name].rstrip()}")
    if args.json:
        print(json.dumps(results, indent=2))
    if not results:
        sys.exit("No device answered (is the lab started? right inventory?)")


if __name__ == "__main__":
    main()
