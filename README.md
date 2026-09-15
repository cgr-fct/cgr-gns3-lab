# CGR — GNS3 labs for Network Configuration and Management

Ready-to-run GNS3 labs for switching (campus, DHCP), routing (OSPF, IS-IS, BGP) and network
automation (**YANG, RESTCONF**, YAML, Jinja2, Python, Ansible), built only from **free,
lightweight containers**: an FRRouting router/switch with a RESTCONF server, a Linux
host/automation station, and GNS3's built-in PCs.

**The same kit for everyone:** Windows, Intel or Apple Silicon Macs, Linux — no licences, no
nested virtualisation, and a complete lab uses well under 1 GB of RAM.

One command builds a whole lab — devices, cables, addresses, management network:

```bash
python tools/cgr_lab.py build labs/lab01-campus --start
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
| [00 First contact](labs/lab00-first-contact/README.md) | setup check, bridge + VLAN, YAML intent, first RESTCONF requests | 2 switches, 2 PCs |
| [01 Campus network](labs/lab01-campus/README.md) | VLANs, trunks, LACP, STP, SVIs, DHCP server + relay, OSPF / IS-IS between pods, summarisation, default route, automation | 8 switches/routers, 6 Linux hosts |
| [02 OSPF](labs/lab02-ospf/README.md) | multi-area OSPF, DR election, summarisation, default route, the hidden issue | 7 routers, 1 switch |
| [03 IS-IS](labs/lab03-isis/README.md) | levels, areas, attached bit, metrics, comparison with OSPF | 4 routers, 3 PCs |
| [04 BGP](labs/lab04-bgp/README.md) | OSPF inside ASes, iBGP full mesh, eBGP, aggregation, local preference | 6 routers |

Every lab has an **automation station** (`netauto`) on an out-of-band management network, and
every router/switch runs a **RESTCONF server** for the YANG model `cgr-device`. The
[automation toolkit](automation/README.md) provides the YANG module, a RESTCONF client, YAML
intent validated against the model, Jinja2 templates, an idempotent deploy tool (SSH or
RESTCONF), bulk commands and backups, and Ansible playbooks.

## How devices are configured

| What | Where | Apply |
|---|---|---|
| Interfaces, bridges, VLANs, bonds, SVIs | `/etc/network/interfaces` (ifupdown2 — the syntax of Cumulus Linux) | `ifreload -a` |
| OSPF, IS-IS, BGP, VRRP, static routes | `vtysh` (FRRouting, Cisco-like CLI) | `write memory` |
| DHCP server / relay | `/etc/dhcp/dhcpd.conf`, `/etc/default/isc-dhcp-{server,relay}` | `service isc-dhcp-… restart` |
| All of the above, model-driven | RESTCONF `https://<eth0>/restconf` or YAML intent (`cgr-device` YANG model) | automatic |

Ports are named `swp1`, `swp2`, … (`eth0` is management). See the [cheat sheet](labs/CHEATSHEET.md).

## Credentials

| Node | Console (double-click in GNS3) | SSH |
|---|---|---|
| Routers / switches | root shell, no login | `cgr` / `cgrlab` (also RESTCONF) |
| Linux hosts, netauto | root shell, no login | — |

## Repository layout

```
docs/          installation guides, overview, troubleshooting, instructor notes
labs/          one folder per lab: README (tasks), topology.yml; CHEATSHEET.md
tools/         cgr_lab.py (build/start/stop labs via the GNS3 API), air2gns3.py, lab_settings.yml
automation/    toolkit: YANG model, RESTCONF client+server, intent tool, templates, Ansible
               (copied into the netauto station /root/cgr and into every router/switch)
images/        Dockerfiles for the router/switch and the netauto/host images
.github/       CI that builds the container images (amd64 + arm64)
```

Instructors: start with [docs/instructor-notes.md](docs/instructor-notes.md).
