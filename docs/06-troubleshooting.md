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
*Shell* (Linux: a terminal) → `sudo modprobe -a bonding 8021q dummy`, then `ifreload -a` again.

### `ifreload -a` prints errors
Read the message — it names the interface and the option. Typical causes: option lines not
indented, a port listed in `bridge-ports` that is also a bond member, a typo in an option name.
Warnings about IPv6 or `/proc/sys` can be ignored.

### My configuration disappeared after a restart
`vtysh` changes must be saved with `write memory`. Interface changes must be in
`/etc/network/interfaces` (commands like `ip addr add` are lost on restart).

### PCs (VPCS) can't ping
VPCS: `show ip` — did the address load? Otherwise `ip 10.0.0.1/24 10.0.0.254` and `save`.
On the switch: `bridge vlan show` (is the port in the right VLAN?), `ip -br link` (is it up?).

### Linux hosts can't ping
Use `eth1` (not `eth0`) and set a default route: `ip route add default via <gateway>`.

### SSH from netauto asks for a password / fails
User `cgr`, password `cgr`. Check reachability first (`ping 192.168.100.X`) and that the device
has its management address (`ip -br addr show eth0` on the device).

### Out of disk space in the GNS3 VM
Delete old projects with `cgr_lab.py delete <project>`.
