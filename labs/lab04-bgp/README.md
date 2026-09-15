# Lab 04 — BGP: a dual-homed enterprise

**Topics:** eBGP and iBGP sessions, next-hop-self, IGP underlay for iBGP, prefix
advertisement, local preference, AS-path prepending, communities, provider filtering.

**Devices:** e1, e2 = your enterprise edge routers (Cumulus VX, AS 65000).
isp1 (AS 65101) and isp2 (AS 65102) are FRR routers **already configured** by the instructor —
you may log in and use `show` commands, but do not change them.
**Resources:** ≈ 4.5 GB (lite: < 0.5 GB).

```mermaid
graph TB
  srv["srv 203.0.113.10<br/>(the Internet)"] --- |swp3| isp2
  isp1["isp1 · AS 65101<br/>announces 198.18.1.0/24"] --- |"swp2 198.51.100.8/30 swp2"| isp2["isp2 · AS 65102<br/>announces 203.0.113.0/24"]
  isp1 --- |"swp1 198.51.100.0/30 swp2"| e1
  isp2 --- |"swp1 198.51.100.4/30 swp2"| e2
  e1["e1 · AS 65000<br/>lo 10.255.4.1"] --- |"swp1 10.4.12.0/30 swp1"| e2["e2 · AS 65000<br/>lo 10.255.4.2"]
  e1 --- |swp3| pc1["pc1 192.0.2.10/25"]
  e2 --- |swp3| pc2["pc2 192.0.2.130/25"]
```

| Link | Subnet | Addresses |
|---|---|---|
| e1–e2 | 10.4.12.0/30 | e1 .1, e2 .2 |
| e1–isp1 | 198.51.100.0/30 | isp1 .1, e1 .2 |
| e2–isp2 | 198.51.100.4/30 | isp2 .5, e2 .6 |
| isp1–isp2 | 198.51.100.8/30 | isp1 .9, isp2 .10 |
| LAN e1 | 192.0.2.0/25 | e1 .1, pc1 .10 |
| LAN e2 | 192.0.2.128/25 | e2 .129, pc2 .130 |
| Internet LAN | 203.0.113.0/24 | isp2 .1, srv .10 |
| Loopbacks | e1 10.255.4.1, e2 10.255.4.2 | |

Your address block is **192.0.2.0/24**. The ISPs accept only 192.0.2.0/24 or more-specifics
up to /25 from you, send you a **default route**, and honour this community:

| Community | Meaning |
|---|---|
| `65101:80` (to isp1) / `65102:80` (to isp2) | "backup link": ISP sets local-preference 80 instead of 200 |

```bash
python tools/cgr_lab.py build labs/lab04-bgp --start
python tools/cgr_lab.py bootstrap lab04-bgp
```

## Part A — Underlay
Configure interface addresses on e1/e2 and OSPF area 0 between them (link + loopbacks + LANs as
passive). Check that e1 can ping e2's loopback.

## Part B — eBGP and iBGP
1. e1: `nv set router bgp autonomous-system 65000`, `nv set router bgp router-id 10.255.4.1`,
   eBGP to 198.51.100.1 (AS 65101): `nv set vrf default router bgp neighbor 198.51.100.1 remote-as 65101`.
   e2: the same towards isp2.
2. iBGP between the loopbacks (`remote-as internal`, `update-source lo`).
3. Advertise your LANs (`nv set vrf default router bgp address-family ipv4-unicast network 192.0.2.0/25`).
4. Verify: `nv show vrf default router bgp neighbor`, `sudo vtysh -c "show bgp ipv4 unicast"`.
   `pc1> ping 203.0.113.10` must work.
5. On e1, look at the route to 203.0.113.0/24 learned from e2 — is its next hop reachable?
   Fix it with **next-hop-self** (`... neighbor 10.255.4.2 address-family ipv4-unicast nexthop-setting self`).

## Part C — Traffic engineering
Company policy: **isp1 is the primary provider** for both directions.

1. *Outbound:* set a higher local preference on routes learned from isp1 (route-map /
   NVUE `router policy route-map`), so that e2 also exits via e1. Verify with `pc2> trace 203.0.113.10`.
2. *Inbound:* make isp2 prefer the path through isp1 to reach 192.0.2.0/24. Try two ways and
   compare on isp2 (`show bgp ipv4 192.0.2.0/24`):
   a) AS-path prepend towards isp2; b) the `65102:80` community towards isp2
   (check that communities are actually sent to the neighbour — NVUE:
   `... neighbor <ip> address-family ipv4-unicast community-advertise regular on`).
   Only one of the two methods works here. Which one, and why? (Hint: read isp2's
   `CUSTOMER-IN` route-map with `show route-map` and remember the BGP decision process order.)
3. Advertise the aggregate 192.0.2.0/24 (in addition to or instead of the /25s). What changes?
4. Fail the e1–isp1 link. How long until pc1 reaches srv again? Restore it.

## Deliverables
`nv config show -o yaml` of e1/e2, `show bgp ipv4 unicast` on isp1 and isp2 before/after
Part C, traceroutes, and a short explanation of each policy.

## Automation corner
`automation/intent/lab04-bgp-example.yml` contains e1's intent (underlay + BGP). Complete e2,
then push both with `./apply_intent.py intent/lab04-bgp-example.yml`. Extend the model with
`local_pref` / `prepend` for Part C.

## Lite version
In `--lite` mode e1/e2 are FRR containers: configure BGP with `vtysh` (`router bgp 65000`,
`neighbor ... remote-as ...`, `address-family ipv4 unicast` / `network ...`), and use
`./apply_intent.py ... --lite` for automation.
