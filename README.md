# CGR — GNS3 labs for Network Configuration and Management

Ready-to-run GNS3 labs for switching (campus), routing (OSPF, IS-IS, BGP) and network
automation (REST API, Python, YAML, Jinja2, data models), built only from **free images**:
NVIDIA **Cumulus VX**, **FRRouting** containers and GNS3's built-in PCs.

One command builds a whole lab — devices, cables, addresses, management network:

```bash
python tools/cgr_lab.py build labs/lab01-campus-switching --start
```

## Quick start

| Step | Windows (x86) | macOS | Linux |
|---|---|---|---|
| 1. Install GNS3 **2.2.54** + VM | [guide](docs/01-install-windows.md) | [guide](docs/02-install-macos.md) | [guide](docs/03-install-linux.md) |
| 2. Get this repo | `git clone <REPO-URL>` or *Code → Download ZIP* | same | same |
| 3. Python tools | `py -m pip install -r tools\requirements.txt` | venv + `pip install -r tools/requirements.txt` | same as macOS |
| 4. Cumulus VX image | [upload it](docs/04-images.md) | Intel: upload · Apple Silicon: skip (lite) | [upload it](docs/04-images.md) |
| 5. Check | `py tools\cgr_lab.py check` | `python tools/cgr_lab.py check` | same |
| 6. First lab | [Lab 00](labs/lab00-first-contact/README.md) | Lab 00 with `--lite` on Apple Silicon | Lab 00 |

Stuck? → [Troubleshooting](docs/07-troubleshooting.md). How it all fits together →
[Overview](docs/00-overview.md).

## Labs

| Lab | Topics | Devices | RAM (full / lite) |
|---|---|---|---|
| [00 First contact](labs/lab00-first-contact/README.md) | setup check, VLAN, first REST call | 2 Cumulus | 5 GB / 0.3 GB |
| [01 Campus switching](labs/lab01-campus-switching/README.md) | VLANs, trunks, STP, SVIs, LACP | 3 Cumulus | 7 GB / 0.5 GB |
| [02 OSPF](labs/lab02-ospf/README.md) | single/multi-area, costs, stub, summarisation | 2 Cumulus + 2 FRR | 5 GB / 0.5 GB |
| [03 IS-IS](labs/lab03-isis/README.md) | levels, areas, attached bit, metrics | 4 FRR | 1 GB |
| [04 BGP](labs/lab04-bgp/README.md) | eBGP/iBGP, next-hop-self, local-pref, prepend, communities | 2 Cumulus + 2 FRR ISPs | 5 GB / 0.5 GB |

### Project 1 (2025/2026 statements, Air topologies ported to GNS3)

| Lab | Content | Lite RAM |
|---|---|---|
| [proj1-campus](labs/proj1-campus/README.md) | Part 1: campus (VLANs, bonds, SVIs, OSPF, summarisation, default route) — 8 switches/routers + 6 hosts | < 1 GB |
| [proj1-ospf](labs/proj1-ospf/README.md) | Part 2: multi-area OSPF, DR, summarisation, default route, the hidden issue | ~0.4 GB |
| [proj1-bgp](labs/proj1-bgp/README.md) | Part 3: BGP scenario (6 routers) | ~0.3 GB |

All three are meant to be built with `--lite` (works on Apple Silicon); the NVUE → lite
translation is in [labs/LITE-CHEATSHEET.md](labs/LITE-CHEATSHEET.md).

Every lab includes an **automation station** (`netauto`) on an out-of-band management
network (`192.168.100.0/24`) with the [automation toolkit](automation/README.md):
curl examples, an NVUE REST client, a YAML intent model validated by a schema, and Jinja2
templates.

**Full vs lite:** add `--lite` to any `build` to replace Cumulus VX VMs by tiny FRR containers
(same routing CLI, Cumulus-style port names). Use it on Apple Silicon Macs, on 8 GB laptops, or
when nested virtualisation is not available. See [Overview](docs/00-overview.md#full-vs-lite).

## Credentials

| Device | User | Password |
|---|---|---|
| Cumulus VX (factory) | `cumulus` | `cumulus` → changed at first login to `CumulusLab1!` |
| Cumulus VX / FRR nodes (lab) | `cumulus` | `CumulusLab1!` |
| netauto | console opens a root shell | |

## Repository layout

```
docs/          installation guides, overview, troubleshooting, instructor notes
labs/          one folder per lab: README (tasks), topology.yml, bootstrap/, configs/
tools/         cgr_lab.py (build/start/bootstrap labs via the GNS3 API), lab_settings.yml
automation/    toolkit copied into the netauto station (/root/cgr)
images/        Dockerfiles for the FRR node and the netauto station
.github/       CI that builds the container images (amd64 + arm64)
```

Instructors: start with [docs/instructor-notes.md](docs/instructor-notes.md).
