# Install on Linux

On Linux no GNS3 VM is needed: the lab containers run directly on your machine.

* **Ubuntu 22.04 / 24.04** and derivatives (Mint, Pop!_OS, …) → section **1A**
* **Debian 12 (bookworm) / 13 (trixie)** → section **1B**

> Windows users: instead of fighting with hypervisor settings you can install a Linux VM and
> follow this guide inside it — see
> [Option C in the Windows guide](01-install-windows.md#2c-option-c--everything-inside-a-linux-vm).

## 1A. Ubuntu — GNS3 + Docker

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

## 1B. Debian — GNS3 + Docker

GNS3 is not in the Debian repositories, so the GUI and the server are installed with `pipx`, and
`ubridge` — the helper GNS3 uses to connect containers to each other — is built from source.
Run everything as your normal user (not as root).

**Packages:**

```bash
sudo apt update
sudo apt install -y pipx python3-venv git docker.io \
                    python3-pyqt5 python3-pyqt5.qtsvg python3-pyqt5.qtwebsockets \
                    build-essential libpcap-dev libcap2-bin
pipx ensurepath          # then open a new terminal, so that ~/.local/bin is in PATH
```

**GNS3 2.2.54 (GUI + server):**

```bash
pipx install --python /usr/bin/python3 "gns3-server==2.2.54"
pipx install --python /usr/bin/python3 --system-site-packages "gns3-gui==2.2.54"
gns3server --version && gns3 --version      # both must print 2.2.54
```

Install **exactly 2.2.54**, not the newest GNS3: version 3.x has a different API and `cgr_lab.py`
would not work with it. `--system-site-packages` lets the GUI use Debian's PyQt5, and
`--python /usr/bin/python3` makes sure it uses the Python those packages were built for —
without it the GUI starts with *Can't import Qt modules*.

**ubridge:**

```bash
git clone https://github.com/GNS3/ubridge.git ~/ubridge
cd ~/ubridge && make && sudo make install     # installs /usr/local/bin/ubridge and sets its capabilities
getcap /usr/local/bin/ubridge                 # must print cap_net_admin,cap_net_raw=ep
cd ~
```

**Docker and kernel modules:**

```bash
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker
sudo modprobe -a bonding 8021q dummy macvlan    # kernel features used by the labs
echo -e "bonding\n8021q\ndummy\nmacvlan" | sudo tee /etc/modules-load.d/cgr.conf
```

**Log out and back in** (group membership), then start GNS3 with `gns3` and in the *Setup Wizard*
choose **Run appliances on my local computer** (host `127.0.0.1`, port `3080`). Ignore the warnings
about missing Dynamips/IOU/QEMU: the lab devices are Docker containers.

> Other distributions: the same idea as 1B — `gns3-gui` and `gns3-server` 2.2.54 from `pipx` (or a
> virtualenv), `ubridge` from source, Docker from your package manager. See <https://docs.gns3.com>.

## 2. Lab tools

```bash
cd ~
git clone https://github.com/cgr-fct/cgr-gns3-lab.git cgr-gns3-lab && cd cgr-gns3-lab
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt
python tools/cgr_lab.py check          # compute 'local', Docker OK
```

Continue with [Building a lab](04-build-a-lab.md) and [Lab 00](../labs/lab00-first-contact/README.md).
