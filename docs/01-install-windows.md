# Install on Windows 10/11

Time: ~30 min, mostly downloads. Needs ~10 GB free disk and 8 GB RAM (16 GB is comfortable).

> **Use exactly GNS3 version `2.2.54`** for the GUI *and* the GNS3 VM — the whole class uses
> the same version, and the GUI and the VM must always match.

The routers and switches run inside the **GNS3 VM**, a small Linux virtual machine. You can run
it with either hypervisor — pick **one**:

| | Option A — VMware Workstation Pro | Option B — VirtualBox |
|---|---|---|
| Cost | free | free (open source) |
| Download | Broadcom portal, needs an account that Broadcom must approve (can take days) | direct download, no account |
| GNS3 support | recommended by GNS3, the most tested | supported by GNS3 |
| Tested with this kit | the GNS3 VM with VMware is the reference setup | not tested on Windows by us |

If you are not sure, start the Broadcom registration now (section 2A, step 1) and, if it is not approved in
time, use VirtualBox. You can switch later: your labs live in GNS3 projects, not in the VM.

You do **not** need to change any Windows virtualisation settings for VMware: the labs use
containers, so VMware works fine next to Hyper-V, WSL2 or Docker Desktop.

## 1. Download GNS3

From <https://github.com/GNS3/gns3-gui/releases/tag/v2.2.54> download:

* `GNS3-2.2.54-all-in-one.exe`
* the GNS3 VM for your hypervisor: `GNS3.VM.VMware.Workstation.2.2.54.zip` (option A) **or**
  `GNS3.VM.VirtualBox.2.2.54.zip` (option B)

Run the installer with the default components (you can untick the optional SolarWinds /
Solar-PuTTY offers; keep Npcap and Wireshark for packet captures). **Don't start GNS3 yet.**

## 2A. Option A — VMware Workstation Pro

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
4. Unzip `GNS3.VM.VMware.Workstation.2.2.54.zip` and double-click the `.ova` file → VMware
   imports it as **GNS3 VM**. Don't start it.
5. Start **GNS3**. In the *Setup Wizard*:
   * **Run appliances in a virtual machine** → Next
   * Server: host `127.0.0.1`, port `3080` → Next
   * **VMware (recommended)**, VM name **GNS3 VM**, **2 vCPUs, 2048 MB RAM** (4096 MB if you
     have 16 GB) → Finish.
6. GNS3 starts the VM. In the *Servers Summary* panel (right side) **GNS3 VM** must turn green.

## 2B. Option B — VirtualBox

1. Download **VirtualBox for Windows hosts** (7.1 or newer) from
   <https://www.virtualbox.org/wiki/Downloads> and install it with the defaults. If the installer
   asks for the *Microsoft Visual C++ Redistributable* or *Python*, accept or skip — neither is
   needed for GNS3.
2. Open VirtualBox → *File → Tools → Network Manager* → tab **Host-only Networks**. There should
   be a *VirtualBox Host-Only Ethernet Adapter* with **DHCP Server: Enabled**. If the list is
   empty, click **Create**, then tick *Enable Server* in the *DHCP Server* tab and **Apply**.
3. Unzip `GNS3.VM.VirtualBox.2.2.54.zip` → in VirtualBox *File → Import Appliance* → select
   `GNS3 VM.ova` → *Finish*. The VM is called **GNS3 VM**. Don't start it.
4. Start **GNS3**. In the *Setup Wizard*:
   * **Run appliances in a virtual machine** → Next
   * Server: host `127.0.0.1`, port `3080` → Next
   * **VirtualBox**, VM name **GNS3 VM**, **2 vCPUs, 2048 MB RAM** (4096 MB if you have
     16 GB) → Finish.
   (The wizard's remark that VirtualBox is only for Dynamips/IOU/VPCS does not apply here: the
   lab devices are Docker containers, which run fine in the VirtualBox GNS3 VM.)
5. GNS3 starts the VM (a VirtualBox window may appear — leave it alone). In the
   *Servers Summary* panel **GNS3 VM** must turn green.

VirtualBox notes:
* When Hyper-V, WSL2 or Docker Desktop is active, VirtualBox runs on top of Hyper-V (a green
  turtle icon in the VM window). That is slower but fine for these labs.
* GNS3 switches on *nested virtualisation* for the VM at every start. If the VM refuses to start
  with an error that mentions nested virtualisation / VT-x / AMD-V, see
  [troubleshooting](06-troubleshooting.md#virtualbox-the-gns3-vm-does-not-start).

## 3. Python and the lab tools

Open **Terminal** (PowerShell):

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git        # optional, you can also download the repo as ZIP
```

Close and reopen Terminal, then:

```powershell
cd $HOME\Documents
git clone https://github.com/cgr-fct/cgr-gns3-lab.git cgr-gns3-lab   # or unzip the downloaded ZIP here
cd cgr-gns3-lab
py -m pip install -r tools\requirements.txt
py tools\cgr_lab.py check
```

`check` must find the controller, the `vm` compute and Docker. Continue with
[Building a lab](04-build-a-lab.md) and [Lab 00](../labs/lab00-first-contact/README.md).
