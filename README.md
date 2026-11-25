# Android / Google TV Streamer Backup & Restore (Linux & Windows)

A full-featured desktop utility for **Windows 10 / 11** and **Linux (Zorin OS / Ubuntu / GNOME)** to back up, restore, and clone Android TV / Google TV streaming boxes (Google TV Streamer, NVIDIA Shield TV, Chromecast with Google TV, etc.) over wireless ADB.

> [!IMPORTANT]
> **Always Download the Entire Folder / ZIP Archive (`< 75 KB`)**
> Do **not** download a single `.exe` or `.bat` file by itself from the `Windows/` folder (doing so will cause missing-file prompts). Instead, download **[`AndroidTV_Streamer_Backup_Windows.zip`](AndroidTV_Streamer_Backup_Windows.zip)** (or **[`AndroidTV_Streamer_Backup_Linux.zip`](AndroidTV_Streamer_Backup_Linux.zip)** for Linux, or click the green **`<> Code` → `Download ZIP`** button to download the whole repository) and **extract the entire folder** before launching.

---

## Easy Platform Downloads (Separate Folders & Ready-to-Download ZIPs)

To avoid mixing Windows and Linux files, the repository is cleanly split into separate folders and standalone `.zip` archives:

### 🪟 For Windows 10 / 11
- **Quick ZIP Download (Recommended)**: Click **[`AndroidTV_Streamer_Backup_Windows.zip`](AndroidTV_Streamer_Backup_Windows.zip)** -> click the **`Download raw file`** button on GitHub -> **Extract All** on your PC. *(Or download the entire repository via **`<> Code` -> `Download ZIP`** and open the **[`Windows/`](Windows/)** folder.)*
- **Zero Prerequisites**: Inside the extracted folder, double-click **`AndroidTV_Streamer_Backup.exe`** (or **`Launch_Windows_App.bat`**). Runs out-of-the-box on every Windows 10 & Windows 11 PC (uses built-in `.NET Framework 4.8` — no Python, no SDKs, and includes a 1-click **Download ADB** button).

### 🐧 For Linux (Zorin OS / Ubuntu / Debian)
- **Quick ZIP Download (Recommended)**: Click **[`AndroidTV_Streamer_Backup_Linux.zip`](AndroidTV_Streamer_Backup_Linux.zip)** -> click **`Download raw file`** -> extract the entire folder. *(Or clone the repo and open the **[`Linux/`](Linux/)** folder.)*
- **Native GTK 4 / Libadwaita GUI + Bash CLI**: Inside the extracted folder, run `./streamer_backup_app.py` (or `./install_launchers.sh` to add Desktop & Start Menu shortcuts).

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

## Smart App Handling: Play Store Manifest (Mode A) + Sideloaded APK Cloning

When cloning between different Android TV / Google TV boxes (for example, from an **Android 14 Google TV Streamer** to an **Android 11 NVIDIA Shield TV**), sideloading Split APK bundles originally downloaded from Google Play onto a different device can fail with `INSTALL_FAILED_OLDER_SDK` or refuse to open due to CPU architecture (`armeabi-v7a` vs `arm64-v8a`) and Google Play licensing checks.

To ensure 100% compatibility across any Android TV or Google TV box:

1. **Play Store Apps (`installer=com.android.vending`) -> Fresh Play Store Install via Manifest (`packages/playstore_packages.txt`)**
   - During **Backup**, the tool inspects every package's installer origin (`pm list packages -3 -i`). Apps installed from the Google Play Store are saved to the Play Store manifest (`packages/playstore_packages.txt`) without wasting time pulling device-locked Split APKs.
   - During **Restore**, the tool checks which Play Store apps from your manifest are not yet installed on the Target TV (skipping all apps you already installed during the initial Google/Android TV setup prompt, and putting **Projectivy Launcher** first if missing) and automatically opens each remaining app's page directly on the Target TV's **Google Play Store** (`market://details?id=<pkg>`) so the TV downloads the exact native build for its Android SDK and CPU.
2. **Sideloaded Apps -> Direct APK & Split APK Cloning (`packages/sideloaded_packages.txt` & `apks/<pkg>/`)**
   - Apps installed outside the Play Store (via Downloader, Aptoide TV, file managers, etc.) have all of their base and split APKs pulled during Backup and automatically cloned onto the Target TV via `adb install-multiple -r -g`.
   - *Backward Compatibility*: If you restore from an older backup folder created before this update, the tool automatically classifies your existing backup into Play Store vs. Sideloaded apps on the fly.

---

## Complete 6-Stage Streamer Cloning Pipeline

Every stage has its own checkbox (plus **Select All** / **Select None** buttons) so you can perform a full box-to-box restore or run any single stage independently:

1. **Play Store Manifest & Sideloaded APK Cloning**
   - Clones sideloaded APKs directly via `adb install-multiple -r -g` and queues missing Play Store manifest apps directly in the Target TV's Google Play Store.
2. **Granted Runtime Permissions**
   - Parses `dumpsys package <pkg>` for `granted=true` runtime permissions and re-grants them on the target device via `pm grant`.
3. **Projectivy Layout, App Groupings & Button Color Schemes (`.plbackup`)**
   - Pulls Projectivy Launcher snapshots from `/sdcard/Android/data/com.spocky.projengmenu/files/backups/*.plbackup` and wallpapers.
   - Preserves Android 11–14 FUSE app-UID ownership on restore by pushing the latest snapshot to `/sdcard/Android/data/com.spocky.projengmenu/files/projectivy-restore.plbackup` and automatically launching Projectivy's internal importer (`com.spocky.projengmenu/.ui.launcherActivities.ImportSettingsActivity`).
4. **Downloads & Wallpapers (`/sdcard/Download` & `/sdcard/Pictures`)**
   - Pulls and restores `/sdcard/Download` and `/sdcard/Pictures` (pushed *first* during restore so media and wallpapers are ready before apps launch).
5. **Safe System, Secure & Global Settings**
   - Dumps and restores `system`, `secure`, and `global` settings while automatically filtering out device-unique and connectivity-sensitive keys (`android_id`, `bluetooth_address`, `wifi_on`, `device_name`, `boot_count`, etc.).
6. **Disabled Bloatware, Stock Launcher & Projectivy HOME Intent**
   - Saves disabled packages (`pm list packages -d`), safely verifies Projectivy is installed before disabling the stock launcher (`com.google.android.apps.tv.launcherx` / `com.google.android.tungsten.setupwraith`), disables bloatware via `pm disable-user --user 0`, sets Projectivy (`com.spocky.projengmenu`) as the default home activity, and triggers the `HOME` intent.
