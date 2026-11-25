#!/usr/bin/env bash
# ==============================================================================
# Helper to install the Zorin OS GUI App & CLI .desktop launchers + Taskbar Icon
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "${HOME}/Desktop")"
APPS_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
LOCAL_ICON_DIR="${SCRIPT_DIR}/hicolor/scalable/apps"
APP_ID="io.github.achim.StreamerBackup"

chmod +x "${SCRIPT_DIR}/streamer_backup_app.py" "${SCRIPT_DIR}/backup_tv.sh" "${SCRIPT_DIR}/restore_tv.sh"

# Generate .desktop files pointing to the current clone directory ($SCRIPT_DIR)
cat > "${SCRIPT_DIR}/Android_TV_Backup_Manager.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Android TV Streamer Backup
GenericName=Android TV Backup & Restore Manager
Comment=Native Zorin OS utility to backup and clone Android/Google TV streamers (APKs, Projectivy, settings, debloat)
Icon=${SCRIPT_DIR}/icon.svg
Terminal=false
Exec=${SCRIPT_DIR}/streamer_backup_app.py
Categories=Utility;System;
Keywords=android;tv;google;backup;restore;adb;projectivy;
StartupNotify=true
StartupWMClass=${APP_ID}
EOF

cat > "${SCRIPT_DIR}/Backup_Android_TV.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Backup Android TV (CLI)
GenericName=Android TV CLI Backup
Comment=Backup 3rd-party APKs, Projectivy files, settings, and permissions from Android/Google TV
Icon=${SCRIPT_DIR}/icon.svg
Terminal=false
Exec=gnome-terminal --title="Android TV Streamer - Backup" -- bash -c '"${SCRIPT_DIR}/backup_tv.sh"; echo ""; read -r -p "Press Enter to close this window..."'
Categories=Utility;System;
StartupNotify=true
EOF

cat > "${SCRIPT_DIR}/Restore_Android_TV.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Restore Android TV (CLI)
GenericName=Android TV CLI Restore
Comment=Restore APKs, Projectivy files, permissions, settings, and disable stock launcher on Android/Google TV
Icon=${SCRIPT_DIR}/icon.svg
Terminal=false
Exec=gnome-terminal --title="Android TV Streamer - Restore" -- bash -c '"${SCRIPT_DIR}/restore_tv.sh"; echo ""; read -r -p "Press Enter to close this window..."'
Categories=Utility;System;
StartupNotify=true
EOF

chmod +x "${SCRIPT_DIR}/Android_TV_Backup_Manager.desktop" \
         "${SCRIPT_DIR}/Backup_Android_TV.desktop" \
         "${SCRIPT_DIR}/Restore_Android_TV.desktop"

# Install app icon into user hicolor icon theme so GTK4 & Zorin taskbar find it
mkdir -p "$ICON_DIR" "$LOCAL_ICON_DIR"
cp -f "${SCRIPT_DIR}/icon.svg" "${ICON_DIR}/${APP_ID}.svg"
cp -f "${SCRIPT_DIR}/icon.svg" "${LOCAL_ICON_DIR}/${APP_ID}.svg"
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

mkdir -p "$APPS_DIR"
# Install under APP_ID.desktop so GNOME Shell / Zorin Taskbar matches the running window's application_id
cp -f "${SCRIPT_DIR}/Android_TV_Backup_Manager.desktop" "${APPS_DIR}/${APP_ID}.desktop"
chmod +x "${APPS_DIR}/${APP_ID}.desktop"
rm -f "${APPS_DIR}/Android_TV_Backup_Manager.desktop"

for f in Backup_Android_TV.desktop Restore_Android_TV.desktop; do
    cp -f "${SCRIPT_DIR}/${f}" "${APPS_DIR}/${f}"
    chmod +x "${APPS_DIR}/${f}"
done

if [[ -d "$DESKTOP_DIR" ]]; then
    for f in Android_TV_Backup_Manager.desktop Backup_Android_TV.desktop Restore_Android_TV.desktop; do
        cp -f "${SCRIPT_DIR}/${f}" "${DESKTOP_DIR}/${f}"
        chmod +x "${DESKTOP_DIR}/${f}"
        if command -v gio >/dev/null 2>&1; then
            gio set "${DESKTOP_DIR}/${f}" metadata::trusted true 2>/dev/null || true
            gio set -t string "${DESKTOP_DIR}/${f}" metadata::trusted true 2>/dev/null || true
        fi
    done
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

echo "Installed shortcuts and taskbar icon (${APP_ID}) to ${DESKTOP_DIR} and ${APPS_DIR}."
