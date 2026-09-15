"""
cgrmodel.py - the cgr-device YANG model: validation and rendering to device files.

Used by apply_intent.py (push over SSH, from netauto) and by the RESTCONF agent that runs
on every router/switch. Both take the same data: the content of the YANG container
`cgr-device:device` (RFC 7951 JSON, or the equivalent YAML).

    from cgrmodel import validate, render
    errors = validate(device_data)            # [] when the data is valid
    files, commands = render(device_data)      # {path: content}, [shell commands]
"""
import ipaddress
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

HERE = Path(__file__).resolve().parent
MODULE = "cgr-device"
TOP = f"{MODULE}:device"
MARKER = "# ---- your data-plane configuration goes below"

ENV = Environment(loader=FileSystemLoader(HERE / "templates"), undefined=StrictUndefined,
                  trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
ENV.filters["ipnet"] = lambda p: ipaddress.ip_network(p, strict=False)

_dm = None


def data_model():
    """The yangson DataModel for cgr-device (loaded once)."""
    global _dm
    if _dm is None:
        from yangson import DataModel
        _dm = DataModel.from_file(str(HERE / "yang" / "yang-library.json"), [str(HERE / "yang")])
    return _dm


def validate(device, content="config"):
    """Validate the content of cgr-device:device. Returns a list of error strings."""
    from yangson.enumerations import ContentType, ValidationScope
    ctype = {"config": ContentType.config, "all": ContentType.all}[content]
    try:
        inst = data_model().from_raw({TOP: device or {}})
        inst.validate(ValidationScope.all, ctype)
    except Exception as e:  # yangson raises several exception types, all with a useful str()
        msg = re.sub(r"pattern '.*?': ", "does not match the expected format: ", str(e))
        return [f"{type(e).__name__}: {msg}"]
    return []


def _ctx(device):
    d = dict(device or {})
    ifs = d.get("interface", [])
    d["l2_ports"] = [i["name"] for i in ifs if i.get("mode") in ("access", "trunk")]
    d["bond_members"] = sorted({m for i in ifs for m in i.get("bond-member", [])})
    # dhcpd needs a (possibly empty) subnet declaration for every interface it listens on
    server = d.get("dhcp", {}).get("server", {})
    pools = [ipaddress.ip_network(p["subnet"], strict=False) for p in server.get("pool", [])]
    addrs = {"lo": d.get("loopback", [])}
    addrs.update({i["name"]: i.get("address", []) for i in ifs})
    addrs.update({f"vlan{s['vlan']}": s.get("address", []) for s in d.get("svi", [])})
    extra = []
    for name in server.get("interface", []):
        for a in addrs.get(name, []):
            net = ipaddress.ip_interface(a).network
            if net not in pools and net not in extra and net.prefixlen < 32:
                extra.append(net)
    d["dhcp_extra_subnets"] = extra
    d["frr_interfaces"] = _frr_interfaces(d)
    return {"d": d}


def _frr_interfaces(d):
    """FRR 'interface X' blocks, one per interface: {name: [lines]}."""
    out = {}
    for s in d.get("svi", []):
        v = s.get("vrrp")
        if v:
            out.setdefault(f"vlan{s['vlan']}", []).extend([
                f"vrrp {v['vrid']} version 2",
                f"vrrp {v['vrid']} ip {v['virtual-address']}",
                f"vrrp {v['vrid']} priority {v.get('priority', 100)}"])
    for i in d.get("ospf", {}).get("interface", []):
        lines = out.setdefault(i["name"], [])
        lines.append(f"ip ospf area {i['area']}")
        if "cost" in i:
            lines.append(f"ip ospf cost {i['cost']}")
        if "network-type" in i:
            lines.append(f"ip ospf network {i['network-type']}")
        if i.get("passive"):
            lines.append("ip ospf passive")
        if "priority" in i:
            lines.append(f"ip ospf priority {i['priority']}")
    for i in d.get("isis", {}).get("interface", []):
        lines = out.setdefault(i["name"], [])
        lines.append("ip router isis CGR")
        if "network-type" in i:
            lines.append(f"isis network {i['network-type']}")
        if i.get("passive"):
            lines.append("isis passive")
        if "metric" in i:
            lines.append(f"isis metric {i['metric']}")
    return out


def render(device):
    """Render device data into ({path: content}, [commands to apply them])."""
    ctx = _ctx(device)
    files = {
        "interfaces-dataplane": ENV.get_template("interfaces.j2").render(**ctx),
        "/etc/frr/frr.conf.new": ENV.get_template("frr.conf.j2").render(**ctx),
    }
    dhcp = (device or {}).get("dhcp", {})
    commands = ["mkdir -p /run/network && ifreload -a",
                "/usr/lib/frr/frr-reload.py --reload /etc/frr/frr.conf.new && vtysh -c 'write memory' >/dev/null"]
    if (device or {}).get("hostname"):
        h = device["hostname"]
        commands.append(f"vtysh -c 'conf t' -c 'hostname {h}' -c 'end' -c 'write memory' >/dev/null"
                        f" && hostname {h}")
    if "server" in dhcp:
        files["/etc/dhcp/dhcpd.conf"] = ENV.get_template("dhcpd.conf.j2").render(**ctx)
        files["/etc/default/isc-dhcp-server"] = (
            f'INTERFACESv4="{" ".join(dhcp["server"]["interface"])}"\nINTERFACESv6=""\n')
        commands.append("service isc-dhcp-server restart >/dev/null")
    else:
        commands.append("service isc-dhcp-server stop >/dev/null 2>&1; true")
    if "relay" in dhcp:
        r = dhcp["relay"]
        opts = " ".join([f"-id {i}" for i in r["client-interface"]]
                        + [f"-iu {i}" for i in r["upstream-interface"]])
        files["/etc/default/isc-dhcp-relay"] = (
            f'SERVERS="{" ".join(r["server"])}"\nINTERFACES=""\nOPTIONS="{opts}"\n')
        commands.append("service isc-dhcp-relay restart >/dev/null")
    else:
        commands.append("service isc-dhcp-relay stop >/dev/null 2>&1; true")
    return files, commands


def merge_interfaces(current, dataplane, who="automation"):
    """Keep the management part of /etc/network/interfaces, replace the data-plane part."""
    head = current.split(MARKER)[0].rstrip() + "\n\n"
    return head + MARKER + f" (managed by {who})\n" + dataplane


def short_error(text, limit=600):
    """Keep the useful part of a command's error output (drop ifupdown2/FRR warnings)."""
    lines = [l for l in (text or "").splitlines() if l.strip()]
    errors = [l for l in lines if "error" in l.lower() and not l.lower().startswith("warning")]
    return ("\n".join(errors) or "\n".join(lines))[-limit:]
