#!/usr/bin/env python3
"""
air2gns3.py - convert an NVIDIA Air topology export (JSON) into a CGR topology.yml.

    python tools/air2gns3.py ProjectCampusNetwork.json -o labs/p1-campus/topology.yml \
        --name p1-campus --mgmt-subnet 192.168.200.0/24

Mapping
  * cumulus-vx-*            -> kind: cumulus   (becomes an FRR container with --lite)
                               ports = highest swp used + 1, same swpN names as in Air
  * ubuntu / other Linux    -> kind: host      (small Debian container, data port eth1)
  * Air management_ip       -> mgmt (kept, so addresses match last year's documents)
  * unconnected ports are dropped; positions are rescaled to the GNS3 canvas.
"""
import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path

import yaml


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("air_json")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--name", help="project name (default: Air title)")
    ap.add_argument("--mgmt-subnet", default=None,
                    help="management subnet (default: derived from the Air management IPs)")
    ap.add_argument("--netauto-ip", default=None, help="address of the netauto station")
    ap.add_argument("--width", type=int, default=1100, help="canvas width to fit the drawing in")
    args = ap.parse_args()

    air = json.loads(Path(args.air_json).read_text(encoding="utf-8"))
    content = air["content"]
    nodes_in, links_in = content["nodes"], content["links"]

    # ports used per node
    used = {}
    links = []
    for link in links_in:
        if len(link) != 2 or not all(isinstance(e, dict) for e in link):
            continue
        a, b = link
        links.append([f"{a['node']}:{a['interface']}", f"{b['node']}:{b['interface']}"])
        for e in (a, b):
            m = re.fullmatch(r"(?:swp|eth)(\d+)", e["interface"])
            if m:
                used[e["node"]] = max(used.get(e["node"], 0), int(m.group(1)))

    # rescale positions
    xs = [n["positioning"]["x"] for n in nodes_in.values()]
    ys = [n["positioning"]["y"] for n in nodes_in.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1)
    scale = args.width / span
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

    nodes, mgmt_ips = {}, []
    for name, n in sorted(nodes_in.items()):
        os_name = n.get("os", "")
        d = {}
        if os_name.startswith("cumulus"):
            d["kind"] = "cumulus"
            d["role"] = "switch" if re.search(r"access|distrib|rack|sw", name, re.I) else "router"
            d["ports"] = max(used.get(name, 0) + 1, 4)
        else:
            d["kind"] = "host"
            if re.search(r"server|internet", name, re.I):
                d["role"] = "server"
        if n.get("management_ip") and d["kind"] == "cumulus":
            d["mgmt"] = n["management_ip"]
            mgmt_ips.append(ipaddress.ip_address(n["management_ip"]))
        d["x"] = int((n["positioning"]["x"] - cx) * scale)
        d["y"] = int((n["positioning"]["y"] - cy) * scale)
        nodes[name] = d

    topo = {"name": args.name or re.sub(r"\W+", "-", air.get("title", "air-lab")).strip("-").lower()}
    if mgmt_ips:
        subnet = args.mgmt_subnet or str(ipaddress.ip_network(f"{mgmt_ips[0]}/24", strict=False))
        topo["mgmt_subnet"] = subnet
        net = ipaddress.ip_network(subnet)
        taken = {str(i) for i in mgmt_ips}
        na = args.netauto_ip or next(str(h) for h in reversed(list(net.hosts())) if str(h) not in taken)
        nodes["netauto"] = {"kind": "netauto", "mgmt": na,
                            "x": -args.width // 2 - 150, "y": -args.width // 2}
        topo["mgmt_switch_pos"] = [-args.width // 2 - 150, -args.width // 2 + 150]
    topo["nodes"] = nodes
    topo["links"] = links

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    header = (f"# Converted from NVIDIA Air export '{Path(args.air_json).name}' by tools/air2gns3.py\n"
              "# Port names are the same as in Air. Build with --lite to use FRR containers.\n")
    body = yaml.safe_dump(topo, sort_keys=False, default_flow_style=None, width=120)
    out.write_text(header + body, encoding="utf-8")
    print(f"{out}: {len(nodes)} nodes, {len(links)} links")


if __name__ == "__main__":
    sys.exit(main())
