# Project 1 · Part 1 — Enterprise campus network (2025/2026 statement, GNS3 version)

This is the topology of the *ProjectCampusNetwork* simulation used in NVIDIA Air, with the
**same device names and the same port names**. The statement (tasks, scenarios 1 and 2,
addressing in 10.8.0.0/16, OSPF, bonds, summarisation, default route) is unchanged — only the
"Work Setup" part is replaced by this page.

![Air topology](air-topology.png)

## Build it

```bash
# Apple Silicon Macs, 8 GB laptops, or no nested virtualisation:
python tools/cgr_lab.py build labs/proj1-campus --lite --start

# x86 with ≥ 24 GB RAM (8 × Cumulus VX = 16 GB in the GNS3 VM):
python tools/cgr_lab.py build labs/proj1-campus --start
python tools/cgr_lab.py bootstrap proj1-campus
```

The lite version runs 8 FRR containers + 6 Linux host containers + netauto in **< 1 GB of RAM**.

| Device | Kind (lite) | Management (eth0) |
|---|---|---|
| Access1, Access2 | FRR switch | 192.168.200.13, .11 |
| Distribution1, Distribution2 | FRR switch/router | 192.168.200.14, .7 |
| SpineRouter1, SpineRouter2 | FRR router | 192.168.200.5, .3 |
| BorderRouter | FRR router | 192.168.200.9 |
| DatacenterRack | FRR switch | 192.168.200.12 |
| UserUbuntu1–4, Ubuntu-Server-5, UbuntuInternet | Linux host (data port **eth1**) | — |
| netauto | automation station | 192.168.200.254 |

Links (identical to Air): Access1 swp1-2 → Distribution1 swp1-2, Access1 swp3-4 → Distribution2 swp3-4,
Access2 swp1-2 → Distribution2 swp1-2, Access2 swp3-4 → Distribution1 swp3-4,
Access1 swp5/swp6 → UserUbuntu1/2, Access2 swp5/swp6 → UserUbuntu3/4,
Distribution1 swp5-6 ↔ Distribution2 swp5-6, Distribution1 swp7-8 → SpineRouter1 swp7-8,
Distribution1 swp9-10 → SpineRouter2 swp9-10, Distribution2 swp7-8 → SpineRouter2 swp7-8,
Distribution2 swp9-10 → SpineRouter1 swp9-10, SpineRouter1 swp1-2 ↔ SpineRouter2 swp1-2,
BorderRouter swp1-2 → SpineRouter1 swp3-4, BorderRouter swp3-4 → SpineRouter2 swp3-4,
BorderRouter swp5 → UbuntuInternet, DatacenterRack swp5-6 → SpineRouter1 swp5-6,
DatacenterRack swp10-11 → SpineRouter2 swp11-12, DatacenterRack swp1 → Ubuntu-Server-5.

## How to configure in lite mode

Same tasks, different syntax — see **[LITE-CHEATSHEET.md](../LITE-CHEATSHEET.md)**:

* VLANs, access ports, trunks, bonds, SVIs → `/etc/network/interfaces` + `ifreload -a`
* OSPF, default route, summarisation → `vtysh`
* Hosts → `ip addr add … dev eth1`, `ip route add default via …`

Example — Access1 in scenario 1 (VLANs 2 and 3, bond to Distribution1 as a trunk):

```
auto bond1
iface bond1
    bond-slaves swp1 swp2
    bond-mode 802.3ad
    bridge-vids 2 3

auto swp5
iface swp5
    bridge-access 2

auto swp6
iface swp6
    bridge-access 3

auto bridge
iface bridge
    bridge-vlan-aware yes
    bridge-ports bond1 bond2 swp5 swp6
    bridge-vids 2 3
    bridge-stp on
```
(`bond2` = swp3+swp4 towards Distribution2, defined the same way.)

## What to deliver

As in the statement: the configuration of every device for scenario 1 and scenario 2.
In lite mode that is, per device, `/etc/network/interfaces` and `/etc/frr/frr.conf`
(`vtysh -c "show running-config"`). Collect them all from netauto:

```bash
for ip in 13 11 14 7 5 3 9 12; do
  sshpass -p 'CumulusLab1!' ssh -o StrictHostKeyChecking=no cumulus@192.168.200.$ip \
    'echo "### $(hostname)"; cat /etc/network/interfaces; sudo vtysh -c "show running-config"'
done > /root/proj1-scenarioX.txt
```

## Scenario switching tip

Build each scenario as its own project so you keep both:
`build labs/proj1-campus --lite --name proj1-scenario1` and `… --name proj1-scenario2`.
