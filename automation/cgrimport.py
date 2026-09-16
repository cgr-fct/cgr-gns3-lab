"""
cgrimport.py - read a device's hand-made configuration back into the cgr-device model,
and compare device configurations semantically.

A *snapshot* is what a device is configured with right now:

    {"interfaces": <text of /etc/network/interfaces>,
     "frr": <text of `vtysh -c 'show running-config'`>,
     "dhcpd": <text of /etc/dhcp/dhcpd.conf>,          "dhcpd_default": <…/isc-dhcp-server>,
     "relay_default": <…/isc-dhcp-relay>}

    snap = snapshot_local()                  # on the device itself (RESTCONF server)
    snap = snapshot_ssh(dev)                 # from netauto, over SSH
    device, notes = import_snapshot(snap)    # model data + what could not be imported
    normalize(snap)                          # order-insensitive view, for comparisons
    rendered_snapshot(device)                # the snapshot a push of `device` would produce
"""
import ipaddress
import re
import subprocess
from pathlib import Path

from cgrmodel import MARKER, render

IGNORED_FRR = ("frr version", "frr defaults", "log ", "service integrated-vtysh-config",
               "hostname", "Building configuration", "Current configuration", "end", "!",
               "line vty", "exit", "agentx", "no ipv6 forwarding", "ipv6 forwarding",
               "ip forwarding", "password", "enable password")
DEFAULT_ENI = {("bridge-pvid", "1"), ("bridge-stp", "on"), ("bridge-stp", "yes"),
               ("bond-miimon", "100"), ("bond-lacp-rate", "fast"), ("bond-lacp-rate", "1"),
               ("bond-mode", "802.3ad")}
ID_RE = re.compile(r"^(swp\d+|bond\d+)$")


# ------------------------------------------------------------------ snapshots
def snapshot_local():
    def read(p):
        try:
            return Path(p).read_text()
        except OSError:
            return ""
    frr = subprocess.run(["vtysh", "-c", "show running-config"], capture_output=True, text=True).stdout
    return {"interfaces": read("/etc/network/interfaces"), "frr": frr,
            "dhcpd": read("/etc/dhcp/dhcpd.conf"),
            "dhcpd_default": read("/etc/default/isc-dhcp-server"),
            "relay_default": read("/etc/default/isc-dhcp-relay")}


def snapshot_ssh(d):
    """d: an open cgrlib.Device."""
    def read(p):
        rc, out, _ = d.exec(f"sudo cat {p} 2>/dev/null")
        return out if rc == 0 else ""
    return {"interfaces": read("/etc/network/interfaces"),
            "frr": d.run("sudo vtysh -c 'show running-config'"),
            "dhcpd": read("/etc/dhcp/dhcpd.conf"),
            "dhcpd_default": read("/etc/default/isc-dhcp-server"),
            "relay_default": read("/etc/default/isc-dhcp-relay")}


def rendered_snapshot(device):
    files, _ = render(device)
    return {"interfaces": MARKER + "\n" + files["interfaces-dataplane"],
            "frr": files["/etc/frr/frr.conf.new"],
            "dhcpd": files.get("/etc/dhcp/dhcpd.conf", ""),
            "dhcpd_default": files.get("/etc/default/isc-dhcp-server", ""),
            "relay_default": files.get("/etc/default/isc-dhcp-relay", "")}


# ------------------------------------------------------------------ parsers
def parse_eni(text):
    """/etc/network/interfaces -> {iface: {"method": str|None, "opts": [(key, value), ...]}}"""
    ifaces, cur = {}, None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        words = line.split()
        if words[0] == "iface":
            name = words[1]
            method = words[3] if len(words) > 3 else None
            cur = ifaces.setdefault(name, {"method": method, "opts": []})
            if method:
                cur["method"] = method
        elif words[0] in ("auto", "allow-hotplug", "source", "source-directory", "mapping"):
            if words[0] != "auto":
                cur = None
            for n in words[1:] if words[0] == "auto" else []:
                ifaces.setdefault(n, {"method": None, "opts": []})
        elif cur is not None:
            cur["opts"].append((words[0], " ".join(words[1:])))
    return ifaces


def _mgmt(name):
    return name == "eth0"


def _vids(value):
    out = []
    for tok in value.replace(",", " ").split():
        if "-" in tok:
            a, b = tok.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif tok.isdigit():
            out.append(int(tok))
    return out


def _prefix(addr, netmask=None):
    if netmask and "/" not in addr:
        return str(ipaddress.ip_interface(f"{addr}/{netmask}"))
    return addr


def parse_frr(text):
    """running-config -> list of (context tuple, line) — order-insensitive representation."""
    items, top, sub = [], None, None
    for raw in text.splitlines():
        if not raw.strip():
            continue
        s = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if indent == 0:
            sub = None
            if s.startswith(IGNORED_FRR) and not s.startswith("log-"):
                top = None if s in ("exit", "!", "end") else top
                if s.startswith("line vty"):
                    top = ("line vty",)
                continue
            if re.match(r"^(interface|router|route-map|vrf|ip prefix-list|bgp community-list)\b", s) \
                    and not s.startswith(("ip prefix-list", "bgp community-list")):
                top = (s,)
            else:
                top = None
                items.append(((), s))
            continue
        if top == ("line vty",) or top is None:
            continue
        if s.startswith("address-family"):
            sub = s
            continue
        if s.startswith("exit-address-family"):
            sub = None
            continue
        if s in ("!", "exit"):
            continue
        items.append((top + ((sub,) if sub else ()), s))
    return items


def parse_dhcpd(text):
    """dhcpd.conf -> (pools, other lines)"""
    pools, other = [], []
    text = re.sub(r"#.*", "", text)
    for m in re.finditer(r"subnet\s+(\S+)\s+netmask\s+(\S+)\s*\{(.*?)\}", text, re.S):
        net = ipaddress.ip_network(f"{m.group(1)}/{m.group(2)}", strict=False)
        body = [l.strip().rstrip(";").strip() for l in m.group(3).split(";") if l.strip()]
        pool = {"subnet": str(net)}
        for stmt in body:
            w = stmt.split()
            if w[0] == "range" and len(w) >= 3:
                pool["range-start"], pool["range-end"] = w[1], w[2]
            elif w[:2] == ["option", "routers"]:
                pool["gateway"] = w[2].rstrip(",")
            elif w[:2] == ["option", "domain-name-servers"]:
                pool["dns-server"] = [x.strip(",") for x in w[2:] if x.strip(",")]
            elif w[0] == "default-lease-time":
                pool["lease-time"] = int(w[1])
            else:
                other.append(f"subnet {net}: {stmt}")
        pools.append(pool)
    rest = re.sub(r"subnet\s+\S+\s+netmask\s+\S+\s*\{.*?\}", "", text, flags=re.S)
    for stmt in [s.strip() for s in rest.split(";") if s.strip()]:
        if stmt not in ("authoritative",) and not stmt.startswith(("default-lease-time", "max-lease-time",
                                                                 "ddns-update-style", "option domain-name ",
                                                                 "option domain-name-servers")):
            other.append(stmt)
    return pools, other


def _shell_vars(text):
    out = {}
    for line in text.splitlines():
        m = re.match(r'^\s*([A-Za-z0-9_]+)="?(.*?)"?\s*$', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


# ------------------------------------------------------------------ import
def import_snapshot(snap):
    """Return (device data for cgr-device:device, [notes about what was not imported])."""
    dev, notes = {}, []
    ifaces = parse_eni(snap.get("interfaces", ""))
    frr = parse_frr(snap.get("frr", ""))
    addr_of = {}                                    # iface -> [prefixes] (for OSPF network stmts)

    # hostname
    m = re.search(r"^hostname (\S+)", snap.get("frr", ""), re.M)
    if m:
        dev["hostname"] = m.group(1)

    # ---- bridge
    bridge_name = None
    for name, st in ifaces.items():
        keys = {k for k, _ in st["opts"]}
        if "bridge-ports" in keys:
            if bridge_name:
                notes.append(f"interfaces: only one bridge is supported, '{name}' ignored")
                continue
            bridge_name = name
    bridge_ports, vlan_aware = [], True
    if bridge_name:
        opts = ifaces[bridge_name]["opts"]
        br = {}
        vlan_aware = any(k == "bridge-vlan-aware" and v in ("yes", "on") for k, v in opts)
        for k, v in opts:
            if k == "bridge-ports":
                bridge_ports += v.split()
            elif k == "bridge-vids":
                br["vlans"] = _vids(v)
            elif k == "bridge-stp":
                br["stp"] = v in ("on", "yes")
            elif k == "bridge-bridgeprio":
                br["stp-priority"] = int(v)
            elif k in ("bridge-vlan-aware",) or (k, v) in DEFAULT_ENI:
                pass
            elif k == "address":
                notes.append(f"interfaces: address {v} on the bridge itself is not in the model (use an SVI)")
            else:
                notes.append(f"interfaces: bridge option '{k} {v}' is not in the model")
        if bridge_name != "bridge":
            notes.append(f"interfaces: the bridge '{bridge_name}' will be called 'bridge' by the model")
        if not vlan_aware:
            notes.append(f"interfaces: '{bridge_name}' is not VLAN-aware; its ports become access ports of VLAN 1")
            br.setdefault("vlans", [1])
        if br.get("stp") is True:
            br.pop("stp")
        dev["bridge"] = br

    # ---- loopback
    lo = []
    for k, v in ifaces.get("lo", {"opts": []})["opts"]:
        if k == "address" and not v.startswith("127."):
            lo.append(v)
        elif k != "address":
            notes.append(f"interfaces: lo option '{k} {v}' is not in the model")
    if lo:
        dev["loopback"] = lo
        addr_of["lo"] = list(lo)

    # ---- ports, bonds, SVIs
    ports, svis = [], []
    for name, st in ifaces.items():
        if name in ("lo", bridge_name) or _mgmt(name):
            continue
        opts = st["opts"]
        vlan_m = re.match(r"^vlan(\d+)$", name)
        if vlan_m or any(k == "vlan-raw-device" for k, _ in opts):
            vid = int(vlan_m.group(1)) if vlan_m else None
            svi, netmask = {}, None
            addrs = []
            for k, v in opts:
                if k == "vlan-id":
                    vid = int(v)
                elif k == "address":
                    addrs.append(v)
                elif k == "netmask":
                    netmask = v
                elif k == "vlan-raw-device":
                    if v != bridge_name:
                        notes.append(f"interfaces: {name} sits on '{v}', not on the bridge")
                elif k == "vrrp":
                    w = v.split()
                    svi["vrrp"] = {"vrid": int(w[0]), "virtual-address": w[1].split("/")[0]}
                elif k == "alias":
                    notes.append(f"interfaces: description of {name} is not in the model")
                else:
                    notes.append(f"interfaces: {name} option '{k} {v}' is not in the model")
            if vid is None or not vlan_m or int(vlan_m.group(1)) != vid:
                notes.append(f"interfaces: VLAN interface '{name}' must be named vlan<ID> to be imported")
                continue
            svi = {"vlan": vid, "address": [_prefix(a, netmask) for a in addrs], **svi}
            if not svi["address"]:
                notes.append(f"interfaces: {name} has no address and was not imported")
                continue
            addr_of[name] = svi["address"]
            svis.append(svi)
            continue
        if not ID_RE.match(name):
            if opts:
                notes.append(f"interfaces: interface '{name}' is not in the model")
            continue
        port, addrs, netmask, members = {"name": name}, [], None, []
        access = vids = pvid = None
        for k, v in opts:
            if k == "alias":
                port["description"] = v
            elif k == "bond-slaves":
                members = v.split()
            elif k == "bridge-access":
                access = int(v)
            elif k == "bridge-vids":
                vids = _vids(v)
            elif k == "bridge-pvid":
                pvid = int(v)
            elif k == "address":
                addrs.append(v)
            elif k == "netmask":
                netmask = v
            elif k == "link-down" and v in ("yes", "on"):
                port["enabled"] = False
            elif k == "bond-mode" and v not in ("802.3ad", "4"):
                notes.append(f"interfaces: {name} uses bond-mode {v}; the model always uses LACP (802.3ad)")
            elif (k, v) in DEFAULT_ENI:
                pass
            else:
                notes.append(f"interfaces: {name} option '{k} {v}' is not in the model")
        if st.get("method") and st["method"] not in ("manual", "static"):
            notes.append(f"interfaces: {name} uses 'inet {st['method']}', which is not in the model")
        if members:
            port["bond-member"] = members
        in_bridge = name in bridge_ports
        if addrs:
            port["mode"] = "routed"
            port["address"] = [_prefix(a, netmask) for a in addrs]
            addr_of[name] = port["address"]
        elif in_bridge and access is not None:
            port["mode"], port["access-vlan"] = "access", access
        elif in_bridge and not vlan_aware:
            port["mode"], port["access-vlan"] = "access", 1
        elif in_bridge:
            port["mode"] = "trunk"
            port["trunk-vlans"] = vids or dev.get("bridge", {}).get("vlans", [1])
            if pvid is not None and pvid != 1:
                port["native-vlan"] = pvid
        if len(port) == 1 and not members:
            continue                                   # only brought up (e.g. a bond member)
        ports.append(port)
    member_names = {m for p in ports for m in p.get("bond-member", [])}
    ports = [p for p in ports if not (p["name"] in member_names and len(p) == 1)]
    if ports:
        dev["interface"] = ports

    # ---- FRR
    rmaps, converted_rm = {}, set()
    for ctx, line in frr:
        if ctx and ctx[0].startswith("route-map "):
            rmaps.setdefault(ctx[0], []).append(line)
    ospf, isis, bgp = {}, {}, {}
    ospf_ifs, isis_ifs, net_stmts = {}, {}, []
    for ctx, line in frr:
        head = ctx[0] if ctx else ""
        w = line.split()
        if head.startswith("interface "):
            ifn = head.split()[1]
            if line.startswith("ip ospf area "):
                ospf_ifs.setdefault(ifn, {})["area"] = _area(w[3])
            elif line.startswith("ip ospf cost "):
                ospf_ifs.setdefault(ifn, {})["cost"] = int(w[3])
            elif line.startswith("ip ospf network "):
                ospf_ifs.setdefault(ifn, {})["network-type"] = w[3]
            elif line == "ip ospf passive":
                ospf_ifs.setdefault(ifn, {})["passive"] = True
            elif line.startswith("ip ospf priority "):
                ospf_ifs.setdefault(ifn, {})["priority"] = int(w[3])
            elif line.startswith("ip router isis "):
                isis_ifs.setdefault(ifn, {})
            elif line.startswith("isis network "):
                isis_ifs.setdefault(ifn, {})["network-type"] = w[2]
            elif line == "isis passive":
                isis_ifs.setdefault(ifn, {})["passive"] = True
            elif line.startswith("isis metric "):
                isis_ifs.setdefault(ifn, {})["metric"] = int(w[2])
            elif line.startswith("ip address "):
                pfx = w[2]
                if ifn == "lo":
                    dev.setdefault("loopback", []).append(pfx)
                elif ifn.startswith("vlan"):
                    s = next((s for s in svis if f"vlan{s['vlan']}" == ifn), None)
                    if s:
                        s["address"].append(pfx)
                    else:
                        notes.append(f"frr: {ifn} has an address but no VLAN interface")
                else:
                    p = next((p for p in dev.get("interface", []) if p["name"] == ifn), None)
                    if p is None:
                        p = {"name": ifn}
                        dev.setdefault("interface", []).append(p)
                    p["mode"] = "routed"
                    p.setdefault("address", []).append(pfx)
                addr_of.setdefault(ifn, []).append(pfx)
            elif line.startswith("vrrp "):
                s = next((s for s in svis if f"vlan{s['vlan']}" == ifn), None)
                if s and "vrrp" in s and line.startswith(f"vrrp {s['vrrp']['vrid']} priority "):
                    s["vrrp"]["priority"] = int(w[3])
                elif not (s and "vrrp" in s and (line.endswith("version 2") or " ip " in line)):
                    notes.append(f"frr: {head}: '{line}' is not in the model")
            elif line.startswith("description "):
                notes.append(f"frr: {head}: '{line}' is not in the model (use alias in interfaces)")
            else:
                notes.append(f"frr: {head}: '{line}' is not in the model")
        elif head == "router ospf":
            if line.startswith("ospf router-id "):
                ospf["router-id"] = w[2]
            elif line.startswith("network ") and len(w) == 4 and w[2] == "area":
                net_stmts.append((w[1], _area(w[3])))
            elif line.startswith("passive-interface "):
                ospf_ifs.setdefault(w[1], {})["passive"] = True
            elif re.match(r"^area \S+ range \S+$", line):
                _ospf_area(ospf, w[1]).setdefault("range", []).append(w[3])
            elif re.match(r"^area \S+ stub( no-summary)?$", line):
                _ospf_area(ospf, w[1])["type"] = "totally-stub" if "no-summary" in line else "stub"
            elif re.match(r"^area \S+ virtual-link \S+$", line):
                _ospf_area(ospf, w[1]).setdefault("virtual-link", []).append(w[3])
            elif line == "default-information originate":
                ospf["default-originate"] = "yes"
            elif line == "default-information originate always":
                ospf["default-originate"] = "always"
            else:
                notes.append(f"frr: router ospf: '{line}' is not in the model")
        elif head.startswith("router isis "):
            if line.startswith("net "):
                isis["net"] = w[1]
            elif line.startswith("is-type "):
                isis["is-type"] = w[1]
            elif line == "metric-style wide":
                pass
            else:
                notes.append(f"frr: {head}: '{line}' is not in the model")
        elif head.startswith("router bgp "):
            if len(head.split()) > 3:
                notes.append(f"frr: '{head}' (BGP in a VRF) is not in the model")
                continue
            bgp["asn"] = int(head.split()[2])
            nb = lambda a: _bgp_nb(bgp, a)  # noqa: E731
            if line.startswith("bgp router-id "):
                bgp["router-id"] = w[2]
            elif line in ("no bgp ebgp-requires-policy", "bgp log-neighbor-changes",
                          "no bgp network import-check") or line.startswith("bgp bestpath"):
                pass
            elif re.match(r"^neighbor \S+ remote-as \S+$", line):
                ra = w[3]
                nb(w[1])["remote-as"] = int(ra) if ra.isdigit() else ra
            elif re.match(r"^neighbor \S+ description ", line):
                nb(w[1])["description"] = line.split(" description ", 1)[1]
            elif re.match(r"^neighbor \S+ update-source \S+$", line):
                nb(w[1])["update-source"] = w[3]
            elif line.startswith("network ") and len(w) == 2:
                bgp.setdefault("network", []).append(w[1])
            elif line.startswith("aggregate-address "):
                bgp.setdefault("aggregate", []).append(
                    {"prefix": w[1], "summary-only": "summary-only" in w})
            elif re.match(r"^neighbor \S+ next-hop-self$", line):
                nb(w[1])["next-hop-self"] = True
            elif re.match(r"^neighbor \S+ activate$", line):
                pass
            elif re.match(r"^neighbor \S+ route-map \S+ (in|out)$", line):
                entries = [k for k in rmaps if k.split()[1] == w[3]]
                sets = rmaps[entries[0]] if len(entries) == 1 and entries[0].split()[2] == "permit" else []
                if w[4] == "in" and len(sets) == 1 and sets[0].startswith("set local-preference "):
                    nb(w[1])["local-preference-in"] = int(sets[0].split()[2])
                    converted_rm.add(w[3])
                elif w[4] == "out" and len(sets) == 1 and sets[0].startswith("set as-path prepend "):
                    asns = sets[0].split()[3:]
                    if asns and all(a == str(bgp["asn"]) for a in asns):
                        nb(w[1])["as-path-prepend-out"] = len(asns)
                        converted_rm.add(w[3])
                    else:
                        notes.append(f"frr: route-map {w[3]} (prepend of other ASNs) is not in the model")
                else:
                    notes.append(f"frr: route-map {w[3]} ({w[4]}) is not in the model — only a single "
                                 "'set local-preference' (in) or own-AS 'set as-path prepend' (out) can be imported")
            else:
                notes.append(f"frr: {head}{' / ' + ctx[1] if len(ctx) > 1 else ''}: '{line}' is not in the model")
        elif head.startswith("route-map "):
            pass
        elif not head:
            notes.append(f"frr: '{line}' is not in the model")
        else:
            notes.append(f"frr: {head}: '{line}' is not in the model")
    # OSPF network statements -> interfaces
    for net, area in net_stmts:
        netw = ipaddress.ip_network(net, strict=False)
        hit = False
        for ifn, pfxs in addr_of.items():
            if any(ipaddress.ip_interface(p).ip in netw for p in pfxs):
                ospf_ifs.setdefault(ifn, {}).setdefault("area", area)
                hit = True
        notes.append(f"frr: 'network {net} area {area}' converted to per-interface OSPF"
                     + ("" if hit else " (no matching interface found!)"))
    if ospf or ospf_ifs:
        if "router-id" not in ospf:
            # the model needs one: use the address FRR picks by itself (highest loopback
            # address, otherwise highest interface address)
            cands = [ipaddress.ip_interface(a).ip for a in dev.get("loopback", [])] or \
                    [ipaddress.ip_interface(a).ip for v in addr_of.values() for a in v]
            rid = str(max(cands)) if cands else "0.0.0.0"
            ospf["router-id"] = rid
            notes.append(f"frr: OSPF had no 'ospf router-id'; set to {rid} (the one FRR chooses "
                         "automatically) - check it")
        missing = [i for i, v in ospf_ifs.items() if "area" not in v]
        for i in missing:
            notes.append(f"frr: OSPF settings on {i} without an area were not imported")
        ospf["interface"] = [{"name": i, **v} for i, v in ospf_ifs.items() if "area" in v]
        if not ospf["interface"]:
            ospf.pop("interface")
        dev["ospf"] = _order(ospf, ["router-id", "default-originate", "area", "interface"])
    if isis or isis_ifs:
        if "net" not in isis:
            notes.append("frr: IS-IS has no 'net' — add it to the imported data")
        isis["interface"] = [{"name": i, **v} for i, v in isis_ifs.items()]
        dev["isis"] = _order(isis, ["net", "is-type", "interface"])
    if bgp:
        dev["bgp"] = _order(bgp, ["asn", "router-id", "network", "aggregate", "neighbor"])
    for key in rmaps:
        if key.split()[1] not in converted_rm:
            notes.append(f"frr: '{key}' is not in the model")
    if svis:
        dev["svi"] = svis

    # ---- DHCP
    dflt = _shell_vars(snap.get("dhcpd_default", ""))
    if dflt.get("INTERFACESv4", "").strip():
        pools, other = parse_dhcpd(snap.get("dhcpd", ""))
        server = {"interface": dflt["INTERFACESv4"].split()}
        full = [p for p in pools if "range-start" in p]
        if full:
            server["pool"] = full
        dev.setdefault("dhcp", {})["server"] = server
        notes += [f"dhcpd.conf: '{o}' is not in the model" for o in other]
    relay = _shell_vars(snap.get("relay_default", ""))
    if relay.get("SERVERS", "").strip():
        opts = relay.get("OPTIONS", "").split()
        down = [opts[i + 1] for i, o in enumerate(opts) if o == "-id" and i + 1 < len(opts)]
        up = [opts[i + 1] for i, o in enumerate(opts) if o == "-iu" and i + 1 < len(opts)]
        if relay.get("INTERFACES", "").strip():
            notes.append("isc-dhcp-relay: INTERFACES= cannot be imported — use -id/-iu in OPTIONS")
        extra = [o for i, o in enumerate(opts) if o not in ("-id", "-iu") and (i == 0 or opts[i - 1] not in ("-id", "-iu"))]
        if extra:
            notes.append(f"isc-dhcp-relay: options {' '.join(extra)} are not in the model")
        dev.setdefault("dhcp", {})["relay"] = {"server": relay["SERVERS"].split(),
                                               "client-interface": down, "upstream-interface": up}
    return _order(dev, ["hostname", "loopback", "bridge", "interface", "svi", "dhcp",
                        "ospf", "isis", "bgp"]), notes


def _area(v):
    return int(v) if v.isdigit() else v


def _ospf_area(ospf, aid):
    aid = _area(aid)
    for a in ospf.setdefault("area", []):
        if a["id"] == aid:
            return a
    a = {"id": aid}
    ospf["area"].append(a)
    return a


def _bgp_nb(bgp, addr):
    for n in bgp.setdefault("neighbor", []):
        if n["address"] == addr:
            return n
    n = {"address": addr}
    bgp["neighbor"].append(n)
    return n


def _order(d, keys):
    return {k: d[k] for k in keys if k in d} | {k: v for k, v in d.items() if k not in keys}


# ------------------------------------------------------------------ comparison
def normalize(snap):
    """Order-insensitive text view of a snapshot (management part and defaults removed)."""
    out = []
    eni = snap.get("interfaces", "")
    if MARKER in eni:
        eni = eni.split(MARKER, 1)[1]
    for name, st in parse_eni(eni).items():
        if _mgmt(name):
            continue
        for k, v in st["opts"]:
            if (k, v) in DEFAULT_ENI or (name == "lo" and v.startswith("127.")):
                continue
            if k in ("bridge-ports", "bond-slaves"):
                v = " ".join(sorted(v.split()))
            elif k == "bridge-vids":
                v = " ".join(str(x) for x in sorted(set(_vids(v))))
            out.append(f"interfaces | {name} | {k} {v}")
        if st.get("method") not in (None, "manual", "static", "loopback"):
            out.append(f"interfaces | {name} | inet {st['method']}")
    frr = parse_frr(snap.get("frr", ""))
    # OSPF 'network ... area ...' statements are written as the equivalent per-interface
    # 'ip ospf area' lines, so both styles compare equal
    addrs = {}
    for name, st in parse_eni(eni).items():
        if not _mgmt(name):
            addrs.setdefault(name, []).extend(v for k, v in st["opts"] if k == "address")
    for ctx, line in frr:
        if len(ctx) == 1 and ctx[0].startswith("interface ") and line.startswith("ip address "):
            addrs.setdefault(ctx[0].split()[1], []).append(line.split()[2])
    converted = []
    for ctx, line in frr:
        m = re.match(r"network (\S+) area (\S+)$", line)
        if ctx == ("router ospf",) and m:
            net = ipaddress.ip_network(m.group(1), strict=False)
            area = _area_dec(m.group(2))
            hits = [i for i, pf in addrs.items()
                    if any(ipaddress.ip_interface(a).ip in net for a in pf if "/" in a)]
            if hits:
                converted += [(("interface " + i,), f"ip ospf area {area}") for i in hits]
                continue
        converted.append((ctx, line))
    for ctx, line in converted:
        if line.startswith("hostname"):
            continue
        m = re.match(r"(ip ospf area|network \S+ area) (\S+)$", line)
        if m:
            line = f"{m.group(1)} {_area_dec(m.group(2))}"
        # route-map names differ between hand-made and generated configs: compare the content
        line = re.sub(r"^(neighbor \S+ route-map) \S+", r"\1 <route-map>", line)
        c = tuple(re.sub(r"^route-map \S+", "route-map <name>", x) for x in ctx)
        out.append(f"frr | {' / '.join(c)} | {line}" if c else f"frr | {line}")
    dflt = _shell_vars(snap.get("dhcpd_default", ""))
    if dflt.get("INTERFACESv4", "").strip():
        out.append(f"dhcp-server | interfaces {' '.join(sorted(dflt['INTERFACESv4'].split()))}")
        pools, other = parse_dhcpd(snap.get("dhcpd", ""))
        for p in pools:
            for k, v in sorted(p.items()):
                if k != "subnet" and not (k == "lease-time" and v == 3600):
                    out.append(f"dhcp-server | {p['subnet']} | {k} {v}")
            out.append(f"dhcp-server | {p['subnet']}")
        out += [f"dhcp-server | {o}" for o in other]
    relay = _shell_vars(snap.get("relay_default", ""))
    if relay.get("SERVERS", "").strip():
        out.append(f"dhcp-relay | servers {' '.join(sorted(relay['SERVERS'].split()))}")
        opts = relay.get("OPTIONS", "").split()
        pairs = sorted(f"{opts[i]} {opts[i + 1]}" for i in range(len(opts) - 1) if opts[i] in ("-id", "-iu"))
        out.append(f"dhcp-relay | options {', '.join(pairs)}")
        if relay.get("INTERFACES", "").strip():
            out.append(f"dhcp-relay | interfaces {relay['INTERFACES']}")
    return sorted(set(out))


def _area_dec(a):
    """OSPF area in decimal form (0.0.0.10 -> 10)."""
    return str(int(ipaddress.ip_address(a))) if "." in a else a


def is_blank(snap):
    """True if the device has no data-plane/routing/DHCP configuration at all."""
    return not normalize(snap)


def handmade_losses(snap, old, new):
    """Settings on the device that were NOT made through the model (old) and that pushing
    `new` would remove. old/new: content of cgr-device:device ({} = never managed)."""
    current = set(normalize(snap))
    known = set(normalize(rendered_snapshot(old or {})))
    wanted = set(normalize(rendered_snapshot(new or {})))
    return sorted((current - known) - wanted)
