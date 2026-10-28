#!/usr/bin/env python3
"""
generate.py - render the configuration files of an EVPN-VXLAN fabric from its data model.

    ./generate.py                         fabric.yml -> configs/<node>/{interfaces,frr.conf}
    ./generate.py my-fabric.yml -o out    other data file / output folder
    ./generate.py --show leaf1            print the variables a template receives for leaf1

fabric.yml is the plan of the fabric (the "source of truth"): tenants, VLANs/VNIs, ASNs,
loopbacks, links and access ports. The templates in templates/ turn it into the device files:

    templates/spine_interfaces.j2   templates/spine_frr.conf.j2
    templates/leaf_interfaces.j2    templates/leaf_frr.conf.j2

Each template receives:
    name        node name (e.g. "leaf1")
    node        that node's entry in fabric.yml
    fabric      the whole fabric.yml
    links       spines: [{port, peer, peer_port, address, peer_ip}]   (from the leaves' uplinks)
                leaves: the uplinks, each with peer_ip added
    networks    leaves: the networks (VLANs) that have an access port on this leaf, each with
                its tenant name added: [{vlan, vni, gateway, tenant}]
    tenants     leaves: {tenant: {vrf data from fabric.yml}} for the tenants of those networks
    spines / leaves   all spines / leaves (dicts from fabric.yml)

Before rendering, the data is checked (unique ASNs per leaf, loopbacks, VNIs and VLANs,
consistent /31 links, access ports that use an existing VLAN, ...): a plan with errors produces
no files.
"""
import argparse
import ipaddress
import json
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

HERE = Path(__file__).resolve().parent


class PlanError(Exception):
    pass


def load(path):
    with open(path, encoding="utf-8") as f:
        fab = yaml.safe_load(f) or {}
    for key in ("tenants", "spines", "leaves"):
        if not isinstance(fab.get(key), dict) or not fab[key]:
            raise PlanError(f"'{key}' is missing or empty")
    return fab


def other_end(addr):
    """10.1.1.1/31 -> 10.1.1.0 (the other address of a /31 or /30)."""
    iface = ipaddress.ip_interface(addr)
    hosts = [h for h in iface.network.hosts()] if iface.network.prefixlen < 31 else list(iface.network)
    others = [h for h in hosts if h != iface.ip]
    if len(others) != 1:
        raise PlanError(f"{addr}: not usable on a point-to-point link (use a /31, or a host address of a /30)")
    return str(others[0])


def check_and_derive(fab):
    errors = []
    tenants, spines, leaves = fab["tenants"], fab["spines"], fab["leaves"]

    # tenants / networks
    vlans, vnis = {}, {}
    for t, td in tenants.items():
        for key in ("l3vni", "l3vlan"):
            if key not in td:
                errors.append(f"tenant {t}: '{key}' missing")
        for key, table in (("l3vni", vnis), ("l3vlan", vlans)):
            if key in td:
                if td[key] in table:
                    errors.append(f"tenant {t}: {key} {td[key]} already used by {table[td[key]]}")
                table[td[key]] = f"tenant {t}"
        for n in td.get("networks") or []:
            for key in ("vlan", "vni", "gateway"):
                if key not in n:
                    errors.append(f"tenant {t}: network {n} has no '{key}'")
            if "vlan" in n:
                if n["vlan"] in vlans:
                    errors.append(f"tenant {t}: VLAN {n['vlan']} already used by {vlans[n['vlan']]}")
                vlans[n["vlan"]] = f"tenant {t}"
            if "vni" in n:
                if n["vni"] in vnis:
                    errors.append(f"tenant {t}: VNI {n['vni']} already used by {vnis[n['vni']]}")
                vnis[n["vni"]] = f"tenant {t}"
            if "gateway" in n:
                try:
                    ipaddress.ip_interface(n["gateway"])
                except ValueError:
                    errors.append(f"tenant {t}: bad gateway {n['gateway']}")
    network_of = {n["vlan"]: dict(n, tenant=t) for t, td in tenants.items()
                  for n in td.get("networks") or [] if "vlan" in n}

    # loopbacks and ASNs
    loops, asns = {}, {}
    for name, d in list(spines.items()) + list(leaves.items()):
        for key in ("asn", "loopback"):
            if key not in d:
                errors.append(f"{name}: '{key}' missing")
        if "loopback" in d:
            if d["loopback"] in loops:
                errors.append(f"{name}: loopback {d['loopback']} already used by {loops[d['loopback']]}")
            loops[d["loopback"]] = name
    for name, d in leaves.items():
        if "asn" in d:
            if d["asn"] in asns:
                errors.append(f"{name}: ASN {d['asn']} already used by {asns[d['asn']]} "
                              "(each leaf has its own AS in this design)")
            asns[d["asn"]] = name
            if any(d["asn"] == s.get("asn") for s in spines.values()):
                errors.append(f"{name}: ASN {d['asn']} is the spines' ASN")

    # links
    spine_links = {s: [] for s in spines}
    used_ports = {}
    subnets = {}
    for name, d in leaves.items():
        for up in d.get("uplinks") or []:
            for key in ("port", "peer", "peer_port", "address"):
                if key not in up:
                    errors.append(f"{name}: uplink {up} has no '{key}'")
            if not all(k in up for k in ("port", "peer", "peer_port", "address")):
                continue
            if up["peer"] not in spines:
                errors.append(f"{name}: uplink {up['port']} goes to unknown spine '{up['peer']}'")
                continue
            try:
                up["peer_ip"] = other_end(up["address"])
            except (PlanError, ValueError) as e:
                errors.append(f"{name}: uplink {up['port']}: {e}")
                continue
            net = str(ipaddress.ip_interface(up["address"]).network)
            if net in subnets:
                errors.append(f"{name}: link subnet {net} already used by {subnets[net]}")
            subnets[net] = f"{name}-{up['peer']}"
            for node, port in ((name, up["port"]), (up["peer"], up["peer_port"])):
                if (node, port) in used_ports:
                    errors.append(f"{node} {port} used twice ({used_ports[(node, port)]})")
                used_ports[(node, port)] = f"link {name}-{up['peer']}"
            mask = ipaddress.ip_interface(up["address"]).network.prefixlen
            spine_links[up["peer"]].append({
                "port": up["peer_port"], "peer": name, "peer_port": up["port"],
                "address": f"{up['peer_ip']}/{mask}",
                "peer_ip": str(ipaddress.ip_interface(up["address"]).ip)})
        for acc in d.get("access") or []:
            if acc.get("vlan") not in network_of:
                errors.append(f"{name}: access port {acc.get('port')} uses VLAN {acc.get('vlan')}, "
                              "which no tenant network defines")
            if (name, acc.get("port")) in used_ports:
                errors.append(f"{name} {acc.get('port')} used twice")
            used_ports[(name, acc.get("port"))] = "access port"
    for s, lst in spine_links.items():
        lst.sort(key=lambda l: int("".join(c for c in l["port"] if c.isdigit()) or 0))
        if not lst:
            errors.append(f"{s}: no leaf is connected to this spine")
    if errors:
        raise PlanError("\n".join(errors))

    ctx = {}
    for s, d in spines.items():
        ctx[s] = {"role": "spine", "links": spine_links[s]}
    for name, d in leaves.items():
        nets = sorted({a["vlan"] for a in d.get("access") or []})
        networks = [network_of[v] for v in nets]
        tns = {}
        for n in networks:
            tns[n["tenant"]] = tenants[n["tenant"]]
        ctx[name] = {"role": "leaf", "links": d.get("uplinks") or [], "networks": networks,
                     "tenants": dict(sorted(tns.items()))}
    return ctx


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fabric", nargs="?", default=str(HERE / "fabric.yml"))
    ap.add_argument("-o", "--outdir", default=str(HERE / "configs"))
    ap.add_argument("-t", "--templates", default=str(HERE / "templates"))
    ap.add_argument("--show", metavar="NODE", help="print the template variables of NODE and exit")
    args = ap.parse_args()

    try:
        fab = load(args.fabric)
        ctx = check_and_derive(fab)
    except PlanError as e:
        print("The plan has errors - no files written:\n  " + str(e).replace("\n", "\n  "))
        return 1

    env = Environment(loader=FileSystemLoader(args.templates), undefined=StrictUndefined,
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    common = {"fabric": fab, "spines": fab["spines"], "leaves": fab["leaves"]}

    if args.show:
        if args.show not in ctx:
            print(f"unknown node {args.show}; nodes: {', '.join(ctx)}")
            return 1
        node = fab["spines"].get(args.show) or fab["leaves"][args.show]
        print(json.dumps({"name": args.show, "node": node, **ctx[args.show]}, indent=2, default=str))
        return 0

    out = Path(args.outdir)
    for name, c in ctx.items():
        node = fab["spines"].get(name) or fab["leaves"][name]
        variables = dict(common, name=name, node=node, **c)
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        for kind, fname in (("interfaces", "interfaces"), ("frr.conf", "frr.conf")):
            tpl = f"{c['role']}_{kind}.j2"
            try:
                text = env.get_template(tpl).render(**variables)
            except Exception as e:  # noqa: BLE001 - show template errors clearly
                print(f"{name}: error in {tpl}: {type(e).__name__}: {e}")
                return 1
            (d / fname).write_text(text, encoding="utf-8")
        print(f"  {name:<8} {c['role']:<6} -> {d}/interfaces, {d}/frr.conf")
    print(f"{len(ctx)} nodes rendered. Deploy with: ./deploy.py" + ("" if out == HERE / "configs" else f" -c {out}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
