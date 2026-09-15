# Troubleshooting

### `KVM support available: False`
The GNS3 VM has no nested virtualisation, so Cumulus VX can't start.
* **Windows:** redo [step 1 of the Windows guide](01-install-windows.md#1-turn-off-the-windows-hypervisor-needed-for-cumulus-vx)
  (Memory integrity off, Hyper-V/VMP/WHP off, `bcdedit /set hypervisorlaunchtype off`, reboot).
  Run `systeminfo` — the line *"A hypervisor has been detected"* must **not** appear.
  In VMware: VM settings → *Processors* → tick **Virtualize Intel VT-x/EPT or AMD-V/RVI**.
* **BIOS/UEFI:** enable Intel VT-x / AMD SVM.
* Still stuck → use `--lite`.

### "Cannot reach the GNS3 server" / 401 from `cgr_lab.py`
GNS3 must be open. Check *Edit → Preferences → Server* and pass
`--server http://127.0.0.1:3080 --user <user> --password <password>`.

### GNS3 VM stays red / "GNS3 VM is not running"
Open VMware and look at the VM console for errors. Give it less RAM if the host is short of memory.
In GNS3: *Edit → Preferences → GNS3 VM* → check the VM name and engine (VMware).
Make sure GUI and VM are **the same version** (the VM console shows its version).

### Cumulus VX console shows nothing
It takes 1–3 minutes to show output; press *Enter*. If it never appears, check that the
template uses `-nographic` in *Advanced options* and console type *telnet*.

### Cumulus VX boots but is extremely slow / reboots
Not enough RAM in the GNS3 VM, or KVM missing. Stop other projects. Try `cumulus.ram: 1536`.

### `bootstrap` times out
Open the console and look: maybe the password was already changed (the tool also tries
`CumulusLab1!`), or the device is still booting. You can always paste
`labs/<lab>/bootstrap/<device>.txt` manually. Run it for one device: `bootstrap <project> --only sw1`.

### REST API: `403 Forbidden`
The password is still the factory one, or wrong. Log in on the console and run `passwd`.

### REST API: connection refused / timeout
From netauto `ping` the device. On the device: `nv show system api` — the listening address
must include the eth0 address (`nv set system api listening-address 192.168.100.X`, `nv config apply`).

### Docker nodes fail to start ("image not found", "pull access denied")
The GNS3 VM needs Internet access (through its NAT network adapter in VMware). The image
name in `tools/lab_settings.yml` must match what your instructor published.

### FRR container: bonds or VLANs fail with "Operation not supported" / "Unknown device type"
The kernel modules are not loaded in the GNS3 VM (or on your Linux host). Open the GNS3 VM
console → *Shell* (Linux: a terminal) and run `sudo modprobe -a bonding 8021q dummy`, then
`ifreload -a` again on the node.

### FRR container: `ifreload -a` errors
Read the message — it points at the line in `/etc/network/interfaces`. Indent option lines
with spaces, and keep the management block at the top untouched.

### PCs can't ping
VPCS: `show ip` — did the address load? Otherwise `ip 10.0.0.1/24 10.0.0.254` and `save`.
Is the switch port up (`nv show interface`)? Is the port in the right VLAN?

### Windows: "VMware Workstation and Hyper-V are not compatible"
Hyper-V is still active — see the first item.

### Out of disk space
Each Cumulus VX uses a *linked clone* (a few hundred MB). Delete old projects with
`cgr_lab.py delete <project>`.
