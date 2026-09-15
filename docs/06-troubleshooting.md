# Troubleshooting

### "Cannot reach the GNS3 server" / 401 from `cgr_lab.py`
GNS3 must be open. Check *Edit → Preferences → Server* and pass
`--server http://127.0.0.1:3080 --user <user> --password <password>`.

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

### RESTCONF: `401`
User `cgr`, password `cgrlab` (`curl -u cgr:cgrlab …`).

### RESTCONF: `400` with "SchemaError" / "YangTypeError"
The data does not match the `cgr-device` YANG model — the message names the node, e.g.
`missing-data: expected 'access-vlan'` (an access port needs a VLAN) or
`does not match the expected format` (an address/prefix is wrong). Check with
`pyang -f tree yang/cgr-device@2026-09-15.yang` and `./apply_intent.py <file> --check`.

### RESTCONF: `404` on PATCH although the interface exists
PATCH only works on data that exists **in the RESTCONF datastore** (configured by RESTCONF or
`apply_intent.py`), not on configuration typed by hand. Use PUT or POST to create it.

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
