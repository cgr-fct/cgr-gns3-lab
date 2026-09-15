#!/usr/bin/env python3
"""
nvue.py - a tiny client for the NVIDIA Cumulus Linux NVUE REST API.

NVUE workflow (same as the CLI `nv set ...` + `nv config apply`):
  1. POST  /nvue_v1/revision                      -> new (empty) revision id
  2. PATCH /nvue_v1/<path>?rev=<id>   {json}      -> stage changes in that revision
  3. PATCH /nvue_v1/revision/<id>     {"state":"apply", ...}  -> apply it
  4. GET   /nvue_v1/revision/<id>                 -> poll until "applied"

Use it as a library:
    from nvue import Nvue
    sw = Nvue("192.168.100.11")
    print(sw.get("/system"))
    sw.set("/", {"system": {"message": {"pre-login": "Hello CGR"}}})

or from the shell:
    ./nvue.py show sw1 /interface
    ./nvue.py show sw1 /interface/swp1 --rev operational
    ./nvue.py set  sw1 /system '{"hostname": "sw1"}'
    ./nvue.py set  sw1 / @my_change.json
    ./nvue.py unset sw1 /interface/swp1/description
    ./nvue.py backup all            # saves backups/<device>.json
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
import urllib3
import yaml

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
HERE = Path(__file__).resolve().parent


class NvueError(RuntimeError):
    pass


class Nvue:
    def __init__(self, host, user="cumulus", password=None, port=8765, timeout=30):
        self.base = f"https://{host}:{port}/nvue_v1"
        self.s = requests.Session()
        self.s.auth = (user, password or os.environ.get("CGR_PASSWORD", "CumulusLab1!"))
        self.s.verify = False          # lab devices use self-signed certificates
        self.s.headers["Content-Type"] = "application/json"
        self.timeout = timeout

    # -- low level ---------------------------------------------------------
    def _call(self, method, path, params=None, body=None):
        url = self.base + "/" + path.strip("/")
        if path.strip("/") == "":
            url = self.base + "/"
        r = self.s.request(method, url, params=params,
                           data=None if body is None else json.dumps(body),
                           timeout=self.timeout, verify=False)
        if r.status_code == 403:
            raise NvueError(f"{method} {url}: 403 Forbidden - wrong password, or the "
                            "default 'cumulus' password was never changed")
        if r.status_code >= 400:
            raise NvueError(f"{method} {url}: {r.status_code} {r.text[:500]}")
        return r.json() if r.content else {}

    # -- read --------------------------------------------------------------
    def get(self, path="/", rev="applied", filled=False):
        """rev: 'applied' (config), 'startup', 'operational' (state), or a revision id."""
        params = {"rev": rev}
        if rev == "operational":
            params = {}
        if not filled and rev != "operational":
            params["filled"] = "false"
        return self._call("GET", path, params=params)

    # -- write -------------------------------------------------------------
    def new_revision(self):
        res = self._call("POST", "/revision")
        return next(iter(res))                     # {"<rev-id>": {...}}

    def _rev_path(self, rev):
        return "/revision/" + quote(str(rev), safe="")

    def patch(self, path, body, rev):
        return self._call("PATCH", path, params={"rev": rev}, body=body)

    def delete(self, path, rev):
        return self._call("DELETE", path, params={"rev": rev})

    def apply(self, rev, wait=120):
        self._call("PATCH", self._rev_path(rev),
                   body={"state": "apply", "auto-prompt": {"ays": "ays_yes"}})
        end = time.time() + wait
        state = "?"
        while time.time() < end:
            st = self._call("GET", self._rev_path(rev))
            state = st.get("state", "?")
            if state == "applied":
                return st
            if state in ("apply_fail", "invalid", "ays_fail", "ignore_fail", "failed"):
                raise NvueError(f"revision {rev} failed: {json.dumps(st, indent=1)[:800]}")
            time.sleep(1.5)
        raise NvueError(f"revision {rev} still '{state}' after {wait}s")

    def set(self, path, body):
        """Stage + apply in one go (like `nv set ...; nv config apply`)."""
        rev = self.new_revision()
        self.patch(path, body, rev)
        return self.apply(rev)

    def unset(self, path):
        rev = self.new_revision()
        self.delete(path, rev)
        return self.apply(rev)

    # Note: since Cumulus Linux 5.x, "apply" also saves to the startup config
    # (unless `nv set system config auto-save state disabled` was configured).


# ---------------------------------------------------------------------------
def load_inventory(path=None):
    path = Path(path or os.environ.get("CGR_INVENTORY", HERE / "inventory.yml"))
    with open(path, encoding="utf-8") as f:
        inv = yaml.safe_load(f)
    defaults = inv.get("defaults", {})
    devices = {}
    for name, d in (inv.get("devices") or {}).items():
        dd = dict(defaults)
        dd.update(d or {})
        devices[name] = dd
    return devices


def connect(name, inventory=None):
    devs = load_inventory(inventory)
    if name in devs:
        d = devs[name]
        return Nvue(d["host"], d.get("user", "cumulus"), d.get("password"))
    return Nvue(name)  # allow a raw IP address


def _body(arg):
    if arg.startswith("@"):
        text = Path(arg[1:]).read_text(encoding="utf-8")
        return yaml.safe_load(text)      # JSON is valid YAML, so both work
    return json.loads(arg)


def main():
    ap = argparse.ArgumentParser(description="NVUE REST API helper")
    ap.add_argument("-i", "--inventory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show"); s.add_argument("device"); s.add_argument("path", nargs="?", default="/")
    s.add_argument("--rev", default="applied", help="applied | startup | operational | <id>")
    s = sub.add_parser("set"); s.add_argument("device"); s.add_argument("path")
    s.add_argument("body", help="JSON text or @file.json/@file.yml")
    s = sub.add_parser("unset"); s.add_argument("device"); s.add_argument("path")
    s = sub.add_parser("backup"); s.add_argument("device", help="device name or 'all'")
    args = ap.parse_args()

    try:
        if args.cmd == "show":
            print(json.dumps(connect(args.device, args.inventory).get(args.path, rev=args.rev), indent=2))
        elif args.cmd == "set":
            st = connect(args.device, args.inventory).set(args.path, _body(args.body))
            print("applied:", st.get("state"))
        elif args.cmd == "unset":
            st = connect(args.device, args.inventory).unset(args.path)
            print("applied:", st.get("state"))
        elif args.cmd == "backup":
            names = list(load_inventory(args.inventory)) if args.device == "all" else [args.device]
            out = HERE / "backups"
            out.mkdir(exist_ok=True)
            for n in names:
                try:
                    cfg = connect(n, args.inventory).get("/")
                    (out / f"{n}.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
                    print(f"saved backups/{n}.json")
                except (NvueError, requests.RequestException) as e:
                    print(f"{n}: {e}", file=sys.stderr)
    except (NvueError, requests.RequestException) as e:
        sys.exit(f"ERROR: {e}")


if __name__ == "__main__":
    main()
