# Install on Windows 10/11

Time: ~30 min, mostly downloads. Needs ~10 GB free disk and 8 GB RAM (16 GB is comfortable).

> **Use exactly GNS3 version `2.2.54`** for the GUI *and* the GNS3 VM — the whole class uses
> the same version, and the GUI and the VM must always match.

## 1. VMware Workstation Pro (free)

Free for personal, educational and commercial use. Download it from the Broadcom support
portal (free account): <https://support.broadcom.com> → *My Downloads* → *VMware Workstation Pro*
→ Windows. Install with the defaults.

You do **not** need to change any Windows virtualisation settings: the labs use containers,
so VMware works fine next to Hyper-V, WSL2 or Docker Desktop.

## 2. GNS3 and the GNS3 VM

Download from <https://github.com/GNS3/gns3-gui/releases/tag/v2.2.54>:

* `GNS3-2.2.54-all-in-one.exe`
* `GNS3.VM.VMware.Workstation.2.2.54.zip`

1. Run the installer with the default components (you can untick the optional
   SolarWinds/Solar-PuTTY offers; keep Npcap and Wireshark for packet captures).
2. Unzip the VM and double-click the `.ova` file → VMware imports it. Don't start it.
3. Start **GNS3**. In the *Setup Wizard*:
   * **Run appliances in a virtual machine** → Next
   * Server: host `127.0.0.1`, port `3080` → Next
   * **VMware**, VM name **GNS3 VM**, **2 vCPUs, 2048 MB RAM** (4096 MB if you have 16 GB) → Finish.
4. GNS3 starts the VM. In the *Servers Summary* panel (right side) **GNS3 VM** must turn green.

## 3. Python and the lab tools

Open **Terminal** (PowerShell):

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git        # optional, you can also download the repo as ZIP
```

Close and reopen Terminal, then:

```powershell
cd $HOME\Documents
git clone https://github.com/cgr-fct/cgr-gns3-lab.git cgr-gns3-lab        # or unzip the downloaded ZIP here
cd cgr-gns3-lab
py -m pip install -r tools\requirements.txt
py tools\cgr_lab.py check
```

`check` must find the controller, the `vm` compute and Docker. Continue with
[Building a lab](04-build-a-lab.md) and [Lab 00](../labs/lab00-first-contact/README.md).
