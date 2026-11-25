# Android / Google TV Streamer Backup & Restore (Windows 10 / 11 Native Edition)

Zero-dependency native Windows 10 / 11 desktop application (`AndroidTV_Streamer_Backup.exe`) to back up, restore, and clone Android TV / Google TV streaming boxes over wireless ADB.

---

## Quick Start (Windows 10 / 11)

1. Double-click **`AndroidTV_Streamer_Backup.exe`** (or **`Launch_Windows_App.bat`**).
   - **No Python, no .NET SDK, and no runtime installers required** — built on native Windows `.NET Framework 4.8`, which is pre-installed on every Windows 10 and Windows 11 PC.
2. If `adb.exe` is not already installed on your PC, click the **"Download ADB"** button in the top-right corner of the app to automatically download and extract Google's official Android Platform-Tools.

---

## How App Backup & Restore Works (Play Store Manifest vs. Sideloaded Cloning)

1. **Play Store Apps (`installer=com.android.vending`) -> Fresh Play Store Manifest Install (Mode A)**
   - During **Backup**, the app records all Google Play Store apps into `packages/playstore_packages.txt`.
   - During **Restore**, instead of sideloading device-specific Split APK bundles (which can fail with `INSTALL_FAILED_OLDER_SDK` or crash when moving between different Android TV OS versions or CPU architectures, e.g. Google TV Streamer Android 14 -> NVIDIA Shield TV Android 11), the app checks which Play Store apps are missing on the Target TV and opens each one directly in the Target TV's **Google Play Store** (`market://details?id=<pkg>`) so you can click **Install** for a 100% genuine, hardware-matched installation.
2. **Sideloaded Apps -> Direct APK & Split APK Cloning**
   - Apps installed outside the Play Store (Downloader, Aptoide TV, file managers, custom APKs) have their full base + split APKs pulled into `apks/<pkg>/` during Backup and automatically batch-installed via `adb install-multiple -r -g` during Restore.

---

## Files in This Folder

- **`AndroidTV_Streamer_Backup.exe`** — Standalone pre-compiled native Windows GUI executable.
- **`StreamerBackup.cs`** — Complete C# WinForms source code.
- **`Launch_Windows_App.bat`** — Launches `AndroidTV_Streamer_Backup.exe` (or auto-compiles `StreamerBackup.cs` in <1 second using Windows's built-in `csc.exe` if the `.exe` is missing).
- **`build_windows_exe.bat`** — Recompiles `StreamerBackup.cs` into `AndroidTV_Streamer_Backup.exe` using Windows's built-in `.NET Framework` compiler.
