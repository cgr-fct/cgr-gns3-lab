# Automation in the labs

Every lab contains a **netauto** station on the management network. Open its console: you
land in `/root/cgr`, a copy of this repository's [`automation/`](../automation/README.md) folder
(the reference), and `/root/lab/inventory.yml` lists the devices of the lab you built.

Every router/switch runs a **RESTCONF server** for the YANG module **`cgr-device`**, and the
same model drives the YAML intent files — so you can configure a device by CLI, by YAML over
SSH, by RESTCONF (curl, Python, Ansible), and compare the results.

What you practise, in increasing order of abstraction:

| Step | Tool | Concepts |
|---|---|---|
| 1 | `ssh`, `collect.py` | remote execution, structured output (`show … json`) |
| 2 | `cgrlib.py`, your own Python | scripting against an inventory |
| 3 | `pyang`, `yang/cgr-device@….yang` | **YANG**: containers, lists and keys, leaf-lists, typedefs, `when`, `mandatory`, `config false` |
| 4 | `curl`, `restconf.py` | **RESTCONF** (RFC 8040): resources, GET/PUT/PATCH/POST/DELETE, `content=`, error reports, JSON encoding (RFC 7951) |
| 5 | `apply_intent.py`, `intent/*.yml`, `templates/` | **YAML** intent, validation against the model, **Jinja2** templates, declarative and idempotent push, drift detection (`--diff`) |
| 6 | `ansible`, `playbooks/` | configuration management; RESTCONF through the `uri` module |

**CLI and automation together.** Build the labs by CLI; RESTCONF GETs work at any time. When
you start pushing configuration, a device becomes model-managed: the tools refuse a push that
would silently delete settings you typed by hand, and `./apply_intent.py <file> --import <device>`
turns a hand-configured device into an intent file so you can continue by automation. Details:
[toolkit, section 3a](../automation/README.md#3a-cli-and-automation-on-the-same-lab).

Start with Lab 00, section 5. Your own scripts can live in `/root` — GNS3 keeps that folder
when the node stops.
