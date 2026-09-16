# Install on macOS (Apple Silicon or Intel)

Time: ~30 min. Needs ~10 GB free disk and 8 GB RAM.

> **Use exactly GNS3 version `2.2.54`** for the GUI and the GNS3 VM. It is the last 2.2 release
> with an Apple Silicon GNS3 VM, and the whole class uses the same version.

## 1. VMware Fusion Pro (free)

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
4. Install it; when asked for a licence key, choose the free option (no key needed). Open Fusion once
   and grant the permissions macOS asks for (*System Settings → Privacy & Security*).

If the download is still blocked by the account check when the classes start, tell the lab
instructor.

## 2. GNS3 and the GNS3 VM

From <https://github.com/GNS3/gns3-gui/releases/tag/v2.2.54> download `GNS3-2.2.54.dmg` and the VM
for your Mac ( → *About This Mac*):

| Chip | GNS3 VM file |
|---|---|
| Apple M1–M4 | `GNS3.VM.ARM64.2.2.54.zip` |
| Intel | `GNS3.VM.VMware.Workstation.2.2.54.zip` (Fusion opens it) |

1. Install GNS3 (drag to *Applications*; the first time, right-click → *Open*).
2. Unzip the VM and import it in VMware Fusion (*File → Import*, or open the `.ova`/`.vmx`). Don't start it.
3. Start GNS3 → *Setup Wizard* → **Run appliances in a virtual machine** → **VMware** →
   **GNS3 VM**, **2 vCPUs, 2048 MB RAM** → Finish.
   The GNS3 VM must turn green in the *Servers Summary* panel.

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

(In every new Terminal window: `cd ~/Documents/cgr-gns3-lab && source .venv/bin/activate`.)

Continue with [Building a lab](04-build-a-lab.md) and [Lab 00](../labs/lab00-first-contact/README.md).
