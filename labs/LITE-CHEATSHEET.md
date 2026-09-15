# Lite cheat sheet — NVUE commands and their FRR-container equivalents

In lite mode (`build … --lite`) every Cumulus VX becomes a small FRR container. The port names
are the same (`swp1`, `swp2`, …, `eth0` = management), the routing daemon is the same (FRR), but
there is no `nv` command. You configure:

* **interfaces, bridges, VLANs, bonds** in `/etc/network/interfaces`
  (ifupdown2 — the format Cumulus Linux itself used before NVUE), then apply with `ifreload -a`;
* **routing** with `vtysh` (Cisco-like CLI), then `write memory`.

In the GNS3 canvas the container ports are labelled `eth1`, `eth2`, …; inside the node they are
renamed to `swp1`, `swp2`, … (the cable on `eth5` is `swp5`).

Keep the management block at the top of `/etc/network/interfaces`; add your configuration
below the `# ---- your data-plane configuration` line. Indent option lines with spaces.

## Layer 2

| NVUE (Cumulus VX) | `/etc/network/interfaces` (lite) |
|---|---|
| `nv set bridge domain br_default vlan 2,3` | `auto bridge` / `iface bridge` / `    bridge-vlan-aware yes` / `    bridge-ports swp5 swp6 bond1` / `    bridge-vids 2 3` |
| `nv set interface swp5 bridge domain br_default access 2` | `auto swp5` / `iface swp5` / `    bridge-access 2` |
| `nv set interface swp1 bridge domain br_default vlan 2,3` (trunk) | `iface swp1` / `    bridge-vids 2 3` (and list swp1 in `bridge-ports`) |
| `nv set bridge domain br_default untagged 1` | `bridge-pvid 1` under `iface bridge` |
| `nv set interface bond1 bond member swp1,swp2` | `auto bond1` / `iface bond1` / `    bond-slaves swp1 swp2` / `    bond-mode 802.3ad` / `    bond-lacp-rate fast` |
| `nv set interface bond1 bridge domain br_default vlan 2,3` | under `iface bond1`: `    bridge-vids 2 3`, and put `bond1` (not swp1/swp2) in `bridge-ports` |
| `nv set interface bond1 ip address 10.8.0.1/30` (L3 bond) | under `iface bond1`: `    address 10.8.0.1/30` |
| `nv set interface vlan2 ip address 10.8.2.1/24` (SVI) | `auto vlan2` / `iface vlan2` / `    address 10.8.2.1/24` / `    vlan-id 2` / `    vlan-raw-device bridge` |
| `nv set bridge domain br_default stp priority 4096` | under `iface bridge`: `    bridge-stp on` / `    bridge-bridgeprio 4096` |
| `nv set interface swp1 ip address 10.8.1.1/30` | `auto swp1` / `iface swp1` / `    address 10.8.1.1/30` |
| `nv set interface lo ip address 10.8.255.1/32` | `auto lo` / `iface lo inet loopback` / `    address 10.8.255.1/32` |
| `nv config apply` | `ifreload -a` |
| `nv show interface` / `nv show bridge domain br_default vlan` | `ip -br addr`, `bridge vlan show`, `bridge link`, `cat /proc/net/bonding/bond1` |

Spanning tree in lite mode is the Linux kernel's STP (802.1D), not RSTP/MSTP — the root bridge
and blocked-port logic is the same, convergence is slower.

## Routing (vtysh — identical on Cumulus VX with `sudo vtysh`)

```
vtysh
conf t
 router ospf
  ospf router-id 10.8.255.1
  default-information originate always        ! inject a default route
  area 1 range 10.8.0.0/22                    ! summarise at an ABR
  summary-address 10.8.0.0/22                 ! summarise redistributed routes (ASBR)
  area 32 virtual-link 5.5.5.5                ! virtual link through area 32
 interface swp1
  ip ospf area 0
  ip ospf network point-to-point              ! or broadcast
  ip ospf priority 255                        ! DR election
  ip ospf passive
 end
write memory
```

| NVUE | vtysh |
|---|---|
| `nv set vrf default router ospf router-id X` | `router ospf` / `ospf router-id X` |
| `nv set interface swp1 router ospf area 0` | `interface swp1` / `ip ospf area 0` |
| `nv set interface swp1 router ospf network-type broadcast` | `ip ospf network broadcast` |
| `nv set interface swp1 router ospf priority 255` | `ip ospf priority 255` |
| `nv set interface swp1 router ospf passive on` | `ip ospf passive` |
| `nv set vrf default router ospf area 1 range P` | `area 1 range P` |
| `nv set vrf default router ospf default-originate on` (+ `always on`) | `default-information originate [always]` |
| `nv set router bgp autonomous-system 65001` | `router bgp 65001` |
| `nv set vrf default router bgp neighbor N remote-as 65002` | `neighbor N remote-as 65002` |
| `nv set vrf default router bgp address-family ipv4-unicast network P` | `address-family ipv4 unicast` / `network P` |
| `nv show vrf default router ospf neighbor` | `show ip ospf neighbor` |

(NVUE command spellings vary slightly between Cumulus releases — use `nv set vrf default router ospf -h`
to check; the vtysh column is what you type in lite mode.)

Useful show commands: `show ip route`, `show ip ospf database`, `show ip ospf interface`,
`show bgp summary`, `show bgp ipv4 unicast`, `show running-config`.

> FRR advertises addresses configured on `lo` as /32 host routes, whatever mask you give them.
> If you want a "loopback" subnet advertised with its real mask (e.g. /27, as on Cisco), create
> a dummy interface instead: `auto lo1` / `iface lo1` / `    link-type dummy` / `    address 172.16.9.33/27`.

## Linux hosts (UserUbuntu*, servers)

The hosts are small Debian containers; the data port is `eth1` (as in Air).

```bash
ip addr add 10.8.2.10/24 dev eth1
ip route add default via 10.8.2.1
ping 10.8.3.10 ; traceroute 10.8.100.10
python3 -m http.server 80            # a quick "server" on Ubuntu-Server-5
```

To keep the address after a restart, edit `/etc/network/interfaces` on the host
(or right-click the node in GNS3 → *Edit config*):
```
auto eth1
iface eth1 inet static
    address 10.8.2.10
    netmask 255.255.255.0
    gateway 10.8.2.1
```
