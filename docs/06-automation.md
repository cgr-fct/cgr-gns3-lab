# Automation in the labs

Every lab contains a **netauto** station on the management network. Open its console: you
land in `/root/cgr`, which is a copy of this repository's [`automation/`](../automation/README.md)
folder (the README there is the reference).

What you practise, in increasing order of abstraction:

1. **Raw REST** — `curl_examples.sh`: revision → PATCH → apply → poll, with basic auth and JSON.
2. **Scripting** — `nvue.py`: the same calls wrapped in a small Python class; `show`, `set`,
   `unset`, `backup`.
3. **Data modelling** — `schema/intent.schema.yml`: JSON Schema that validates the intent
   before anything touches the network (the role YANG plays for NETCONF/RESTCONF).
4. **Intent + templates** — `apply_intent.py`: YAML intent → NVUE JSON (REST) or Jinja2 →
   device files (SSH). `--dry-run`, `--cli` and `--render` show what would be sent.
5. **Configuration management** — Ansible (`ansible-core`) is installed. Example ad-hoc
   command against the lite nodes:
   ```bash
   ansible all -i 192.168.100.33,192.168.100.34, -u cumulus -k -m command -a "vtysh -c 'show ip route'"
   ```
   (`-k` asks for the SSH password `CumulusLab1!`; add `ansible_host_key_checking=False` in
   `ansible.cfg` or export `ANSIBLE_HOST_KEY_CHECKING=False`).

Your own scripts can live in `/root` — GNS3 keeps that folder when the node stops.
To copy files in/out, use `scp`/`git` from netauto, or paste into `nano`.

## RESTCONF and YANG

The Cumulus NVUE API is REST + JSON with an OpenAPI model, **not** RESTCONF/YANG. The concepts
are the same (resource tree, GET/PATCH/DELETE, candidate + commit) — see the mapping table in
[`automation/README.md`](../automation/README.md#nvue-vs-restconf--what-to-keep-in-mind).
Your instructor may provide a separate RESTCONF exercise.
