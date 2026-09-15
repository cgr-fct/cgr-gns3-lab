# Device images

## Cumulus VX (full mode only)

1. Go to <https://www.nvidia.com/en-us/networking/ethernet-switching/cumulus-vx/download/>
   (you may be asked to register — it is free).
2. Download the **KVM/QEMU** image of the version your instructor names, e.g.
   `cumulus-linux-5.16.0-vx-amd64-qemu.qcow2` (~2 GB).
3. Upload it to GNS3 (GNS3 must be open and the GNS3 VM green):
   ```bash
   python tools/cgr_lab.py upload-image ~/Downloads/cumulus-linux-5.16.0-vx-amd64-qemu.qcow2
   ```
   (Windows: `py tools\cgr_lab.py upload-image $HOME\Downloads\cumulus-linux-...qcow2`)
4. If your file name differs from `cumulus.image` in `tools/lab_settings.yml`, edit that line.
5. Optional — create device templates so you can also drag devices from the GUI palette:
   ```bash
   python tools/cgr_lab.py templates
   ```

You don't need to create any QEMU template by hand. If you prefer the GUI anyway, see
[the manual method](05-build-a-lab.md#manual-method-gui-only).

**Factory login:** `cumulus` / `cumulus`. At the first login Cumulus forces a password change;
in this course the new password is always **`CumulusLab1!`** (the bootstrap does it for you).

## Containers (all modes)

The FRR router and the automation station are Docker images published by the course:

| Image | Used as |
|---|---|
| `ghcr.io/<course>/cgr-frr:latest` | lite routers/switches, ISP routers, r3/r4 |
| `ghcr.io/<course>/cgr-netauto:latest` | netauto station |

(the exact names are in `tools/lab_settings.yml`). There is nothing to do: GNS3 downloads them
the **first time you start a lab** — this needs Internet access from the GNS3 VM and takes a
couple of minutes (≈500 MB). Starting labs afterwards is instant.

To pre-download them (e.g. before an exam), open the GNS3 VM console → *Shell* and run
`docker pull <image>` for both images.
