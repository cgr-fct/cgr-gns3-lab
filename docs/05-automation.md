# Automation in the labs

Every lab contains a **netauto** station on the management network. Open its console: you
land in `/root/cgr`, a copy of this repository's [`automation/`](../automation/README.md) folder
(the reference), and `/root/lab/inventory.yml` lists the devices of the lab you built.

What you practise, in increasing order of abstraction:

1. **Remote execution** — `ssh cgr@<ip>`, then `collect.py` runs one command on every device
   and returns text or JSON.
2. **Scripting** — `cgrlib.py`: a ~80-line Python library (inventory + SSH session) you
   import in your own scripts.
3. **Data modelling** — `schema/intent.schema.yml`: a JSON Schema that validates the intent
   before anything touches the network (the job YANG does for NETCONF/RESTCONF).
4. **Intent + templates** — `apply_intent.py`: YAML intent → Jinja2 → device configuration,
   with `--dry-run`, `--diff` and `--render`, pushed idempotently over SSH.
5. **Configuration management** — Ansible is installed:
   ```bash
   cd /root/cgr
   ansible all -i ~/lab/inventory.yml -m ping             # see automation/README.md for the one-time setup
   ```

Your own scripts can live in `/root` — GNS3 keeps that folder when the node stops.
