# Lab 02 — OSPFv2

**Topics:** adjacencies, LSDB, single-area and multi-area OSPF, costs and path selection,
stub / totally stubby areas, summarisation at the ABR.

**Devices:** r1, r2 = Cumulus VX (configure with **NVUE**); r3, r4 = FRR containers
(configure with **vtysh** + `/etc/network/interfaces`). Both use FRRouting underneath, so the
`show` commands are the same. **Resources:** ≈ 4.5 GB (lite: < 0.5 GB).

```mermaid
graph TB
  pc1["pc1 172.16.1.10"] --- |swp3| r1
  r1["r1 (Cumulus)<br/>lo 10.255.2.1"] --- |"swp1 10.2.12.0/30 swp1"| r2["r2 (Cumulus)<br/>lo 10.255.2.2"]
  r1 --- |"swp2 10.2.13.0/30 swp1"| r3["r3 (FRR)<br/>lo 10.255.2.3"]
  r2 --- |"swp2 10.2.24.0/30 swp1"| r4["r4 (FRR)<br/>lo 10.255.2.4"]
  r3 --- |"swp2 10.2.34.0/30 swp2"| r4
  r3 --- |swp3| pc3["pc3 172.16.3.10"]
  r4 --- |swp3| pc4["pc4 172.16.4.10"]
```

| Link / LAN | Subnet | Addresses |
|---|---|---|
| r1–r2 | 10.2.12.0/30 | r1 .1, r2 .2 |
| r1–r3 | 10.2.13.0/30 | r1 .1, r3 .2 |
| r2–r4 | 10.2.24.0/30 | r2 .1, r4 .2 |
| r3–r4 | 10.2.34.0/30 | r3 .1, r4 .2 |
| pc1 LAN (r1 swp3) | 172.16.1.0/24 | r1 .1, pc1 .10 |
| pc3 LAN (r3 swp3) | 172.16.3.0/24 | r3 .1, pc3 .10 |
| pc4 LAN (r4 swp3) | 172.16.4.0/24 | r4 .1, pc4 .10 |
| Loopbacks | 10.255.2.N/32 | rN |

Management: r1 .31, r2 .32, r3 .33, r4 .34 (192.168.100.0/24).

```bash
python tools/cgr_lab.py build labs/lab02-ospf --start
python tools/cgr_lab.py bootstrap lab02-ospf          # r1, r2 only (r3/r4 need no bootstrap)
```

### How to configure each kind of router

**r1 / r2 (NVUE):**
```bash
nv set interface lo ip address 10.255.2.1/32
nv set interface swp1 ip address 10.2.12.1/30
nv set vrf default router ospf router-id 10.255.2.1
nv set interface swp1 router ospf area 0
nv set interface swp1 router ospf network-type point-to-point
nv set interface lo router ospf area 0
nv config apply -y
nv show vrf default router ospf neighbor          # or: sudo vtysh -c "show ip ospf neighbor"
```

**r3 / r4 (FRR container):** addresses in `/etc/network/interfaces`, then `ifreload -a`:
```
auto swp1
iface swp1
    address 10.2.13.2/30
```
routing in `vtysh`:
```
conf t
 router ospf
  ospf router-id 10.255.2.3
 interface swp1
  ip ospf area 0
  ip ospf network point-to-point
 end
write memory
```

## Part A — Single area
Put **everything** in area 0 (links, loopbacks, LANs — make the LAN interfaces passive).
Verify full reachability (`pc1> ping 172.16.4.10`) and explain `show ip ospf database`
(how many router LSAs? any network LSAs? why?).

## Part B — Costs and path selection
1. From pc1, `trace 172.16.4.10`. Which path is used? Why? (`show ip route 172.16.4.0/24`)
2. Change interface costs so that r1 reaches r4's LAN **via r3** (r1→r3→r4).
   NVUE: `nv set interface swp1 router ospf cost 100`; FRR: `ip ospf cost 100`.
3. What happens to the path when you shut the r3–r4 link?

## Part C — Multi-area
Re-design: **area 0** = r1–r2 link, r1/r2 loopbacks and pc1 LAN. **area 1** = r1–r3, r3–r4,
r2–r4 links, r3/r4 loopbacks and LANs. r1 and r2 are now ABRs.
Look at the LSDB on r1 and on r3: which LSA types appear, and who generates them?

## Part D — Stub areas and summarisation
1. Make area 1 a **stub** area, then **totally stubby**. Compare `show ip route` on r3 each time.
   NVUE: `nv set vrf default router ospf area 1 type stub` (`totally-stub`); FRR: `area 1 stub [no-summary]`.
2. On the ABRs summarise area 1's LANs as one prefix. Which prefix covers 172.16.3.0/24 and
   172.16.4.0/24 but not 172.16.1.0/24? NVUE: `nv set vrf default router ospf area 1 range <prefix>`;
   FRR: `area 1 range <prefix>`. Check the result on r2 and on pc1.

## Deliverables
Final configs (`nv config show -o yaml` for r1/r2, `show running-config` for r3/r4), LSDB
excerpts with your explanation, traceroutes for Part B.

## Automation corner
`apply_intent.py` supports OSPF (`ospf.router_id`, `ospf.interfaces.<if>.area|network_type|passive`).
Write `intent/lab02.yml` for Part A and push it: it uses NVUE for r1/r2 and SSH+FRR for r3/r4
(the `platform` field in `inventory.yml`).
