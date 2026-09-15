#!/usr/bin/env python3
"""
apply_intent.py - intent-based configuration for the CGR labs.

    YAML intent  --(validate with JSON Schema)-->  data model
                 --(translate)-->  NVUE JSON  --(REST API)-->  Cumulus VX
                 --(Jinja2)----->  ifupdown2 + FRR config --(SSH)--> FRR (lite) nodes

Examples
    ./apply_intent.py intent/lab00.yml --dry-run          # show the JSON that would be sent
    ./apply_intent.py intent/lab00.yml --cli              # show equivalent `nv set` commands
    ./apply_intent.py intent/lab00.yml                    # push to every device in the file
    ./apply_intent.py intent/lab00.yml -d sw1             # only sw1
    ./apply_intent.py intent/lab00.yml --lite             # lab built with --lite (SSH + FRR)
    ./apply_intent.py intent/lab00.yml --render out/      # write all generated configs to files
"""
import argparse
import json
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from nvue import Nvue, NvueError, load_inventory

HERE = Path(__file__).resolve().parent
ENV = Environment(loader=FileSystemLoader(HERE / "templates"), undefined=StrictUndefined,
                  trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
MARKER = "# ---- your data-plane configuration goes below"


# ----------------------------------------------------------------- validation
def validate(intent):
    try:
        import jsonschema
    except ImportError:
        print("(jsonschema not installed - skipping validation)")
        return
    schema = yaml.safe_load((HERE / "schema" / "intent.schema.yml").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(intent), key=lambda e: list(e.path))
    if errors:
        print("Intent file is NOT valid:")
        for e in errors:
            where = "/".join(str(p) for p in e.path) or "(top)"
            print(f"  - {where}: {e.message}")
        sys.exit(1)


# ----------------------------------------------------------------- NVUE model
def to_nvue(name, d):
    """Translate one device's intent into an NVUE JSON document (PATCH on '/')."""
    doc = {"system": {"hostname": d.get("hostname", name)}, "interface": {}}
    ifs = doc["interface"]

    if d.get("loopback"):
        ifs["lo"] = {"type": "loopback", "ip": {"address": {d["loopback"]: {}}}}

    if d.get("vlans"):
        doc["bridge"] = {"domain": {"br_default": {
            "vlan": {str(v): {} for v in d["vlans"]}}}}

    for ifname, i in (d.get("interfaces") or {}).items():
        body = {"type": "swp"}
        if i.get("description"):
            body["description"] = i["description"]
        mode = i.get("mode") or ("routed" if i.get("ip") else None)
        if mode == "access":
            body["bridge"] = {"domain": {"br_default": {"access": i["vlan"]}}}
        elif mode == "trunk":
            body["bridge"] = {"domain": {"br_default": {
                "vlan": {str(v): {} for v in i["vlans"]}}}}
        elif mode == "routed":
            body["ip"] = {"address": {i["ip"]: {}}}
        ifs[ifname] = body

    for vid, s in (d.get("svis") or {}).items():
        ifs[f"vlan{vid}"] = {"type": "svi", "vlan": int(vid),
                             "ip": {"address": {s["ip"]: {}}}}

    if d.get("ospf"):
        o = d["ospf"]
        doc.setdefault("router", {})["ospf"] = {"enable": "on"}
        doc.setdefault("vrf", {}).setdefault("default", {}).setdefault("router", {})["ospf"] = {
            "enable": "on", "router-id": o["router_id"]}
        for ifname, oi in o["interfaces"].items():
            ospf_if = {"enable": "on", "area": oi["area"]}
            if oi.get("network_type"):
                ospf_if["network-type"] = oi["network_type"]
            if oi.get("passive"):
                ospf_if["passive"] = "on"
            ifs.setdefault(ifname, {}).setdefault("router", {})["ospf"] = ospf_if

    if d.get("bgp"):
        b = d["bgp"]
        doc.setdefault("router", {})["bgp"] = {
            "enable": "on", "autonomous-system": b["asn"], "router-id": b["router_id"]}
        vb = {"enable": "on", "neighbor": {}}
        if b.get("networks"):
            vb["address-family"] = {"ipv4-unicast": {
                "enable": "on", "network": {n: {} for n in b["networks"]}}}
        for peer, n in (b.get("neighbors") or {}).items():
            nb = {"remote-as": n["remote_as"], "type": "numbered"}
            if n.get("description"):
                nb["description"] = n["description"]
            if n.get("update_source"):
                nb["update-source"] = n["update_source"]
            if n.get("next_hop_self"):
                nb["address-family"] = {"ipv4-unicast": {"nexthop-setting": "self"}}
            vb["neighbor"][peer] = nb
        doc.setdefault("vrf", {}).setdefault("default", {}).setdefault("router", {})["bgp"] = vb
    return doc


# ----------------------------------------------------------------- lite (FRR) push
def push_lite(name, dev_inv, d):
    import paramiko
    eni = ENV.get_template("frr_interfaces.j2").render(name=name, d=d)
    frr = ENV.get_template("frr.conf.j2").render(name=name, d=d)
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(dev_inv["host"], username=dev_inv.get("user", "cumulus"),
                password=dev_inv.get("password"), look_for_keys=False, allow_agent=False,
                timeout=10)

    def run(cmd, data=None):
        stdin, stdout, stderr = cli.exec_command(cmd)
        if data is not None:
            stdin.write(data)
            stdin.channel.shutdown_write()
        rc = stdout.channel.recv_exit_status()
        return rc, stdout.read().decode(), stderr.read().decode()

    _, current, _ = run("cat /etc/network/interfaces")
    head = current.split(MARKER)[0].rstrip() + "\n\n"
    new_eni = head + MARKER + " (managed by apply_intent.py)\n" + eni
    run("sudo tee /etc/network/interfaces >/dev/null", new_eni)
    rc, out, err = run("sudo mkdir -p /run/network && sudo ifreload -a")
    if rc:
        print(f"  {name}: ifreload warnings:\n{err.strip()}")
    run("sudo tee /etc/frr/frr.conf.new >/dev/null", frr)
    rc, out, err = run("sudo /usr/lib/frr/frr-reload.py --reload /etc/frr/frr.conf.new "
                       "&& sudo vtysh -c 'write memory' >/dev/null")
    cli.close()
    if rc:
        raise RuntimeError(f"frr-reload failed: {err.strip() or out.strip()}")


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("intent")
    ap.add_argument("-d", "--device", action="append", help="only this device (repeatable)")
    ap.add_argument("-i", "--inventory")
    ap.add_argument("--dry-run", action="store_true", help="print the NVUE JSON, change nothing")
    ap.add_argument("--cli", action="store_true", help="print the equivalent nv set commands")
    ap.add_argument("--lite", action="store_true", help="all devices are FRR containers")
    ap.add_argument("--render", metavar="DIR", help="write generated configs into DIR")
    args = ap.parse_args()

    intent = yaml.safe_load(Path(args.intent).read_text(encoding="utf-8"))
    validate(intent)
    inv = load_inventory(args.inventory)
    devices = intent["devices"]
    if args.device:
        devices = {k: v for k, v in devices.items() if k in args.device}

    failed = []
    for name, d in devices.items():
        dinv = inv.get(name, {})
        platform = "frr" if args.lite else dinv.get("platform", "cumulus")
        if args.render:
            out = Path(args.render) / name
            out.mkdir(parents=True, exist_ok=True)
            (out / "nvue.json").write_text(json.dumps(to_nvue(name, d), indent=2), encoding="utf-8")
            (out / "nv_commands.txt").write_text(ENV.get_template("nv_cli.j2").render(name=name, d=d), encoding="utf-8")
            (out / "interfaces").write_text(ENV.get_template("frr_interfaces.j2").render(name=name, d=d), encoding="utf-8")
            (out / "frr.conf").write_text(ENV.get_template("frr.conf.j2").render(name=name, d=d), encoding="utf-8")
            print(f"{name}: rendered into {out}/")
            continue
        if args.cli:
            print(f"# ---- {name}")
            print(ENV.get_template("nv_cli.j2").render(name=name, d=d))
            continue
        if args.dry_run:
            print(f"# ---- {name}  (PATCH /nvue_v1/?rev=<new>)")
            print(json.dumps(to_nvue(name, d), indent=2))
            continue
        if not dinv:
            print(f"{name}: not in inventory - skipped")
            continue
        print(f"{name} ({dinv['host']}, {platform}) ... ", end="", flush=True)
        try:
            if platform == "cumulus":
                sw = Nvue(dinv["host"], dinv.get("user", "cumulus"), dinv.get("password"))
                sw.set("/", to_nvue(name, d))
            else:
                push_lite(name, dinv, d)
            print("applied")
        except (NvueError, RuntimeError, OSError) as e:
            print("FAILED")
            print(f"   {e}")
            failed.append(name)
        except Exception as e:  # requests / paramiko errors
            print("FAILED")
            print(f"   {type(e).__name__}: {e}")
            failed.append(name)
    if failed:
        sys.exit(f"Failed on: {', '.join(failed)}")


if __name__ == "__main__":
    main()
