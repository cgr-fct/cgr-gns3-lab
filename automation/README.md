# Automation toolkit (`/root/cgr` on the netauto station)

Everything here runs **inside the lab**, on the `netauto` node, which is connected to the
management network `192.168.100.0/24` together with every device's `eth0`.

| File | What it teaches |
|------|-----------------|
| `curl_examples.sh` | The raw REST workflow: revision → PATCH → apply → poll |
| `nvue.py` | A ~150-line Python client for the NVUE REST API (library + CLI) |
| `inventory.yml` | Device inventory (names → management IPs, credentials, platform) |
| `schema/intent.schema.yml` | A data model (JSON Schema) that validates intent files — the same job YANG does for NETCONF/RESTCONF |
| `intent/*.yml` | Network intent written in YAML |
| `apply_intent.py` | Validates intent, translates it to NVUE JSON (Cumulus) or renders Jinja2 templates (FRR lite nodes) and pushes it |
| `templates/*.j2` | Jinja2 templates: `nv set` commands, ifupdown2 interfaces, FRR config |

## Quick tour

```bash
cd /root/cgr
./curl_examples.sh sw1                      # 1. raw REST with curl
./nvue.py show sw1 /system                  # 2. read config
./nvue.py show sw1 /interface/swp1 --rev operational
./nvue.py set sw1 /system '{"message": {"pre-login": "Hello"}}'
./nvue.py backup all                        # JSON backups in backups/

./apply_intent.py intent/lab00.yml --dry-run    # 3. what would be sent?
./apply_intent.py intent/lab00.yml --cli        #    same thing as nv set commands
./apply_intent.py intent/lab00.yml              #    push it
./apply_intent.py intent/lab00.yml --render out # write every generated file to out/
```

Using a lab built with `--lite` (FRR containers instead of Cumulus VX)? Add `--lite`:
the same intent is rendered with Jinja2 and pushed over SSH (ifupdown2 + `frr-reload`).

## The NVUE REST API in 4 calls

```
POST  https://<ip>:8765/nvue_v1/revision                          -> {"<rev>": {...}}
PATCH https://<ip>:8765/nvue_v1/<path>?rev=<rev>     {json}          (stage)
PATCH https://<ip>:8765/nvue_v1/revision/<rev>       {"state":"apply","auto-prompt":{"ays":"ays_yes"}}
GET   https://<ip>:8765/nvue_v1/revision/<rev>                        (poll until "applied")
```

* Authentication: HTTP Basic, same user/password as SSH (`cumulus` / `CumulusLab1!`).
  The API refuses the factory password, which is why the bootstrap changes it.
* Paths mirror the CLI: `nv set interface swp1 ip address 10.0.0.1/30` ⇔
  `PATCH /nvue_v1/interface/swp1 {"ip": {"address": {"10.0.0.1/30": {}}}}`
* `GET ...?rev=applied` = running config, `?rev=startup`, or no `rev` = operational state.
* Revision IDs may contain `/` — URL-encode them (the scripts do it for you).
* Tip: on a switch, `nv config show -o json` shows the JSON for the current config, and
  `nv set ...` followed by `nv config diff` shows what a PATCH should contain.

## NVUE vs RESTCONF — what to keep in mind

NVUE is a REST API whose data model is described in **OpenAPI**, not in YANG, so it is not
RESTCONF (RFC 8040). The ideas map one-to-one, which is what matters for the course:

| RESTCONF (RFC 8040) | NVUE REST API |
|---|---|
| YANG module defines the data tree | OpenAPI schema defines the data tree (`nv` CLI mirrors it) |
| `/restconf/data/<path>` | `/nvue_v1/<path>` |
| `GET` config / state (`content=config\|nonconfig`) | `GET ?rev=applied` / no rev (operational) |
| `PATCH` (merge), `PUT` (replace), `DELETE` | `PATCH` (merge), `DELETE` |
| candidate datastore + commit (NETCONF) | revision + `state: apply` |
| `application/yang-data+json` | `application/json` |
