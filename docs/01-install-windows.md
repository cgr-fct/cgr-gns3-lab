# Install on Windows 10/11

Time: ~30 min, mostly downloads. Needs ~10 GB free disk and 8 GB RAM (16 GB is comfortable).

> **Use exactly GNS3 version `2.2.54`** for the GUI *and* the GNS3 VM — the whole class uses
> the same version, and the GUI and the VM must always match.

## 1. VMware Workstation Pro (free)

Free for personal, educational and commercial use (current release: **25H2 / 26H1**; any recent
version works). It is only distributed through the Broadcom support portal:

1. **Register now** at <https://support.broadcom.com> (*Register*, a free *Basic* account). Fill in
   the profile with your real name, address and country: Broadcom checks it (export compliance)
   before the first download, and that can take from minutes to **several days** — don't leave it
   for the day of the first lab class.
2. Log in → *My Downloads* → click the link **Free Software Downloads available HERE** → search
   **VMware Workstation Pro** → open the latest release → Windows.
   (Direct link after logging in:
   <https://support.broadcom.com/group/ecx/productdownloads?subfamily=VMware%20Workstation%20Pro&freeDownloads=true>.)
3. Tick *I agree to the Terms and Conditions* and download. Install with the defaults; when the
   installer asks for a licence key, leave it empty and choose the free option.

If your account is still waiting for approval, you can start with **VirtualBox** instead
(<https://www.virtualbox.org>, and `GNS3.VM.VirtualBox.2.2.54.zip` below; in the Setup Wizard choose
*VirtualBox* instead of *VMware*). This should work the same way but was not tested by us; VMware is recommended because it is
faster and more stable with GNS3.

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
