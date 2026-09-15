# Instructor notes

## One-time setup of the repository

1. Push this repository to GitHub (organisation or personal account).
2. **Actions → build-lab-images → Run workflow.** It builds `cgr-frr` and `cgr-netauto` for
   amd64 + arm64 and pushes them to `ghcr.io/<owner>/…` (≈10 min the first time, mostly the arm64
   emulation).
3. Make both packages **public** (*Packages → package → Package settings → Change visibility*).
4. In `tools/lab_settings.yml` replace `CHANGE-ME` with the lower-case owner name. Replace
   `<REPO-URL>` in `docs/` and `README.md`. Commit.
5. Rebuilds run automatically whenever `images/` or `automation/` change (the netauto image
   embeds `automation/`).

Local build alternative (no GitHub):
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t <registry>/cgr-frr:latest --push images/frr
docker buildx build --platform linux/amd64,linux/arm64 -t <registry>/cgr-netauto:latest \
  -f images/netauto/Dockerfile --push .
```

## Design

* **One kit for everyone.** Every router/switch is the `cgr-frr` container (Debian + FRRouting +
  ifupdown2 + Linux bridge/bonding, ports renamed `swpN`). Hosts and the automation station
  are the `cgr-netauto` container. Both images are multi-arch, so Windows, Intel and Apple
  Silicon Macs and Linux run identical software. No nested virtualisation, no licences, no
  vendor image downloads.
* **Syntax taught:** `/etc/network/interfaces` (ifupdown2, Cumulus' own "classic" format) for
  L2/L3 interfaces and `vtysh` (FRR) for routing. `labs/CHEATSHEET.md` has an NVUE → FRR/ifupdown2
  mapping table that helps converting last year's slides.
* **GNS3 2.2.54** for everyone — last 2.2 release with an ARM64 GNS3 VM; `cgr_lab.py` uses the
  2.2 REST API (`/v2`). GNS3 3.x changed the API (`/v3`, JWT auth) — porting means changing the
  `GNS3` class only.
* **Management network** 192.168.100.0/24 in labs 00–04; the `proj1-*` labs keep Air's
  192.168.200.0/24. `cgr_lab.py build` writes `/root/lab/inventory.yml` (Ansible YAML format) on
  the netauto node, so scripts and Ansible always target the lab that was built.
* **Automation** is SSH-based: Python (`cgrlib`, `collect.py`), YAML intent validated by JSON
  Schema, Jinja2 templates, idempotent push with `--diff` (`ifreload` + `frr-reload.py`), and the
  same workflow as Ansible playbooks.
* **Solutions** live in the separate instructor package, not in this repository.

## Project 1 (2025/2026)

`labs/proj1-*` are the 2025/2026 Air topologies (converted with `tools/air2gns3.py`, same names
and ports; the OSPF one redrawn from the statement figure). The statement PDFs need two edits:
the title ("… in Cumulus using NVUE" → FRR/ifupdown2) and the *Work Setup* section (→ point to
`labs/proj1-campus/README.md`). The BGP statement still has to be added to
`labs/proj1-bgp/README.md`.

Differences from Cumulus to keep in mind when grading:
* STP is the kernel's 802.1D (no RSTP/MSTP), so convergence is slower.
* OSPF advertises addresses on `lo` as /32 host routes (use dummy interfaces for /27s).
* "Summarise at the distribution switches" in a single-area design requires them to be ABRs
  (`area X range`) or ASBRs (`summary-address`), exactly as on Cumulus.

## What was verified (GNS3 server 2.2.61 on Linux, Docker, local image builds)

* All 8 labs build; the three `proj1-*` labs run simultaneously in ~2.3 GB.
* `cgr-frr`: swpN renaming, ifupdown2, FRR daemons (OSPF, IS-IS, BGP), config persistence, SSH, sudo.
* Lab 04 end to end: pre-configured ISPs (filters, default route), eBGP/iBGP, reachability.
* Complete `proj1-ospf` solution: virtual link through area 32 (the hidden issue),
  `area 20 range 172.16.9.0/25`, DR election on the R1–R4–R5 segment,
  `default-information originate always`, full reachability.
* Automation: generated inventory, `collect.py` (text, JSON, backups), `apply_intent.py`
  (`--dry-run`, `--diff`, push, idempotent second run), schema validation, Ansible ad-hoc
  commands and both playbooks (idempotent), Linux host nodes.

**Not verified — please check once on real hardware:**

- [ ] macOS Apple Silicon: GNS3 2.2.54 + ARM64 GNS3 VM on VMware Fusion; Lab 00 end to end
      (VPCS and the built-in Ethernet switch on the ARM VM).
- [ ] VLAN-aware bridges, VLAN SVIs and LACP bonds inside the containers (the build
      environment's kernel lacked these modules; the GNS3 VM's Ubuntu kernel has them — if
      needed, `sudo modprobe -a bonding 8021q dummy` in the GNS3 VM shell): Lab 00 ping,
      Lab 01 Part D.
- [ ] The Debian `ifupdown2` package and the FRR apt repository used by
      `images/frr/Dockerfile` (the local test used ifupdown2 from source and Ubuntu's FRR 8.4).
- [ ] GHCR publishing and the first pull from the GNS3 VM.

## RESTCONF / YANG

Without Cumulus VX the labs have no vendor REST API: the automation part is
SSH + YAML + Jinja2 + JSON Schema + Ansible. For an RFC 8040 exercise, options are:
* a small RESTCONF agent inside `cgr-frr`, backed by FRR's own YANG models, or
* a vendor sandbox with RESTCONF enabled (e.g. Cisco DevNet's always-on IOS XE sandbox —
  free account, availability varies).

## Ideas for more labs
VRRP (`vrrpd` is enabled), BFD, route reflectors (cheap to scale to 10+ routers), EVPN-VXLAN
with FRR, IPv6 (OSPFv3 is enabled), monitoring with `show … json` → Python → CSV.
