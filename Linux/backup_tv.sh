#!/usr/bin/env bash
# ==============================================================================
# Zorin OS Android / Google TV Backup Utility (backup_tv.sh)
# Default Target: 192.168.4.64:5555
# Backup Destination: "${HOME}/Android Streamer Backup"
# ==============================================================================

set -u

DEFAULT_IP="192.168.4.64"
DEFAULT_PORT="5555"
BACKUP_ROOT="${HOME}/Android Streamer Backup"
PLAYSTORE_INSTALLER="com.android.vending"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err()   { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "\n${BOLD}${CYAN}==> $*${NC}"; }

echo -e "${BOLD}============================================================${NC}"
echo -e "${BOLD}   Zorin OS Android / Google TV Streamer Backup Utility     ${NC}"
echo -e "${BOLD}============================================================${NC}"

# ------------------------------------------------------------------------------
# 1. Verify ADB Installation
# ------------------------------------------------------------------------------
log_step "Step 1: Verifying ADB installation"
if ! command -v adb >/dev/null 2>&1; then
    log_err "'adb' is not installed or not in PATH."
    echo -e "Install it on Zorin OS with:\n  ${BOLD}sudo apt update && sudo apt install -y adb${NC}"
    exit 1
fi
log_ok "Found $(adb --version | head -n 1)"

# ------------------------------------------------------------------------------
# 2. Prompt for Source Device IP (or IP:PORT)
# ------------------------------------------------------------------------------
log_step "Step 2: Source Device IP Configuration"

prompt_for_ip() {
    local input_ip="${1:-}"
    while true; do
        if [[ -z "$input_ip" ]]; then
            echo -e "Enter the ${BOLD}SOURCE${NC} Android/Google TV IP address (or IP:PORT)."
            read -r -p "Source Device IP [press Enter for ${DEFAULT_IP}:${DEFAULT_PORT}]: " USER_INPUT
            input_ip="${USER_INPUT:-${DEFAULT_IP}:${DEFAULT_PORT}}"
        fi

        input_ip="$(echo "$input_ip" | tr -d '[:space:]')"

        if [[ "$input_ip" == *:* ]]; then
            TARGET_ADDR="$input_ip"
        else
            TARGET_ADDR="${input_ip}:${DEFAULT_PORT}"
        fi

        if [[ "$TARGET_ADDR" =~ ^[a-zA-Z0-9.-]+:[0-9]+$ ]]; then
            break
        else
            log_warn "Invalid address format: '${input_ip}'. Expected IP (e.g. 192.168.4.64) or IP:PORT (e.g. 192.168.4.64:5555)."
            input_ip=""
        fi
    done
}

prompt_for_ip "${1:-}"
log_info "Source Android/Google TV set to: ${BOLD}${TARGET_ADDR}${NC}"

# ------------------------------------------------------------------------------
# 3. Connect & Handle TV RSA Authorization Prompt
# ------------------------------------------------------------------------------
log_step "Step 3: Connecting to ${TARGET_ADDR} & verifying RSA authorization"
adb start-server >/dev/null 2>&1

connect_and_authorize() {
    local max_attempts=30
    local attempt=1

    adb connect "$TARGET_ADDR" >/dev/null 2>&1 || true

    while (( attempt <= max_attempts )); do
        local state
        state=$(adb -s "$TARGET_ADDR" get-state 2>&1 || true)

        if [[ "$state" == "device" ]]; then
            log_ok "Connected and authorized with ${TARGET_ADDR}!"
            return 0
        elif [[ "$state" == *"unauthorized"* ]]; then
            if (( attempt == 1 )); then
                echo -e "${YELLOW}------------------------------------------------------------${NC}"
                echo -e "${BOLD}${YELLOW}ACTION REQUIRED ON YOUR TV:${NC}"
                echo -e "Please look at your Android/Google TV screen now."
                echo -e "Check ${BOLD}'Always allow from this computer'${NC} and select ${BOLD}'Allow'${NC}."
                echo -e "${YELLOW}------------------------------------------------------------${NC}"
            fi
            log_warn "Waiting for RSA authorization on TV screen... (${attempt}/${max_attempts})"
            sleep 3
        else
            if (( attempt == 1 )); then
                log_info "Attempting network connection to ${TARGET_ADDR}..."
            fi
            adb disconnect "$TARGET_ADDR" >/dev/null 2>&1 || true
            local conn_out
            conn_out=$(adb connect "$TARGET_ADDR" 2>&1 || true)
            if [[ "$conn_out" == *"cannot connect"* || "$conn_out" == *"Connection refused"* || "$conn_out" == *"No route to host"* ]]; then
                log_warn "Connection attempt ${attempt}/${max_attempts}: ${conn_out}"
            fi
            sleep 2
        fi
        ((attempt++))
    done

    log_err "Could not establish an authorized ADB session with ${TARGET_ADDR}."
    echo "Please verify:"
    echo "  1. The TV is powered on and on the same network."
    echo "  2. Developer Options -> 'USB debugging' / 'Wireless debugging' is ON."
    echo "  3. The IP address and port (${TARGET_ADDR}) are correct."
    return 1
}

while ! connect_and_authorize; do
    echo ""
    read -r -p "Would you like to enter a different Source IP address and try again? [Y/n]: " RETRY_CHOICE
    if [[ "${RETRY_CHOICE:-Y}" =~ ^[Nn]$ ]]; then
        exit 1
    fi
    prompt_for_ip ""
    log_info "Retrying with Source Android/Google TV: ${BOLD}${TARGET_ADDR}${NC}"
done

ADB_CMD=(adb -s "$TARGET_ADDR")

# ------------------------------------------------------------------------------
# 4. Prepare Backup Directory Structure
# ------------------------------------------------------------------------------
log_step "Step 4: Preparing backup directories"
APKS_DIR="${BACKUP_ROOT}/apks"
PERMS_DIR="${BACKUP_ROOT}/permissions"
SDCARD_DIR="${BACKUP_ROOT}/sdcard"
SETTINGS_DIR="${BACKUP_ROOT}/settings"
PACKAGES_DIR="${BACKUP_ROOT}/packages"

mkdir -p "$APKS_DIR" "$PERMS_DIR" "$SDCARD_DIR" "$SETTINGS_DIR" "$PACKAGES_DIR"

DEVICE_MODEL=$("${ADB_CMD[@]}" shell getprop ro.product.model 2>/dev/null | tr -d '\r')
ANDROID_VER=$("${ADB_CMD[@]}" shell getprop ro.build.version.release 2>/dev/null | tr -d '\r')
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

cat > "${BACKUP_ROOT}/backup_metadata.txt" <<EOF
Backup Timestamp : ${TIMESTAMP}
Source Address   : ${TARGET_ADDR}
Device Model     : ${DEVICE_MODEL:-Unknown}
Android Version  : ${ANDROID_VER:-Unknown}
EOF

log_ok "Backup destination ready: \"${BACKUP_ROOT}\""
log_info "Detected Device: ${BOLD}${DEVICE_MODEL:-Unknown}${NC} (Android ${ANDROID_VER:-Unknown})"

# ------------------------------------------------------------------------------
# 5. Classify Play Store Manifest vs. Sideloaded APKs & Export Permissions
# ------------------------------------------------------------------------------
log_step "Step 5: Classifying Play Store manifest vs. Sideloaded APKs & exporting runtime permissions"

: > "${PACKAGES_DIR}/third_party_packages.txt"
: > "${PACKAGES_DIR}/playstore_packages.txt"
: > "${PACKAGES_DIR}/sideloaded_packages.txt"
: > "${PACKAGES_DIR}/package_installers.txt"
: > "${PERMS_DIR}/granted_permissions.txt"

mapfile -t RAW_PKG_INSTALLERS < <("${ADB_CMD[@]}" shell pm list packages -3 -i 2>/dev/null | tr -d '\r' | grep -v '^[[:space:]]*$' | sort)

THIRD_PARTY_PKGS=()
PLAYSTORE_PKGS=()
SIDELOADED_PKGS=()
declare -A IS_SIDELOADED_MAP=()

for line in "${RAW_PKG_INSTALLERS[@]}"; do
    pkg=$(echo "$line" | sed -E 's/^package:([^[:space:]]+).*/\1/')
    inst=$(echo "$line" | sed -nE 's/.*installer=([^[:space:]]+).*/\1/p')
    [[ -z "$inst" ]] && inst="null"
    [[ -z "$pkg" ]] && continue

    THIRD_PARTY_PKGS+=("$pkg")
    echo "${pkg} ${inst}" >> "${PACKAGES_DIR}/package_installers.txt"
    echo "${pkg}" >> "${PACKAGES_DIR}/third_party_packages.txt"

    if [[ "${inst,,}" == "${PLAYSTORE_INSTALLER}" ]]; then
        PLAYSTORE_PKGS+=("$pkg")
        echo "${pkg}" >> "${PACKAGES_DIR}/playstore_packages.txt"
    else
        SIDELOADED_PKGS+=("$pkg")
        IS_SIDELOADED_MAP["$pkg"]=1
        echo "${pkg}" >> "${PACKAGES_DIR}/sideloaded_packages.txt"
    fi
done

TOTAL_PKGS=${#THIRD_PARTY_PKGS[@]}
log_info "Found ${BOLD}${TOTAL_PKGS}${NC} 3rd-party package(s): ${BOLD}${#PLAYSTORE_PKGS[@]}${NC} Play Store (manifest), ${BOLD}${#SIDELOADED_PKGS[@]}${NC} Sideloaded (APK clone)."

# Generate human-readable APP_MANIFEST_CHECKLIST.txt for checking off apps on Device B
CHECKLIST_FILE="${BACKUP_ROOT}/APP_MANIFEST_CHECKLIST.txt"
{
    echo "=============================================================================="
    echo "  ANDROID / GOOGLE TV APP MANIFEST & DEVICE-A -> DEVICE-B CHECKLIST"
    echo "=============================================================================="
    echo "Backup Timestamp     : ${TIMESTAMP}"
    echo "Source Device (A)    : ${DEVICE_MODEL:-Unknown} (Android ${ANDROID_VER:-Unknown}) @ ${TARGET_ADDR}"
    echo "Total 3rd-Party Apps : ${TOTAL_PKGS} (${#PLAYSTORE_PKGS[@]} Play Store + ${#SIDELOADED_PKGS[@]} Sideloaded)"
    echo "=============================================================================="
    echo "INSTRUCTIONS FOR TARGET DEVICE (B):"
    echo "  1. Complete the initial Android/Google TV setup on Device B and allow it"
    echo "     to install your desired apps when prompted during setup."
    echo "  2. Run 'Restore to Target TV' (or restore_tv.sh)."
    echo "  3. Use the checkboxes [ ] below (or check APP_RESTORE_VERIFICATION_REPORT.txt"
    echo "     after restore) to verify every app from Device A is installed on Device B."
    echo "=============================================================================="
    echo ""
    echo "--- SECTION 1: GOOGLE PLAY STORE APPS (${#PLAYSTORE_PKGS[@]}) ---"
    echo "(Installed fresh from Google Play on Device B to match its Android SDK & CPU)"
    echo ""
    idx=0
    for p in "${PLAYSTORE_PKGS[@]}"; do
        ((idx++))
        printf "[ ] %2d. %s\n" "$idx" "$p"
    done
    echo ""
    echo "--- SECTION 2: SIDELOADED APPS (${#SIDELOADED_PKGS[@]}) ---"
    echo "(Cloned automatically via ADB from apks/<package>/ during Restore)"
    echo ""
    idx=0
    for p in "${SIDELOADED_PKGS[@]}"; do
        ((idx++))
        printf "[ ] %2d. %s\n" "$idx" "$p"
    done
    echo ""
    echo "=============================================================================="
} > "$CHECKLIST_FILE"
log_ok "Created user checklist: \"${CHECKLIST_FILE}\""

PKG_INDEX=0
CLONED_SIDELOAD_PKGS=0

for pkg in "${THIRD_PARTY_PKGS[@]}"; do
    ((PKG_INDEX++))

    if [[ -n "${IS_SIDELOADED_MAP[$pkg]:-}" ]]; then
        echo -e "\n${BOLD}[${PKG_INDEX}/${TOTAL_PKGS}] Cloning Sideloaded App: ${pkg}${NC}"
        PKG_APK_DIR="${APKS_DIR}/${pkg}"
        mkdir -p "$PKG_APK_DIR"
        rm -f "${PKG_APK_DIR}"/*.apk

        mapfile -t APK_PATHS < <("${ADB_CMD[@]}" shell pm path "$pkg" 2>/dev/null | tr -d '\r' | sed 's/^package://' | grep -v '^[[:space:]]*$')

        if (( ${#APK_PATHS[@]} > 0 )); then
            PULL_OK=true
            SPLIT_COUNT=0
            for remote_apk in "${APK_PATHS[@]}"; do
                ((SPLIT_COUNT++))
                apk_basename=$(basename "$remote_apk")
                local_apk="${PKG_APK_DIR}/${apk_basename}"
                if [[ -e "$local_apk" ]]; then
                    local_apk="${PKG_APK_DIR}/${SPLIT_COUNT}_${apk_basename}"
                fi

                log_info "  Pulling (${SPLIT_COUNT}/${#APK_PATHS[@]}): ${apk_basename}"
                if ! "${ADB_CMD[@]}" pull "$remote_apk" "$local_apk" >/dev/null; then
                    log_warn "  Failed to pull ${remote_apk}"
                    PULL_OK=false
                fi
            done
            if [[ "$PULL_OK" == true ]]; then
                ((CLONED_SIDELOAD_PKGS++))
                log_ok "  Saved ${#APK_PATHS[@]} APK file(s) for sideloaded app ${pkg}"
            fi
        else
            log_warn "  Could not resolve APK path(s) for ${pkg}, skipping APK pull."
        fi
    else
        log_info "[${PKG_INDEX}/${TOTAL_PKGS}] Recorded Play Store app in manifest: ${pkg}"
    fi

    # Export granted runtime permissions for this package
    mapfile -t GRANTED_PERMS < <(
        "${ADB_CMD[@]}" shell dumpsys package "$pkg" 2>/dev/null | tr -d '\r' | \
        grep "granted=true" | \
        sed -E 's/^[[:space:]]*([a-zA-Z0-9._]+): granted=true.*/\1/' | \
        grep '^android\.permission\.' | sort -u
    )

    if (( ${#GRANTED_PERMS[@]} > 0 )); then
        printf "%s\n" "${GRANTED_PERMS[@]}" > "${PERMS_DIR}/${pkg}.permissions"
        for perm in "${GRANTED_PERMS[@]}"; do
            echo "${pkg} ${perm}" >> "${PERMS_DIR}/granted_permissions.txt"
        done
        log_info "  Exported ${#GRANTED_PERMS[@]} granted Android permission(s) for ${pkg}."
    fi
done

log_ok "Saved ${#PLAYSTORE_PKGS[@]} Play Store app(s) to manifest and cloned ${CLONED_SIDELOAD_PKGS}/${#SIDELOADED_PKGS[@]} sideloaded app(s)."

# ------------------------------------------------------------------------------
# 6. Pull /sdcard/Download, /sdcard/Pictures & Projectivy .plbackup files
# ------------------------------------------------------------------------------
log_step "Step 6: Pulling Projectivy .plbackup files, /sdcard/Download & /sdcard/Pictures"

PROJ_BACKUPS_DIR="${BACKUP_ROOT}/projectivy_backups"
PROJ_WALLPAPERS_DIR="${BACKUP_ROOT}/projectivy_wallpapers"
mkdir -p "$PROJ_BACKUPS_DIR" "$PROJ_WALLPAPERS_DIR"

REMOTE_PROJ_BACKUPS="/sdcard/Android/data/com.spocky.projengmenu/files/backups"
REMOTE_PROJ_WALLPAPERS="/sdcard/Android/data/com.spocky.projengmenu/files/wallpapers"

if "${ADB_CMD[@]}" shell "[ -d '${REMOTE_PROJ_BACKUPS}' ]" 2>/dev/null; then
    log_info "Pulling Projectivy layout & color backups from ${REMOTE_PROJ_BACKUPS} ..."
    "${ADB_CMD[@]}" pull -a "${REMOTE_PROJ_BACKUPS}/." "$PROJ_BACKUPS_DIR/" || true
    log_ok "Saved Projectivy .plbackup file(s) to \"${PROJ_BACKUPS_DIR}\""
fi

if "${ADB_CMD[@]}" shell "[ -d '${REMOTE_PROJ_WALLPAPERS}' ]" 2>/dev/null; then
    log_info "Pulling Projectivy wallpapers from ${REMOTE_PROJ_WALLPAPERS} ..."
    "${ADB_CMD[@]}" pull -a "${REMOTE_PROJ_WALLPAPERS}/." "$PROJ_WALLPAPERS_DIR/" || true
fi

for remote_folder in "Download" "Pictures"; do
    REMOTE_PATH="/sdcard/${remote_folder}"
    LOCAL_DEST="${SDCARD_DIR}/${remote_folder}"
    mkdir -p "$LOCAL_DEST"

    if "${ADB_CMD[@]}" shell "[ -d '${REMOTE_PATH}' ]" 2>/dev/null; then
        log_info "Pulling ${REMOTE_PATH} -> \"${LOCAL_DEST}\" ..."
        if "${ADB_CMD[@]}" pull -a "${REMOTE_PATH}/." "$LOCAL_DEST/"; then
            log_ok "Finished pulling ${REMOTE_PATH}"
        else
            log_warn "Encountered minor warning(s) while pulling ${REMOTE_PATH}"
        fi
    else
        log_warn "Remote directory ${REMOTE_PATH} does not exist on device."
    fi
done

# ------------------------------------------------------------------------------
# 7. Dump System, Secure, and Global Settings
# ------------------------------------------------------------------------------
log_step "Step 7: Dumping system, secure, and global settings"

for namespace in system secure global; do
    OUT_FILE="${SETTINGS_DIR}/${namespace}.txt"
    log_info "Dumping '${namespace}' settings..."
    if "${ADB_CMD[@]}" shell settings list "$namespace" 2>/dev/null | tr -d '\r' | sort > "$OUT_FILE"; then
        LINE_CNT=$(wc -l < "$OUT_FILE")
        log_ok "Saved ${LINE_CNT} '${namespace}' setting entries to ${OUT_FILE}"
    else
        log_warn "Failed to dump '${namespace}' settings."
    fi
done

# ------------------------------------------------------------------------------
# 8. Save Disabled Packages List
# ------------------------------------------------------------------------------
log_step "Step 8: Saving disabled packages list"

DISABLED_FILE="${PACKAGES_DIR}/disabled_packages.txt"
"${ADB_CMD[@]}" shell pm list packages -d 2>/dev/null | tr -d '\r' | sed 's/^package://' | grep -v '^[[:space:]]*$' | sort > "$DISABLED_FILE"
DISABLED_COUNT=$(wc -l < "$DISABLED_FILE")
log_ok "Saved ${DISABLED_COUNT} disabled package(s) to \"${DISABLED_FILE}\""

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}${GREEN}============================================================${NC}"
echo -e "${BOLD}${GREEN}   BACKUP COMPLETE!                                         ${NC}"
echo -e "${BOLD}${GREEN}============================================================${NC}"
echo -e "Backup Location   : ${BOLD}${BACKUP_ROOT}${NC}"
echo -e "Play Store Apps   : ${BOLD}${#PLAYSTORE_PKGS[@]} (saved to manifest)${NC}"
echo -e "Sideloaded Apps   : ${BOLD}${CLONED_SIDELOAD_PKGS} / ${#SIDELOADED_PKGS[@]} (APKs cloned)${NC}"
echo -e "Disabled Packages : ${BOLD}${DISABLED_COUNT}${NC}"
echo -e "Media & Backups   : ${BOLD}${SDCARD_DIR}/Download${NC} & ${BOLD}${SDCARD_DIR}/Pictures${NC}"
echo -e "Settings Dumped   : ${BOLD}system.txt, secure.txt, global.txt${NC}"
echo -e "${BOLD}${GREEN}============================================================${NC}"
