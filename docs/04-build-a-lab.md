# Building and using a lab

Keep the **GNS3 GUI open** (it runs the controller the tool talks to). On Windows use
`py` instead of `python`; on macOS/Linux activate the venv first (`source .venv/bin/activate`).

## The workflow

```bash
python tools/cgr_lab.py build labs/lab01-campus --start
python tools/cgr_lab.py consoles lab01-campus       # optional: list console ports
```

Then in GNS3: **File → Open project → lab01-campus**. Double-click a node to open its
console (a root shell — no login).

* `build` creates the project, every node, every cable, the management switch, the addresses
  of the PCs and of the management interfaces, any pre-configured device files of the lab, and
  the lab inventory on the netauto station.
* The **first** start downloads the two container images (~500 MB) into the GNS3 VM, which takes
  a few minutes and needs Internet access. Later starts take seconds.

| Command | Does |
|---|---|
| `check` | Tests the connection to GNS3 and Docker support |
| `templates` | Adds *CGR Router*, *CGR Switch* and *CGR NetAuto* to the GUI device list |
| `start <project>` / `stop <project>` | Start/stop all nodes |
| `build <lab> --force` | Rebuilds the project from scratch (**your configuration is lost**) |
| `build <lab> --name myname` | Builds another copy under a different name (e.g. one per scenario) |
| `delete <project>` | Deletes the project |
| `--server http://IP:3080 --user U --password P` | Connect to another GNS3 server |
| `--compute ID` | Use this compute (default: the GNS3 VM, else a remote server with Docker, else local) |

If `cgr_lab.py` can't log in: GNS3 → **Edit → Preferences → Server** shows the host, port,
user and password of the local server. Pass them with `--server/--user/--password` or set
`GNS3_SERVER`, `GNS3_USER`, `GNS3_PASSWORD`.

## Configuring the nodes

See the [cheat sheet](../labs/CHEATSHEET.md). In short, on a router/switch:

```bash
nano /etc/network/interfaces      # add your config below the "your data-plane configuration" line
ifreload -a                       # apply it
vtysh                             # routing: conf t ... end, write memory
```

In the GNS3 canvas the ports of a router/switch are labelled `eth1`, `eth2`, …; inside the node
they are `swp1`, `swp2`, … (the cable on `eth5` is `swp5`). `eth0` is always management.

## Saving your work

* `/etc/network/interfaces`, `/etc/frr` (after `write memory`), `/etc/dhcp`, `/etc/default`,
  `/etc/cgr` (RESTCONF datastore) and `/root` are kept by GNS3 when a node is stopped and started.
* **Stop** the project before shutting down your computer, and close GNS3 normally.
* To hand in configurations, use `./collect.py all` on the netauto station (one text file per
  device) or **File → Export portable project** in GNS3.

## Writing your own topology

`labs/<lab>/topology.yml` is short and readable:

```yaml
name: my-lab
nodes:
  sw1: {kind: frr, role: switch, mgmt: 192.168.100.11, x: 0, y: 0}
  r9:  {kind: frr, mgmt: 192.168.100.19, x: 200, y: 0, ports: 12,
        interfaces: my.interfaces, frr_config: my.frr.conf}   # optional pre-configuration
  pc1: {kind: vpcs, ip: 10.0.0.1/24, gw: 10.0.0.254, x: 0, y: 200}
  srv: {kind: host, role: server, ip: 10.9.0.10/24, gw: 10.9.0.1, x: 200, y: 200}
  pc2: {kind: host, ip: dhcp, x: 400, y: 200}                  # DHCP client on eth1
  netauto: {kind: netauto, mgmt: 192.168.100.10, x: -300, y: 0}
links:
  - [sw1:swp1, r9:swp1]
  - [sw1:swp2, pc1:e0]
  - [r9:swp2, srv:eth1]
```

Kinds: `frr` (router/switch, `role: router|switch` only changes the icon), `host` (Linux,
data port `eth1`), `netauto`, `vpcs`, `switch` (plain GNS3 Ethernet switch), `nat`.
Optional per node: `ports` (default 8), `mgmt`, `ip`/`gw` (hosts and PCs; `ip: dhcp` for a DHCP client).

**Coming from NVIDIA Air?** Export the simulation as JSON and convert it — same node and port names:

```bash
python tools/air2gns3.py MyLab.json -o labs/mylab/topology.yml --name mylab --mgmt-subnet 192.168.200.0/24
```

## Manual method (GUI only)

Run `python tools/cgr_lab.py templates` once, then drag *CGR Router*/*CGR Switch*/*CGR NetAuto*
and *VPCS* from the device list, draw the cables, and add an *Ethernet switch* for management.
To give a container its management address: right-click → **Edit config** →
```
auto eth0
iface eth0 inet static
    address 192.168.100.11
    netmask 255.255.255.0
```
