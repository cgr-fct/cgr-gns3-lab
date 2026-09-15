# Automation toolkit (`/root/cgr` on the netauto station)

Everything here runs **inside the lab**, on the `netauto` node, which shares the management
network with the `eth0` of every router/switch. When a lab is built, `cgr_lab.py` writes that
lab's device list to `/root/lab/inventory.yml` (Ansible YAML format); all tools use it
automatically. Login on the devices: user `cgr`, password `cgrlab`.

| File | What it is |
|---|---|
| `yang/cgr-device@2026-09-15.yang` | **The YANG data model** of a lab router/switch (VLANs, bonds, STP, SVIs, VRRP, DHCP, OSPF, IS-IS, BGP, operational state) |
| `restconf.py` | RESTCONF client (library + command line) |
| `apply_intent.py` | Model-driven deployment: YAML intent → validate against the YANG model → push over SSH or RESTCONF |
| `intent/*.yml` | Intent files (the device data, in YAML) |
| `templates/*.j2` | Jinja2 templates that turn the model into device files (interfaces, frr.conf, dhcpd.conf) |
| `cgrmodel.py` | Validation (yangson) and rendering, shared by `apply_intent.py` and the RESTCONF server |
| `cgrlib.py` | Small Python library: inventory + SSH sessions |
| `collect.py` | Run a command on all devices (text or JSON); back up configurations |
| `ansible.cfg`, `playbooks/` | The same ideas with Ansible (RESTCONF through the `uri` module) |
| `restconf_server.py` | The RESTCONF server that runs on every router/switch (for reference) |

## 1. The data model

```bash
cd /root/cgr
pyang -f tree yang/cgr-device@2026-09-15.yang
```

```
module: cgr-device
  +--rw device
     +--rw hostname?    string
     +--rw loopback*    ipv4-prefix
     +--rw bridge
     |  +--rw vlans*          vlan-id
     |  +--rw stp?            boolean
     |  +--rw stp-priority?   uint16
     +--rw interface* [name]              swpN or bondN
     |  +--rw bond-member*   string
     |  +--rw mode?          enumeration  access | trunk | routed
     |  +--rw access-vlan    vlan-id      (when mode = access)
     |  +--rw trunk-vlans*   vlan-id      (when mode = trunk)
     |  +--rw address*       ipv4-prefix  (when mode = routed)
     |  ...
     +--rw svi* [vlan]
     +--rw dhcp        server! (pools) / relay!
     +--rw ospf!       router-id, default-originate, area* (type, range, virtual-link), interface*
     +--rw isis!       net, is-type, interface*
     +--rw bgp!        asn, router-id, network*, aggregate*, neighbor* (...)
     +--ro state       interface*, route*, ospf-neighbor*, bgp-neighbor*
```

The same data is used everywhere: in YAML intent files, as JSON in RESTCONF bodies
(RFC 7951: `{"cgr-device:device": {...}}`), and in the device's datastore
(`/etc/cgr/running.json`). Every write is validated against the model first — types, patterns,
ranges, `mandatory`, `when` conditions.

## 2. RESTCONF

Every router/switch runs a RESTCONF server (RFC 8040, JSON encoding) on
`https://<eth0 address>/restconf`, with HTTP Basic authentication.

| Request | Meaning |
|---|---|
| `GET /restconf` | API root |
| `GET /restconf/data/ietf-yang-library:modules-state` | which modules the server implements |
| `GET /restconf/data/cgr-device:device` | configuration and state (`?content=config` / `nonconfig`) |
| `GET …/cgr-device:device/interface=swp1` | one list entry (keys after `=`, URL-encoded: `route=10.0.0.0%2F24`) |
| `PUT …/cgr-device:device/svi=10` | create or replace the target |
| `PATCH …/cgr-device:device` | merge the body into the target |
| `POST …/cgr-device:device` | create a child (`409` if it already exists) |
| `DELETE …/cgr-device:device/svi=10` | delete the target |

Media type `application/yang-data+json`. Status codes: `200` (GET), `201` (created),
`204` (changed), `400` (invalid data — the YANG error is in the body), `401`, `404`, `409`.

With `curl`:

```bash
R=https://192.168.100.11/restconf/data/cgr-device:device
curl -sk -u cgr:cgrlab "$R?content=config" | jq
curl -sk -u cgr:cgrlab "$R/state/interface=swp1" | jq
curl -sk -u cgr:cgrlab -X PATCH -H "Content-Type: application/yang-data+json" \
     -d '{"cgr-device:device": {"hostname": "sw1"}}' "$R" -w "%{http_code}\n"
```

With `restconf.py` (paths are relative to `cgr-device:device`; devices by inventory name):

```bash
./restconf.py sw1 get --content config
./restconf.py sw1 get state/route --content nonconfig
./restconf.py sw1 put svi=10 '{"cgr-device:svi": [{"vlan": 10, "address": ["10.10.10.1/24"]}]}'
./restconf.py sw1 post "" @new-port.yml            # body from a file (JSON or YAML)
./restconf.py sw1 delete svi=10
./restconf.py -v sw1 get hostname                  # -v prints the HTTP exchange
./restconf.py sw1 get --raw /restconf/data/ietf-yang-library:modules-state
```

or from Python:

```python
from restconf import Restconf
rc = Restconf("192.168.100.11")
print(rc.get("state/bgp-neighbor", content="nonconfig"))
rc.patch("", {"cgr-device:device": {"bridge": {"vlans": [30]}}})
```

**Good to know:** the RESTCONF datastore holds what was configured through RESTCONF or
`apply_intent.py`. Configuration typed by hand (vtysh, `/etc/network/interfaces`) is not
read back into it, but its effects show up in `state`. A RESTCONF write replaces the data-plane
part of `/etc/network/interfaces` and the whole FRR configuration of the device — so on one
device, use either the CLI or the model, not both at the same time.

## 3. Intent files and `apply_intent.py`

```yaml
# intent/lab00.yml
devices:
  sw1:                      # content of cgr-device:device for sw1
    hostname: sw1
    bridge: {vlans: [10]}
    interface:
      - {name: swp1, mode: trunk, trunk-vlans: [10]}
      - {name: swp2, mode: access, access-vlan: 10}
```

```bash
./apply_intent.py intent/lab00.yml --check          # validate against the YANG model
./apply_intent.py intent/lab00.yml --dry-run        # the device files it would generate
./apply_intent.py intent/lab00.yml --diff           # what would change on the devices
./apply_intent.py intent/lab00.yml                  # push over SSH (files + ifreload + frr-reload + dhcpd)
./apply_intent.py intent/lab00.yml --restconf       # push with RESTCONF (one PUT per device)
./apply_intent.py intent/lab00.yml --render out     # write the generated files to out/<device>/
```

Pushing is **declarative and idempotent**: you describe the desired state, the tools apply only
the differences (`ifreload`, `frr-reload.py`), and a second push changes nothing. After a push,
`--diff` shows any drift introduced later by hand or by RESTCONF.

A bigger example (bonds, SVIs, VRRP, DHCP relay, OSPF with a summarised area, BGP):

```yaml
devices:
  dist1:
    hostname: dist1
    loopback: [10.8.255.1/32]
    bridge: {vlans: [2, 3], stp-priority: 4096}
    interface:
      - {name: bond1, bond-member: [swp1, swp2], mode: trunk, trunk-vlans: [2, 3]}
      - {name: swp7, mode: routed, address: [10.8.100.1/30]}
    svi:
      - {vlan: 2, address: [10.8.2.2/24], vrrp: {vrid: 2, virtual-address: 10.8.2.1, priority: 200}}
      - {vlan: 3, address: [10.8.3.2/24]}
    dhcp:
      relay: {server: [10.8.200.10], client-interface: [vlan2, vlan3], upstream-interface: [swp7]}
    ospf:
      router-id: 10.8.255.1
      area: [{id: 1, range: [10.8.0.0/22]}]
      interface:
        - {name: lo, area: 0, passive: true}
        - {name: swp7, area: 0, network-type: point-to-point}
        - {name: vlan2, area: 1, passive: true}
    bgp:
      asn: 65500
      neighbor:
        - {address: 10.8.255.2, remote-as: internal, update-source: lo, next-hop-self: true}
```

## 4. Scripts and Ansible

```bash
./collect.py all -c "ip -br addr"                          # one command, every device
./collect.py all -c "vtysh -c 'show ip route json'" --json > routes.json
./collect.py all                                           # backups/<device>.txt

ansible all -m ping                                        # SSH
ansible all -b -m command -a "vtysh -c 'show bgp summary'"
ansible-playbook playbooks/deploy_intent.yml -e intent=intent/lab00.yml   # RESTCONF PUT
ansible-playbook playbooks/show_state.yml                  # RESTCONF GET of the state
ansible-playbook playbooks/show_routes.yml                 # SSH, saves reports/<device>-routes.yml
```

Your own script (save it in `/root/cgr`):

```python
#!/usr/bin/env python3
from cgrlib import load_inventory
from restconf import Restconf

for name, dev in load_inventory().items():
    rc = Restconf(dev["host"], dev["user"], dev["password"])
    state = rc.get("state", content="nonconfig")["cgr-device:state"]
    up = [n["address"] for n in state.get("bgp-neighbor", []) if n["state"] == "Established"]
    print(f"{name}: {len(state.get('route', []))} routes, BGP up with {up}")
```

## 5. Extending the model (exercise)

Add a feature end to end — e.g. static routes:
1. add a `list static-route` to `yang/cgr-device@2026-09-15.yang` and check it with
   `pyang --strict`;
2. render it in `templates/frr.conf.j2` (`ip route <prefix> <next-hop>`);
3. test with `./apply_intent.py … --dry-run`.

The routers use their own copy of the model, so an extended model works with
`apply_intent.py` over SSH; to use it with RESTCONF, copy the `yang/` and `templates/` folders
to `/usr/local/lib/cgr/` on the device and restart the server
(`pkill -f cgr-restconf; nohup cgr-restconf >/var/log/cgr-restconf.log 2>&1 &`).
