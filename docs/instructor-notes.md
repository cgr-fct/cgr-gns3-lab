# Instructor notes

## One-time setup of the repository

1. Push this repository to GitHub (organisation or personal account).
2. **Actions → build-lab-images → Run workflow.** It builds `cgr-frr` and `cgr-netauto` for
   amd64 + arm64 and pushes them to `ghcr.io/<owner>/…` (≈10 min the first time, mostly the arm64
   emulation).
3. Make both packages **public** (*Packages → package → Package settings → Change visibility*).
4. In `tools/lab_settings.yml` replace `CHANGE-ME` with the lower-case owner name, and set
   `cumulus.image` to the Cumulus VX version you tested. Replace `<REPO-URL>` in `docs/` and
   `README.md`. Commit.
5. Rebuilds run automatically whenever `images/` or `automation/` change (the netauto image
   embeds `automation/`).

Local build alternative (no GitHub):
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t <registry>/cgr-frr:latest --push images/frr
docker buildx build --platform linux/amd64,linux/arm64 -t <registry>/cgr-netauto:latest \
  -f images/netauto/Dockerfile --push .
```

## Validate before the semester (checklist)

What was verified while writing this kit (GNS3 server 2.2.61 on Linux, Docker, local
image builds): project/node/link creation via `cgr_lab.py`, templates, image upload, the FRR
container (swpN renaming, ifupdown2, FRR daemons, config persistence, SSH), the full Lab 04
in lite mode (ISP pre-configuration, eBGP/iBGP, filtering, default route), intent push over
SSH, schema validation, and `nvue.py` / `curl_examples.sh` against a mock NVUE server.
The console bootstrap logic was tested against a simulated Cumulus login sequence.

**Not verified — please run once on real hardware:**

- [ ] A real Cumulus VX 5.x boot in the GNS3 VM (Windows + VMware) and `cgr_lab.py bootstrap`
      (first-login password change prompts can vary between releases).
- [ ] `nv set system api listening-address <eth0-ip>` makes the API reachable from netauto
      (mgmt VRF) on the version you pick.
- [ ] `apply_intent.py intent/lab00.yml` and `lab04-bgp-example.yml` (completed) against real
      NVUE — especially the SVI (`type: svi`, `vlan`) and BGP neighbour objects. If NVUE
      rejects a key, `nv set …` + `nv config diff -o json` shows the right shape; fix `to_nvue()`.
- [ ] macOS Apple Silicon: GNS3 2.2.54 + ARM64 GNS3 VM on VMware Fusion, lite Lab 00
      (VPCS and the built-in Ethernet switch on the ARM VM).
- [ ] VLAN-aware bridges in the FRR container (the test environment kernel lacked VLAN
      filtering; the GNS3 VM's Ubuntu kernel has it): lite Lab 00 ping pc1 → pc2.
- [ ] The Debian `ifupdown2` package path used by `images/frr/Dockerfile` (the local test used
      ifupdown2 from source).

## Project 1 in lite mode (Apple Silicon)

`labs/proj1-*` are the 2025/2026 Air topologies (converted with `tools/air2gns3.py`, same names
and ports; the OSPF one redrawn from the statement figure). Verified in lite mode on the test
server: all three build and run **at the same time** in ~2.3 GB; the complete OSPF statement was
solved with FRR (virtual link through area 32, `area 20 range 172.16.9.0/25`, DR on the R1–R4–R5
segment, `default-information originate always`) with full reachability — the solution configs
are in the separate instructor package, not in this repository.

Things lite mode changes for students:
* **No NVUE.** The Project 1 statement title says "configuration in Cumulus using NVUE". Mac
  students do the same tasks in ifupdown2 + vtysh (`labs/LITE-CHEATSHEET.md`). If NVUE itself is an
  assessment objective, they can keep using **NVIDIA Air** (cloud, works from any laptop), as in
  2025/2026, and use GNS3 lite only for practice — or accept either syntax in the deliverables.
* Kernel STP instead of RSTP; loopback addresses advertised as /32.
* Bonds/VLAN sub-interfaces need the `bonding`/`8021q` kernel modules in the GNS3 VM (see
  troubleshooting). Not testable in the build environment — check once on the ARM64 VM.
* In OSPF single-area designs, "summarise at the distribution switches" requires the
  distribution switches to be ABRs (or ASBRs with `summary-address`); FRR behaves like Cumulus here.

## Design decisions

* **GNS3 2.2.54 for everyone** — last 2.2 release with an ARM64 GNS3 VM; `cgr_lab.py` uses the
  2.2 REST API (`/v2`). GNS3 3.x changed the API (`/v3`, JWT auth) — porting means changing
  the `GNS3` class only.
* **Cumulus VX + FRR containers.** Cumulus gives a real NOS and the NVUE REST API; FRR
  containers keep labs light, run on Apple Silicon, and use the same routing CLI. ifupdown2
  (Cumulus' own tool) keeps the "classic Cumulus" interface syntax in lite mode.
* **IS-IS on FRR only** — NVUE does not model IS-IS; configuring FRR by hand on Cumulus
  conflicts with NVUE owning `frr.conf`.
* **Management network** 192.168.100.0/24 in labs 00–04 so the inventory never changes; the
  `proj1-*` labs keep Air's 192.168.200.0/24 addresses (netauto = .254).
* **Password `CumulusLab1!`** — Cumulus 5.x forces a change at first login and the API refuses
  the factory password; it satisfies the default password-complexity rules.

## RESTCONF / YANG options

NVUE is not RESTCONF. If you want students to hit a real RFC 8040 endpoint:
* a vendor sandbox with RESTCONF enabled (e.g. Cisco DevNet's always-on IOS XE sandbox —
  free account, availability varies), or
* a YANG-based open-source NOS/agent in a container (e.g. Nokia SR Linux is free and
  YANG-modelled, but exposes gNMI/JSON-RPC rather than RESTCONF).
The `automation/schema` + intent pattern is deliberately model-first so the YANG discussion
carries over.

## Ideas for more labs
EVPN-VXLAN between two Cumulus VX (NVUE supports it), MLAG (needs 2 × Cumulus + peerlink),
VRRP/VRR, route reflectors with FRR containers (cheap to scale to 10+ routers),
monitoring with `nv show` → Python → CSV.
