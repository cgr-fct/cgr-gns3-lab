#!/usr/bin/env python3
"""
restconf.py - a small RESTCONF client for the lab devices (library + command line).

    from restconf import Restconf
    rc = Restconf("192.168.100.11")                       # user/password cgr/cgrlab
    rc.get("interface=swp1")                               # GET  .../cgr-device:device/interface=swp1
    rc.put("svi=10", {"cgr-device:svi": [{"vlan": 10, "address": ["10.10.10.1/24"]}]})
    rc.patch("", {"cgr-device:device": {"hostname": "sw1"}})
    rc.post("", {"cgr-device:interface": [{"name": "swp3", "mode": "access", "access-vlan": 10}]})
    rc.delete("interface=swp3")

Paths are relative to /restconf/data/cgr-device:device ("" = the device itself).

Command line (device = inventory name or IP address):
    ./restconf.py sw1 get                          # whole device, config + state
    ./restconf.py sw1 get state/route --content nonconfig
    ./restconf.py sw1 get interface=swp1 --content config
    ./restconf.py sw1 put ospf @ospf.json          # body from a file (JSON or YAML)
    ./restconf.py sw1 patch "" '{"cgr-device:device": {"hostname": "sw1"}}'
    ./restconf.py sw1 post "" @new-interface.yml
    ./restconf.py sw1 delete interface=swp3
    ./restconf.py sw1 get --raw /restconf/data/ietf-yang-library:modules-state
    ./restconf.py sw1 get --raw /restconf/yang/cgr-device@2026-09-15.yang
    ./restconf.py sw1 get -v interface=swp1        # also print the HTTP request and response
"""
import argparse
import json
import sys
from pathlib import Path

import requests
import urllib3
import yaml

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
MIME = "application/yang-data+json"
ROOT = "/restconf/data/cgr-device:device"


class RestconfError(RuntimeError):
    def __init__(self, response):
        self.response = response
        try:
            errs = response.json()["ietf-restconf:errors"]["error"]
            msg = "; ".join(f"{e.get('error-tag')}: {e.get('error-message')}" for e in errs)
        except (ValueError, KeyError, TypeError):
            msg = response.text[:300]
        super().__init__(f"HTTP {response.status_code} - {msg}")


class Restconf:
    def __init__(self, host, user="cgr", password="cgrlab", port=443, verbose=False, timeout=60):
        self.base = f"https://{host}:{port}"
        self.s = requests.Session()
        self.s.auth = (user, password)
        self.s.verify = False                      # lab devices use self-signed certificates
        self.s.headers.update({"Accept": MIME})
        self.verbose, self.timeout = verbose, timeout

    def url(self, path, raw=False):
        if raw:
            return self.base + path
        path = path.strip("/")
        return self.base + ROOT + ("/" + path if path else "")

    def request(self, method, path, body=None, raw=False, **params):
        url = self.url(path, raw)
        headers = {"Content-Type": MIME} if body is not None else {}
        data = json.dumps(body) if body is not None else None
        if self.verbose:
            q = "&".join(f"{k}={v}" for k, v in params.items())
            print(f">>> {method} {url}{'?' + q if q else ''}", file=sys.stderr)
            if data:
                print(f">>> {data}", file=sys.stderr)
        r = self.s.request(method, url, data=data, headers=headers, params=params or None,
                           timeout=self.timeout, verify=False)
        if self.verbose:
            print(f"<<< {r.status_code} {r.reason}" + (f"  Location: {r.headers['Location']}"
                                                       if "Location" in r.headers else ""), file=sys.stderr)
        if r.status_code >= 400:
            raise RestconfError(r)
        if not r.content:
            return None
        return r.json() if "json" in r.headers.get("Content-Type", "") else r.text

    def get(self, path="", content="all", raw=False):
        return self.request("GET", path, raw=raw, **({} if raw else {"content": content}))

    # force=True adds ?force=true: the device then accepts a change that removes
    # configuration made by hand (CLI) instead of refusing it with 409 resource-denied.
    def put(self, path, body, force=False):
        return self.request("PUT", path, body, **_force(force))

    def patch(self, path, body, force=False):
        return self.request("PATCH", path, body, **_force(force))

    def post(self, path, body, force=False):
        return self.request("POST", path, body, **_force(force))

    def delete(self, path, force=False):
        return self.request("DELETE", path, **_force(force))


def _force(force):
    return {"force": "true"} if force else {}


def _body(arg):
    if arg is None:
        return None
    text = Path(arg[1:]).read_text(encoding="utf-8") if arg.startswith("@") else arg
    return yaml.safe_load(text)             # JSON is valid YAML, so both work


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("device", help="inventory name or IP address")
    ap.add_argument("method", choices=["get", "put", "patch", "post", "delete"])
    ap.add_argument("path", nargs="?", default="", help="path below cgr-device:device ('' = device)")
    ap.add_argument("body", nargs="?", help="JSON/YAML text or @file")
    ap.add_argument("--content", default="all", choices=["all", "config", "nonconfig"])
    ap.add_argument("--raw", action="store_true", help="path is a full URL path (/restconf/...)")
    ap.add_argument("--force", action="store_true",
                    help="write even if configuration made by hand (CLI) would be removed")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("-i", "--inventory")
    args = ap.parse_args()

    host, user, pw = args.device, "cgr", "cgrlab"
    try:
        from cgrlib import load_inventory
        inv = load_inventory(args.inventory)
        if args.device in inv:
            d = inv[args.device]
            host, user, pw = d["host"], d.get("user", "cgr"), d.get("password", "cgrlab")
    except (OSError, ImportError):
        pass
    rc = Restconf(host, user, pw, verbose=args.verbose)
    try:
        if args.method == "get":
            out = rc.get(args.path, args.content, raw=args.raw)
        elif args.method == "delete":
            out = rc.delete(args.path, force=args.force)
        else:
            body = _body(args.body)
            if body is None:
                sys.exit("this method needs a body")
            out = getattr(rc, args.method)(args.path, body, force=args.force)
    except RestconfError as e:
        sys.exit(f"ERROR: {e}")
    except requests.RequestException as e:
        sys.exit(f"ERROR: cannot reach {host}: {e}")
    if out is None:
        print("OK")
    elif isinstance(out, str):
        print(out)
    else:
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
