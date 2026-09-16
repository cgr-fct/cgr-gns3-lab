# Instructor notes

## One-time setup of the repository

1. Push this repository to GitHub (organisation or personal account).
2. **Actions → build-lab-images → Run workflow.** It builds `cgr-frr` and `cgr-netauto` for
   amd64 + arm64 and pushes them to `ghcr.io/<owner>/…` (≈15 min the first time, mostly the
   arm64 emulation). Both images are built from the repository root, because they embed
   `automation/` (YANG model, templates, RESTCONF server and client).
3. Make both packages **public** (*Packages → package → Package settings → Change visibility*).
4. In `tools/lab_settings.yml` replace `CHANGE-ME` with the lower-case owner name. Replace
   `https://github.com/cgr-fct/cgr-gns3-lab.git` in `docs/` and `README.md`. Commit.
5. Rebuilds run automatically whenever `images/` or `automation/` change.

Local build alternative (no GitHub):
```bash
docker buildx build --platform linux/amd64,linux/arm64 -f images/frr/Dockerfile \
  -t <registry>/cgr-frr:latest --push .
docker buildx build --platform linux/amd64,linux/arm64 -f images/netauto/Dockerfile \
  -t <registry>/cgr-netauto:latest --push .
```

## Design

* **One kit for everyone.** Every router/switch is the `cgr-frr` container (Debian + FRRouting +
  ifupdown2 + Linux bridge/bonding + ISC DHCP server/relay + RESTCONF server, ports renamed
  `swpN`). Hosts and the automation station are the `cgr-netauto` container. Both images are
  multi-arch: Windows, Intel/Apple Silicon Macs and Linux run identical software, with no
  nested virtualisation and no vendor images.
* **CLI syntax taught:** `/etc/network/interfaces` (ifupdown2, Cumulus' classic format) for
  L2/L3 interfaces, `vtysh` (FRR) for routing, ISC files for DHCP. `labs/CHEATSHEET.md` has an
  NVUE → FRR/ifupdown2 mapping to help converting last year's slides.
* **Model-driven layer:** a YANG 1.1 module, `cgr-device`
  (`automation/yang/cgr-device@2026-09-15.yang`, passes `pyang --strict`), covers VLANs,
  trunks, bonds, STP priority, SVIs, VRRP, DHCP server/relay, OSPF (areas, stub, ranges,
  virtual links, default origination, costs, priorities), IS-IS, BGP (networks, aggregates,
  iBGP/eBGP, next-hop-self, local-preference in, AS-path prepend out) and a `config false`
  state subtree (interfaces, routes, OSPF and BGP neighbours).
  * **RESTCONF server** on every router/switch (`automation/restconf_server.py`, HTTPS :443,
    Basic auth `cgr`/`cgrlab`): RFC 8040 subset with JSON encoding — API root, host-meta,
    yang-library (modules-state), GET with `content=`, PUT/PATCH (merge)/POST/DELETE on any node,
    list keys in the URI, `ietf-restconf:errors` reports, `Location` on create. Every write is
    validated with **yangson** against the module (types, patterns, `mandatory`, `when`),
    rendered with Jinja2, applied (ifreload, frr-reload, dhcpd/dhcrelay) and rolled back on
    failure. Not implemented: XML encoding, `depth`/`fields`/`with-defaults`, YANG-PATCH, ETags,
    RPCs/actions, notifications (NETCONF is not provided).
  * **YAML intent** (`apply_intent.py`) uses exactly the same data, pushed over SSH or RESTCONF,
    with `--check`, `--dry-run`, `--diff`, `--render`. SSH pushes also update the device's
    RESTCONF datastore (`/etc/cgr/running.json`), so both paths stay consistent.
  * The datastore only reflects what was configured through the model; manual CLI changes are
    visible in `state` and in `apply_intent.py --diff` (drift), not in the RESTCONF config.
  * **CLI/automation ownership guard** (`automation/cgrimport.py`). Every push compares the
    device's live configuration, normalised to order-insensitive lines, with what the previous
    and the new model data generate. Lines explained by neither were typed by hand; if the push
    would remove them it is refused (`REFUSED` / RESTCONF `409 resource-denied`) unless forced
    (`--force`, `?force=true`, Ansible `-e force=true`).
  * **Import** (`apply_intent.py <file> --import <devices>|all`) parses `/etc/network/interfaces`,
    `vtysh show running-config` and the DHCP files back into `cgr-device` data and lists what the
    model cannot hold (MTU, prefix-lists, general route-maps, static routes, …) as notes. OSPF
    `network` statements are converted to per-interface areas; a missing OSPF router-id is set to
    the one FRR picks. Suggested semester flow: labs by CLI (RESTCONF GET anytime); after the
    automation class either a fresh lab copy by automation, mixed ownership (e.g. Lab 04: Provider
    AS by automation, Bank by CLI), or take-over with `--import all`.
* **FRR profile** `datacenter` (as on Cumulus): eBGP needs no explicit policy; faster timers.
* **Kernel STP** (802.1D) — mstpd (RSTP) cannot run inside containers; no admin-edge setting.
* **GNS3 2.2.54** for everyone — last 2.2 release with an ARM64 GNS3 VM; `cgr_lab.py` uses the
  2.2 REST API (`/v2`).
* **Password `cgrlab`** (not `cgr`): Ansible masks the password in all module output, so a
  password equal to `cgr` would corrupt the `cgr-device:…` keys of RESTCONF replies.

## The five labs

| Lab | Source | Notes |
|---|---|---|
| 00 first contact | new | bridge/VLAN by hand, YAML intent, first RESTCONF requests |
| 01 campus | 2025/2026 project 1, part 1 (Air *ProjectCampusNetwork* topology) | + DHCP server/relay (user hosts are DHCP clients), OSPF **or** IS-IS, automation part |
| 02 OSPF | 2025/2026 project 1, part 2 (figure redrawn with the lab port names) | the "hidden issue" is area 43 not touching area 0 → virtual link R1–R5 through area 32 |
| 03 IS-IS | new | 4 routers |
| 04 BGP | 2025/2026 lab 2, part 1 (Air *BGP* topology) | the statement's 10.1.405/406/506.0/29 are invalid → 10.1.45/46/56.0/29; R4 loopback 10.4.4.4/24 added; the Air file lacked the R1–R3 link (added) |

Solutions (separate instructor package, not in this repository): `lab02-ospf/` (FRR files) and
`lab04-bgp/intent.yml` (cgr-device intent, deployable with `apply_intent.py` or RESTCONF).

Things to keep in mind when grading: OSPF advertises addresses on `lo` as /32 host routes; a
single-area design can only summarise with `area … range` on an ABR (or `summary-address` for
redistributed routes).

## What was verified (GNS3 server 2.2.61 on Linux, Docker, locally built images)

* All five labs build.
* **Lab 04 complete solution**: all BGP sessions established, both aggregates
  (10.20.0.0/22, 172.16.0.0/20) with components suppressed, R4 prefers R3, the Bank prefers
  R1–R4, R2 ↔ R5 reachability; deployed with SSH (Bank) and with Ansible → RESTCONF (Provider);
  second runs change nothing; `--diff` is clean on all six routers.
* **Lab 02 complete solution** (earlier kit version, same router image): virtual link,
  `area 20 range`, DR election, `default-information originate always`, full reachability.
* **DHCP**: server and relay deployed by SSH and by RESTCONF; Linux hosts lease addresses at boot
  (direct and relayed); configuration and daemons survive a stop/start of the nodes.
* **CLI → automation take-over** (Lab 04 topology): hand-configured routers refused by SSH push,
  RESTCONF PATCH and the Ansible playbook, with the offending settings listed; `--import` → clean
  `--diff` except the noted lines; `--force` removes them; a clean import pushes without force;
  drift after a hand edit on a managed device is detected and refused. Importing the six routers
  of the deployed Lab 04 solution reproduces the solution intent exactly (up to list order).
  Offline, the campus intents (bonds, SVIs, VRRP, DHCP relay/server) round-trip through
  render → import with no semantic difference.
* **RESTCONF**: all methods, list keys, leaf targets, content filtering, operational state
  (interfaces, routes, OSPF/BGP neighbours), 400/401/404/405/409/415 error reports, YANG
  validation errors, hostname changes, datastore shared with SSH pushes, Ansible `uri` playbooks.

**Not verified — please check once on real hardware:**

- [ ] macOS Apple Silicon: GNS3 2.2.54 + ARM64 GNS3 VM on VMware Fusion; Lab 00 end to end.
- [ ] **VirtualBox** on Windows (install guide, option B) and on Intel Macs (macOS option C):
      the VirtualBox GNS3 VM managed by GNS3; on Windows check nested virtualisation with Hyper-V on.
- [x] **VirtualBox on Apple Silicon does not work** (checked on a Mac with VirtualBox 7.2: GRUB
      starts, the Ubuntu 20.04 GNS3 VM never comes up — no console, no DHCP lease). Removed from
      the guide.
- [x] **UTM on Apple Silicon — Lab 00 works end to end** (checked on a Mac; the university VPN must be
      off, otherwise the VM has no Internet access and the image pull fails).
- [ ] **UTM on Apple Silicon** — still to check: Lab 01 (bonds, VRRP; `sudo modprobe -a bonding 8021q dummy macvlan`
      in the VM) and a large lab's memory use. Background of the UTM setup (macOS option B): VM from the two ARM64 disks (VirtIO), one
      *Shared Network* NIC, serial console, added to GNS3 as a *remote server*. Checked here on
      the equivalent QEMU machine (virt, EFI, virtio-blk, virtio-net, one NIC): boots in ~4 min
      under emulation, eth0 gets DHCP, server answers on :80 without auth, a 2.2.54 controller
      accepts it as a remote compute and `cgr_lab.py` selects it. Not checked: UTM's UI, and
      pulling/running the lab containers inside that VM (registry blocked in the test environment).
- [ ] **VLAN-aware bridges, VLAN SVIs, LACP bonds and VRRP (macvlan)** inside the containers —
      the build environment's kernel lacked these features, so the Lab 00 VLAN, the campus
      bonds/SVIs and VRRP were only checked as generated configuration. The GNS3 VM's Ubuntu
      kernel has them; if needed, `sudo modprobe -a bonding 8021q dummy macvlan` in the GNS3 VM shell.
- [ ] DHCP relay on an **SVI** (tested on a routed port).
- [ ] The Debian packages used by `images/frr/Dockerfile` (the local test used Ubuntu's FRR 8.4,
      ifupdown2 from source and ISC DHCP 4.4.3) — in particular FRR 10's `frr-reload.py` and
      JSON outputs used for the RESTCONF state (`show ip ospf neighbor json` changed format
      between FRR versions; the server accepts both known formats).
- [ ] GHCR publishing and the first image pull from the GNS3 VM.
- [ ] GNS3 "Reload" of a node left it waiting for its interfaces in the test environment;
      stop/start works (documented in troubleshooting).

## Lab figures
All lab figures use one style and are generated: `labs/<lab>/figure.yml` → `python tools/draw_topology.py --all --png`
→ `figure.svg` + `figure.png`. The tool fails if a port written in a figure is not a link of the
lab's `topology.yml`. Re-run it after changing a topology or its addressing (and copy the Lab 01/02
PNGs to the course site: `img/project1_campus.png`, `img/project1_ospf.png`).

## Ideas for more labs
BFD, route reflectors (cheap to scale), EVPN-VXLAN with FRR, IPv6 (OSPFv3 is enabled),
extending the YANG model (static routes, ACLs) as an exercise, monitoring with RESTCONF
`state` → Python → CSV.
