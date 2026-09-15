# Building and using a lab

Keep the **GNS3 GUI open** (it runs the controller the tool talks to). On Windows use
`py` instead of `python`; on macOS/Linux activate the venv first (`source .venv/bin/activate`).

## The 3-command workflow

```bash
python tools/cgr_lab.py build labs/lab01-campus-switching --start   # add --lite if needed
python tools/cgr_lab.py bootstrap lab01-campus-switching            # full mode only
python tools/cgr_lab.py consoles lab01-campus-switching             # list console ports
```

Then in GNS3: **File → Open project → lab01-campus-switching**. Double-click a device to open
its console (or right-click → *Console*).

* `build` creates the project, every device, every cable, the management switch, the IP
  addresses of the PCs, and the management addresses of the containers.
* `bootstrap` waits for each Cumulus VX to boot (2–4 min), logs in, changes the factory
  password to `CumulusLab1!`, sets the hostname, the management IP and enables the REST API.
  It uses the lines in `labs/<lab>/bootstrap/<device>.txt` — you can also paste them by hand.
* The first start of a lab downloads the container images (a few minutes).

Other commands:

| Command | Does |
|---|---|
| `check` | Tests the connection, compute, Docker, KVM and the Cumulus image |
| `start <project>` / `stop <project>` | Start/stop all devices |
| `build <lab> --force` | Rebuilds the project from scratch (**your configs are lost**) |
| `build <lab> --name myname` | Build a second copy with another name |
| `delete <project>` | Deletes the project |
| `--server http://IP:3080 --user U --password P` | Connect to another GNS3 server |

If `cgr_lab.py` can't log in: GNS3 → **Edit → Preferences → Server** shows the host, port,
user and password of the local server. Pass them with `--server/--user/--password` or set
`GNS3_SERVER`, `GNS3_USER`, `GNS3_PASSWORD`.

## Saving your work

* Cumulus: `nv config apply` also saves to the startup configuration by default;
  `nv config save` does it explicitly.
* FRR nodes: `write memory` in vtysh; `/etc/network/interfaces`, `/etc/frr` and `/root` are
  kept by GNS3.
* **Stop** the project before shutting down your computer, and close GNS3 normally
  (this also suspends/stops the GNS3 VM).
* To hand in a project: **File → Export portable project** (untick *include base images*).

## Manual method (GUI only)

Useful to understand what the tool does, or to extend a topology.

1. `python tools/cgr_lab.py templates` once — or create them by hand:
   * **Cumulus VX:** *Edit → Preferences → QEMU VMs → New* → run on the GNS3 VM → name
     `CGR Cumulus VX` → RAM 2048 MB → disk image = the Cumulus qcow2 → Finish. Then *Edit*:
     *General*: vCPUs 2, console telnet; *HDD*: disk interface `virtio`;
     *Network*: adapters **8**, type **virtio-net-pci**, first port name `eth0`,
     name format `swp{port1}`; *Advanced*: options `-nographic`.
   * **FRR / netauto:** *Docker containers → New* → image name from `tools/lab_settings.yml`,
     adapters 8 (netauto: 1), console telnet.
2. *File → New blank project*, drag the devices, draw the cables (`swp1` = second port).
3. Add an **Ethernet switch** named `mgmt-sw` and connect every device's `eth0` to it.
4. For each container: right-click → **Edit config** (network configuration) and set eth0,
   e.g. for netauto:
   ```
   auto eth0
   iface eth0 inet static
       address 192.168.100.10
       netmask 255.255.255.0
   ```
5. For each VPCS: open the console and type `ip 10.0.0.1/24 10.0.0.254` then `save`.
6. Start everything and bootstrap each Cumulus VX by pasting its `bootstrap/<device>.txt`.

## Writing your own topology

`labs/<lab>/topology.yml` is short and readable:

```yaml
name: my-lab
nodes:
  sw1: {kind: cumulus, role: switch, mgmt: 192.168.100.11, x: 0, y: 0}
  r9:  {kind: frr, mgmt: 192.168.100.19, x: 200, y: 0,
        interfaces: my.interfaces, frr_config: my.frr.conf}   # optional pre-configuration
  pc1: {kind: vpcs, ip: 10.0.0.1/24, gw: 10.0.0.254, x: 0, y: 200}
  netauto: {kind: netauto, mgmt: 192.168.100.10, x: -300, y: 0}
links:
  - [sw1:swp1, r9:swp1]
  - [sw1:swp2, pc1:e0]
```

Kinds: `cumulus`, `frr`, `netauto`, `vpcs`, `switch` (plain GNS3 Ethernet switch), `nat`.
Optional per node: `ram`, `cpus`, `ports`.
