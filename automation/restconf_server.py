#!/usr/bin/env python3
"""
restconf_server.py - a small RESTCONF (RFC 8040) server for the CGR lab routers/switches.

It serves ONE YANG module, cgr-device (yang/cgr-device@2026-09-15.yang), as JSON (RFC 7951):

    GET    /.well-known/host-meta
    GET    /restconf                                   API root
    GET    /restconf/yang-library-version
    GET    /restconf/data/ietf-yang-library:modules-state
    GET    /restconf/yang/cgr-device@2026-09-15.yang   the module source
    GET    /restconf/data[/cgr-device:device[/...]]    ?content=config|nonconfig|all (default all)
    PUT    /restconf/data[/cgr-device:device[/...]]    create or replace the target
    PATCH  /restconf/data[/cgr-device:device[/...]]    merge into the target ("plain patch")
    POST   /restconf/data/cgr-device:device[/...]      create a child of the target
    DELETE /restconf/data/cgr-device:device/...        delete the target

Every change is validated against the YANG model (yangson), rendered with the same Jinja2
templates as apply_intent.py, and applied to the device (ifupdown2, frr-reload, dhcpd). If the
change cannot be applied, the previous configuration is restored.

The configuration datastore is the JSON file /etc/cgr/running.json. It only contains what was
configured through RESTCONF or apply_intent.py: settings typed by hand in vtysh or in
/etc/network/interfaces are not read back (but they are visible in the operational state).

Runs on HTTPS port 443 with a self-signed certificate and HTTP Basic authentication
(users in /etc/cgr/restconf-users, "user:password" per line; default cgr:cgrlab).
"""
import argparse
import base64
import copy
import hmac
import json
import os
import ssl
import subprocess
import sys
import threading
import traceback
from datetime import datetime, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cgrimport  # noqa: E402
import cgrmodel  # noqa: E402

MOD = cgrmodel.MODULE
TOP = cgrmodel.TOP
YANG_FILE = next((cgrmodel.HERE / "yang").glob(f"{MOD}@*.yang"))
MIME = "application/yang-data+json"

ETC = Path(os.environ.get("CGR_ETC", "/etc/cgr"))
RUNNING = ETC / "running.json"
USERS = ETC / "restconf-users"
LOCK = threading.Lock()
LAST_CHANGE = [datetime.now(timezone.utc)]
DRY_RUN = [False]


# ------------------------------------------------------------------ errors
class RCError(Exception):
    def __init__(self, status, tag, message, etype="application", path=None):
        super().__init__(message)
        self.status, self.tag, self.etype, self.path = status, tag, etype, path

    def body(self):
        err = {"error-type": self.etype, "error-tag": self.tag, "error-message": str(self)}
        if self.path:
            err["error-path"] = self.path
        return {"ietf-restconf:errors": {"error": [err]}}


# ------------------------------------------------------------------ schema helpers
def schema_children(snode):
    """{name: schema node} of the data children of a yangson schema node."""
    out = {}
    for c in getattr(snode, "children", []):
        if type(c).__name__ in ("ChoiceNode", "CaseNode"):
            out.update(schema_children(c))
        else:
            out[c.name] = c
    return out


def kind(snode):
    return {"ContainerNode": "container", "ListNode": "list", "LeafNode": "leaf",
            "LeafListNode": "leaf-list"}.get(type(snode).__name__, "other")


def keys_of(snode):
    return [k[0] for k in getattr(snode, "keys", [])]


def is_config(snode):
    return snode.content_type().name != "nonconfig"


def parse_path(path):
    """'/cgr-device:device/interface=swp1/description' -> [(name, [keyvals]|None), ...]"""
    steps = []
    for i, seg in enumerate([s for s in path.split("/") if s]):
        name, eq, keys = seg.partition("=")
        name = unquote(name)
        if ":" in name:
            prefix, name = name.split(":", 1)
            if prefix != MOD:
                raise RCError(404, "invalid-value", f"unknown module '{prefix}'", "protocol")
        elif i == 0:
            raise RCError(400, "malformed-message",
                          "the first path segment must be module-qualified (cgr-device:device)", "protocol")
        steps.append((name, [unquote(k) for k in keys.split(",")] if eq else None))
    return steps


class Target:
    """A resolved RESTCONF target inside the data tree."""

    def __init__(self, steps):
        self.steps = steps
        root = schema_children(cgrmodel.data_model().schema)
        if not steps or steps[0][0] != "device":
            raise RCError(404, "invalid-value", "resource not found (only cgr-device:device exists)", "protocol")
        self.snodes, snode, children = [], None, root
        for name, keys in steps:
            if name not in children:
                raise RCError(404, "invalid-value", f"no schema node '{name}'", "protocol")
            snode = children[name]
            k = kind(snode)
            if keys is not None and k == "list" and len(keys) != len(keys_of(snode)):
                raise RCError(400, "invalid-value", f"'{name}' needs keys: {', '.join(keys_of(snode))}", "protocol")
            if keys is not None and k not in ("list", "leaf-list"):
                raise RCError(400, "invalid-value", f"'{name}' is not a list", "protocol")
            self.snodes.append(snode)
            children = schema_children(snode)
        self.snode = snode
        self.kind = kind(snode)
        self.name, self.keys = steps[-1]

    # -- navigation on plain JSON (dict/list) -------------------------------
    @staticmethod
    def _match(entry, snode, keys):
        return all(str(entry.get(k)) == v for k, v in zip(keys_of(snode), keys))

    def locate(self, data, create=False):
        """Return (parent_obj, getter) for the target; parent is the dict holding the member."""
        node = data                      # data = {"device": {...}}
        for idx, ((name, keys), snode) in enumerate(zip(self.steps, self.snodes)):
            last = idx == len(self.steps) - 1
            k = kind(snode)
            if last:
                return node, name, keys, snode
            if k == "list":
                entries = node.get(name)
                if entries is None:
                    if not create:
                        return None, name, keys, snode
                    entries = node[name] = []
                match = [e for e in entries if self._match(e, snode, keys or [])] if keys else []
                if not match:
                    if not create or keys is None:
                        return None, name, keys, snode
                    entry = dict(zip(keys_of(snode), [self._typed(snode, kk, v) for kk, v in zip(keys_of(snode), keys)]))
                    entries.append(entry)
                    match = [entry]
                node = match[0]
            else:
                if name not in node:
                    if not create:
                        return None, name, keys, snode
                    node[name] = {}
                node = node[name]
        raise AssertionError

    @staticmethod
    def _typed(list_snode, key, value):
        leaf = schema_children(list_snode)[key]
        base = type(leaf.type).__name__.lower()
        if ("int" in base or base == "uniontype") and value.isdigit():
            return int(value)
        return value

    def get(self, data):
        parent, name, keys, snode = self.locate(data)
        if parent is None or name not in parent:
            return None
        value = parent[name]
        if self.kind == "list" and keys is not None:
            found = [e for e in value if self._match(e, snode, keys)]
            return found or None
        if self.kind == "leaf-list" and keys is not None:
            found = [v for v in value if str(v) == keys[0]]
            return found or None
        return value

    def qname(self):
        return f"{MOD}:{self.name}"


# ------------------------------------------------------------------ merge / body
def merge(dst, src, snode):
    """RFC 7951 merge of src into dst (both plain JSON for the schema node snode)."""
    children = schema_children(snode)
    for name, value in src.items():
        c = children.get(name)
        if c is None:
            raise RCError(400, "unknown-element", f"unknown element '{name}'")
        k = kind(c)
        if k == "container":
            if not isinstance(value, dict):
                raise RCError(400, "invalid-value", f"'{name}' must be an object")
            merge(dst.setdefault(name, {}), value, c)
        elif k == "list":
            if not isinstance(value, list):
                raise RCError(400, "invalid-value", f"'{name}' must be an array")
            entries = dst.setdefault(name, [])
            for item in value:
                keyvals = [str(item.get(kk)) for kk in keys_of(c)]
                cur = [e for e in entries if Target._match(e, c, keyvals)]
                if cur:
                    merge(cur[0], item, c)
                else:
                    entries.append(copy.deepcopy(item))
        elif k == "leaf-list":
            if not isinstance(value, list):
                raise RCError(400, "invalid-value", f"'{name}' must be an array")
            cur = dst.setdefault(name, [])
            cur.extend(v for v in value if v not in cur)
        else:
            dst[name] = value


def body_value(body, target):
    """Extract the value for the target from a request body {"cgr-device:<name>": value}."""
    if not isinstance(body, dict) or len(body) != 1:
        raise RCError(400, "malformed-message", "the body must be a JSON object with exactly one member")
    (member, value), = body.items()
    name = member.split(":", 1)[-1]
    if name != target.name:
        raise RCError(400, "invalid-value", f"body member '{member}' does not match the target '{target.qname()}'")
    if target.kind == "list" and target.keys is not None:
        if not (isinstance(value, list) and len(value) == 1):
            raise RCError(400, "invalid-value", "a list entry must be sent as an array with one object")
        entry = value[0]
        for k, v in zip(keys_of(target.snode), target.keys):
            if str(entry.get(k)) != v:
                raise RCError(400, "invalid-value", f"key '{k}' in the body does not match the URI")
        return value
    return value


# ------------------------------------------------------------------ datastore + apply
def load_running():
    try:
        return json.loads(RUNNING.read_text())
    except (OSError, ValueError):
        return {}


def run(cmd):
    return subprocess.run(["sh", "-c", cmd], capture_output=True, text=True)


def guard_handmade(new, old):
    """Refuse a write that would silently remove configuration typed by hand (CLI)."""
    losses = cgrimport.handmade_losses(cgrimport.snapshot_local(), old, new)
    if not losses:
        return
    shown = "; ".join(losses[:10]) + (f"; ... and {len(losses) - 10} more" if len(losses) > 10 else "")
    raise RCError(409, "resource-denied",
                  f"this write would remove {len(losses)} setting(s) made by hand (not through the model): "
                  f"{shown}. Add them to the data (apply_intent.py <file> --import <device> reads them) "
                  f"or repeat the request with ?force=true to remove them")


def apply_config(new, old, force=False):
    """Validate, render and apply `new` (content of cgr-device:device); roll back on failure."""
    errors = cgrmodel.validate(new)
    if errors:
        raise RCError(400, "invalid-value", "; ".join(errors))
    if DRY_RUN[0]:
        RUNNING.write_text(json.dumps(new, indent=2))
        return
    if not force:
        guard_handmade(new, old)
    files, commands = cgrmodel.render(new)
    eni_path = Path("/etc/network/interfaces")
    targets = [eni_path] + [Path(p) for p in files if p.startswith("/")]
    backup = {p: (p.read_text() if p.exists() else None) for p in targets}
    try:
        eni_path.write_text(cgrmodel.merge_interfaces(backup[eni_path] or "",
                                                     files.pop("interfaces-dataplane")))
        for p, content in files.items():
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            Path(p).write_text(content)
        for cmd in commands:
            r = run(cmd)
            if r.returncode:
                raise RCError(400, "operation-failed",
                              f"'{cmd}' failed: {cgrmodel.short_error(r.stderr or r.stdout)}")
    except Exception:
        for p, content in backup.items():
            if content is None:
                p.unlink(missing_ok=True)
            else:
                p.write_text(content)
        if old is not None:
            for cmd in cgrmodel.render(old)[1]:
                run(cmd)
        raise
    tmp = RUNNING.with_suffix(".tmp")
    tmp.write_text(json.dumps(new, indent=2))
    tmp.replace(RUNNING)
    LAST_CHANGE[0] = datetime.now(timezone.utc)


# ------------------------------------------------------------------ operational state
def _json(cmd):
    r = run(cmd)
    try:
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
    except ValueError:
        return {}


def read_state():
    st = {"interface": [], "route": [], "ospf-neighbor": [], "bgp-neighbor": []}
    for i in _json("ip -j addr show") or []:
        entry = {"name": i.get("ifname"), "oper-status": str(i.get("operstate", "")).lower(),
                 "mtu": i.get("mtu", 0)}
        if i.get("address"):
            entry["mac-address"] = i["address"]
        addrs = [f"{a['local']}/{a['prefixlen']}" for a in i.get("addr_info", []) if a.get("family") == "inet"]
        if addrs:
            entry["address"] = addrs
        st["interface"].append(entry)
    for prefix, routes in (_json("vtysh -c 'show ip route json'") or {}).items():
        best = next((r for r in routes if r.get("selected")), routes[0] if routes else None)
        if not best:
            continue
        hops = [h.get("ip") or h.get("interfaceName", "") for h in best.get("nexthops", [])]
        entry = {"prefix": prefix, "protocol": best.get("protocol", "")}
        if [h for h in hops if h]:
            entry["next-hop"] = [h for h in hops if h]
        st["route"].append(entry)
    ospf = _json("vtysh -c 'show ip ospf neighbor json'") or {}
    for rid, nbrs in (ospf.get("neighbors") or {}).items():
        for n in nbrs if isinstance(nbrs, list) else [nbrs]:
            iface = (n.get("ifaceName") or n.get("interfaceName") or "").split(":")[0]
            entry = {"router-id": rid, "interface": iface,
                     "state": n.get("state") or n.get("nbrState") or ""}
            addr = n.get("address") or n.get("ifaceAddress")
            if addr:
                entry["address"] = addr
            st["ospf-neighbor"].append(entry)
    bgp = _json("vtysh -c 'show bgp summary json'") or {}
    peers = (bgp.get("ipv4Unicast") or {}).get("peers") or {}
    for addr, p in peers.items():
        entry = {"address": addr, "state": p.get("state", "")}
        if isinstance(p.get("remoteAs"), int):
            entry["remote-as"] = p["remoteAs"]
        if isinstance(p.get("pfxRcd"), int):
            entry["prefixes-received"] = p["pfxRcd"]
        st["bgp-neighbor"].append(entry)
    return {k: v for k, v in st.items() if v}


def filter_content(value, snode, content):
    """Keep config / nonconfig parts of a JSON value according to ?content=."""
    if content == "all" or not isinstance(value, (dict, list)):
        return value
    if isinstance(value, list):
        items = [filter_content(v, snode, content) for v in value]
        return [v for v in items if v not in ({}, [])] if content == "nonconfig" else items
    out = {}
    children = schema_children(snode)
    for name, v in value.items():
        c = children.get(name)
        if c is None:
            continue
        if content == "config" and not is_config(c):
            continue
        if content == "nonconfig" and kind(c) in ("leaf", "leaf-list") and is_config(c):
            continue
        fv = filter_content(v, c, content)
        if fv in ({}, []) and content == "nonconfig":
            continue
        out[name] = fv
    return out


# ------------------------------------------------------------------ HTTP handler
class Handler(BaseHTTPRequestHandler):
    server_version = "cgr-restconf/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[restconf] %s %s\n" % (self.address_string(), fmt % args))

    # -- plumbing ---------------------------------------------------------------
    def send(self, status, body=None, headers=None, ctype=MIME):
        data = b""
        if body is not None:
            data = (body if isinstance(body, str) else json.dumps(body, indent=2)).encode()
        self.send_response(status)
        if data:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Last-Modified", format_datetime(LAST_CHANGE[0], usegmt=True))
        self.send_header("Cache-Control", "no-cache")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if data and self.command != "HEAD":
            self.wfile.write(data)

    def authorized(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return False
        try:
            user, _, pw = base64.b64decode(auth[6:]).decode().partition(":")
        except Exception:  # noqa: BLE001
            return False
        try:
            lines = USERS.read_text().splitlines()
        except OSError:
            lines = ["cgr:cgrlab"]
        for line in lines:
            u, _, p = line.strip().partition(":")
            if u and hmac.compare_digest(u, user) and hmac.compare_digest(p, pw):
                return True
        return False

    def read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if ctype not in (MIME, "application/json", "application/yang-data+json"):
            raise RCError(415, "invalid-value",
                          "only application/yang-data+json is supported", "protocol")
        try:
            return json.loads(raw or b"null")
        except ValueError as e:
            raise RCError(400, "malformed-message", f"invalid JSON: {e}", "protocol") from None

    def handle_any(self):
        try:
            url = urlsplit(self.path)
            path, query = url.path, parse_qs(url.query)
            if path == "/.well-known/host-meta":
                xrd = ('<XRD xmlns="http://docs.oasis-open.org/ns/xri/xrd-1.0">\n'
                       '  <Link rel="restconf" href="/restconf"/>\n</XRD>\n')
                return self.send(200, xrd, ctype="application/xrd+xml")
            if not self.authorized():
                return self.send(401, RCError(401, "access-denied", "authentication required",
                                              "protocol").body(),
                                 {"WWW-Authenticate": 'Basic realm="restconf"'})
            path = path.rstrip("/") or "/"
            if path == "/restconf":
                return self.only_get(lambda: {"ietf-restconf:restconf": {
                    "data": {}, "operations": {}, "yang-library-version": "2016-06-21"}})
            if path == "/restconf/yang-library-version":
                return self.only_get(lambda: {"ietf-restconf:yang-library-version": "2016-06-21"})
            if path == "/restconf/operations":
                return self.only_get(lambda: {"ietf-restconf:operations": {}})
            if path == "/restconf/data/ietf-yang-library:modules-state":
                def lib():
                    lib = json.loads((cgrmodel.HERE / "yang" / "yang-library.json").read_text())
                    for m in lib["ietf-yang-library:modules-state"]["module"]:
                        m["schema"] = f"https://{self.headers.get('Host', 'device')}/restconf/yang/{YANG_FILE.name}"
                    return lib
                return self.only_get(lib)
            if path == f"/restconf/yang/{YANG_FILE.name}":
                return self.only_get(lambda: YANG_FILE.read_text(), ctype="application/yang")
            if path == "/restconf/data" or path.startswith("/restconf/data/"):
                return self.data(path[len("/restconf/data"):], query)
            raise RCError(404, "invalid-value", "unknown resource", "protocol")
        except RCError as e:
            self.send(e.status, e.body())
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.send(500, RCError(500, "operation-failed", f"{type(e).__name__}: {e}").body())

    def only_get(self, producer, ctype=MIME):
        if self.command not in ("GET", "HEAD"):
            raise RCError(405, "operation-not-supported", "only GET is allowed here", "protocol")
        self.send(200, producer(), ctype=ctype)

    # -- the datastore ----------------------------------------------------------
    def data(self, path, query):
        content = query.get("content", ["all"])[0]
        force = query.get("force", ["false"])[0].lower() in ("true", "1", "yes")
        if content not in ("all", "config", "nonconfig"):
            raise RCError(400, "invalid-value", "content must be all, config or nonconfig", "protocol")
        steps = parse_path(path)
        method = self.command

        if method in ("GET", "HEAD"):
            tree = {"device": load_running()}
            if content != "config":
                tree["device"]["state"] = read_state()
            if not steps:
                dev = filter_content(tree["device"], Target([("device", None)]).snode, content)
                return self.send(200, {TOP: dev})
            t = Target(steps)
            value = t.get(tree)
            if value is None:
                raise RCError(404, "invalid-value", "the requested data does not exist", path=path)
            value = filter_content(value, t.snode, content)
            return self.send(200, {t.qname(): value})

        with LOCK:
            old = load_running()
            tree = {"device": copy.deepcopy(old)}
            status = 204
            headers = {}

            if not steps:                        # the whole datastore
                if method == "DELETE":
                    raise RCError(405, "operation-not-supported", "cannot delete the datastore", "protocol")
                body = self.read_body()
                t = Target([("device", None)])
                if method == "POST":
                    if old:
                        raise RCError(409, "data-exists", "cgr-device:device already exists")
                    tree["device"] = body_value(body, t)
                    status, headers = 201, {"Location": "/restconf/data/cgr-device:device"}
                elif method == "PUT":
                    tree["device"] = body_value(body, t)
                elif method == "PATCH":
                    merge(tree["device"], body_value(body, t), t.snode)
                else:
                    raise RCError(405, "operation-not-supported", f"{method} not supported", "protocol")
            else:
                t = Target(steps)
                if not all(is_config(s) for s in t.snodes):
                    raise RCError(405, "operation-not-supported", "state data is read-only", "protocol")
                exists = t.get(tree) is not None
                if method == "DELETE":
                    if not exists:
                        raise RCError(404, "data-missing", "the target does not exist", path=path)
                    self._delete(t, tree)
                elif method == "PUT":
                    value = body_value(self.read_body(), t)
                    self._put(t, tree, value)
                    status = 204 if exists else 201
                elif method == "PATCH":
                    if not exists:
                        raise RCError(404, "data-missing", "the target does not exist (use PUT or POST)", path=path)
                    value = body_value(self.read_body(), t)
                    self._patch(t, tree, value)
                elif method == "POST":
                    body = self.read_body()
                    location = self._post(t, tree, body)
                    status, headers = 201, {"Location": location}
                else:
                    raise RCError(405, "operation-not-supported", f"{method} not supported", "protocol")
            apply_config(tree["device"], old, force)
            self.send(status, None, headers)

    # -- write helpers ---------------------------------------------------------
    def _delete(self, t, tree):
        parent, name, keys, snode = t.locate(tree)
        if t.kind == "list" and keys is not None:
            parent[name] = [e for e in parent[name] if not Target._match(e, snode, keys)]
            if not parent[name]:
                del parent[name]
        elif t.kind == "leaf-list" and keys is not None:
            parent[name] = [v for v in parent[name] if str(v) != keys[0]]
            if not parent[name]:
                del parent[name]
        else:
            del parent[name]
        if not tree.get("device"):
            tree["device"] = {}

    def _put(self, t, tree, value):
        parent, name, keys, snode = t.locate(tree, create=True)
        if t.kind == "list" and keys is not None:
            entries = [e for e in parent.get(name, []) if not Target._match(e, snode, keys)]
            parent[name] = entries + value
        elif t.kind == "leaf-list" and keys is not None:
            cur = parent.setdefault(name, [])
            for v in value:
                if v not in cur:
                    cur.append(v)
        else:
            parent[name] = value

    def _patch(self, t, tree, value):
        parent, name, keys, snode = t.locate(tree)
        if t.kind == "list" and keys is not None:
            entry = [e for e in parent[name] if Target._match(e, snode, keys)][0]
            merge(entry, value[0], snode)
        elif t.kind == "container":
            merge(parent[name], value, snode)
        elif t.kind in ("list", "leaf-list"):
            merge(parent, {name: value}, t.snodes[-2] if len(t.snodes) > 1 else snode)
        else:
            parent[name] = value

    def _post(self, t, tree, body):
        if t.kind not in ("container", "list") or (t.kind == "list" and t.keys is None):
            raise RCError(400, "invalid-value", "POST target must be a container or a list entry")
        if t.get(tree) is None:
            raise RCError(404, "data-missing", "the parent resource does not exist")
        if not isinstance(body, dict) or len(body) != 1:
            raise RCError(400, "malformed-message", "the body must contain exactly one child")
        (member, value), = body.items()
        cname = member.split(":", 1)[-1]
        child_t = Target(t.steps + [(cname, None)])
        parent_obj = t.get(tree)
        if isinstance(parent_obj, list):
            parent_obj = parent_obj[0]
        csn = child_t.snode
        base = "/restconf/data/" + "/".join(
            (f"{MOD}:{n}" if i == 0 else n) + ("=" + ",".join(k) if k else "")
            for i, (n, k) in enumerate(t.steps))
        if child_t.kind == "list":
            if not (isinstance(value, list) and len(value) == 1):
                raise RCError(400, "invalid-value", "a new list entry must be an array with one object")
            keyvals = [str(value[0].get(k)) for k in keys_of(csn)]
            if any(Target._match(e, csn, keyvals) for e in parent_obj.get(cname, [])):
                raise RCError(409, "data-exists", f"{cname} {','.join(keyvals)} already exists")
            parent_obj.setdefault(cname, []).extend(value)
            return f"{base}/{cname}={','.join(keyvals)}"
        if cname in parent_obj:
            raise RCError(409, "data-exists", f"{cname} already exists")
        parent_obj[cname] = value
        return f"{base}/{cname}"

    do_GET = do_HEAD = do_PUT = do_PATCH = do_POST = do_DELETE = handle_any

    def do_OPTIONS(self):
        self.send(200, None, {"Allow": "GET, HEAD, PUT, PATCH, POST, DELETE, OPTIONS",
                              "Accept-Patch": MIME})


# ------------------------------------------------------------------ main
def ensure_cert(cert, key):
    if cert.exists() and key.exists():
        return
    cert.parent.mkdir(parents=True, exist_ok=True)
    host = os.uname().nodename
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "3650",
                    "-subj", f"/CN={host}", "-keyout", str(key), "-out", str(cert)],
                   check=True, capture_output=True)
    key.chmod(0o600)


def main():
    ap = argparse.ArgumentParser(description="CGR RESTCONF server")
    ap.add_argument("--port", type=int, default=443)
    ap.add_argument("--address", default="0.0.0.0")
    ap.add_argument("--no-tls", action="store_true", help="plain HTTP (testing only)")
    ap.add_argument("--dry-run", action="store_true", help="store the config but do not apply it")
    args = ap.parse_args()
    DRY_RUN[0] = args.dry_run
    ETC.mkdir(parents=True, exist_ok=True)
    if not USERS.exists():
        USERS.write_text("cgr:cgrlab\n")
        USERS.chmod(0o600)
    srv = ThreadingHTTPServer((args.address, args.port), Handler)
    if not args.no_tls:
        cert, key = ETC / "restconf.crt", ETC / "restconf.key"
        ensure_cert(cert, key)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    cgrmodel.data_model()           # load the YANG model before serving
    print(f"[restconf] listening on {'http' if args.no_tls else 'https'}://{args.address}:{args.port}",
          flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
