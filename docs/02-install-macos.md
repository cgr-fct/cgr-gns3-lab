# Install on macOS (Apple Silicon or Intel)

Time: ~30–45 min. Needs ~10 GB free disk and 8 GB RAM.

> **Use exactly GNS3 version `2.2.54`** for the GUI and the GNS3 VM. It is the last 2.2 release
> with an Apple Silicon GNS3 VM, and the whole class uses the same version.

The routers and switches run inside the **GNS3 VM**, a small Linux virtual machine. You can run
it with either hypervisor — pick **one**:

| | Option A — VMware Fusion Pro | Option B — VirtualBox |
|---|---|---|
| Cost | free | free (open source) |
| Download | Broadcom portal, needs an account that Broadcom must approve (can take days) | direct download, no account |
| How GNS3 uses it | GNS3 starts and stops the VM for you | you start the VM yourself, GNS3 connects to it as a *remote server* |
| Apple Silicon | supported by GNS3 | works with VirtualBox **7.2 or newer**; less tested (see note below) |

If you are not sure, start the Broadcom registration now (section 2A, step 1) and, if it is not approved in
time, use VirtualBox. You can switch later: your labs live in GNS3 projects, not in the VM.

## 1. Download GNS3

From <https://github.com/GNS3/gns3-gui/releases/tag/v2.2.54> download `GNS3-2.2.54.dmg` and the
GNS3 VM for your Mac ( → *About This Mac*):

| Chip | Option A (VMware Fusion) | Option B (VirtualBox) |
|---|---|---|
| Apple M1–M5 | `GNS3.VM.ARM64.2.2.54.zip` | `GNS3.VM.ARM64.2.2.54.zip` |
| Intel | `GNS3.VM.VMware.Workstation.2.2.54.zip` | `GNS3.VM.VirtualBox.2.2.54.zip` |

The Apple Silicon file contains only two disk files, `gns3vm-disk1.vmdk` and
`gns3vm-disk2.vmdk`: you create the VM around them (steps below). Unzip it into a folder you will
keep, e.g. `~/GNS3 VM/`.

Install GNS3: open the `.dmg`, drag GNS3 to *Applications*; the first time, right-click → *Open*.
**Don't run the Setup Wizard yet** (if it opens, close it — you can reopen it from *Help → Setup Wizard*).

## 2A. Option A — VMware Fusion Pro

VMware Fusion is **not discontinued** — it is free for personal, educational and commercial use
(current release: **25H2 / 26H1**, Apple Silicon and Intel). It is only distributed through the
Broadcom support portal, and the product pages on vmware.com don't have a download button:

1. **Register now** at <https://support.broadcom.com> (*Register*, a free *Basic* account). Fill in
   the profile with your real name, address and country: Broadcom checks it (export compliance)
   before the first download, and that can take from minutes to **several days** — don't leave it
   for the day of the first lab class.
2. Log in → *My Downloads* → click the link **Free Software Downloads available HERE** → search
   **VMware Fusion** → open the latest release.
   (Direct link after logging in:
   <https://support.broadcom.com/group/ecx/productdownloads?subfamily=VMware%20Fusion&freeDownloads=true>.)
3. Tick *I agree to the Terms and Conditions* and download the `.dmg`.
4. Install it; when asked for a licence key, choose the free option (no key needed). Open Fusion
   once and grant the permissions macOS asks for (*System Settings → Privacy & Security*).

**Create the GNS3 VM — Apple Silicon:**

5. Fusion → *File → New…* → **Create a custom virtual machine** → Continue.
6. Operating system: **Linux → Ubuntu 64-bit Arm** → Continue.
7. *Choose a Virtual Disk*: **Use an existing virtual disk** → *Choose virtual disk…* →
   `gns3vm-disk1.vmdk` (let Fusion make a copy if it asks) → Continue → **Customize Settings** →
   save it as **GNS3 VM**.
8. In the settings window: *Processors & Memory* → **2 processor cores, 2048 MB** (4096 MB if you
   have 16 GB). Then *Add Device… → Existing Hard Disk* → `gns3vm-disk2.vmdk` → Apply.
   Leave the network adapter as it is (*Share with my Mac*). Close the window; don't start the VM.

**Create the GNS3 VM — Intel Mac:** unzip `GNS3.VM.VMware.Workstation.2.2.54.zip` and
double-click the `.ova` → Fusion imports it as **GNS3 VM**. Don't start it.

**Connect GNS3:**

9. Start GNS3 → *Setup Wizard* (*Help → Setup Wizard*):
   * **Run appliances in a virtual machine** → Next
   * Server: host `127.0.0.1`, port `3080` → Next
   * **VMware (recommended)** → *Refresh* → VM name **GNS3 VM**, **2 vCPUs, 2048 MB RAM** → Finish.
10. GNS3 starts the VM. In the *Servers Summary* panel (right side) **GNS3 VM** must turn green.

## 2B. Option B — VirtualBox

1. Download VirtualBox from <https://www.virtualbox.org/wiki/Downloads>:
   **macOS / Apple Silicon hosts** (M chips — version **7.2 or newer**) or **macOS / Intel hosts**.
   Install it and allow the system extension if macOS asks (*System Settings → Privacy & Security*).
2. Create the host-only network the GNS3 VM will use. Do it in **Terminal** (VirtualBox itself
   does not need to be open, and no VM needs to exist yet):
   ```bash
   VBoxManage hostonlynet add --name=HostNetwork --netmask=255.255.255.0 \
       --lower-ip=192.168.56.100 --upper-ip=192.168.56.199 --enable
   VBoxManage list hostonlynets          # HostNetwork must be listed
   ```
   If Terminal answers `command not found`, use the full path
   `/Applications/VirtualBox.app/Contents/MacOS/VBoxManage` instead of `VBoxManage`.

**Create the GNS3 VM — Apple Silicon:**

3. *New* (toolbar) — the wizard has a few collapsible sections:
   * *Virtual machine name and operating system*: Name **GNS3 VM**; ISO image: leave empty;
     OS **Linux**, distribution **Ubuntu**, version **Ubuntu (64-bit ARM)**.
   * *Specify virtual hardware*: **Base Memory 2048 MB** (4096 MB if you have 16 GB),
     **2 CPUs**. Leave *Use EFI* as it is.
   * *Specify virtual hard disk*: select **Use an Existing Virtual Hard Disk File** → click the
     folder icon on its right → **Add** → `gns3vm-disk1.vmdk` → **Choose**.
     (Not *Create a New Virtual Hard Disk*, which is selected by default.)
   * **Finish**. Don't start the VM yet.
4. Select the VM → *Settings* → **Storage**: select the storage **controller** (the line above
   `gns3vm-disk1.vmdk`), click the *Adds hard disk* icon → **Add** → `gns3vm-disk2.vmdk` →
   **Choose**. `gns3vm-disk1.vmdk` must stay the first disk. Leave any empty optical drive as it is.

   Then, still in *Settings*:
   * **Network → Adapter 1**: *Attached to* **Host-only Network**, name *HostNetwork* (the one
     created in step 2; if the name list is empty, step 2 was not done).
   * **Network → Adapter 2**: tick *Enable*, *Attached to* **NAT** (Internet access for the VM).
   * OK.

**Create the GNS3 VM — Intel Mac:** *File → Import Appliance* → `GNS3 VM.ova` (from
`GNS3.VM.VirtualBox.2.2.54.zip`) → Finish. Then *Settings → Network → Adapter 1*: change
*Attached to* to **Host-only Network** (*HostNetwork*) and leave Adapter 2 as NAT.

**Start the VM and connect GNS3** (Apple Silicon and Intel):

5. Start the VM: *Start* (arrow next to it) → **Start with GUI** the first time, so you can see
   the console. After 1–2 minutes it shows a blue GNS3 VM screen with its **IP address** on
   `eth0`, something like `192.168.56.3`. Note it. If you only see a login prompt, log in as
   `gns3` / `gns3` and run `ip -4 addr show eth0`.
   Keep the VM window open (you can minimise it) while you work: closing it offers to power off
   or save the VM. Later you can use **Start without GUI** instead — the VM runs in the background
   and *Show* opens its window when you need it. (*Start with detachable GUI* also works: its
   window can be closed while the VM keeps running.)
6. Start GNS3 → *Setup Wizard* → **Run appliances on my local computer** → keep the proposed
   settings (host `127.0.0.1`, port `3080`) → Finish. Ignore warnings about missing local
   emulators.
7. *GNS3 → Preferences → Server* → tab **Remote servers** → **Add**: protocol **HTTP**, host = the
   VM address from step 5, port **80**, no authentication → OK → **Apply**.
   The new server appears in the *Servers Summary* panel and must be green.
   In *Preferences → GNS3 VM* leave *Enable the GNS3 VM* **unticked** (you manage the VM yourself).

Every time you work on the labs: **start the VM in VirtualBox first, then GNS3**. When you finish:
close GNS3, then in VirtualBox *Close → ACPI Shutdown* for the VM. If the VM ever gets a different
address, update it in *Preferences → Server → Remote servers → Edit*.

> **Note (Apple Silicon + VirtualBox):** we checked that the Apple Silicon GNS3 VM disks boot on
> generic ARM virtual hardware and that GNS3 2.2.54 uses a VM added this way (`cgr_lab.py`
> selects it automatically). The combination was not tested end-to-end on a real Mac with
> VirtualBox. If it gives you trouble, use option A, or tell the lab instructor.

## 3. Python and the lab tools

In Terminal:

```bash
xcode-select --install          # provides git and python3 if you don't have them
cd ~/Documents
git clone https://github.com/cgr-fct/cgr-gns3-lab.git cgr-gns3-lab && cd cgr-gns3-lab
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt
python tools/cgr_lab.py check
```

`check` lists the computes and must end with **Using compute …** and **Docker nodes supported**
(option A: compute `vm`; option B: the remote server you added).

(In every new Terminal window: `cd ~/Documents/cgr-gns3-lab && source .venv/bin/activate`.)

Continue with [Building a lab](04-build-a-lab.md) and [Lab 00](../labs/lab00-first-contact/README.md).
