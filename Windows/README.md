# Android / Google TV Streamer Backup & Restore (Windows 10 / 11 Native Edition)

Zero-dependency native Windows 10 / 11 desktop application (`AndroidTV_Streamer_Backup.exe`) to back up, restore, and clone Android TV / Google TV streaming boxes over wireless ADB.

> [!IMPORTANT]
> **Download the Entire Windows Folder (`< 75 KB`)**
> Do **not** download `AndroidTV_Streamer_Backup.exe` or `Launch_Windows_App.bat` individually by itself. Instead, download **[`AndroidTV_Streamer_Backup_Windows.zip`](../AndroidTV_Streamer_Backup_Windows.zip)** from the main repository page (or download the full repo via **`<> Code` → `Download ZIP`**) and **extract the entire folder** so all companion files stay together.

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

## Quick Start (Windows 10 / 11)

1. Download and extract **[`AndroidTV_Streamer_Backup_Windows.zip`](../AndroidTV_Streamer_Backup_Windows.zip)** (or the entire `Windows/` folder).
2. Inside the extracted folder, double-click **`AndroidTV_Streamer_Backup.exe`** (or **`Launch_Windows_App.bat`**).
   - **No Python, no .NET SDK, and no runtime installers required** — built on native Windows `.NET Framework 4.8`, which is pre-installed on every Windows 10 and Windows 11 PC.
3. If `adb.exe` is not already installed on your PC, click the **"Download ADB"** button in the top-right corner of the app to automatically download and extract Google's official Android Platform-Tools.

---

## How App Backup & Restore Works (Play Store Manifest vs. Sideloaded Cloning)

1. **Play Store Apps (`installer=com.android.vending`) -> Fresh Play Store Manifest Install (Mode A)**
   - During **Backup**, the app records all Google Play Store apps into `packages/playstore_packages.txt`.
   - During **Restore**, instead of sideloading device-specific Split APK bundles (which can fail with `INSTALL_FAILED_OLDER_SDK` or crash when moving between different Android TV OS versions or CPU architectures, e.g. Google TV Streamer Android 14 -> NVIDIA Shield TV Android 11), the app checks which Play Store apps are still missing on the Target TV (automatically skipping any apps you already installed during the initial Google/Android TV setup prompt) and opens each remaining one directly in the Target TV's **Google Play Store** (`market://details?id=<pkg>`) so you can click **Install** for a 100% genuine, hardware-matched installation.
2. **Sideloaded Apps -> Direct APK & Split APK Cloning**
   - Apps installed outside the Play Store (Downloader, Aptoide TV, file managers, custom APKs) have their full base + split APKs pulled into `apks/<pkg>/` during Backup and automatically batch-installed via `adb install-multiple -r -g` during Restore.

---

## Files in This Folder

- **`AndroidTV_Streamer_Backup.exe`** — Standalone pre-compiled native Windows GUI executable.
- **`StreamerBackup.cs`** — Complete C# WinForms source code.
- **`Launch_Windows_App.bat`** — Launches `AndroidTV_Streamer_Backup.exe` (or auto-compiles `StreamerBackup.cs` in <1 second using Windows's built-in `csc.exe` if the `.exe` is missing).
- **`build_windows_exe.bat`** — Recompiles `StreamerBackup.cs` into `AndroidTV_Streamer_Backup.exe` using Windows's built-in `.NET Framework` compiler.
