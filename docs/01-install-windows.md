# Install on Windows 10/11

Time: ~30 min, mostly downloads. Needs ~10 GB free disk and 8 GB RAM (16 GB is comfortable).

> **Use exactly GNS3 version `2.2.54`** for the GUI *and* the GNS3 VM — the whole class uses
> the same version, and the GUI and the VM must always match.

The routers and switches always run inside a virtual machine. You have three ways to get there —
pick **one**:

| | Option A — VMware Workstation Pro | Option B — VirtualBox | Option C — Linux VM |
|---|---|---|---|
| What runs on Windows | GNS3 GUI | GNS3 GUI | nothing — everything is inside the VM |
| Which VM | the ready-made **GNS3 VM** appliance | the ready-made **GNS3 VM** appliance | an **Ubuntu Desktop** VM you install yourself |
| Cost / download | free; Broadcom account that must be approved (can take days) | free, direct download, no account | free (VirtualBox or Hyper-V) + Ubuntu ISO |
| Good when | you want the reference setup | you want to avoid the Broadcom account | Hyper-V / WSL2 / Docker Desktop get in the way, or the GNS3 VM refuses to start |
| Tested with this kit | reference setup | not tested on Windows by us | the Linux install is the one we develop the labs on |

If you are not sure, start the Broadcom registration now (section 2A, step 1) and, if it is not approved in
time, use VirtualBox. You can switch later: your labs live in GNS3 projects, not in the VM.

You do **not** need to change any Windows virtualisation settings for VMware: the labs use
containers, so VMware works fine next to Hyper-V, WSL2 or Docker Desktop.

## 1. Download GNS3

*(Option C does not need these downloads — go straight to section 2C.)*

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

Continue with section 3.

## 2B. Option B — VirtualBox

1. Download **VirtualBox for Windows hosts** (7.1 or newer) from
   <https://www.virtualbox.org/wiki/Downloads> and install it with the defaults. If the installer
   asks for the *Microsoft Visual C++ Redistributable* or *Python*, accept or skip — neither is
   needed for GNS3.
2. Check that VirtualBox created a host-only adapter during installation. In PowerShell:
   ```powershell
   & "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" list hostonlyifs      # must list one adapter
   & "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" hostonlyif create      # only if the list is empty
   ```
   (GNS3 enables the DHCP server on it by itself when it starts the VM.)
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

Continue with section 3.

## 2C. Option C — everything inside a Linux VM

Instead of the GNS3 VM appliance, install a normal **Ubuntu Desktop** VM and run GNS3, Docker and
the lab tools *inside* it. Windows only hosts the VM. This avoids the whole nested-virtualisation
question: the lab devices are Docker containers, and containers do not need VT-x inside the VM —
so the VM starts even with Hyper-V, WSL2 or Docker Desktop active on Windows.

1. Download **Ubuntu Desktop 24.04 LTS** (the `.iso`) from <https://ubuntu.com/download/desktop>.
2. Create the VM, with VirtualBox (<https://www.virtualbox.org/wiki/Downloads>) or with
   VMware Workstation Pro — whichever you already have:
   * **4096 MB RAM** (6144 MB if your PC has 16 GB), **2 CPUs**, **40 GB disk**
   * network: the default (**NAT**) — the VM needs Internet access to download the lab images
   * VirtualBox only: *Display → Video Memory* **128 MB**, and after installing Ubuntu insert the
     *Guest Additions CD* (*Devices* menu) so the window resizes properly.
3. Boot the VM from the ISO and install Ubuntu normally (*Minimal installation* is enough).
   Remember the user name and password; this is the machine you will work on all semester.
4. Inside the VM, follow **[Install on Linux](03-install-linux.md)** — section 1A (Ubuntu) and
   section 2. Then continue with [Building a lab](04-build-a-lab.md) inside the VM too.
   You do **not** need sections 1 and 3 of this Windows guide.

Notes:
* Everything — GNS3, the projects, the repository — lives inside the VM. To move a file to
  Windows, use a *Shared Folder* (VirtualBox: *Devices → Shared Folders*, tick *Auto-mount*) or
  copy it through GitHub.
* Give the VM a snapshot once the installation works (VirtualBox: *Machine → Take Snapshot*), so
  you can go back if an experiment breaks the system.
* Hyper-V users: *Hyper-V Manager → Quick Create → Ubuntu* creates the same kind of VM in one
  step; use *Enhanced session* for a full-screen desktop.

## 3. Python and the lab tools

*(Options A and B only — with option C these tools are installed inside the Linux VM.)*

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
