# Install on macOS (Apple Silicon or Intel)

Time: ~30–45 min. Needs ~10 GB free disk and 8 GB RAM.

> **Use exactly GNS3 version `2.2.54`** for the GUI and the GNS3 VM. It is the last 2.2 release
> with an Apple Silicon GNS3 VM, and the whole class uses the same version.

The routers and switches run inside the **GNS3 VM**, a small Linux virtual machine. Pick **one**
way to run it:

| | Option A — VMware Fusion Pro | Option B — UTM | Option C — VirtualBox |
|---|---|---|---|
| For | Apple Silicon and Intel | **Apple Silicon** | **Intel Macs** only |
| Cost / download | free; Broadcom account that must be approved (can take days) | free, direct download, no account | free, direct download, no account |
| How GNS3 uses it | starts and stops the VM for you | you start the VM, GNS3 connects to it as a *remote server* | starts and stops the VM for you |
| Status | reference setup | VM image tested on the same virtual hardware; UTM itself less tested | less tested |

VirtualBox does **not** work for the GNS3 VM on Apple Silicon (the VM firmware starts but the
GNS3 VM system does not boot) — use Fusion or UTM there.

If you are not sure, start the Broadcom registration now (section 2A, step 1) and, if it is not
approved in time, use option B or C. You can switch later: your labs live in GNS3 projects, not in
the VM.

## 1. Download GNS3

From <https://github.com/GNS3/gns3-gui/releases/tag/v2.2.54> download `GNS3-2.2.54.dmg` and the
GNS3 VM for your Mac ( → *About This Mac*):

| Chip | GNS3 VM file |
|---|---|
| Apple M1–M5 (options A and B) | `GNS3.VM.ARM64.2.2.54.zip` |
| Intel, option A (Fusion) | `GNS3.VM.VMware.Workstation.2.2.54.zip` |
| Intel, option C (VirtualBox) | `GNS3.VM.VirtualBox.2.2.54.zip` |

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

## 2B. Option B — UTM (Apple Silicon)

1. Download **UTM** from <https://mac.getutm.app> (free; the Mac App Store version is the same
   app, but paid) and install it.

**Create the GNS3 VM:**

2. UTM → **Create a New Virtual Machine** → **Virtualize** → **Linux**:
   * Leave **Use Apple Virtualization** unticked (UTM then uses QEMU, which is what we tested).
   * *Boot Image Type*: **Import existing drive** → *Import Disk Image* → **Browse…** →
     `gns3vm-disk1.vmdk` → **Continue**.
   * *Hardware*: **Memory 2048 MB** (4096 MB if you have 16 GB), **2 CPU cores** → Continue.
   * If a *Storage* or *Shared Directory* page appears, keep the defaults / skip → Continue.
   * *Summary*: Name **GNS3 VM**, tick **Open VM Settings** → **Save**.
3. In the settings window:
   * **Drives**: `gns3vm-disk1` is already there (UTM converts it to its own format). Add the second
     disk: **New…** → **Import…** → `gns3vm-disk2.vmdk`, interface **VirtIO** (the same interface as
     the first drive). `gns3vm-disk1` must stay the **first** drive in the list. If a CD/DVD drive
     is listed, you can delete it.
   * **Network**: *Network Mode* **Shared Network**, card **virtio-net-pci** (the defaults).
     One network card is enough: in this mode the Mac can reach the VM and the VM has Internet.
   * **Devices → New… → Serial**: mode **Built-in Terminal**. The GNS3 VM shows its console there
     (the normal display window may stay black — that is expected).
   * **Save**.

**Start the VM and connect GNS3:**

4. Start the VM (▶). Two windows open: the display (may stay black) and the **serial terminal**.
   After 1–2 minutes the terminal shows `gns3vm login:`. Log in as `gns3` / `gns3` — a GNS3 VM
   menu or prompt appears; the **IP address** of `eth0` is shown there, or run
   `ip -4 addr show eth0`. It looks like `192.168.64.5`. Note it.
   You can also find it from the Mac, in Terminal:
   ```bash
   for i in $(seq 2 40); do curl -s -m 1 http://192.168.64.$i/v2/version && echo "   <-- 192.168.64.$i"; done
   ```
   (the address that answers with `"version": "2.2.54"` is the VM).
5. Start GNS3 → *Setup Wizard* → **Run appliances on my local computer** → keep the proposed
   settings (host `127.0.0.1`, port `3080`) → Finish. Ignore warnings about missing local
   emulators.
6. *GNS3 → Preferences → Server* → tab **Remote servers** → **Add**: protocol **HTTP**, host = the
   VM address from step 4, port **80**, no authentication → OK → **Apply**.
   The new server appears in the *Servers Summary* panel and must be green.
   In *Preferences → GNS3 VM* leave *Enable the GNS3 VM* **unticked** (you manage the VM yourself).

Every time you work on the labs: **start the VM in UTM first, then GNS3**. When you finish: close
GNS3, then stop the VM in UTM (■). If the VM ever gets a different address, update it in
*Preferences → Server → Remote servers → Edit*.

> **Note:** the Apple Silicon GNS3 VM disks were tested on the same kind of virtual machine UTM
> creates (QEMU `virt`, VirtIO disks and network, one shared NIC): the VM boots, gets an address on
> `eth0` and GNS3 2.2.54 uses it as a remote server (`cgr_lab.py` selects it automatically). UTM's
> own windows and menus were not tested by us; if something differs, tell the lab instructor.

## 2C. Option C — VirtualBox (Intel Macs only)

1. Download VirtualBox (7.1 or newer) from <https://www.virtualbox.org/wiki/Downloads> —
   **macOS / Intel hosts** — install it and allow the system extension if macOS asks
   (*System Settings → Privacy & Security*).
2. Create the host-only network the GNS3 VM will use, in **Terminal**:
   ```bash
   VBoxManage hostonlynet add --name=HostNetwork --netmask=255.255.255.0 \
       --lower-ip=192.168.56.100 --upper-ip=192.168.56.199 --enable
   VBoxManage list hostonlynets          # HostNetwork must be listed
   ```
   If Terminal answers `command not found`, use the full path
   `/Applications/VirtualBox.app/Contents/MacOS/VBoxManage` instead of `VBoxManage`.
3. Unzip `GNS3.VM.VirtualBox.2.2.54.zip` → VirtualBox *File → Import Appliance* → `GNS3 VM.ova` →
   Finish. Then *Settings → Network → Adapter 1*: *Attached to* **Host-only Network**
   (*HostNetwork*); leave Adapter 2 as **NAT**. Don't start the VM.
4. Start GNS3 → *Setup Wizard*:
   * **Run appliances in a virtual machine** → Next
   * Server: host `127.0.0.1`, port `3080` → Next
   * **VirtualBox**, VM name **GNS3 VM**, **2 vCPUs, 2048 MB RAM** → Finish.
5. GNS3 starts the VM. In the *Servers Summary* panel **GNS3 VM** must turn green.

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
(options A and C: compute `vm`; option B: the remote server you added).

(In every new Terminal window: `cd ~/Documents/cgr-gns3-lab && source .venv/bin/activate`.)

Continue with [Building a lab](04-build-a-lab.md) and [Lab 00](../labs/lab00-first-contact/README.md).
