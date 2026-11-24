# Android / Google TV Streamer Backup & Restore (Linux & Windows)

A full-featured desktop utility for **Linux (Zorin OS / Ubuntu / GNOME)** and **Windows 10 / 11** to back up, restore, and clone Android TV / Google TV streaming boxes over wireless ADB.

---

## Platforms Included

1. **Linux / Zorin OS Native App (`streamer_backup_app.py`)**
   - Built with **Python 3 + GTK 4 + Libadwaita** for a 100% native Zorin OS / GNOME desktop look and feel.
   - Includes `install_launchers.sh` to install desktop shortcuts, start-menu entries, and the custom taskbar icon (`icon.svg`).
   - Also includes standalone Bash CLI scripts (`backup_tv.sh` and `restore_tv.sh`).

2. **Windows 10 / 11 App (`streamer_backup_windows.py` & `Launch_Windows_App.bat`)**
   - Built with Python's standard `tkinter.ttk` (zero third-party pip packages required) with Windows 10/11 DPI scaling and native Dark Mode titlebar support.
   - **Built-in 1-Click ADB Installer**: Automatically detects `adb.exe` or downloads and extracts Google's official `platform-tools` for Windows with a single click.
   - Includes `build_windows_exe.bat` to package a standalone single-file `AndroidTV_Streamer_Backup.exe` via PyInstaller.

---

## Complete 6-Stage Streamer Cloning Pipeline

Every stage has its own checkbox (plus **Select All** / **Select None** buttons) so you can perform a full box-to-box clone or run any single stage independently:

1. **3rd-Party APKs & Split APKs**
   - Enumerates all user-installed packages (`pm list packages -3`), resolves base and split APK paths via `pm path <pkg>`, pulls them into `apks/<pkg>/`, and batch-installs them on the target device via `adb install-multiple -r -g`.
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
   - Saves disabled packages (`pm list packages -d`), re-disables the stock Google TV launcher (`com.google.android.apps.tv.launcherx` and `com.google.android.tungsten.setupwraith`) and disabled bloatware via `pm disable-user --user 0`, sets Projectivy (`com.spocky.projengmenu`) as the home activity, and triggers the `HOME` intent.

---

## Quick Start

### On Linux (Zorin OS / Ubuntu / Debian)

1. Install `adb`:
   ```bash
   sudo apt update && sudo apt install -y adb
   ```
2. Launch the native GTK 4 / Libadwaita GUI:
   ```bash
   ./streamer_backup_app.py
   ```
3. *(Optional)* Install Desktop & Application Menu shortcuts:
   ```bash
   ./install_launchers.sh
   ```
4. *(Optional)* Run the standalone interactive CLI scripts:
   ```bash
   ./backup_tv.sh
   ./restore_tv.sh
   ```

### On Windows 10 / 11

1. Make sure [Python 3 for Windows](https://www.python.org/downloads/) is installed (with **"Add Python to PATH"** checked).
2. Double-click **`Launch_Windows_App.bat`** (or run `python streamer_backup_windows.py`).
3. If `adb.exe` is not already installed on your PC, click the **"Download ADB (Windows)"** button in the top-right corner of the app to automatically download Google's official Android Platform-Tools.
4. *(Optional)* Double-click **`build_windows_exe.bat`** to generate a standalone `dist\AndroidTV_Streamer_Backup.exe` executable.
