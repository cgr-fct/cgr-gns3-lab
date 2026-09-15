# Install on macOS

First check your chip:  → *About This Mac*.

* **Apple Silicon (M1–M4)** → section A. Cumulus VX is an x86 image and cannot run at usable
  speed on ARM, so you will do the labs in **lite mode** (FRR containers). Everything in
  the labs works except the NVUE-specific commands and the NVUE REST API calls; for those,
  pair up with a colleague who runs the full labs, or use a lab PC.
* **Intel** → section B (full labs, like Windows).

> **Use exactly GNS3 version `2.2.54`** for the GUI and the VM. It is the last 2.2 release that
> ships an Apple Silicon (ARM64) GNS3 VM, and the whole class uses the same version.

## A. Apple Silicon

1. **VMware Fusion Pro** (free): download it from the Broadcom support portal (free account):
   <https://support.broadcom.com> → *My Downloads* → *VMware Fusion*. Install and open it once
   to grant the permissions macOS asks for.
2. From <https://github.com/GNS3/gns3-gui/releases/tag/v2.2.54> download
   `GNS3-2.2.54.dmg` and `GNS3.VM.ARM64.2.2.54.zip`.
3. Install GNS3 (drag to *Applications*; the first time, right-click → *Open*).
4. Unzip the VM and open the `.ova`/`.vmx` with VMware Fusion (*File → Import*). Don't start it.
5. Start GNS3 → *Setup Wizard* → **Run appliances in a virtual machine** → VMware →
   **GNS3 VM**, 2–4 vCPUs, **4096 MB** RAM (lite labs need little) → Finish.
   The GNS3 VM must turn green in the *Servers Summary* panel.
6. Python and the lab tools (Terminal):
   ```bash
   xcode-select --install          # provides git and python3 if you don't have them
   cd ~/Documents
   git clone <REPO-URL> cgr-gns3-lab && cd cgr-gns3-lab
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r tools/requirements.txt
   python tools/cgr_lab.py check
   ```
   `check` will warn that there is no Cumulus image / no KVM — that is expected.
7. Build every lab with `--lite`, e.g.
   `python tools/cgr_lab.py build labs/lab00-first-contact --lite --start`.
   Skip [04 – Images](04-images.md) except the *containers* part.

## B. Intel Mac

Same as Apple Silicon, but download `GNS3.VM.VMware.Workstation.2.2.54.zip` (Fusion opens it)
and give the VM 8 GB RAM. In VMware Fusion, open the VM settings → *Processors & Memory* →
*Advanced* → tick **Enable hypervisor applications in this virtual machine**. The GNS3 VM
console must show `KVM support available: True`. Then continue with [04 – Images](04-images.md).
