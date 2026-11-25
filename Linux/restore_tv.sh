#!/usr/bin/env bash
# ==============================================================================
# Zorin OS Android / Google TV Restore Utility (restore_tv.sh)
# Default Target: 192.168.4.64:5555
# Backup Source:  "${HOME}/Android Streamer Backup"
# ==============================================================================

set -u

DEFAULT_IP="192.168.4.64"
DEFAULT_PORT="5555"
BACKUP_ROOT="${HOME}/Android Streamer Backup"
STOCK_LAUNCHER="com.google.android.apps.tv.launcherx"
PROJECTIVY_PKG="com.spocky.projengmenu"
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
echo -e "${BOLD}   Zorin OS Android / Google TV Streamer Restore Utility    ${NC}"
echo -e "${BOLD}============================================================${NC}"

# ------------------------------------------------------------------------------
# 1. Verify ADB Installation & Backup Directory
# ------------------------------------------------------------------------------
log_step "Step 1: Verifying ADB installation & backup directory"
if ! command -v adb >/dev/null 2>&1; then
    log_err "'adb' is not installed or not in PATH."
    echo -e "Install it on Zorin OS with:\n  ${BOLD}sudo apt update && sudo apt install -y adb${NC}"
    exit 1
fi
log_ok "Found $(adb --version | head -n 1)"

if [[ ! -d "$BACKUP_ROOT" ]]; then
    log_err "Backup directory not found: \"${BACKUP_ROOT}\""
    echo "Please run backup_tv.sh first."
    exit 1
fi
log_ok "Found backup directory: \"${BACKUP_ROOT}\""

if [[ -f "${BACKUP_ROOT}/backup_metadata.txt" ]]; then
    echo -e "${CYAN}--- Backup Metadata ---${NC}"
    cat "${BACKUP_ROOT}/backup_metadata.txt"
    echo -e "${CYAN}-----------------------${NC}"
fi

# ------------------------------------------------------------------------------
# 2. Prompt for Target Device IP (or IP:PORT)
# ------------------------------------------------------------------------------
log_step "Step 2: Target Device IP Configuration"

prompt_for_ip() {
    local input_ip="${1:-}"
    while true; do
        if [[ -z "$input_ip" ]]; then
            echo -e "Enter the ${BOLD}TARGET${NC} Android/Google TV IP address (or IP:PORT) to restore to."
            read -r -p "Target Device IP [press Enter for ${DEFAULT_IP}:${DEFAULT_PORT}]: " USER_INPUT
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
log_info "Target Android/Google TV set to: ${BOLD}${TARGET_ADDR}${NC}"

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
    read -r -p "Would you like to enter a different Target IP address and try again? [Y/n]: " RETRY_CHOICE
    if [[ "${RETRY_CHOICE:-Y}" =~ ^[Nn]$ ]]; then
        exit 1
    fi
    prompt_for_ip ""
    log_info "Retrying with Target Android/Google TV: ${BOLD}${TARGET_ADDR}${NC}"
done

ADB_CMD=(adb -s "$TARGET_ADDR")

APKS_DIR="${BACKUP_ROOT}/apks"
PERMS_DIR="${BACKUP_ROOT}/permissions"
SDCARD_DIR="${BACKUP_ROOT}/sdcard"
SETTINGS_DIR="${BACKUP_ROOT}/settings"
PACKAGES_DIR="${BACKUP_ROOT}/packages"

# ------------------------------------------------------------------------------
# 4. Push /sdcard/Download & /sdcard/Pictures First
# ------------------------------------------------------------------------------
log_step "Step 4: Pushing /sdcard/Download & /sdcard/Pictures (Projectivy backups & wallpapers)"

for folder in "Download" "Pictures"; do
    LOCAL_SRC="${SDCARD_DIR}/${folder}"
    REMOTE_DEST="/sdcard/${folder}"

    if [[ -d "$LOCAL_SRC" ]]; then
        "${ADB_CMD[@]}" shell "mkdir -p '${REMOTE_DEST}'" 2>/dev/null || true
        if [[ -n "$(ls -A "$LOCAL_SRC" 2>/dev/null)" ]]; then
            log_info "Pushing \"${LOCAL_SRC}\" -> ${REMOTE_DEST} ..."
            if "${ADB_CMD[@]}" push "${LOCAL_SRC}/." "${REMOTE_DEST}/"; then
                log_ok "Restored ${REMOTE_DEST}"
            else
                log_warn "Some files in ${LOCAL_SRC} could not be pushed."
            fi
        else
            log_info "Local folder \"${LOCAL_SRC}\" is empty; nothing to push."
        fi
    else
        log_warn "Local backup folder \"${LOCAL_SRC}\" not found; skipping."
    fi
done

# ------------------------------------------------------------------------------
# 5. Clone Sideloaded APKs via ADB & Install Play Store Apps Fresh (Mode A)
# ------------------------------------------------------------------------------
log_step "Step 5: Cloning Sideloaded APKs & Installing Play Store Manifest Apps"

PLAYSTORE_FILE="${PACKAGES_DIR}/playstore_packages.txt"
SIDELOADED_FILE="${PACKAGES_DIR}/sideloaded_packages.txt"

PLAYSTORE_PKGS=()
SIDELOADED_PKGS=()

if [[ -f "$PLAYSTORE_FILE" || -f "$SIDELOADED_FILE" ]]; then
    [[ -f "$PLAYSTORE_FILE" ]] && mapfile -t PLAYSTORE_PKGS < <(grep -v '^[[:space:]]*$' "$PLAYSTORE_FILE" | tr -d '\r')
    [[ -f "$SIDELOADED_FILE" ]] && mapfile -t SIDELOADED_PKGS < <(grep -v '^[[:space:]]*$' "$SIDELOADED_FILE" | tr -d '\r')
elif [[ -d "$APKS_DIR" ]]; then
    log_info "Legacy backup detected (no playstore_packages.txt found). Classifying packages..."
    shopt -s nullglob
    for pkg_dir in "${APKS_DIR}"/*/; do
        pkg_name=$(basename "$pkg_dir")
        apk_files=("${pkg_dir}"*.apk)
        if (( ${#apk_files[@]} > 1 )); then
            PLAYSTORE_PKGS+=("$pkg_name")
        else
            SIDELOADED_PKGS+=("$pkg_name")
        fi
    done
    shopt -u nullglob
fi

log_info "Manifest Summary: ${BOLD}${#SIDELOADED_PKGS[@]}${NC} Sideloaded app(s) to clone via ADB, ${BOLD}${#PLAYSTORE_PKGS[@]}${NC} Play Store app(s) to verify/install via Google Play."

# 5A. Clone Sideloaded APKs
INSTALLED_SIDELOAD=0
FAILED_SIDELOAD=0
SIDELOAD_IDX=0

shopt -s nullglob
for pkg_name in "${SIDELOADED_PKGS[@]}"; do
    ((SIDELOAD_IDX++))
    pkg_dir="${APKS_DIR}/${pkg_name}"
    apk_files=("${pkg_dir}"/*.apk)

    if (( ${#apk_files[@]} == 0 )); then
        log_warn "[Sideload ${SIDELOAD_IDX}/${#SIDELOADED_PKGS[@]}] No APK files found for ${pkg_name}, skipping."
        continue
    fi

    echo -e "\n${BOLD}[Sideload ${SIDELOAD_IDX}/${#SIDELOADED_PKGS[@]}] Cloning ${pkg_name} (${#apk_files[@]} APK file(s))...${NC}"
    if "${ADB_CMD[@]}" install-multiple -r -g "${apk_files[@]}"; then
        ((INSTALLED_SIDELOAD++))
        log_ok "Cloned sideloaded app: ${pkg_name}"
    else
        log_warn "install-multiple -r -g failed for ${pkg_name}, retrying without -g..."
        if "${ADB_CMD[@]}" install-multiple -r "${apk_files[@]}"; then
            ((INSTALLED_SIDELOAD++))
            log_ok "Cloned sideloaded app: ${pkg_name} (without -g)"
        else
            ((FAILED_SIDELOAD++))
            log_err "Failed to clone sideloaded app: ${pkg_name}"
        fi
    fi
done
shopt -u nullglob

log_ok "Sideloaded APK cloning complete (${INSTALLED_SIDELOAD} succeeded, ${FAILED_SIDELOAD} failed)."

# 5B. Play Store Manifest Queue (Mode A)
if (( ${#PLAYSTORE_PKGS[@]} > 0 )); then
    INSTALLED_NOW=$("${ADB_CMD[@]}" shell pm list packages 2>/dev/null | tr -d '\r' | sed 's/^package://')
    MISSING_PLAY_PKGS=()
    ALREADY_PLAY_CNT=0

    # Put Projectivy first if missing
    for pkg in "${PLAYSTORE_PKGS[@]}"; do
        if [[ "$pkg" == "$PROJECTIVY_PKG" ]] && ! echo "$INSTALLED_NOW" | grep -qx "$PROJECTIVY_PKG"; then
            MISSING_PLAY_PKGS+=("$PROJECTIVY_PKG")
        fi
    done

    for pkg in "${PLAYSTORE_PKGS[@]}"; do
        if echo "$INSTALLED_NOW" | grep -qx "$pkg"; then
            ((ALREADY_PLAY_CNT++))
        elif [[ "$pkg" != "$PROJECTIVY_PKG" ]]; then
            MISSING_PLAY_PKGS+=("$pkg")
        fi
    done

    log_info "Play Store Manifest Check: ${BOLD}${ALREADY_PLAY_CNT}${NC} already installed, ${BOLD}${#MISSING_PLAY_PKGS[@]}${NC} missing on Target TV."

    if (( ${#MISSING_PLAY_PKGS[@]} > 0 )); then
        echo -e "${YELLOW}------------------------------------------------------------${NC}"
        echo -e "${BOLD}${YELLOW}PLAY STORE FRESH INSTALL QUEUE (${#MISSING_PLAY_PKGS[@]} app(s)):${NC}"
        echo -e "Each missing Play Store app will open directly on your TV's Google Play Store"
        echo -e "so the TV downloads the exact build for its Android SDK & CPU architecture."
        echo -e "${YELLOW}------------------------------------------------------------${NC}"

        P_IDX=0
        while (( P_IDX < ${#MISSING_PLAY_PKGS[@]} )); do
            pkg="${MISSING_PLAY_PKGS[$P_IDX]}"
            DISP_NUM=$((P_IDX + 1))

            INSTALLED_NOW=$("${ADB_CMD[@]}" shell pm list packages 2>/dev/null | tr -d '\r' | sed 's/^package://')
            if echo "$INSTALLED_NOW" | grep -qx "$pkg"; then
                log_ok "[Play Store ${DISP_NUM}/${#MISSING_PLAY_PKGS[@]}] ${pkg} is now installed!"
                ((P_IDX++))
                continue
            fi

            echo -e "\n${BOLD}[Play Store ${DISP_NUM}/${#MISSING_PLAY_PKGS[@]}] Opening Google Play Store on TV for: ${pkg}${NC}"
            "${ADB_CMD[@]}" shell am start -a android.intent.action.VIEW -d "market://details?id=${pkg}" -p "${PLAYSTORE_INSTALLER}" >/dev/null 2>&1 || \
            "${ADB_CMD[@]}" shell am start -a android.intent.action.VIEW -d "https://play.google.com/store/apps/details?id=${pkg}" >/dev/null 2>&1 || true

            read -r -p "Press 'Install' on your TV remote, then press [Enter] for next app ([r] to re-open, [s] to skip remaining): " PLAY_CHOICE
            if [[ "${PLAY_CHOICE:-}" =~ ^[Rr]$ ]]; then
                continue
            elif [[ "${PLAY_CHOICE:-}" =~ ^[Ss]$ ]]; then
                log_info "Skipping remaining Play Store manifest apps."
                break
            fi
            ((P_IDX++))
        done
    fi
fi

# ------------------------------------------------------------------------------
# 6. Re-grant Runtime Permissions
# ------------------------------------------------------------------------------
log_step "Step 6: Re-granting exported runtime permissions"

GRANTED_COUNT=0
PERM_LIST_FILE="${PERMS_DIR}/granted_permissions.txt"

if [[ -f "$PERM_LIST_FILE" ]]; then
    while IFS=' ' read -r pkg perm; do
        [[ -z "$pkg" || -z "$perm" ]] && continue
        if "${ADB_CMD[@]}" shell pm grant "$pkg" "$perm" >/dev/null 2>&1; then
            ((GRANTED_COUNT++))
        fi
    done < "$PERM_LIST_FILE"
    log_ok "Re-applied ${GRANTED_COUNT} runtime permission grant(s)."
else
    log_warn "No permissions export file found at \"${PERM_LIST_FILE}\"."
fi

# ------------------------------------------------------------------------------
# 7. Apply Safe System, Secure, and Global Settings
# ------------------------------------------------------------------------------
log_step "Step 7: Applying safe settings (filtering device-unique & risky keys)"

FILTER_REGEX='^(android_id|bluetooth_address|wifi_on|device_name|boot_count|bluetooth_name|bluetooth_addr_valid|adb_enabled|adb_wifi_enabled|development_settings_enabled|verifier_verify_adb_installs|network_scoring_provisioned|wifi_saved_state)$'

apply_settings_file() {
    local namespace="$1"
    local file="${SETTINGS_DIR}/${namespace}.txt"

    if [[ ! -f "$file" ]]; then
        log_warn "Settings file \"${file}\" not found, skipping '${namespace}'."
        return
    fi

    local applied=0
    local skipped=0

    log_info "Applying safe '${namespace}' settings from ${file}..."
    while IFS='=' read -r key value; do
        [[ -z "$key" ]] && continue
        if [[ ! "$key" =~ ^[a-zA-Z0-9_.:-]+$ ]]; then
            continue
        fi
        if [[ "$value" == "null" || -z "$value" ]]; then
            continue
        fi
        if [[ "$key" =~ $FILTER_REGEX ]]; then
            log_info "  [FILTERED] Skipping ${namespace}:${key}"
            ((skipped++))
            continue
        fi

        if "${ADB_CMD[@]}" shell settings put "$namespace" "$key" "\"$value\"" >/dev/null 2>&1; then
            ((applied++))
        fi
    done < "$file"

    log_ok "Namespace '${namespace}': applied ${applied} setting(s), filtered ${skipped} key(s)."
}

for ns in system secure global; do
    apply_settings_file "$ns"
done

# ------------------------------------------------------------------------------
# 8. Re-disable Stock Launcher (com.google.android.apps.tv.launcherx) & Bloatware
# ------------------------------------------------------------------------------
log_step "Step 8: Re-disabling stock launcher (${STOCK_LAUNCHER}) & disabled bloatware"

DISABLED_FILE="${PACKAGES_DIR}/disabled_packages.txt"
declare -A TO_DISABLE_MAP=()

if [[ -f "$DISABLED_FILE" ]]; then
    while IFS= read -r pkg; do
        pkg=$(echo "$pkg" | tr -d '\r[:space:]')
        [[ -n "$pkg" ]] && TO_DISABLE_MAP["$pkg"]=1
    done < "$DISABLED_FILE"
fi

TO_DISABLE_MAP["$STOCK_LAUNCHER"]=1

INSTALLED_ALL=$("${ADB_CMD[@]}" shell pm list packages 2>/dev/null | tr -d '\r' | sed 's/^package://')
ALT_LAUNCHER_READY=false
if echo "$INSTALLED_ALL" | grep -Eq '^(com\.spocky\.projengmenu|me\.efesser\.flauncher|ca\.dstudio\.atvlauncher)'; then
    ALT_LAUNCHER_READY=true
fi

DISABLED_APPLIED=0
for pkg in "${!TO_DISABLE_MAP[@]}"; do
    if ! echo "$INSTALLED_ALL" | grep -qx "$pkg"; then
        log_info "Package ${pkg} is not present on this device; skipping disable."
        continue
    fi

    if [[ ( "$pkg" == "$STOCK_LAUNCHER" || "$pkg" == "com.google.android.tvlauncher" ) && "$ALT_LAUNCHER_READY" == false ]]; then
        log_warn "Projectivy is not installed yet; keeping stock launcher (${pkg}) enabled so the TV has a home screen."
        continue
    fi

    log_info "Disabling package: ${pkg}"
    if "${ADB_CMD[@]}" shell pm disable-user --user 0 "$pkg" >/dev/null 2>&1; then
        ((DISABLED_APPLIED++))
        log_ok "Disabled ${pkg}"
    else
        log_warn "Could not disable ${pkg} (may require additional privileges or is already disabled)."
    fi
done

if echo "$INSTALLED_ALL" | grep -qx "com.google.android.tungsten.setupwraith" && [[ "$ALT_LAUNCHER_READY" == true ]]; then
    log_info "Disabling Google TV SetupWraith companion (com.google.android.tungsten.setupwraith)..."
    "${ADB_CMD[@]}" shell pm disable-user --user 0 "com.google.android.tungsten.setupwraith" >/dev/null 2>&1 || true
fi

log_ok "Disabled ${DISABLED_APPLIED} bloatware / stock launcher package(s)."

# ------------------------------------------------------------------------------
# 9. Trigger HOME Intent to Launch Projectivy
# ------------------------------------------------------------------------------
log_step "Step 9: Triggering HOME intent to launch Projectivy"

if echo "$INSTALLED_ALL" | grep -qx "$PROJECTIVY_PKG"; then
    log_info "Setting ${PROJECTIVY_PKG} as default HOME activity..."
    "${ADB_CMD[@]}" shell cmd package set-home-activity "${PROJECTIVY_PKG}/.ui.home.MainActivity" >/dev/null 2>&1 || true
fi

log_info "Sending HOME intent and KEYCODE_HOME event..."
"${ADB_CMD[@]}" shell am start -a android.intent.action.MAIN -c android.intent.category.HOME >/dev/null 2>&1 || true
"${ADB_CMD[@]}" shell input keyevent KEYCODE_HOME >/dev/null 2>&1 || true
log_ok "HOME intent triggered! Projectivy should now be active on your TV screen."

# ------------------------------------------------------------------------------
# 10. Push Projectivy .plbackup Files & Auto-Launch ImportSettingsActivity
# ------------------------------------------------------------------------------
log_step "Step 10: Restoring Projectivy layout, app groupings & button color schemes (.plbackup)"

PROJ_BACKUPS_DIR="${BACKUP_ROOT}/projectivy_backups"
REMOTE_PROJ_FILES="/sdcard/Android/data/${PROJECTIVY_PKG}/files"
REMOTE_PROJ_BACKUPS="${REMOTE_PROJ_FILES}/backups"

if [[ -d "$PROJ_BACKUPS_DIR" ]] && compgen -G "${PROJ_BACKUPS_DIR}/*.plbackup" >/dev/null; then
    if ! "${ADB_CMD[@]}" shell "[ -d '${REMOTE_PROJ_FILES}' ]" 2>/dev/null; then
        log_info "Launching Projectivy once so Android initializes its external data directory..."
        "${ADB_CMD[@]}" shell am start -n "${PROJECTIVY_PKG}/.ui.home.MainActivity" >/dev/null 2>&1 || true
        sleep 2
    fi

    if [[ "$("${ADB_CMD[@]}" shell "stat -c '%U' '${REMOTE_PROJ_BACKUPS}' 2>/dev/null" | tr -d '\r')" == "shell" ]]; then
        "${ADB_CMD[@]}" shell "rm -rf '${REMOTE_PROJ_BACKUPS}' '${REMOTE_PROJ_FILES}/wallpapers'" 2>/dev/null || true
    fi

    NEWEST_PL=$(ls -1t "${PROJ_BACKUPS_DIR}"/*.plbackup 2>/dev/null | head -n 1)
    if [[ -n "$NEWEST_PL" ]]; then
        NEWEST_NAME=$(basename "$NEWEST_PL")
        REMOTE_TARGET_FILE="${REMOTE_PROJ_FILES}/projectivy-restore.plbackup"
        log_info "Pushing Projectivy backup (${NEWEST_NAME}) -> ${REMOTE_TARGET_FILE} ..."
        "${ADB_CMD[@]}" push "$NEWEST_PL" "$REMOTE_TARGET_FILE" || true
        "${ADB_CMD[@]}" push "$NEWEST_PL" "/sdcard/Download/${NEWEST_NAME}" >/dev/null 2>&1 || true

        log_info "Launching Projectivy ImportSettingsActivity with: ${REMOTE_TARGET_FILE}"
        "${ADB_CMD[@]}" shell am start \
            -a android.intent.action.VIEW \
            -d "file://${REMOTE_TARGET_FILE}" \
            -n "${PROJECTIVY_PKG}/.ui.launcherActivities.ImportSettingsActivity" >/dev/null 2>&1 || true
        echo -e "${YELLOW}------------------------------------------------------------${NC}"
        echo -e "${BOLD}${YELLOW}ACTION ON YOUR TV:${NC}"
        echo -e "Click ${BOLD}'OK'${NC} on the Projectivy Import prompt on your TV screen"
        echo -e "to apply your app groupings, categories, and button color schemes!"
        echo -e "${YELLOW}------------------------------------------------------------${NC}"
    fi
else
    log_warn "No Projectivy .plbackup files found in \"${PROJ_BACKUPS_DIR}\"."
fi

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}${GREEN}============================================================${NC}"
echo -e "${BOLD}${GREEN}   RESTORE COMPLETE!                                        ${NC}"
echo -e "${BOLD}${GREEN}============================================================${NC}"
echo -e "Target Device     : ${BOLD}${TARGET_ADDR}${NC}"
echo -e "Sideloaded Cloned : ${BOLD}${INSTALLED_SIDELOAD}${NC} (Failed: ${FAILED_SIDELOAD})"
echo -e "Play Store Apps   : ${BOLD}${#PLAYSTORE_PKGS[@]} verified/queued via Google Play${NC}"
echo -e "Permissions       : ${BOLD}${GRANTED_COUNT} runtime grant(s) restored${NC}"
echo -e "Packages Disabled : ${BOLD}${DISABLED_APPLIED}${NC}"
echo -e "${BOLD}${GREEN}============================================================${NC}"
