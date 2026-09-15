# Automation toolkit (`/root/cgr` on the netauto station)

Everything here runs **inside the lab**, on the `netauto` node, which shares the management
network with every router/switch `eth0`. When you build a lab, `cgr_lab.py` writes that lab's
device list to `/root/lab/inventory.yml` (Ansible YAML format); all tools below use it
automatically.

| File | What it teaches |
|---|---|
| `cgrlib.py` | A small Python library: read the inventory, open an SSH session, run commands, read/write files |
| `collect.py` | Run a command on all devices (text or JSON output); back up configurations |
| `schema/intent.schema.yml` | A data model (JSON Schema) that validates intent files — the role YANG plays for NETCONF/RESTCONF |
| `intent/*.yml` | Network intent written in YAML |
| `templates/*.j2` | Jinja2 templates: ifupdown2 interfaces and FRR configuration |
| `apply_intent.py` | Validate → render → diff → push (idempotent) |
| `ansible.cfg`, `playbooks/` | The same ideas with Ansible (same inventory, same templates) |
| `inventory.yml` | Fallback inventory for labs 00–04 |

## Quick tour

```bash
cd /root/cgr
cat ~/lab/inventory.yml                              # the devices of this lab

./collect.py all -c "ip -br addr"                    # 1. one command, every device
./collect.py all -c "vtysh -c 'show ip route json'" --json > routes.json
./collect.py all                                     #    backups/<device>.txt

./apply_intent.py intent/lab00.yml --dry-run         # 2. what would be configured?
./apply_intent.py intent/lab00.yml --diff            #    what would change on the devices?
./apply_intent.py intent/lab00.yml                   #    push it (run it twice: nothing changes)
./apply_intent.py intent/lab00.yml --render out      #    write every generated file to out/

ansible all -m ping                                  # 3. Ansible
ansible all -b -m command -a "vtysh -c 'show bgp summary'"
ansible-playbook playbooks/show_routes.yml           #    reports/<device>-routes.yml
ansible-playbook playbooks/deploy_intent.yml -e intent=intent/lab00.yml
```

## Writing your own script (save it in /root/cgr)

```python
#!/usr/bin/env python3
import json
from cgrlib import Device, load_inventory

for name, dev in load_inventory().items():
    with Device(dev) as d:
        nbrs = json.loads(d.run("sudo vtysh -c 'show ip ospf neighbor json'"))
        print(name, list(nbrs.get("neighbors", {})))
```

Most FRR `show` commands accept `json` at the end — structured data instead of screen-scraping.

## The intent model

```yaml
devices:
  e1:
    hostname: e1
    loopback: 10.255.4.1/32
    vlans: [10, 20]
    interfaces:
      swp1: {mode: routed, ip: 10.4.12.1/30, description: "to e2"}
      swp2: {mode: access, vlan: 10}
      swp3: {mode: trunk, vlans: [10, 20]}
    svis:
      10: {ip: 10.10.10.1/24}
    ospf:
      router_id: 10.255.4.1
      interfaces:
        lo:   {area: 0, passive: true}
        swp1: {area: 0, network_type: point-to-point}
    bgp:
      asn: 65000
      router_id: 10.255.4.1
      networks: [192.0.2.0/25]
      neighbors:
        198.51.100.1: {remote_as: 65101, description: ISP1}
        10.255.4.2:   {remote_as: internal, update_source: lo, next_hop_self: true}
```

Extending it (bonds, STP priority, IS-IS, route-maps …) is a good exercise: add the field to
`schema/intent.schema.yml`, render it in the templates, test with `--dry-run`.

## How a push works

1. The intent file is validated against the schema — nothing is sent if it is invalid.
2. The templates produce the data-plane part of `/etc/network/interfaces` and a full `frr.conf`.
3. On the device, everything below the `# ---- your data-plane configuration` line is replaced
   and `ifreload -a` applies only the differences.
4. The FRR configuration is loaded with `frr-reload.py`, which computes and applies only the
   differences, then saved with `write memory`.

This is the same *declarative* model used by NETCONF/RESTCONF (`edit-config` with replace,
candidate datastore + commit): you describe the desired state; the tool works out the changes.
