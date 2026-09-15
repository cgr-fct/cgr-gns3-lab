# Install on Linux

On Linux no GNS3 VM is needed: the lab containers run directly on your machine.
Instructions for **Ubuntu 22.04 / 24.04** and derivatives (Mint, Pop!_OS, …).

## 1. GNS3 + Docker

```bash
sudo add-apt-repository -y ppa:gns3/ppa
sudo apt update
sudo apt install -y gns3-gui gns3-server        # answer "Yes" to "non-root users capture packets"
sudo apt install -y docker.io python3-venv git
for g in ubridge wireshark docker; do sudo usermod -aG $g "$USER"; done
sudo modprobe -a bonding 8021q dummy macvlan    # kernel features used by the labs
echo -e "bonding\n8021q\ndummy\nmacvlan" | sudo tee /etc/modules-load.d/cgr.conf
```

**Log out and back in** (group membership), then start GNS3 and in the *Setup Wizard* choose
**Run appliances on my local computer** (host `127.0.0.1`, port `3080`).

> The PPA installs the newest 2.2.x release. That is fine on Linux: GUI and server come from
> the same package, and the lab tools work with any 2.2.x.
> Other distributions: install `gns3-gui`/`gns3-server` with `pipx`, plus `ubridge`, `dynamips`,
> `vpcs` and Docker from your package manager — see <https://docs.gns3.com>.

## 2. Lab tools

```bash
cd ~
git clone <REPO-URL> cgr-gns3-lab && cd cgr-gns3-lab
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt
python tools/cgr_lab.py check          # compute 'local', Docker OK
```

Continue with [Building a lab](04-build-a-lab.md) and [Lab 00](../labs/lab00-first-contact/README.md).
