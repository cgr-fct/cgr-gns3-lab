# CGR — GNS3 labs for Network Configuration and Management

Ready-to-run GNS3 labs for switching (campus), routing (OSPF, IS-IS, BGP) and network
automation (Python, YAML, Jinja2, data models, SSH), built only from **free, lightweight
containers**: an FRRouting router/switch, a Linux host/automation station, and GNS3's built-in PCs.

**The same kit for everyone:** Windows, Intel or Apple Silicon Macs, Linux — no licences, no
nested virtualisation, and a complete lab uses well under 1 GB of RAM.

One command builds a whole lab — devices, cables, addresses, management network:

```bash
python tools/cgr_lab.py build labs/lab01-campus-switching --start
```

## Quick start

| Step | Windows | macOS (Intel or Apple Silicon) | Linux |
|---|---|---|---|
| 1. Install GNS3 **2.2.54** (+ GNS3 VM) | [guide](docs/01-install-windows.md) | [guide](docs/02-install-macos.md) | [guide](docs/03-install-linux.md) |
| 2. Get this repo | `git clone <REPO-URL>` or *Code → Download ZIP* | same | same |
| 3. Python tools | `py -m pip install -r tools\requirements.txt` | venv + `pip install -r tools/requirements.txt` | same as macOS |
| 4. Check | `py tools\cgr_lab.py check` | `python tools/cgr_lab.py check` | same |
| 5. First lab | [Lab 00](labs/lab00-first-contact/README.md) | same | same |

Stuck? → [Troubleshooting](docs/06-troubleshooting.md). How it fits together →
[Overview](docs/00-overview.md). Configuration syntax → [Cheat sheet](labs/CHEATSHEET.md).

## Labs

| Lab | Topics | Nodes |
|---|---|---|
| [00 First contact](labs/lab00-first-contact/README.md) | setup check, bridge + VLAN, first automation run | 2 switches, 2 PCs |
| [01 Campus switching](labs/lab01-campus-switching/README.md) | VLANs, trunks, STP, SVIs, LACP | 3 switches, 4 PCs |
| [02 OSPF](labs/lab02-ospf/README.md) | single/multi-area, costs, stub, summarisation | 4 routers, 3 PCs |
| [03 IS-IS](labs/lab03-isis/README.md) | levels, areas, attached bit, metrics | 4 routers, 3 PCs |
| [04 BGP](labs/lab04-bgp/README.md) | eBGP/iBGP, next-hop-self, local-pref, prepend, communities | 2 routers + 2 ISPs, 3 PCs |

### Project 1 (2025/2026 statements)

| Lab | Content |
|---|---|
| [proj1-campus](labs/proj1-campus/README.md) | Part 1: campus (VLANs, bonds, SVIs, OSPF, summarisation, default route) — 8 switches/routers + 6 Linux hosts |
| [proj1-ospf](labs/proj1-ospf/README.md) | Part 2: multi-area OSPF, DR, summarisation, default route, the hidden issue |
| [proj1-bgp](labs/proj1-bgp/README.md) | Part 3: BGP scenario (6 routers) |

Every lab has an **automation station** (`netauto`) on an out-of-band management network with
the [automation toolkit](automation/README.md): an inventory generated for the lab, YAML intent
validated by a schema, Jinja2 templates, config push with diff, bulk commands and backups, Ansible.

## How devices are configured

| What | Where | Apply |
|---|---|---|
| Interfaces, bridges, VLANs, bonds, SVIs | `/etc/network/interfaces` (ifupdown2 — the syntax of Cumulus Linux) | `ifreload -a` |
| OSPF, IS-IS, BGP, static routes | `vtysh` (FRRouting, Cisco-like CLI) | `write memory` |

Ports are named `swp1`, `swp2`, … (`eth0` is management). See the [cheat sheet](labs/CHEATSHEET.md).

## Credentials

| Node | Console (double-click in GNS3) | SSH |
|---|---|---|
| Routers / switches | root shell, no login | `cgr` / `cgr` |
| Linux hosts, netauto | root shell, no login | — |

## Repository layout

```
docs/          installation guides, overview, troubleshooting, instructor notes
labs/          one folder per lab: README (tasks), topology.yml, configs/; CHEATSHEET.md
tools/         cgr_lab.py (build/start/stop labs via the GNS3 API), air2gns3.py, lab_settings.yml
automation/    toolkit copied into the netauto station (/root/cgr)
images/        Dockerfiles for the router/switch and the netauto/host images
.github/       CI that builds the container images (amd64 + arm64)
```

Instructors: start with [docs/instructor-notes.md](docs/instructor-notes.md).
