# Android / Google TV Streamer Backup & Restore (Linux / Zorin OS Native Edition)

Native **GTK 4 + Libadwaita** desktop application (`streamer_backup_app.py`) and standalone Bash CLI utilities (`backup_tv.sh` & `restore_tv.sh`) for Zorin OS / Ubuntu / Debian Linux.

---

## Quick Start (Zorin OS / Ubuntu / Debian)

1. Install `adb`:
   ```bash
   sudo apt update && sudo apt install -y adb
   ```
2. Launch the native GTK 4 / Libadwaita GUI:
   ```bash
   ./streamer_backup_app.py
   ```
3. *(Optional)* Install Desktop & Application Menu shortcuts + taskbar icon:
   ```bash
   ./install_launchers.sh
   ```
4. *(Optional)* Run the standalone interactive CLI scripts:
   ```bash
   ./backup_tv.sh
   ./restore_tv.sh
   ```

---

## How App Backup & Restore Works (Play Store Manifest vs. Sideloaded Cloning)

1. **Play Store Apps (`installer=com.android.vending`) -> Fresh Play Store Manifest Install (Mode A)**
   - During **Backup**, the app queries `pm list packages -3 -i` and records all Google Play Store apps into `packages/playstore_packages.txt`.
   - During **Restore**, instead of sideloading device-specific Split APK bundles (which can fail with `INSTALL_FAILED_OLDER_SDK` or crash when moving between different Android TV OS versions or CPU architectures), the app checks which Play Store apps are missing on the Target TV and opens each one directly in the Target TV's **Google Play Store** (`market://details?id=<pkg>`) for a 100% genuine, hardware-matched installation.
2. **Sideloaded Apps -> Direct APK & Split APK Cloning**
   - Apps installed outside the Play Store have their full base + split APKs pulled into `apks/<pkg>/` during Backup and automatically batch-installed via `adb install-multiple -r -g` during Restore.

---

## Files in This Folder

- **`streamer_backup_app.py`** — Native Python 3 + GTK 4 + Libadwaita GUI application.
- **`backup_tv.sh`** / **`restore_tv.sh`** — Standalone interactive Bash CLI backup and restore scripts.
- **`install_launchers.sh`** — Installs `.desktop` shortcuts and the custom taskbar icon (`icon.svg`).
