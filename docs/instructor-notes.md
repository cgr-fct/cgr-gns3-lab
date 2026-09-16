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
| 02 OSPF | 2025/2026 project 1, part 2 (figure redrawn; port mapping in the README) | the "hidden issue" is area 43 not touching area 0 → virtual link R1–R5 through area 32 |
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
* **RESTCONF**: all methods, list keys, leaf targets, content filtering, operational state
  (interfaces, routes, OSPF/BGP neighbours), 400/401/404/405/409/415 error reports, YANG
  validation errors, hostname changes, datastore shared with SSH pushes, Ansible `uri` playbooks.

**Not verified — please check once on real hardware:**

- [ ] macOS Apple Silicon: GNS3 2.2.54 + ARM64 GNS3 VM on VMware Fusion; Lab 00 end to end.
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

## Ideas for more labs
BFD, route reflectors (cheap to scale), EVPN-VXLAN with FRR, IPv6 (OSPFv3 is enabled),
extending the YANG model (static routes, ACLs) as an exercise, monitoring with RESTCONF
`state` → Python → CSV.
