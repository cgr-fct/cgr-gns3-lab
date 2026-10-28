#!/usr/bin/env python3
"""
deploy.py - push the files rendered by generate.py to the fabric's switches (over SSH).

    ./deploy.py                      every node in configs/
    ./deploy.py leaf1 leaf2          only these nodes
    ./deploy.py --dry-run leaf1      show what would change (diff), push nothing
    ./deploy.py -c other-configs     files rendered to another folder

For each node configs/<node>/{interfaces,frr.conf}:
  * /etc/network/interfaces: the management part written by cgr_lab.py is kept, the data-plane
    part (below the "# ---- your data-plane configuration goes below" line) is replaced by
    configs/<node>/interfaces, then `ifreload -a`;
  * /etc/frr/frr.conf: replaced by configs/<node>/frr.conf through frr-reload (only the
    differences are applied to the running FRR), then `write memory`.
The devices are the ones of the lab inventory (/root/lab/inventory.yml), user cgr / cgrlab.
"""
import argparse
import difflib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))          # cgrlib.py lives in /root/cgr
from cgrlib import Device, load_inventory     # noqa: E402

MARKER = "# ---- your data-plane configuration goes below"
# lines FRR writes by itself (defaults of the datacenter profile), not differences of the plan
FRR_AUTO = {"use-underlays-nexthop-weight", "no use-underlays-nexthop-weight",
            "bgp deterministic-med", "no bgp deterministic-med"}


def merged_interfaces(current, dataplane):
    head = current.split(MARKER)[0].rstrip() + "\n\n" if MARKER in current else \
        "auto lo\niface lo inet loopback\n\n"
    return head + MARKER + " (managed by fabric/deploy.py)\n" + dataplane


def show_diff(name, path, old, new):
    diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(),
                                     f"{name}:{path} (now)", f"{name}:{path} (new)", lineterm="", n=1))
    print("\n".join(diff) if diff else f"  {name}:{path} unchanged")


def deploy(dev, files, dry_run):
    name = dev["name"]
    with Device(dev) as d:
        eni_now = d.read_file("/etc/network/interfaces")
        eni_new = merged_interfaces(eni_now, files["interfaces"])
        frr_new = files["frr.conf"]
        if dry_run:
            show_diff(name, "/etc/network/interfaces", eni_now, eni_new)
            # FRR's own view: which lines frr-reload would delete from / add to the running config
            d.write_file("/tmp/frr.conf.test", frr_new)
            _, out, err = d.exec("sudo /usr/lib/frr/frr-reload.py --test /tmp/frr.conf.test")
            lines = [l for l in out.splitlines() if l.strip() and not l.startswith("frr version")
                     and l.strip() not in FRR_AUTO]
            # drop blocks left empty ("router bgp 65101" followed directly by "exit")
            kept = []
            for l in lines:
                if l.strip() == "exit" and kept and not kept[-1].startswith((" ", "Lines", "=")):
                    kept.pop()
                    continue
                kept.append(l)
            lines = [l for i, l in enumerate(kept) if not (l.startswith("Lines To") and
                     (i + 2 >= len(kept) or kept[i + 2].startswith("Lines To")))]
            lines = [l for i, l in enumerate(lines) if not (l.startswith("=") and
                     (i == 0 or not lines[i - 1].startswith("Lines To")))]
            changes = [l for l in lines if not l.startswith(("Lines To", "="))]
            print(f"  {name}: FRR running config" + (" unchanged" if not changes else ":"))
            if changes:
                print("    " + "\n    ".join(lines))
            return
        d.write_file("/etc/network/interfaces", eni_new)
        rc, out, err = d.exec("sudo sh -c 'mkdir -p /run/network && ifreload -a'")
        problems = [l for l in (out + err).splitlines() if "error" in l.lower()]
        if rc or problems:
            print(f"  ! {name}: ifreload reported:\n    " + "\n    ".join(problems or (out + err).splitlines()[-5:]))
        d.write_file("/etc/frr/frr.conf.new", frr_new)
        rc, out, err = d.exec("sudo sh -c \"/usr/lib/frr/frr-reload.py --reload /etc/frr/frr.conf.new"
                              " && vtysh -c 'write memory' >/dev/null\"")
        if rc:
            tail = "\n    ".join((err or out).strip().splitlines()[-8:])
            raise RuntimeError(f"frr-reload failed:\n    {tail}")
        print(f"  {name}: interfaces + frr.conf applied")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("nodes", nargs="*", help="only these nodes (default: all in configs/)")
    ap.add_argument("-c", "--configs", default=str(HERE / "configs"), help="folder rendered by generate.py")
    ap.add_argument("--dry-run", action="store_true", help="show the differences, change nothing")
    ap.add_argument("-i", "--inventory", help="inventory file (default: the lab's)")
    args = ap.parse_args()

    cfg = Path(args.configs)
    if not cfg.is_dir():
        print(f"{cfg} does not exist - run ./generate.py first")
        return 1
    nodes = args.nodes or sorted(p.name for p in cfg.iterdir() if p.is_dir())
    inv = load_inventory(args.inventory)
    failed = 0
    for n in nodes:
        if n not in inv:
            print(f"  ! {n}: not in the lab inventory ({', '.join(inv)})")
            failed += 1
            continue
        files = {}
        for f in ("interfaces", "frr.conf"):
            p = cfg / n / f
            if not p.exists():
                print(f"  ! {n}: {p} missing")
                break
            files[f] = p.read_text(encoding="utf-8")
        else:
            try:
                deploy(inv[n], files, args.dry_run)
            except Exception as e:  # noqa: BLE001
                print(f"  ! {n}: {e}")
                failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
