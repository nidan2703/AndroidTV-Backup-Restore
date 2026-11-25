# Android / Google TV Streamer Backup & Restore (Linux / Zorin OS Native Edition)

Native **GTK 4 + Libadwaita** desktop application (`streamer_backup_app.py`) and standalone Bash CLI utilities (`backup_tv.sh` & `restore_tv.sh`) for Zorin OS / Ubuntu / Debian Linux.

---

## ⚠️ Important: Target TV Preparation Before Running a Restore

When setting up a brand-new or factory-reset Android TV / Google TV device (such as an NVIDIA Shield TV or Google TV Streamer), **always complete the initial on-screen device setup first** before running the Restore tool:

1. **Complete Initial Android / Google TV Setup**: Sign in with your Google account and finish the initial system walkthrough.
2. **Install Suggested Apps When Prompted**: When Android TV / Google TV prompts you during initial setup to select or restore desired apps from your Google account, **check and allow it to install all desired apps** (do *not* skip/ignore that prompt). Letting Google Play batch-install your common streaming apps during setup ensures it automatically downloads the exact native builds for that specific device's Android OS version and CPU architecture, and speeds up the restore process significantly.
3. **Install & Open Projectivy Launcher Once *(Recommended)***: If you use **Projectivy Launcher**, either install it from the Play Store during setup (or let our Restore tool open its Play Store page first) and open it once so Android initializes its external data directory.
4. **Enable Developer Options & USB / Network Debugging**:
   - Go to **Settings -> System -> About** and click **Android TV OS build** 7 times until *"You are now a developer!"* appears.
   - Go to **Settings -> System -> Developer options** and turn ON **USB debugging** / **Network debugging** (Wireless debugging).
5. **Run the Restore Tool**: Now click **Restore to Target TV** in our app to clone all your sideloaded apps, queue any remaining Play Store apps from your manifest, restore runtime permissions, system/secure/global settings, wallpapers/downloads, disable the stock launcher/bloatware, and automatically import your Projectivy layout, categories, and button color schemes!

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
   - During **Restore**, instead of sideloading device-specific Split APK bundles (which can fail with `INSTALL_FAILED_OLDER_SDK` or crash when moving between different Android TV OS versions or CPU architectures), the app checks which Play Store apps are still missing on the Target TV (automatically skipping any apps you already installed during the initial Google/Android TV setup prompt) and opens each remaining one directly in the Target TV's **Google Play Store** (`market://details?id=<pkg>`) for a 100% genuine, hardware-matched installation.
2. **Sideloaded Apps -> Direct APK & Split APK Cloning**
   - Apps installed outside the Play Store have their full base + split APKs pulled into `apks/<pkg>/` during Backup and automatically batch-installed via `adb install-multiple -r -g` during Restore.

---

## Files in This Folder

- **`streamer_backup_app.py`** — Native Python 3 + GTK 4 + Libadwaita GUI application.
- **`backup_tv.sh`** / **`restore_tv.sh`** — Standalone interactive Bash CLI backup and restore scripts.
- **`install_launchers.sh`** — Installs `.desktop` shortcuts and the custom taskbar icon (`icon.svg`).
