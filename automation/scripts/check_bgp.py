#!/usr/bin/env python3
"""
check_bgp.py - check the Lab 04 requirements by reading the routers' state over RESTCONF.

STARTING POINT (Lab 04, part B): one check is written; add one check per requirement.

    ./scripts/check_bgp.py            run all checks, exit code 0 only if all pass

Each router's RESTCONF server returns its live state under cgr-device:device/state:
    state/bgp-neighbor   [{address, remote-as, state, prefixes-received}]
    state/route          [{prefix, protocol, next-hop: [...]}]   (the routing table)
    state/interface      [{name, oper-status, address: [...]}]
    state/ospf-neighbor  [{router-id, interface, state, address}]
Try: ./restconf.py R4 get state/route --content nonconfig
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # /root/cgr
from cgrlib import load_inventory      # noqa: E402
from restconf import Restconf          # noqa: E402

inv = load_inventory()
results = []


def state(router, what):
    """GET .../cgr-device:device/state/<what> on a router; returns a list of entries."""
    r = Restconf(inv[router]["host"])
    data = r.get(f"state/{what}", content="nonconfig")
    return data.get(f"cgr-device:{what}", [])


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


# ---- requirement 6: every BGP session is Established
for router in ["R1", "R2", "R3", "R4", "R5", "R6"]:
    peers = state(router, "bgp-neighbor")
    down = [p["address"] for p in peers if p.get("state") != "Established"]
    check(f"{router} BGP sessions", peers and not down,
          f"{len(peers)} peers" + (f", not established: {down}" if down else ""))

# ---- TODO: requirements 7 and 8 (only the summaries are announced between the ASes)
# ---- TODO: requirement 9 (R4's path to the Bank network)
# ---- TODO: requirement 10 (the Bank's exit to the Provider networks)
# ---- TODO: requirement 2/3/5 (OSPF neighbours, the eBGP links are not in OSPF)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
