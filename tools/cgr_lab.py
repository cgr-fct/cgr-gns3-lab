#!/usr/bin/env python3
"""
cgr_lab.py - build and manage the CGR GNS3 labs from YAML topology files.

Talks to the GNS3 2.2 controller REST API (the same API the GNS3 GUI uses).
Keep the GNS3 GUI open while you use it.

  python tools/cgr_lab.py check
  python tools/cgr_lab.py templates
  python tools/cgr_lab.py build labs/lab00-first-contact --start
  python tools/cgr_lab.py consoles lab00-first-contact
  python tools/cgr_lab.py stop lab00-first-contact
  python tools/cgr_lab.py delete lab00-first-contact

Connection settings (first match wins):
  1. --server / --user / --password options
  2. environment variables GNS3_SERVER, GNS3_USER, GNS3_PASSWORD
  3. the GNS3 GUI's own gns3_server.conf (found automatically)
  4. http://127.0.0.1:3080 without authentication
Lab-wide settings (container image names) live in tools/lab_settings.yml.

Only needs Python 3.8+ with the packages in tools/requirements.txt.
"""
import argparse
import configparser
import ipaddress
import os
import re
import sys
from pathlib import Path

try:
    import requests
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("Missing packages. Run:  python -m pip install -r tools/requirements.txt")

REPO = Path(__file__).resolve().parent.parent
SETTINGS_FILE = REPO / "tools" / "lab_settings.yml"
MGMT_SWITCH = "mgmt-sw"


# --------------------------------------------------------------------------- utils
def info(msg):
    print(f"\033[1;34m==>\033[0m {msg}")


def ok(msg):
    print(f"\033[1;32m OK\033[0m {msg}")


def warn(msg):
    print(f"\033[1;33m !!\033[0m {msg}")


def die(msg):
    print(f"\033[1;31mERR\033[0m {msg}")
    sys.exit(1)


if os.name == "nt":  # enable ANSI colours on Windows 10+
    os.system("")


def load_settings():
    with open(SETTINGS_FILE, encoding="utf-8") as f:
        s = yaml.safe_load(f) or {}
    # allow overrides from the environment
    for key in ("frr_image", "netauto_image"):
        if os.environ.get("CGR_" + key.upper()):
            s[key] = os.environ["CGR_" + key.upper()]
    return s


def gns3_conf_candidates():
    home = Path.home()
    names = []
    if os.name == "nt":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        base = appdata / "GNS3"
    else:
        base = home / ".config" / "GNS3"
    if base.exists():
        # newest version folder first (e.g. 2.2)
        for d in sorted([p for p in base.iterdir() if p.is_dir()], reverse=True):
            names.append(d / "gns3_server.conf")
    names.append(base / "gns3_server.conf")
    return names


def connection_settings(args):
    server, user, password = args.server, args.user, args.password
    server = server or os.environ.get("GNS3_SERVER")
    user = user or os.environ.get("GNS3_USER")
    password = password or os.environ.get("GNS3_PASSWORD")
    if not server or user is None:
        for conf in gns3_conf_candidates():
            if conf.exists():
                cp = configparser.ConfigParser(interpolation=None)
                try:
                    cp.read(conf, encoding="utf-8")
                except configparser.Error:
                    continue
                if "Server" in cp:
                    sec = cp["Server"]
                    host = sec.get("host", "127.0.0.1")
                    if host in ("0.0.0.0", "::", ""):
                        host = "127.0.0.1"
                    port = sec.get("port", "3080")
                    server = server or f"http://{host}:{port}"
                    if sec.get("auth", "false").lower() in ("true", "1", "yes"):
                        user = user or sec.get("user")
                        password = password or sec.get("password")
                    break
    server = (server or "http://127.0.0.1:3080").rstrip("/")
    if not server.startswith("http"):
        server = "http://" + server
    return server, user, password


# --------------------------------------------------------------------------- API
class GNS3:
    def __init__(self, server, user=None, password=None):
        self.base = server + "/v2"
        self.s = requests.Session()
        if user:
            self.s.auth = (user, password or "")

    def _req(self, method, path, **kw):
        url = self.base + path
        try:
            r = self.s.request(method, url, timeout=kw.pop("timeout", 60), **kw)
        except requests.ConnectionError:
            die(f"Cannot reach the GNS3 server at {self.base}. Is the GNS3 GUI open? "
                "(see docs/04-build-a-lab.md)")
        if r.status_code == 401:
            die("GNS3 server refused the credentials. Check Edit > Preferences > Server "
                "(or set GNS3_USER / GNS3_PASSWORD).")
        if r.status_code >= 400:
            try:
                msg = r.json().get("message", r.text)
            except ValueError:
                msg = r.text
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {msg}")
        if r.content and "json" in r.headers.get("Content-Type", ""):
            return r.json()
        return r.text

    def get(self, p, **kw):
        return self._req("GET", p, **kw)

    def post(self, p, json=None, **kw):
        return self._req("POST", p, json=json, **kw)

    def put(self, p, json=None, **kw):
        return self._req("PUT", p, json=json, **kw)

    def delete(self, p, **kw):
        return self._req("DELETE", p, **kw)

    # helpers
    def compute_id(self, prefer=None):
        comps = self.get("/computes")
        ids = {c["compute_id"]: c for c in comps if c.get("connected", True)}
        if prefer:
            if prefer in ids:
                return prefer
            die(f"Compute '{prefer}' is not connected. Connected: {', '.join(ids) or 'none'}")

        def docker(cid):
            return "docker" in ((ids[cid].get("capabilities") or {}).get("node_types") or [])
        # the GNS3 VM, then any other compute that runs Docker (e.g. a VM added as a remote
        # server), then the local server (Linux with Docker)
        order = ["vm"] + sorted(c for c in ids if c not in ("vm", "local")) + ["local"]
        for cid in order:
            if cid in ids and docker(cid):
                return cid
        for cid in order:
            if cid in ids:
                return cid
        die("The GNS3 server has no connected compute. Is the GNS3 VM running?")

    def project_by_name(self, name):
        for p in self.get("/projects"):
            if p["name"] == name:
                return p
        return None

    def template_by_name(self, name):
        for t in self.get("/templates"):
            if t["name"] == name:
                return t
        return None


# --------------------------------------------------------------------------- node kinds
def node_spec(kind, name, data, settings, compute):
    """Return the GNS3 node creation body for one topology node."""
    c = settings
    if kind == "frr":
        return {
            "name": name, "node_type": "docker", "compute_id": compute,
            "symbol": ":/symbols/classic/multilayer_switch.svg" if data.get("role") == "switch"
            else ":/symbols/classic/router.svg",
            "properties": {
                "image": c["frr_image"],
                "adapters": int(data.get("ports", 8)),
                "console_type": "telnet",
                "usage": "CGR router/switch: eth0 = management, GNS3 port ethN = swpN inside. "
                         "Interfaces: /etc/network/interfaces + ifreload -a. Routing: vtysh.",
            },
        }
    if kind == "netauto":
        return {
            "name": name, "node_type": "docker", "compute_id": compute,
            "symbol": ":/symbols/classic/server.svg",
            "properties": {
                "image": c["netauto_image"],
                "adapters": 1,
                "console_type": "telnet",
                "usage": "Automation station. Files in /root/cgr",
            },
        }
    if kind == "host":
        return {
            "name": name, "node_type": "docker", "compute_id": compute,
            "symbol": ":/symbols/classic/server.svg" if data.get("role") == "server"
            else ":/symbols/classic/computer.svg",
            "properties": {
                "image": c["netauto_image"],
                "adapters": int(data.get("ports", 2)),
                "console_type": "telnet",
                "environment": "CGR_ROLE=host",
                "usage": "Linux host (Debian). Data interface: eth1. "
                         "ip addr / ip route, or edit /etc/network/interfaces.",
            },
        }
    if kind == "vpcs":
        return {"name": name, "node_type": "vpcs", "compute_id": compute,
                "symbol": ":/symbols/classic/computer.svg",
                "properties": {"console_type": "telnet"}}
    if kind == "switch":
        ports = int(data.get("ports", 8))
        return {
            "name": name, "node_type": "ethernet_switch", "compute_id": compute,
            "symbol": ":/symbols/classic/ethernet_switch.svg",
            "properties": {"ports_mapping": [
                {"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1,
                 "ethertype": ""} for i in range(ports)]},
        }
    if kind == "nat":
        return {"name": name, "node_type": "nat", "compute_id": compute, "properties": {}}
    die(f"Unknown node kind '{kind}' for node {name}")


def port_to_adapter(kind, port):
    """'swp3' -> (3, 0); 'eth0' -> (0, 0); 'e0' -> (0, 0); '5' (switch) -> (0, 5)."""
    port = str(port)
    if kind in ("switch",):
        return 0, int(re.sub(r"\D", "", port) or 0)
    if kind in ("vpcs", "nat"):
        return 0, 0
    m = re.fullmatch(r"(swp|eth|e)(\d+)", port)
    if not m:
        die(f"Bad port name '{port}' (use swpN, eth0 or e0)")
    return int(m.group(2)), 0


# --------------------------------------------------------------------------- lab files
def load_topology(labdir):
    labdir = Path(labdir)
    f = labdir / "topology.yml" if labdir.is_dir() else labdir
    if not f.exists():
        die(f"No topology.yml in {labdir}")
    with open(f, encoding="utf-8") as fh:
        topo = yaml.safe_load(fh)
    topo["_dir"] = f.parent
    return topo


def mgmt_interfaces_file(ip, prefix):
    netmask = ipaddress.ip_network(f"0.0.0.0/{prefix}").netmask
    return (
        "# Management interface (written by cgr_lab.py)\n"
        "auto lo\niface lo inet loopback\n\n"
        f"auto eth0\niface eth0 inet static\n    address {ip}\n    netmask {netmask}\n\n"
        "# ---- your data-plane configuration goes below (ifupdown2 syntax), then: ifreload -a\n"
    )


def cmd_check(api, args, settings):
    v = api.get("/version")
    ok(f"GNS3 controller {v.get('version')} at {api.base}")
    if not str(v.get("version", "")).startswith("2.2"):
        warn("These tools are written for GNS3 2.2.x. Other versions may not work.")
    comps = api.get("/computes")
    for c in comps:
        state = "connected" if c.get("connected") else "NOT connected"
        cap = c.get("capabilities", {}) or {}
        print(f"     compute '{c['compute_id']}' ({c.get('name')}): {state}, "
              f"platform={cap.get('platform')}")
    cid = api.compute_id(args.compute)
    ok(f"Using compute '{cid}'")
    cap = next((c.get("capabilities", {}) for c in comps if c["compute_id"] == cid), {}) or {}
    node_types = cap.get("node_types", [])
    if "docker" in node_types:
        ok("Docker nodes supported")
    else:
        warn("Docker is not available on this compute (FRR / netauto nodes need it). "
             "Use the GNS3 VM, or install Docker on Linux.")


def cmd_templates(api, args, settings):
    """Create GUI templates so students can also drag devices by hand."""
    cid = api.compute_id(args.compute)
    wanted = {
        "CGR Router": ("frr", "router"),
        "CGR Switch": ("frr", "switch"),
        "CGR NetAuto": ("netauto", "guest"),
    }
    for tname, (kind, category) in wanted.items():
        spec = node_spec(kind, tname, {"role": category}, settings, cid)
        body = {"name": tname, "compute_id": cid, "category": category,
                "symbol": spec.get("symbol"), "default_name_format": "{name}-{0}",
                "template_type": spec["node_type"]}
        body.update(spec["properties"])
        if kind == "frr":
            body["default_name_format"] = "sw{0}" if category == "switch" else "r{0}"
        else:
            body["default_name_format"] = "netauto{0}"
        existing = api.template_by_name(tname)
        try:
            if existing:
                api.put(f"/templates/{existing['template_id']}", json=body)
                ok(f"Updated template '{tname}'")
            else:
                api.post("/templates", json=body)
                ok(f"Created template '{tname}'")
        except RuntimeError as e:
            warn(f"Template '{tname}': {e}")


def cmd_build(api, args, settings):
    topo = load_topology(args.lab)
    name = args.name or topo["name"]
    cid = api.compute_id(args.compute)
    for n, d in topo["nodes"].items():
        if d.get("kind") not in ("frr", "host", "netauto", "vpcs", "switch", "nat"):
            die(f"Node {n}: unknown kind '{d.get('kind')}'")
    mgmt = ipaddress.ip_network(topo.get("mgmt_subnet", settings["mgmt_subnet"]))

    if api.project_by_name(name):
        if not args.force:
            die(f"Project '{name}' already exists. Use --force to replace it, or --name.")
        cmd_delete(api, argparse.Namespace(project=name), settings, quiet=True)

    info(f"Creating project '{name}' on compute '{cid}'")
    proj = api.post("/projects", json={"name": name, "auto_close": True,
                                        "scene_width": 2000, "scene_height": 1000})
    pid = proj["project_id"]
    try:
        _populate(api, args, settings, topo, name, pid, cid, mgmt)
    except (SystemExit, RuntimeError, KeyboardInterrupt) as e:
        warn("Build failed - removing the half-built project")
        try:
            api.post(f"/projects/{pid}/close")
            api.delete(f"/projects/{pid}")
        except Exception:  # noqa
            pass
        if isinstance(e, RuntimeError):
            die(str(e))
        raise


def _populate(api, args, settings, topo, name, pid, cid, mgmt):
    nodes_def = topo["nodes"]
    created = {}
    need_mgmt = [n for n, d in nodes_def.items() if d.get("mgmt")]
    if need_mgmt:
        ports = max(8, len(need_mgmt) + 1)
        sx, sy = topo.get("mgmt_switch_pos", (-450, -250))
        spec = node_spec("switch", MGMT_SWITCH, {"ports": ports}, settings, cid)
        spec.update({"x": sx, "y": sy})
        created[MGMT_SWITCH] = (api.post(f"/projects/{pid}/nodes", json=spec), "switch")
        ok(f"{MGMT_SWITCH} (management network {mgmt})")

    for nname, d in nodes_def.items():
        kind = d["kind"]
        spec = node_spec(kind, nname, d, settings, cid)
        spec.update({"x": int(d.get("x", 0)), "y": int(d.get("y", 0))})
        try:
            node = api.post(f"/projects/{pid}/nodes", json=spec, timeout=900)
        except RuntimeError as e:
            die(f"Creating {nname} failed: {e}")
        created[nname] = (node, kind)
        ok(f"{nname} ({kind})")

        # ---- per-node files
        nid = node["node_id"]
        if kind == "frr":
            if d.get("mgmt"):
                content = mgmt_interfaces_file(d["mgmt"], mgmt.prefixlen)
            else:
                content = "auto lo\niface lo inet loopback\n"
            if d.get("interfaces"):
                content += "\n" + (topo["_dir"] / d["interfaces"]).read_text(encoding="utf-8")
            api.post(f"/projects/{pid}/nodes/{nid}/files/etc/network/interfaces", data=content)
            if d.get("frr_config"):
                conf = (topo["_dir"] / d["frr_config"]).read_text(encoding="utf-8")
                api.post(f"/projects/{pid}/nodes/{nid}/files/etc/frr/frr.conf", data=conf)
        elif kind == "netauto":
            content = mgmt_interfaces_file(d["mgmt"], mgmt.prefixlen)
            api.post(f"/projects/{pid}/nodes/{nid}/files/etc/network/interfaces", data=content)
            # inventory of this lab for the automation scripts (/root/lab/inventory.yml)
            inv = {"all": {
                "vars": {"ansible_user": settings.get("user", "cgr"),
                         "ansible_password": settings.get("password", "cgrlab"),
                         "ansible_python_interpreter": "/usr/bin/python3"},
                "hosts": {n: {"ansible_host": dd["mgmt"]} for n, dd in nodes_def.items()
                          if dd["kind"] == "frr" and dd.get("mgmt")}}}
            api.post(f"/projects/{pid}/nodes/{nid}/files/root/lab/inventory.yml",
                     data=f"# Ansible/CGR inventory generated by cgr_lab.py for lab {name}\n"
                          + yaml.safe_dump(inv, sort_keys=False))
        elif kind == "host":
            content = "auto lo\niface lo inet loopback\n"
            if str(d.get("ip", "")).lower() == "dhcp":
                content += f"\nauto {d.get('dev', 'eth1')}\niface {d.get('dev', 'eth1')} inet dhcp\n"
            elif d.get("ip"):
                ip = ipaddress.ip_interface(d["ip"])
                dev = d.get("dev", "eth1")
                content += (f"\nauto {dev}\niface {dev} inet static\n    address {ip.ip}\n"
                            f"    netmask {ip.netmask}\n")
                if d.get("gw"):
                    content += f"    gateway {d['gw']}\n"
            api.post(f"/projects/{pid}/nodes/{nid}/files/etc/network/interfaces", data=content)
        elif kind == "vpcs" and d.get("ip"):
            if str(d["ip"]).lower() == "dhcp":
                script = f"set pcname {nname}\nip dhcp\n"
            else:
                script = f"set pcname {nname}\nip {d['ip']}" + (f" {d['gw']}" if d.get("gw") else "") + "\n"
            api.post(f"/projects/{pid}/nodes/{nid}/files/startup.vpc", data=script)

    # ---- links
    mgmt_port = 1
    links = [tuple(l) for l in topo.get("links", [])]
    for nname in need_mgmt:
        links.append((f"{nname}:eth0", f"{MGMT_SWITCH}:{mgmt_port}"))
        mgmt_port += 1
    for a, b in links:
        ends = []
        for end in (a, b):
            n, _, p = end.partition(":")
            if n not in created:
                die(f"Link {a} <-> {b}: unknown node '{n}'")
            node, kind = created[n]
            adapter, port = port_to_adapter(kind, p or "0")
            ends.append({"node_id": node["node_id"], "adapter_number": adapter,
                         "port_number": port})
        try:
            api.post(f"/projects/{pid}/links", json={"nodes": ends})
        except RuntimeError as e:
            die(f"Link {a} <-> {b} failed: {e}")
    ok(f"{len(links)} links")

    # ---- title on the canvas
    title = f"{name}  |  mgmt {mgmt}"
    svg = (f'<svg height="30" width="600"><text font-family="Arial" font-size="18" '
           f'font-weight="bold" fill="#1f4e79">{title}</text></svg>')
    try:
        api.post(f"/projects/{pid}/drawings", json={"x": -450, "y": -380, "svg": svg})
    except RuntimeError:
        pass

    ok(f"Project '{name}' ready. In the GNS3 GUI: File > Open project > {name}")
    if args.start:
        cmd_start(api, argparse.Namespace(project=name), settings)
    print_next_steps(name, topo)


def print_next_steps(name, topo):
    rel = topo["_dir"]
    try:
        rel = rel.relative_to(REPO)
    except ValueError:
        pass
    print("\nNext steps:")
    print(f"  1. Start all nodes (GUI play button, or: cgr_lab.py start {name})")
    print("  2. Double-click a node in GNS3 to open its console")
    print(f"  3. Follow the lab guide: {rel}/README.md")


def cmd_start(api, args, settings):
    p = api.project_by_name(args.project) or die(f"No project '{args.project}'")
    api.post(f"/projects/{p['project_id']}/open")
    info("Starting all nodes (Docker images are downloaded the first time - be patient)")
    api.post(f"/projects/{p['project_id']}/nodes/start", timeout=1800)
    ok("All nodes started")


def cmd_stop(api, args, settings):
    p = api.project_by_name(args.project) or die(f"No project '{args.project}'")
    api.post(f"/projects/{p['project_id']}/nodes/stop", timeout=600)
    ok("All nodes stopped")


def cmd_delete(api, args, settings, quiet=False):
    p = api.project_by_name(args.project)
    if not p:
        die(f"No project '{args.project}'")
    try:
        api.post(f"/projects/{p['project_id']}/close")
    except RuntimeError:
        pass
    api.delete(f"/projects/{p['project_id']}")
    if not quiet:
        ok(f"Deleted project '{args.project}'")


def project_nodes(api, name):
    p = api.project_by_name(name) or die(f"No project '{name}'")
    if p.get("status") != "opened":
        api.post(f"/projects/{p['project_id']}/open")
    return p, api.get(f"/projects/{p['project_id']}/nodes")


def console_host_for(node, server):
    host = node.get("console_host") or ""
    if host in ("", "0.0.0.0", "::", "0:0:0:0:0:0:0:0"):
        host = re.sub(r"^https?://", "", server).rsplit(":", 1)[0]
    return host.strip("[]")


def cmd_consoles(api, args, settings):
    _, nodes = project_nodes(api, args.project)
    for n in sorted(nodes, key=lambda x: x["name"]):
        if n.get("console"):
            print(f"  {n['name']:<12} {n['status']:<8} telnet {console_host_for(n, args.server_url)} {n['console']}")


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Build and manage CGR GNS3 labs")
    ap.add_argument("--server", help="GNS3 controller URL, e.g. http://127.0.0.1:3080")
    ap.add_argument("--user")
    ap.add_argument("--password")
    ap.add_argument("--compute", help="compute id to use (default: the GNS3 VM, else another compute with Docker, else local)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="test the connection and the prerequisites")
    sub.add_parser("templates", help="create the CGR device templates in the GNS3 GUI")
    s = sub.add_parser("build", help="create a GNS3 project from labs/<lab>/topology.yml")
    s.add_argument("lab")
    s.add_argument("--name", help="project name (default: lab name)")
    s.add_argument("--force", action="store_true", help="replace an existing project")
    s.add_argument("--start", action="store_true", help="start all nodes afterwards")
    for c in ("start", "stop", "delete", "consoles"):
        s = sub.add_parser(c, help=f"{c} a lab project")
        s.add_argument("project")
    args = ap.parse_args()

    settings = load_settings()
    server, user, password = connection_settings(args)
    args.server_url = server
    api = GNS3(server, user, password)
    handlers = {"check": cmd_check, "templates": cmd_templates,
                "build": cmd_build, "start": cmd_start, "stop": cmd_stop, "delete": cmd_delete,
                "consoles": cmd_consoles}
    try:
        handlers[args.cmd](api, args, settings)
    except RuntimeError as e:
        die(str(e))
    except KeyboardInterrupt:
        die("interrupted")


if __name__ == "__main__":
    main()
