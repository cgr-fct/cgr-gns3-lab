# Install on Windows 10/11 (x86)

Time: ~45 min, most of it downloads. You need ~25 GB free disk and ideally 16 GB RAM.

> **Use exactly GNS3 version `2.2.54`** for the GUI *and* the VM (the whole class uses the same
> version; the GUI and the VM must always match).

## 1. Turn off the Windows hypervisor (needed for Cumulus VX)

Cumulus VX needs *nested virtualisation* inside the GNS3 VM. VMware can only provide it when
Windows' own hypervisor (Hyper-V) is **off**.

1. **Settings → Privacy & security → Windows Security → Device security → Core isolation →
   Memory integrity: Off**.
2. Press *Win*, type **Turn Windows features on or off**, and **untick**: *Hyper-V*,
   *Virtual Machine Platform*, *Windows Hypervisor Platform*, *Windows Sandbox* (if present).
3. Open **Terminal (Admin)** and run:
   ```powershell
   bcdedit /set hypervisorlaunchtype off
   ```
4. **Reboot.**

> This disables WSL2 and Docker Desktop while it is off. To undo later:
> `bcdedit /set hypervisorlaunchtype auto`, re-tick the features, reboot.
> Can't or don't want to do this? Skip this section and use the **lite** labs (`--lite`) —
> everything except the Cumulus-specific NVUE parts works.

Also make sure virtualisation (Intel VT-x / AMD-V, "SVM") is enabled in the BIOS/UEFI.
Check: *Task Manager → Performance → CPU → Virtualization: Enabled*.

## 2. Install VMware Workstation Pro (free)

VMware Workstation Pro is free for personal, educational and commercial use. Download it from
the Broadcom support portal (free account needed): search for *VMware Workstation Pro* on
<https://support.broadcom.com> → *My Downloads* → *VMware Workstation Pro* → Windows.
Install with the defaults.

## 3. Install GNS3 and the GNS3 VM

Download from <https://github.com/GNS3/gns3-gui/releases/tag/v2.2.54>:

* `GNS3-2.2.54-all-in-one.exe`
* `GNS3.VM.VMware.Workstation.2.2.54.zip`

1. Run the installer. Keep the default components. You may untick the optional
   SolarWinds/Solar-PuTTY offers. Accept Npcap and Wireshark (useful for packet captures).
2. Unzip the VM and double-click `GNS3 VM.ova` → VMware imports it. Don't start it.
3. Start **GNS3**. In the *Setup Wizard*:
   * **Run appliances in a virtual machine** → Next
   * Server: host `127.0.0.1`, port `3080` → Next
   * **VMware**, VM name **GNS3 VM**, vCPUs = half of your cores, RAM = **8192 MB**
     (16 GB laptop) or 4096 MB (8 GB laptop, lite labs only) → Finish.
4. GNS3 starts the VM. In the *Servers Summary* panel (right side) **GNS3 VM** must turn green.
5. In VMware, open the *GNS3 VM* window: it must show **`KVM support available: True`**.
   If it says `False`, see [troubleshooting](07-troubleshooting.md#kvm-support-available-false).

## 4. Install Python and the lab tools

Open **Terminal** (PowerShell):

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git        # optional, you can also download the repo as ZIP
```

Close and reopen Terminal, then:

```powershell
cd $HOME\Documents
git clone <REPO-URL> cgr-gns3-lab        # or unzip the downloaded ZIP here
cd cgr-gns3-lab
py -m pip install -r tools\requirements.txt
py tools\cgr_lab.py check
```

`check` must say it found the controller, the `vm` compute, Docker and KVM.

Continue with [04 – Images](04-images.md).
