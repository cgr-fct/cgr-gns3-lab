"""
cgrlib.py - small helpers shared by the automation scripts.

    from cgrlib import load_inventory, Device
    inv = load_inventory()
    with Device(inv["sw1"]) as d:
        print(d.run("vtysh -c 'show ip route'"))
"""
import os
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent


def _walk_group(group, inherited, out):
    """Collect hosts from an Ansible-style YAML inventory group (recursively)."""
    vars_ = dict(inherited)
    vars_.update((group or {}).get("vars") or {})
    for name, hv in ((group or {}).get("hosts") or {}).items():
        d = dict(vars_)
        d.update(hv or {})
        out[name] = d
    for child in ((group or {}).get("children") or {}).values():
        _walk_group(child, vars_, out)


def load_inventory(path=None):
    """Read an Ansible YAML inventory and return {name: {host, user, password, ...}}."""
    lab_inv = Path.home() / "lab" / "inventory.yml"      # written by cgr_lab.py for the current lab
    default = lab_inv if lab_inv.exists() else HERE / "inventory.yml"
    path = Path(path or os.environ.get("CGR_INVENTORY", default))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    hosts = {}
    _walk_group(raw.get("all"), {}, hosts)
    devices = {}
    for name, h in hosts.items():
        devices[name] = {
            "name": name,
            "host": h.get("ansible_host", name),
            "user": h.get("ansible_user", "cgr"),
            "password": os.environ.get("CGR_PASSWORD", h.get("ansible_password", "cgrlab")),
            **{k: v for k, v in h.items() if not k.startswith("ansible_")},
        }
    return devices


class Device:
    """An SSH session to a lab router/switch (paramiko)."""

    def __init__(self, dev, timeout=10):
        self.dev, self.timeout, self.cli = dev, timeout, None

    def __enter__(self):
        import paramiko
        self.cli = paramiko.SSHClient()
        self.cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.cli.connect(self.dev["host"], username=self.dev.get("user", "cgr"),
                         password=self.dev.get("password", "cgrlab"),
                         look_for_keys=False, allow_agent=False, timeout=self.timeout)
        return self

    def __exit__(self, *exc):
        self.cli.close()

    def exec(self, cmd, stdin_data=None):
        """Run a command; return (exit code, stdout, stderr)."""
        stdin, stdout, stderr = self.cli.exec_command(cmd, timeout=120)
        if stdin_data is not None:
            stdin.write(stdin_data)
            stdin.channel.shutdown_write()
        rc = stdout.channel.recv_exit_status()
        return rc, stdout.read().decode(), stderr.read().decode()

    def run(self, cmd):
        """Run a command and return its output (raises on error)."""
        rc, out, err = self.exec(cmd)
        if rc:
            raise RuntimeError(f"{self.dev['name']}: '{cmd}' failed: {err.strip() or out.strip()}")
        return out

    def read_file(self, path):
        return self.run(f"sudo cat {path}")

    def write_file(self, path, content):
        rc, _, err = self.exec(f"sudo tee {path} >/dev/null", content)
        if rc:
            raise RuntimeError(f"{self.dev['name']}: cannot write {path}: {err.strip()}")
