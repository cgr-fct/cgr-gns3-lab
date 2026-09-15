# Install on Linux (the lightest setup)

On Linux no GNS3 VM is needed: devices run directly on your machine with KVM and Docker.
Instructions for **Ubuntu 22.04 / 24.04** (and derivatives such as Mint, Pop!_OS).

## 1. Check virtualisation

```bash
sudo apt install -y cpu-checker && kvm-ok      # must say "KVM acceleration can be used"
```

## 2. GNS3 + Docker

```bash
sudo add-apt-repository -y ppa:gns3/ppa
sudo apt update
sudo apt install -y gns3-gui gns3-server        # answer "Yes" to "non-root users capture packets"
sudo apt install -y docker.io python3-venv git
for g in ubridge libvirt kvm wireshark docker; do sudo usermod -aG $g "$USER"; done
```

**Log out and back in** (group membership), then start GNS3 and in the *Setup Wizard* choose
**Run appliances on my local computer** (host `127.0.0.1`, port `3080`).

> The PPA installs the newest 2.2.x release (not necessarily 2.2.54). That is fine on Linux:
> GUI and server come from the same package, and the lab tools work with any 2.2.x.
> Other distributions: `pipx install gns3-gui gns3-server` plus `ubridge`, `dynamips`, `vpcs`,
> `qemu-kvm` and Docker from your package manager — see <https://docs.gns3.com>.

## 3. Lab tools

```bash
cd ~
git clone <REPO-URL> cgr-gns3-lab && cd cgr-gns3-lab
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt
python tools/cgr_lab.py check          # compute 'local', Docker OK, KVM OK
```

Continue with [04 – Images](04-images.md).
