# Troubleshooting

### "Cannot reach the GNS3 server" / 401 from `cgr_lab.py`
GNS3 must be open. Check *Edit → Preferences → Server* and pass
`--server http://127.0.0.1:3080 --user <user> --password <password>`.

### VirtualBox: the GNS3 VM does not start
* *"must have a network adapter attached to a host-only …"*: create a host-only network with the
  `VBoxManage` commands in the install guide and attach **Adapter 1** of the GNS3 VM to it; **Adapter 2** must be NAT.
* An error about **nested virtualisation / VT-x / AMD-V** (Windows): GNS3 turns nested
  virtualisation on at every start and VirtualBox may refuse it while Hyper-V is active. Either
  turn Hyper-V off (*Windows Features*: untick *Hyper-V*, *Virtual Machine Platform* and
  *Windows Hypervisor Platform*, reboot — this disables WSL2/Docker Desktop), or use VMware.
* **Apple Silicon Mac:** VirtualBox cannot run the GNS3 VM (the firmware starts, the system
  does not boot, the screen stays blank). Use VMware Fusion or UTM (install guide, options A/B).

### "Could not pull the 'ghcr.io/…' image" (UTM on macOS)
The VM has no Internet access. The usual cause is a **VPN** on the Mac (e.g. the university VPN):
with it active, UTM's *Shared Network* does not forward the VM's traffic. Disconnect the VPN, quit
UTM (⌘Q), start the VM again, and check inside the VM (`ssh gns3@<VM address>`, password `gns3`):
`ping -c2 1.1.1.1` and `curl -sI https://ghcr.io/v2/`. Also check *System Settings → Privacy &
Security → Local Network* (UTM allowed) and firewalls/content filters. Then pull the images once
by hand (`docker pull ghcr.io/cgr-fct/cgr-frr:latest` and `…/cgr-netauto:latest`) and build
again. On other systems the same message means the GNS3 VM has no Internet access or the first
download was too slow — pulling by hand in the VM helps there too.

### UTM (Apple Silicon): the remote server stays red
GNS3 does not start the UTM VM for you — start it in UTM first, then GNS3. Check the VM address
(serial terminal: log in `gns3`/`gns3`, `ip -4 addr show eth0`) and that
`curl http://<address>/v2/version` answers in Terminal; fix the address in
*Preferences → Server → Remote servers*. The UTM display window may stay black — the console is in
the serial terminal window.

### `cgr_lab.py check` uses the wrong compute / says Docker is not available
It prefers the GNS3 VM, then any other connected server with Docker (e.g. the VirtualBox VM added
as a remote server), then the local server. `check` lists them all; pick one explicitly with
`--compute <id>` if needed. A red (not connected) server is ignored: start its VM first.

### I can't find the VMware download / Broadcom says my account is pending
VMware Workstation Pro and Fusion are free but only downloadable from the Broadcom support portal
after the (free) account passes an export-compliance check, which can take days. Use the exact
steps in the install guide (*My Downloads* → *Free Software Downloads available HERE*). On Windows
you can start with VirtualBox meanwhile (see the Windows guide).

### GNS3 VM stays red / "GNS3 VM is not running"
Open VMware and look at the VM console for errors. In GNS3: *Edit → Preferences → GNS3 VM* →
check the VM name and engine (VMware). GUI and VM must be **the same version** (2.2.54) — the VM
console shows its version.

### `check` says Docker is not available
You are connected to the local compute on Windows/macOS instead of the GNS3 VM: redo the setup
wizard and choose *Run appliances in a virtual machine*. On Linux: `sudo apt install docker.io`,
add yourself to the `docker` group, log out and in.

### Nodes fail to start ("image not found", "pull access denied", timeout)
The first start downloads the images and needs Internet access from the GNS3 VM (through its
NAT network adapter in VMware). Check that the image names in `tools/lab_settings.yml` are the
ones your instructor published. To download them in advance: GNS3 VM console → *Shell* →
`docker pull <image>` for both images.

### Bonds or VLANs fail with "Operation not supported" / "Unknown device type"
The kernel modules are not loaded in the GNS3 VM (or on your Linux machine). GNS3 VM console →
*Shell* (Linux: a terminal) → `sudo modprobe -a bonding 8021q dummy macvlan`, then `ifreload -a` again.

### `ifreload -a` prints errors
Read the message — it names the interface and the option. Typical causes: option lines not
indented, a port listed in `bridge-ports` that is also a bond member, a typo in an option name.
Warnings about IPv6 or `/proc/sys` can be ignored.

### A node hangs after *Reload* (console shows nothing, no interfaces)
Stop the node and start it again (or stop/start the whole project with `cgr_lab.py stop` /
`start`) instead of using *Reload*.

### `apply_intent.py` or RESTCONF: "… failed: error: bridge: … Operation not supported"
The GNS3 VM kernel is missing a feature (VLAN filtering, bonding): see the item about kernel
modules above. The RESTCONF server rolls the change back; `apply_intent.py` leaves the files
written, so fix the cause and push again.

### `REFUSED … hand-made setting(s) that this push would remove` / RESTCONF `409 resource-denied`
The device has configuration typed by hand that the pushed data does not contain, so the push
would delete it. Either keep it — `./apply_intent.py <file> --import <device>`, check the notes,
push again — or drop it: `--force` (apply_intent.py, restconf.py), `?force=true` (curl),
`-e force=true` (Ansible playbook). Settings the model cannot express (see the import notes)
can only be kept by leaving the device CLI-managed.

### RESTCONF: `401`
User `cgr`, password `cgrlab` (`curl -u cgr:cgrlab …`).

### RESTCONF: `400` with "SchemaError" / "YangTypeError"
The data does not match the `cgr-device` YANG model — the message names the node, e.g.
`missing-data: expected 'access-vlan'` (an access port needs a VLAN) or
`does not match the expected format` (an address/prefix is wrong). Check with
`pyang -f tree yang/cgr-device@2026-09-15.yang` and `./apply_intent.py <file> --check`.

### RESTCONF: `404` on PATCH although the interface exists
PATCH only works on data that exists **in the RESTCONF datastore** (configured by RESTCONF or
`apply_intent.py`), not on configuration typed by hand. Import the device first
(`./apply_intent.py <file> --import <device>` and push), or create the data with PUT or POST.

### RESTCONF: connection refused
The server runs on the router/switch: `ps aux | grep cgr-restconf`, log in
`/var/log/cgr-restconf.log`. Restart it with
`pkill -f cgr-restconf; nohup cgr-restconf >/var/log/cgr-restconf.log 2>&1 &`.

### DHCP clients get no address
On the server: `dhcpd -t` (syntax), `ps aux | grep dhcpd`, `INTERFACESv4` in
`/etc/default/isc-dhcp-server`, and a `subnet` declaration for every listening interface. With a
relay: `ps aux | grep dhcrelay`, and the server needs a route back to the relay's SVI subnet.
`tcpdump -ni <iface> port 67 or port 68` on each hop shows where the requests stop.

### My configuration disappeared after a restart
`vtysh` changes must be saved with `write memory`. Interface changes must be in
`/etc/network/interfaces` (commands like `ip addr add` are lost on restart).

### PCs (VPCS) can't ping
VPCS: `show ip` — did the address load? Otherwise `ip 10.0.0.1/24 10.0.0.254` and `save`.
On the switch: `bridge vlan show` (is the port in the right VLAN?), `ip -br link` (is it up?).

### Linux hosts can't ping
Use `eth1` (not `eth0`) and set a default route: `ip route add default via <gateway>`.

### SSH from netauto asks for a password / fails
User `cgr`, password `cgrlab`. Check reachability first (`ping 192.168.100.X`) and that the device
has its management address (`ip -br addr show eth0` on the device).

### Out of disk space in the GNS3 VM
Delete old projects with `cgr_lab.py delete <project>`.
