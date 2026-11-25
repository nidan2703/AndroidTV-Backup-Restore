#!/usr/bin/env python3
"""
Android / Google TV Streamer Backup & Restore Manager for Zorin OS / Linux
Built with Python 3 + GTK 4 + Libadwaita (Adw 1)
"""

import json
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

APP_ID = "io.github.achim.StreamerBackup"
APP_TITLE = "Android TV Streamer Backup"
SCRIPT_DIR = Path(__file__).resolve().parent
GLib.set_prgname(APP_ID)
GLib.set_application_name(APP_TITLE)
DEFAULT_IP = "192.168.4.64:5555"
DEFAULT_PORT = "5555"
DEFAULT_BACKUP_DIR = str(Path.home() / "Android Streamer Backup")
CONFIG_PATH = Path.home() / ".config" / "streamer-backup" / "config.json"

STOCK_LAUNCHER = "com.google.android.apps.tv.launcherx"
SETUP_WRAITH = "com.google.android.tungsten.setupwraith"
PROJECTIVY_PKG = "com.spocky.projengmenu"
PLAYSTORE_INSTALLER = "com.android.vending"

# Settings keys that must never be copied across devices
FILTERED_SETTINGS_KEYS = {
    "android_id",
    "bluetooth_address",
    "wifi_on",
    "device_name",
    "boot_count",
    "bluetooth_name",
    "bluetooth_addr_valid",
    "adb_enabled",
    "adb_wifi_enabled",
    "development_settings_enabled",
    "verifier_verify_adb_installs",
    "network_scoring_provisioned",
    "wifi_saved_state",
}

# Known apps strictly distributed via Google Play Store (for legacy backups that lack package_installers.txt)
KNOWN_PLAYSTORE_PACKAGES = {
    "air.com.vudu.air.DownloaderTablet",
    "com.amazon.amazonvideo.livingroom",
    "com.angel.tv",
    "com.apple.atve.androidtv.appletv",
    "com.cbs.ott",
    "com.disney.disneyplus",
    "com.esaba.downloader",
    "com.espn.score_center",
    "com.fox.foxone",
    "com.google.android.youtube.tv",
    "com.hulu.livingroomplus",
    "com.kanopy.tvapp",
    "com.mixplorer.silver",
    "com.moviesanywhere.goo",
    "com.nbcuni.nbc.androidtv",
    "com.netflix.ninja",
    "com.peacocktv.peacockandroid",
    "com.phlox.tvwebbrowser",
    "com.plexapp.android",
    "com.roku.web.trc",
    "com.sling",
    "com.spectrum.stva.androidtv",
    "com.spocky.projengmenu",
    "com.stremio.one",
    "com.surfshark.vpnclient.android",
    "com.truthsocial.android.tv.tplus",
    "com.tubitv",
    "com.viki.android",
    "com.wbd.stream",
    "com.zdf.android.mediathek",
    "de.eye_interactive.atvl.playstore",
    "de.fcbayern.android",
    "de.swr.avp.ard.tv",
    "dev.vodik7.tvquickactions",
    "org.videolan.vlc",
    "pl.solidexplorer2",
    "tv.pluto.android",
    "tv.wuaki.apptv",
}


def normalize_target(raw_ip: str) -> str:
    raw = raw_ip.strip()
    if not raw:
        return DEFAULT_IP
    if ":" not in raw:
        return f"{raw}:{DEFAULT_PORT}"
    return raw


class StreamerBackupWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title=APP_TITLE)
        self.set_default_size(780, 780)

        display = Gdk.Display.get_default()
        if display is not None:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            icon_theme.add_search_path(str(SCRIPT_DIR))
        Gtk.Window.set_default_icon_name(APP_ID)
        self.set_icon_name(APP_ID)

        self.config = self.load_config()
        self.worker_thread = None
        self.cancel_requested = False

        self._build_ui()
        self.refresh_backup_summary()

    # --------------------------------------------------------------------------
    # Config persistence
    # --------------------------------------------------------------------------
    def load_config(self) -> dict:
        default_cfg = {
            "source_ip": DEFAULT_IP,
            "target_ip": DEFAULT_IP,
            "backup_dir": DEFAULT_BACKUP_DIR,
        }
        try:
            if CONFIG_PATH.exists():
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                default_cfg.update(data)
        except Exception:
            pass
        return default_cfg

    def save_config(self):
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.config["source_ip"] = self.source_ip_Row.get_text().strip() or DEFAULT_IP
            self.config["target_ip"] = self.target_ip_Row.get_text().strip() or DEFAULT_IP
            self.config["backup_dir"] = self.backup_dir_row.get_text().strip() or DEFAULT_BACKUP_DIR
            CONFIG_PATH.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # UI Construction
    # --------------------------------------------------------------------------
    def _build_ui(self):
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.toast_overlay.set_child(main_box)

        # Header Bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Status badge in header
        self.adb_status_label = Gtk.Label(label="ADB Ready" if shutil.which("adb") else "ADB Missing!")
        self.adb_status_label.add_css_class("caption")
        header.pack_start(self.adb_status_label)

        open_folder_btn = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text="Open Backup Folder")
        open_folder_btn.connect("clicked", self.on_open_backup_folder)
        header.pack_end(open_folder_btn)

        # Scrollable content area
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        main_box.append(scrolled)

        clamp = Adw.Clamp(maximum_size=720, tightening_threshold=560)
        scrolled.set_child(clamp)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(16)
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)
        clamp.set_child(content_box)

        # 1. Devices & Backup Location Group
        conn_group = Adw.PreferencesGroup(
            title="Devices and Backup Storage",
            description="Enter the IP (or IP:PORT, default port 5555) for your source and target Android/Google TV boxes.",
        )
        content_box.append(conn_group)

        # Source IP row
        self.source_ip_Row = Adw.EntryRow(title="Source TV IP (Backup From)", use_markup=False)
        self.source_ip_Row.set_text(self.config.get("source_ip", DEFAULT_IP))
        test_src_btn = Gtk.Button(label="Test Source", valign=Gtk.Align.CENTER)
        test_src_btn.connect("clicked", lambda _: self.on_test_connection(self.source_ip_Row.get_text(), "Source"))
        self.source_ip_Row.add_suffix(test_src_btn)
        conn_group.add(self.source_ip_Row)

        # Target IP row
        self.target_ip_Row = Adw.EntryRow(title="Target TV IP (Restore To)", use_markup=False)
        self.target_ip_Row.set_text(self.config.get("target_ip", DEFAULT_IP))
        test_dst_btn = Gtk.Button(label="Test Target", valign=Gtk.Align.CENTER)
        test_dst_btn.connect("clicked", lambda _: self.on_test_connection(self.target_ip_Row.get_text(), "Target"))
        self.target_ip_Row.add_suffix(test_dst_btn)
        conn_group.add(self.target_ip_Row)

        # Backup Directory row
        self.backup_dir_row = Adw.EntryRow(title="Backup Folder", use_markup=False)
        self.backup_dir_row.set_text(self.config.get("backup_dir", DEFAULT_BACKUP_DIR))
        self.backup_dir_row.connect("changed", lambda _: self.refresh_backup_summary())
        browse_btn = Gtk.Button(icon_name="folder-symbolic", tooltip_text="Browse Folder", valign=Gtk.Align.CENTER)
        browse_btn.connect("clicked", self.on_browse_folder)
        self.backup_dir_row.add_suffix(browse_btn)
        conn_group.add(self.backup_dir_row)

        # Existing backup metadata banner row
        self.backup_info_row = Adw.ActionRow(
            title="Existing Backup Status",
            subtitle="Checking backup folder...",
            use_markup=False,
        )
        conn_group.add(self.backup_info_row)

        # 2. Backup / Restore Components Group
        components_group = Adw.PreferencesGroup(
            title="Included Components",
            description="Check the specific items you want to Backup or Restore (uncheck others to run one section separately).",
        )
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_all = Gtk.Button(label="Select All", valign=Gtk.Align.CENTER)
        btn_all.add_css_class("flat")
        btn_all.connect("clicked", lambda _: self.set_all_checkboxes(True))
        btn_none = Gtk.Button(label="Select None", valign=Gtk.Align.CENTER)
        btn_none.add_css_class("flat")
        btn_none.connect("clicked", lambda _: self.set_all_checkboxes(False))
        toggle_box.append(btn_all)
        toggle_box.append(btn_none)
        components_group.set_header_suffix(toggle_box)
        content_box.append(components_group)

        self.chk_apks = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        row_apks = Adw.ActionRow(
            title="Play Store Manifest & Sideloaded APK Cloning",
            subtitle="Clones sideloaded APKs via ADB; installs Play Store apps fresh from Google Play on Target TV",
            use_markup=False,
        )
        row_apks.add_prefix(self.chk_apks)
        row_apks.set_activatable_widget(self.chk_apks)
        components_group.add(row_apks)

        self.chk_perms = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        row_perms = Adw.ActionRow(
            title="Granted Runtime Permissions",
            subtitle="Exports granted=true permissions from dumpsys and re-grants them",
            use_markup=False,
        )
        row_perms.add_prefix(self.chk_perms)
        row_perms.set_activatable_widget(self.chk_perms)
        components_group.add(row_perms)

        self.chk_projectivy = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        row_projectivy = Adw.ActionRow(
            title="Projectivy Layout, App Groupings & Button Color Schemes (.plbackup)",
            subtitle="Pulls/pushes /sdcard/Android/data/com.spocky.projengmenu/files/backups & auto-opens Projectivy Import",
            use_markup=False,
        )
        row_projectivy.add_prefix(self.chk_projectivy)
        row_projectivy.set_activatable_widget(self.chk_projectivy)
        components_group.add(row_projectivy)

        self.chk_media = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        row_media = Adw.ActionRow(
            title="Downloads & Wallpapers (/sdcard/Download & /sdcard/Pictures)",
            subtitle="Pulls and pushes /sdcard/Download and /sdcard/Pictures folders",
            use_markup=False,
        )
        row_media.add_prefix(self.chk_media)
        row_media.set_activatable_widget(self.chk_media)
        components_group.add(row_media)

        self.chk_settings = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        row_settings = Adw.ActionRow(
            title="System, Secure & Global Settings",
            subtitle="Filters out android_id, bluetooth_address, wifi_on, device_name, boot_count",
            use_markup=False,
        )
        row_settings.add_prefix(self.chk_settings)
        row_settings.set_activatable_widget(self.chk_settings)
        components_group.add(row_settings)

        self.chk_debloat = Gtk.CheckButton(active=True, valign=Gtk.Align.CENTER)
        row_debloat = Adw.ActionRow(
            title="Disabled Bloatware, Stock Launcher & Projectivy HOME Intent",
            subtitle=f"Disables {STOCK_LAUNCHER} & disabled packages, then triggers HOME intent",
            use_markup=False,
        )
        row_debloat.add_prefix(self.chk_debloat)
        row_debloat.set_activatable_widget(self.chk_debloat)
        components_group.add(row_debloat)

        # 3. Action Buttons Row
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        action_box.set_halign(Gtk.Align.CENTER)
        content_box.append(action_box)

        self.btn_backup = Gtk.Button(label="Backup from Source TV")
        self.btn_backup.add_css_class("suggested-action")
        self.btn_backup.add_css_class("pill")
        self.btn_backup.connect("clicked", self.on_start_backup)
        action_box.append(self.btn_backup)

        self.btn_restore = Gtk.Button(label="Restore to Target TV")
        self.btn_restore.add_css_class("destructive-action")
        self.btn_restore.add_css_class("pill")
        self.btn_restore.connect("clicked", self.on_confirm_restore)
        action_box.append(self.btn_restore)

        self.btn_cancel = Gtk.Button(label="Stop")
        self.btn_cancel.add_css_class("pill")
        self.btn_cancel.set_sensitive(False)
        self.btn_cancel.connect("clicked", self.on_cancel_task)
        action_box.append(self.btn_cancel)

        # 4. Progress & Live Console Output
        progress_group = Adw.PreferencesGroup(title="Operation Progress and Live ADB Log")
        content_box.append(progress_group)

        prog_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        progress_group.add(prog_box)

        self.progress_bar = Gtk.ProgressBar(show_text=True)
        self.progress_bar.set_text("Idle")
        prog_box.append(self.progress_bar)

        # Log view frame
        log_frame = Gtk.Frame()
        prog_box.append(log_frame)

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_min_content_height(210)
        log_scroll.set_vexpand(True)
        log_frame.set_child(log_scroll)

        self.log_view = Gtk.TextView(
            editable=False,
            cursor_visible=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
        )
        self.log_view.set_top_margin(8)
        self.log_view.set_bottom_margin(8)
        self.log_view.set_left_margin(10)
        self.log_view.set_right_margin(10)
        log_scroll.set_child(self.log_view)
        self.log_buffer = self.log_view.get_buffer()

        # Log utility buttons
        log_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        log_btn_box.set_halign(Gtk.Align.END)
        prog_box.append(log_btn_box)

        clear_btn = Gtk.Button(label="Clear Log")
        clear_btn.connect("clicked", lambda _: self.log_buffer.set_text(""))
        log_btn_box.append(clear_btn)

        copy_btn = Gtk.Button(label="Copy Log")
        copy_btn.connect("clicked", self.on_copy_log)
        log_btn_box.append(copy_btn)

    # --------------------------------------------------------------------------
    # UI Helpers
    # --------------------------------------------------------------------------
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"

        def _append():
            end_iter = self.log_buffer.get_end_iter()
            self.log_buffer.insert(end_iter, line)
            mark = self.log_buffer.create_mark(None, self.log_buffer.get_end_iter(), False)
            self.log_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
            return False

        GLib.idle_add(_append)

    def set_progress(self, fraction: float, text: str):
        def _update():
            self.progress_bar.set_fraction(max(0.0, min(1.0, fraction)))
            self.progress_bar.set_text(text)
            return False

        GLib.idle_add(_update)

    def set_all_checkboxes(self, active: bool):
        for chk in (
            self.chk_apks,
            self.chk_perms,
            self.chk_projectivy,
            self.chk_media,
            self.chk_settings,
            self.chk_debloat,
        ):
            chk.set_active(active)

    def set_busy(self, busy: bool):
        def _update():
            self.btn_backup.set_sensitive(not busy)
            self.btn_restore.set_sensitive(not busy)
            self.btn_cancel.set_sensitive(busy)
            self.source_ip_Row.set_sensitive(not busy)
            self.target_ip_Row.set_sensitive(not busy)
            self.backup_dir_row.set_sensitive(not busy)
            if not busy:
                self.refresh_backup_summary()
            return False

        GLib.idle_add(_update)

    def show_toast(self, title: str):
        GLib.idle_add(lambda: self.toast_overlay.add_toast(Adw.Toast.new(title)) or False)

    @staticmethod
    def _count_nonempty_lines(p: Path) -> int:
        if not p.exists():
            return 0
        return len([l for l in p.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()])

    def refresh_backup_summary(self):
        bdir = Path(self.backup_dir_row.get_text().strip() or DEFAULT_BACKUP_DIR)
        meta_file = bdir / "backup_metadata.txt"
        apks_dir = bdir / "apks"
        play_file = bdir / "packages" / "playstore_packages.txt"
        side_file = bdir / "packages" / "sideloaded_packages.txt"
        disabled_file = bdir / "packages" / "disabled_packages.txt"
        proj_dir = bdir / "projectivy_backups"

        if not bdir.exists():
            self.backup_info_row.set_subtitle("Folder does not exist yet (will be created on first backup).")
            return

        apk_count = len([p for p in apks_dir.iterdir() if p.is_dir()]) if apks_dir.exists() else 0
        play_count = self._count_nonempty_lines(play_file)
        side_count = self._count_nonempty_lines(side_file)
        dis_count = self._count_nonempty_lines(disabled_file)
        pl_count = len(list(proj_dir.glob("*.plbackup"))) if proj_dir.exists() else 0

        app_summary = (
            f"{play_count} Play Store + {side_count} Sideloaded"
            if (play_count > 0 or side_count > 0)
            else f"{apk_count} Apps"
        )

        if meta_file.exists():
            meta_lines = [l.strip() for l in meta_file.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
            summary = " | ".join(meta_lines)
            self.backup_info_row.set_subtitle(
                f"{summary} | {app_summary} | {pl_count} Projectivy .plbackup(s) | {dis_count} Disabled"
            )
        elif apk_count > 0 or play_count > 0 or pl_count > 0:
            self.backup_info_row.set_subtitle(
                f"Found {app_summary}, {pl_count} Projectivy .plbackup(s), {dis_count} disabled package(s)."
            )
        else:
            self.backup_info_row.set_subtitle("Folder exists, no backup found yet.")

    def ask_playstore_dialog_sync(self, pkg: str, idx: int, total: int) -> str:
        """
        Shows a blocking modal Adw.MessageDialog from a worker thread and returns:
        'next', 'reopen', or 'skip_all'
        """
        event = threading.Event()
        result_holder = {"choice": "next"}

        def _present():
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=f"Install from Google Play on TV ({idx}/{total})",
                body=(
                    f"Package: {pkg}\n\n"
                    f"The Google Play Store page for this app is now open on your TV screen.\n"
                    f"1. Press 'Install' on your TV remote.\n"
                    f"2. Click 'Next App' below (you don't need to wait for the download to complete once it queues)."
                ),
            )
            dialog.add_response("skip_all", "Skip Remaining")
            dialog.add_response("reopen", "Re-open on TV")
            dialog.add_response("next", "Next App")
            dialog.set_response_appearance("next", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("next")
            dialog.set_close_response("next")

            def _on_resp(_dlg, resp):
                result_holder["choice"] = resp if resp in ("next", "reopen", "skip_all") else "next"
                event.set()

            dialog.connect("response", _on_resp)
            dialog.present()
            return False

        GLib.idle_add(_present)
        event.wait()
        return result_holder["choice"]

    # --------------------------------------------------------------------------
    # Button Callbacks
    # --------------------------------------------------------------------------
    def on_open_backup_folder(self, _btn):
        bdir = Path(self.backup_dir_row.get_text().strip() or DEFAULT_BACKUP_DIR)
        bdir.mkdir(parents=True, exist_ok=True)
        Gio.AppInfo.launch_default_for_uri(bdir.as_uri(), None)

    def on_browse_folder(self, _btn):
        dialog = Gtk.FileDialog(title="Select Backup Folder")
        initial = Path(self.backup_dir_row.get_text().strip() or DEFAULT_BACKUP_DIR)
        if initial.exists():
            dialog.set_initial_folder(Gio.File.new_for_path(str(initial)))

        def on_selected(dlg, res):
            try:
                folder = dlg.select_folder_finish(res)
                if folder:
                    self.backup_dir_row.set_text(folder.get_path())
                    self.save_config()
            except Exception:
                pass

        dialog.select_folder(self, None, on_selected)

    def on_copy_log(self, _btn):
        start, end = self.log_buffer.get_bounds()
        text = self.log_buffer.get_text(start, end, False)
        clipboard = self.get_clipboard()
        clipboard.set(text)
        self.show_toast("Log copied to clipboard")

    def on_cancel_task(self, _btn):
        self.cancel_requested = True
        self.log("Cancellation requested by user... waiting for current ADB command to finish.")
        self.show_toast("Stopping after current command...")

    def on_test_connection(self, raw_ip: str, label: str):
        self.save_config()
        target = normalize_target(raw_ip)

        def _worker():
            self.set_busy(True)
            self.set_progress(0.1, f"Testing connection to {label} ({target})...")
            ok = self.connect_and_authorize(target)
            if ok:
                model = self.adb_out(target, ["shell", "getprop", "ro.product.model"]).strip() or "Android TV"
                ver = self.adb_out(target, ["shell", "getprop", "ro.build.version.release"]).strip() or "?"
                msg = f"{label} Connected: {model} (Android {ver})"
                self.log(f"[OK] {msg}")
                self.set_progress(1.0, msg)
                self.show_toast(msg)
            else:
                self.set_progress(0.0, f"{label} connection failed")
                self.show_toast(f"Failed to connect to {target}")
            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    def on_start_backup(self, _btn):
        self.save_config()
        target = normalize_target(self.source_ip_Row.get_text())
        bdir = Path(self.backup_dir_row.get_text().strip() or DEFAULT_BACKUP_DIR)
        self.cancel_requested = False

        threading.Thread(target=self.run_backup_workflow, args=(target, bdir), daemon=True).start()

    def on_confirm_restore(self, _btn):
        self.save_config()
        target = normalize_target(self.target_ip_Row.get_text())
        bdir = Path(self.backup_dir_row.get_text().strip() or DEFAULT_BACKUP_DIR)

        if not bdir.exists():
            self.show_toast("Backup directory does not exist!")
            self.log(f"[ERROR] Backup directory not found: {bdir}")
            return

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"Restore to {target}?",
            body=(
                f"- Sideloaded apps will be cloned directly via ADB.\n"
                f"- Play Store apps missing on {target} will open in Google Play on your TV for fresh hardware-matched installation.\n"
                f"- Runtime permissions, safe settings, debloat, and Projectivy layout will be applied.\n\n"
                f"Backup Source Folder:\n{bdir}"
            ),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("restore", "Start Restore")
        dialog.set_response_appearance("restore", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("restore")
        dialog.set_close_response("cancel")

        def _on_response(dlg, response):
            if response == "restore":
                self.cancel_requested = False
                threading.Thread(target=self.run_restore_workflow, args=(target, bdir), daemon=True).start()

        dialog.connect("response", _on_response)
        dialog.present()

    # --------------------------------------------------------------------------
    # Projectivy Backup & Auto-Import Helpers
    # --------------------------------------------------------------------------
    def pull_projectivy_backups(self, target: str, bdir: Path):
        proj_dir = bdir / "projectivy_backups"
        proj_dir.mkdir(parents=True, exist_ok=True)
        remote_backups = f"/sdcard/Android/data/{PROJECTIVY_PKG}/files/backups"
        remote_wallpapers = f"/sdcard/Android/data/{PROJECTIVY_PKG}/files/wallpapers"

        self.log(f"Pulling Projectivy backups from {remote_backups} ...")
        code, out = self.adb(target, ["pull", "-a", f"{remote_backups}/.", str(proj_dir)], timeout=120)
        if code == 0:
            pl_files = sorted(proj_dir.glob("*.plbackup"))
            self.log(f"[OK] Pulled {len(pl_files)} Projectivy .plbackup file(s) to {proj_dir}")
        else:
            self.log(f"[WARN] Could not pull {remote_backups}: {out.strip()}")

        # Also pull any custom Projectivy wallpapers stored in external app data
        wp_dir = bdir / "projectivy_wallpapers"
        wp_dir.mkdir(parents=True, exist_ok=True)
        self.adb(target, ["pull", "-a", f"{remote_wallpapers}/.", str(wp_dir)], timeout=120)

        # Also copy any .plbackup / .pltheme found in /sdcard/Download
        dl_dir = bdir / "sdcard" / "Download"
        if dl_dir.exists():
            for f in dl_dir.glob("*.pl*"):
                shutil.copy2(f, proj_dir / f.name)

    def push_and_import_projectivy_backups(self, target: str, bdir: Path):
        proj_dir = bdir / "projectivy_backups"
        dl_dir = bdir / "sdcard" / "Download"

        # Collect any .plbackup files from projectivy_backups or sdcard/Download
        proj_dir.mkdir(parents=True, exist_ok=True)
        if dl_dir.exists():
            for f in dl_dir.glob("*.pl*"):
                if not (proj_dir / f.name).exists():
                    shutil.copy2(f, proj_dir / f.name)

        pl_files = sorted(proj_dir.glob("*.plbackup"), key=lambda p: p.stat().st_mtime)
        if not pl_files:
            self.log("[WARN] No Projectivy .plbackup files found in backup folder!")
            self.log("Tip: On your Source TV, open Projectivy Settings -> General -> Manage Settings -> Export Settings, then run Backup again.")
            return

        remote_files_dir = f"/sdcard/Android/data/{PROJECTIVY_PKG}/files"
        remote_backups = f"{remote_files_dir}/backups"

        # Ensure Projectivy has been launched at least once so Android creates its /sdcard/Android/data/<pkg>/files dir with the app's UID
        if not self.adb_out(target, ["shell", f"[ -d '{remote_files_dir}' ] && echo yes"]).strip():
            self.log("Launching Projectivy once so Android initializes its external data directory...")
            self.adb(target, ["shell", "am", "start", "-n", f"{PROJECTIVY_PKG}/.ui.home.MainActivity"])
            threading.Event().wait(2.5)

        owner = self.adb_out(target, ["shell", f"stat -c '%U' '{remote_backups}' 2>/dev/null"]).strip()
        if owner == "shell":
            self.log("Cleaning shell-owned backups subfolder so Projectivy retains full read/write access...")
            self.adb(target, ["shell", f"rm -rf '{remote_backups}' '{remote_files_dir}/wallpapers'"])

        newest_pl = pl_files[-1]
        remote_target_file = f"{remote_files_dir}/projectivy-restore.plbackup"
        self.log(f"Pushing newest Projectivy backup ({newest_pl.name}) -> {remote_target_file} ...")
        self.adb(target, ["push", str(newest_pl), remote_target_file], timeout=60)
        self.adb(target, ["push", str(newest_pl), f"/sdcard/Download/{newest_pl.name}"], timeout=60)

        owner_after = self.adb_out(target, ["shell", f"stat -c '%U' '{remote_backups}' 2>/dev/null"]).strip()
        if owner_after and owner_after != "shell":
            self.adb(target, ["push", f"{proj_dir}/.", f"{remote_backups}/"], timeout=120)

        remote_uri = f"file://{remote_target_file}"
        self.log(f"Triggering Projectivy ImportSettingsActivity with: {remote_uri}")

        code, out = self.adb(
            target,
            [
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                remote_uri,
                "-n",
                f"{PROJECTIVY_PKG}/.ui.launcherActivities.ImportSettingsActivity",
            ],
            timeout=20,
        )
        if code == 0 and "Error" not in out:
            self.log("==========================================================")
            self.log(f"[OK] Projectivy Import launched on Target TV with: {newest_pl.name}")
            self.log("ACTION ON TV: Click 'OK' on the Projectivy dialog on your TV screen!")
            self.log("(All app groupings, categories, layout & button color schemes will load immediately.)")
            self.log("==========================================================")
        else:
            self.log(f"[WARN] Could not auto-launch ImportSettingsActivity: {out.strip()}")
            self.log("You can import manually on TV: Projectivy Settings -> Manage Settings -> Import.")

    # --------------------------------------------------------------------------
    # Play Store vs Sideloaded Classification Helpers
    # --------------------------------------------------------------------------
    def load_package_lists_for_restore(self, bdir: Path) -> tuple[list[str], list[str]]:
        packages_dir = bdir / "packages"
        apks_dir = bdir / "apks"
        play_file = packages_dir / "playstore_packages.txt"
        side_file = packages_dir / "sideloaded_packages.txt"
        inst_file = packages_dir / "package_installers.txt"

        play_set = set()
        side_set = set()

        if play_file.exists() or side_file.exists():
            if play_file.exists():
                for line in play_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    p = line.strip()
                    if p:
                        play_set.add(p)
            if side_file.exists():
                for line in side_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    p = line.strip()
                    if p and p not in play_set:
                        side_set.add(p)
        elif inst_file.exists():
            for line in inst_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    pkg, inst = parts[0].strip(), parts[1].strip()
                    if inst.lower() == PLAYSTORE_INSTALLER:
                        play_set.add(pkg)
                    else:
                        side_set.add(pkg)
        else:
            self.log("[INFO] Legacy backup detected (no playstore_packages.txt found). Classifying Play Store vs. Sideloaded apps...")
            all_candidates = set()
            tp_file = packages_dir / "third_party_packages.txt"
            if tp_file.exists():
                for line in tp_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.strip():
                        all_candidates.add(line.strip())
            if apks_dir.exists():
                for d in apks_dir.iterdir():
                    if d.is_dir():
                        all_candidates.add(d.name)

            for pkg in all_candidates:
                pkg_dir = apks_dir / pkg
                apk_cnt = len(list(pkg_dir.glob("*.apk"))) if pkg_dir.exists() else 0
                if pkg in KNOWN_PLAYSTORE_PACKAGES or apk_cnt > 1:
                    play_set.add(pkg)
                else:
                    side_set.add(pkg)

            try:
                packages_dir.mkdir(parents=True, exist_ok=True)
                play_file.write_text("\n".join(sorted(play_set)) + ("\n" if play_set else ""), encoding="utf-8")
                side_file.write_text("\n".join(sorted(side_set)) + ("\n" if side_set else ""), encoding="utf-8")
            except Exception:
                pass

        return sorted(play_set), sorted(side_set)

    def open_playstore_for_package(self, target: str, pkg: str):
        code, out = self.adb(
            target,
            [
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                f"market://details?id={pkg}",
                "-p",
                PLAYSTORE_INSTALLER,
            ],
            timeout=15,
        )
        if code != 0 or "Error" in out:
            self.adb(
                target,
                [
                    "shell",
                    "am",
                    "start",
                    "-a",
                    "android.intent.action.VIEW",
                    "-d",
                    f"https://play.google.com/store/apps/details?id={pkg}",
                ],
                timeout=15,
            )

    # --------------------------------------------------------------------------
    # ADB Helpers
    # --------------------------------------------------------------------------
    def run_cmd(self, args: list[str], timeout: int = 300) -> tuple[int, str]:
        try:
            proc = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )
            return proc.returncode, (proc.stdout or "").replace("\r", "")
        except subprocess.TimeoutExpired:
            return 124, "Command timed out"
        except Exception as e:
            return 1, str(e)

    def adb(self, target: str, subargs: list[str], timeout: int = 300) -> tuple[int, str]:
        return self.run_cmd(["adb", "-s", target] + subargs, timeout=timeout)

    def adb_out(self, target: str, subargs: list[str], timeout: int = 60) -> str:
        _, out = self.adb(target, subargs, timeout=timeout)
        return out

    def get_installed_packages_on_device(self, target: str) -> set[str]:
        raw = self.adb_out(target, ["shell", "pm", "list", "packages"])
        return {l.replace("package:", "").strip() for l in raw.splitlines() if l.strip()}

    def connect_and_authorize(self, target: str) -> bool:
        if not shutil.which("adb"):
            self.log("[ERROR] 'adb' is not installed! Run: sudo apt update && sudo apt install -y adb")
            return False

        self.run_cmd(["adb", "start-server"], timeout=15)
        self.log(f"Connecting to {target}...")
        self.run_cmd(["adb", "connect", target], timeout=15)

        max_attempts = 25
        for attempt in range(1, max_attempts + 1):
            if self.cancel_requested:
                return False

            code, state_out = self.adb(target, ["get-state"], timeout=10)
            state = state_out.strip()

            if state == "device":
                self.log(f"[OK] Authorized ADB session established with {target}")
                return True
            elif "unauthorized" in state.lower():
                if attempt == 1:
                    self.log("==========================================================")
                    self.log("ACTION REQUIRED ON TV: Check 'Always allow from this computer'")
                    self.log("and click 'Allow' on the Android/Google TV screen!")
                    self.log("==========================================================")
                    self.show_toast("Please accept the RSA authorization prompt on your TV!")
                self.log(f"Waiting for RSA authorization on TV screen... ({attempt}/{max_attempts})")
                self.set_progress(0.05, f"Waiting for TV RSA prompt ({attempt}/{max_attempts})...")
                threading.Event().wait(3.0)
            else:
                self.run_cmd(["adb", "disconnect", target], timeout=10)
                _, conn_out = self.run_cmd(["adb", "connect", target], timeout=10)
                self.log(f"Connection attempt {attempt}/{max_attempts}: {conn_out.strip()}")
                threading.Event().wait(2.0)

        self.log(f"[ERROR] Failed to connect/authorize with {target}. Check IP & Wireless/USB Debugging.")
        return False

    # --------------------------------------------------------------------------
    # BACKUP WORKFLOW
    # --------------------------------------------------------------------------
    def run_backup_workflow(self, target: str, bdir: Path):
        self.set_busy(True)
        self.log("==========================================================")
        self.log(f"STARTING BACKUP FROM {target}")
        self.log(f"Destination: {bdir}")
        self.log("==========================================================")

        if not self.connect_and_authorize(target):
            self.set_progress(0.0, "Backup aborted: Connection failed")
            self.set_busy(False)
            return

        apks_dir = bdir / "apks"
        perms_dir = bdir / "permissions"
        sdcard_dir = bdir / "sdcard"
        settings_dir = bdir / "settings"
        packages_dir = bdir / "packages"

        for d in (apks_dir, perms_dir, sdcard_dir, settings_dir, packages_dir):
            d.mkdir(parents=True, exist_ok=True)

        model = self.adb_out(target, ["shell", "getprop", "ro.product.model"]).strip() or "Unknown"
        ver = self.adb_out(target, ["shell", "getprop", "ro.build.version.release"]).strip() or "Unknown"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        (bdir / "backup_metadata.txt").write_text(
            f"Timestamp: {ts}\nSource: {target}\nModel: {model} (Android {ver})\n",
            encoding="utf-8",
        )
        self.log(f"Detected Source Device: {model} (Android {ver})")

        # 1. Classify 3rd-party packages (Play Store Manifest vs. Sideloaded APKs) & Permissions
        if self.chk_apks.get_active() or self.chk_perms.get_active():
            self.set_progress(0.15, "Listing 3rd-party packages & installer origins...")
            raw_pkgs = self.adb_out(target, ["shell", "pm", "list", "packages", "-3", "-i"])
            pkgs = []
            playstore_pkgs = []
            sideloaded_pkgs = []
            installer_lines = []

            pkg_inst_re = re.compile(r"^package:(\S+)\s+installer=(\S+)")
            for line in raw_pkgs.splitlines():
                t = line.strip()
                if not t:
                    continue
                pkg_name = ""
                installer = "null"
                m = pkg_inst_re.match(t)
                if m:
                    pkg_name, installer = m.group(1).strip(), m.group(2).strip()
                elif t.startswith("package:"):
                    tokens = t[len("package:"):].strip().split()
                    if tokens:
                        pkg_name = tokens[0]
                    for tok in tokens[1:]:
                        if tok.startswith("installer="):
                            installer = tok[len("installer="):].strip()
                if pkg_name:
                    pkgs.append(pkg_name)
                    installer_lines.append(f"{pkg_name} {installer}")
                    if installer.lower() == PLAYSTORE_INSTALLER:
                        playstore_pkgs.append(pkg_name)
                    else:
                        sideloaded_pkgs.append(pkg_name)

            pkgs.sort()
            playstore_pkgs.sort()
            sideloaded_pkgs.sort()
            installer_lines.sort()

            (packages_dir / "third_party_packages.txt").write_text(
                "\n".join(pkgs) + ("\n" if pkgs else ""), encoding="utf-8"
            )
            (packages_dir / "playstore_packages.txt").write_text(
                "\n".join(playstore_pkgs) + ("\n" if playstore_pkgs else ""), encoding="utf-8"
            )
            (packages_dir / "sideloaded_packages.txt").write_text(
                "\n".join(sideloaded_pkgs) + ("\n" if sideloaded_pkgs else ""), encoding="utf-8"
            )
            (packages_dir / "package_installers.txt").write_text(
                "\n".join(installer_lines) + ("\n" if installer_lines else ""), encoding="utf-8"
            )

            self.log(
                f"Found {len(pkgs)} 3rd-party app(s): {len(playstore_pkgs)} Play Store app(s) (manifest), "
                f"{len(sideloaded_pkgs)} Sideloaded app(s) (APK clone)."
            )

            sideload_set = set(sideloaded_pkgs)
            all_perms_lines = []
            for idx, pkg in enumerate(pkgs, start=1):
                if self.cancel_requested:
                    break
                is_sideloaded = pkg in sideload_set
                frac = 0.15 + (0.45 * (idx / max(1, len(pkgs))))
                self.set_progress(frac, f"[{idx}/{len(pkgs)}] Processing {pkg}...")

                if self.chk_apks.get_active():
                    if is_sideloaded:
                        self.log(f"[{idx}/{len(pkgs)}] Cloning sideloaded app: {pkg}...")
                        pkg_dir = apks_dir / pkg
                        pkg_dir.mkdir(parents=True, exist_ok=True)
                        for old_apk in pkg_dir.glob("*.apk"):
                            old_apk.unlink(missing_ok=True)

                        raw_paths = self.adb_out(target, ["shell", "pm", "path", pkg])
                        apk_paths = [
                            line.replace("package:", "").strip()
                            for line in raw_paths.splitlines()
                            if line.strip().startswith("package:")
                        ]
                        for s_idx, remote_apk in enumerate(apk_paths, start=1):
                            base_name = os.path.basename(remote_apk)
                            local_apk = pkg_dir / base_name
                            if local_apk.exists():
                                local_apk = pkg_dir / f"{s_idx}_{base_name}"
                            code, out = self.adb(target, ["pull", remote_apk, str(local_apk)], timeout=300)
                            if code != 0:
                                self.log(f"  [WARN] Failed pulling {remote_apk}: {out.strip()}")
                        self.log(f"  [OK] Pulled {len(apk_paths)} APK file(s) for sideloaded app {pkg}")
                    else:
                        self.log(f"[{idx}/{len(pkgs)}] Recorded Play Store app in manifest: {pkg}")

                if self.chk_perms.get_active():
                    dump_out = self.adb_out(target, ["shell", "dumpsys", "package", pkg], timeout=60)
                    granted = set()
                    for line in dump_out.splitlines():
                        if "granted=true" in line:
                            m = re.match(r"^\s*(android\.permission\.[a-zA-Z0-9._]+):\s*granted=true", line)
                            if m:
                                granted.add(m.group(1))
                    if granted:
                        sorted_g = sorted(granted)
                        (perms_dir / f"{pkg}.permissions").write_text("\n".join(sorted_g) + "\n", encoding="utf-8")
                        for perm in sorted_g:
                            all_perms_lines.append(f"{pkg} {perm}")
                        self.log(f"  [OK] Exported {len(sorted_g)} granted runtime permission(s) for {pkg}")

            if self.chk_perms.get_active():
                (perms_dir / "granted_permissions.txt").write_text(
                    "\n".join(all_perms_lines) + ("\n" if all_perms_lines else ""),
                    encoding="utf-8",
                )

        # 2. Pull Projectivy .plbackup files (if checked)
        if not self.cancel_requested and self.chk_projectivy.get_active():
            self.set_progress(0.64, "Pulling Projectivy layout & color backups (.plbackup)...")
            self.pull_projectivy_backups(target, bdir)

        # 3. Pull /sdcard/Download & /sdcard/Pictures (if checked)
        if not self.cancel_requested and self.chk_media.get_active():
            for idx, folder in enumerate(("Download", "Pictures"), start=1):
                self.set_progress(0.68 + idx * 0.06, f"Pulling /sdcard/{folder}...")
                remote_path = f"/sdcard/{folder}/."
                local_dest = sdcard_dir / folder
                local_dest.mkdir(parents=True, exist_ok=True)
                self.log(f"Pulling /sdcard/{folder} -> {local_dest} ...")
                code, out = self.adb(target, ["pull", "-a", remote_path, str(local_dest)], timeout=300)
                if code == 0:
                    self.log(f"[OK] Pulled /sdcard/{folder}")
                else:
                    self.log(f"[WARN] Pull /sdcard/{folder}: {out.strip()}")

        # 4. Dump system / secure / global settings
        if not self.cancel_requested and self.chk_settings.get_active():
            self.set_progress(0.85, "Dumping system, secure, and global settings...")
            for ns in ("system", "secure", "global"):
                out = self.adb_out(target, ["shell", "settings", "list", ns])
                lines = sorted([l for l in out.splitlines() if l.strip()])
                (settings_dir / f"{ns}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
                self.log(f"[OK] Saved {len(lines)} '{ns}' settings")

        # 5. Disabled packages list
        if not self.cancel_requested and self.chk_debloat.get_active():
            self.set_progress(0.95, "Saving disabled packages list...")
            raw_dis = self.adb_out(target, ["shell", "pm", "list", "packages", "-d"])
            dis_pkgs = sorted(
                [line.replace("package:", "").strip() for line in raw_dis.splitlines() if line.strip()]
            )
            (packages_dir / "disabled_packages.txt").write_text("\n".join(dis_pkgs) + "\n", encoding="utf-8")
            self.log(f"[OK] Saved {len(dis_pkgs)} disabled package(s)")

        if self.cancel_requested:
            self.set_progress(0.0, "Backup cancelled")
            self.log("[WARN] Backup cancelled by user.")
        else:
            self.set_progress(1.0, "Backup Complete!")
            self.log("==========================================================")
            self.log("BACKUP COMPLETED SUCCESSFULLY!")
            self.log("==========================================================")
            self.show_toast("Backup Complete!")

        self.set_busy(False)

    # --------------------------------------------------------------------------
    # RESTORE WORKFLOW
    # --------------------------------------------------------------------------
    def run_restore_workflow(self, target: str, bdir: Path):
        self.set_busy(True)
        self.log("==========================================================")
        self.log(f"STARTING RESTORE TO {target}")
        self.log(f"Backup Source: {bdir}")
        self.log("==========================================================")

        if not self.connect_and_authorize(target):
            self.set_progress(0.0, "Restore aborted: Connection failed")
            self.set_busy(False)
            return

        apks_dir = bdir / "apks"
        perms_dir = bdir / "permissions"
        sdcard_dir = bdir / "sdcard"
        settings_dir = bdir / "settings"
        packages_dir = bdir / "packages"

        # 1. Push /sdcard/Download & /sdcard/Pictures FIRST
        if not self.cancel_requested and self.chk_media.get_active():
            for idx, folder in enumerate(("Download", "Pictures"), start=1):
                self.set_progress(0.05 + idx * 0.05, f"Pushing /sdcard/{folder}...")
                local_src = sdcard_dir / folder
                if local_src.exists() and any(local_src.iterdir()):
                    self.adb(target, ["shell", f"mkdir -p /sdcard/{folder}"])
                    self.log(f"Pushing {local_src} -> /sdcard/{folder}/ ...")
                    code, out = self.adb(target, ["push", f"{local_src}/.", f"/sdcard/{folder}/"], timeout=300)
                    if code == 0:
                        self.log(f"[OK] Restored /sdcard/{folder}")
                    else:
                        self.log(f"[WARN] Push /sdcard/{folder}: {out.strip()}")
                else:
                    self.log(f"[INFO] {local_src} is empty or not present; skipping.")

        # 2. Restore Sideloaded APKs via ADB & Install Play Store Apps Fresh from Google Play (Mode A)
        if not self.cancel_requested and self.chk_apks.get_active():
            playstore_pkgs, sideloaded_pkgs = self.load_package_lists_for_restore(bdir)
            self.log(
                f"Manifest Summary: {len(sideloaded_pkgs)} Sideloaded app(s) to clone via ADB, "
                f"{len(playstore_pkgs)} Play Store app(s) to verify/install via Google Play."
            )

            # 2A. Clone Sideloaded Apps via install-multiple -r -g
            sideload_installed = 0
            sideload_attempted = 0
            for idx, pkg_name in enumerate(sideloaded_pkgs, start=1):
                if self.cancel_requested:
                    break
                pkg_dir = apks_dir / pkg_name
                if not pkg_dir.exists():
                    self.log(f"  [WARN] Sideloaded APK folder missing for {pkg_name}, skipping.")
                    continue
                apk_files = sorted([str(f) for f in pkg_dir.glob("*.apk")])
                if not apk_files:
                    continue

                sideload_attempted += 1
                frac = 0.15 + (0.20 * (idx / max(1, len(sideloaded_pkgs))))
                self.set_progress(frac, f"[Sideload {idx}/{len(sideloaded_pkgs)}] Installing {pkg_name}...")
                self.log(f"[Sideload {idx}/{len(sideloaded_pkgs)}] Cloning {pkg_name} ({len(apk_files)} APK(s))...")

                code, out = self.adb(target, ["install-multiple", "-r", "-g"] + apk_files, timeout=300)
                if code == 0:
                    sideload_installed += 1
                    self.log(f"  [OK] Cloned sideloaded app: {pkg_name}")
                else:
                    self.log(f"  [WARN] Retrying {pkg_name} without -g...")
                    code2, out2 = self.adb(target, ["install-multiple", "-r"] + apk_files, timeout=300)
                    if code2 == 0:
                        sideload_installed += 1
                        self.log(f"  [OK] Cloned sideloaded app: {pkg_name} (without -g)")
                    else:
                        self.log(f"  [ERROR] Failed to clone sideloaded app {pkg_name}: {out2.strip()}")
            self.log(f"[OK] Sideloaded APK cloning finished: {sideload_installed}/{sideload_attempted} succeeded.")

            # 2B. Play Store Manifest Queue (Mode A: Fresh Install from Target TV's Google Play Store)
            if not self.cancel_requested and playstore_pkgs:
                currently_installed = self.get_installed_packages_on_device(target)
                missing_play_pkgs = []
                already_installed_play = 0

                if PROJECTIVY_PKG in playstore_pkgs and PROJECTIVY_PKG not in currently_installed:
                    missing_play_pkgs.append(PROJECTIVY_PKG)

                for pkg in playstore_pkgs:
                    if pkg in currently_installed:
                        already_installed_play += 1
                    elif pkg != PROJECTIVY_PKG:
                        missing_play_pkgs.append(pkg)

                self.log("==========================================================")
                self.log(
                    f"PLAY STORE MANIFEST CHECK: {already_installed_play} already installed, "
                    f"{len(missing_play_pkgs)} to install from Google Play."
                )
                self.log("==========================================================")

                if missing_play_pkgs:
                    play_installed_count = 0
                    i = 0
                    while i < len(missing_play_pkgs):
                        if self.cancel_requested:
                            break
                        pkg = missing_play_pkgs[i]
                        currently_installed = self.get_installed_packages_on_device(target)
                        if pkg in currently_installed:
                            play_installed_count += 1
                            self.log(f"[Play Store {i+1}/{len(missing_play_pkgs)}] {pkg} is now installed!")
                            i += 1
                            continue

                        frac = 0.35 + (0.25 * ((i + 1) / max(1, len(missing_play_pkgs))))
                        self.set_progress(
                            frac, f"[Play Store {i+1}/{len(missing_play_pkgs)}] Opening {pkg} on TV Play Store..."
                        )
                        self.log(
                            f"[Play Store {i+1}/{len(missing_play_pkgs)}] Opening Google Play Store on TV for: {pkg}"
                        )
                        self.open_playstore_for_package(target, pkg)

                        choice = self.ask_playstore_dialog_sync(pkg, i + 1, len(missing_play_pkgs))
                        if choice == "reopen":
                            continue
                        elif choice == "skip_all":
                            self.log("[INFO] Skipping remaining Play Store manifest apps at user request.")
                            break

                        currently_installed = self.get_installed_packages_on_device(target)
                        if pkg in currently_installed:
                            play_installed_count += 1
                            self.log(f"  [OK] Confirmed installed: {pkg}")
                        else:
                            self.log(f"  [INFO] Queued/proceeding to next app: {pkg}")
                        i += 1

                    self.log(
                        f"[OK] Play Store manifest queue finished ({play_installed_count} confirmed installed immediately; "
                        f"background downloads may continue on TV)."
                    )

        # 3. Re-grant runtime permissions
        if not self.cancel_requested and self.chk_perms.get_active():
            self.set_progress(0.65, "Re-granting runtime permissions...")
            perm_file = perms_dir / "granted_permissions.txt"
            granted_cnt = 0
            if perm_file.exists():
                installed_now = self.get_installed_packages_on_device(target)
                for line in perm_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if self.cancel_requested:
                        break
                    parts = line.strip().split()
                    if len(parts) == 2 and parts[0] in installed_now:
                        pkg, perm = parts
                        code, _ = self.adb(target, ["shell", "pm", "grant", pkg, perm], timeout=15)
                        if code == 0:
                            granted_cnt += 1
                self.log(f"[OK] Re-applied {granted_cnt} runtime permission grant(s).")

        # 4. Apply safe settings
        if not self.cancel_requested and self.chk_settings.get_active():
            self.set_progress(0.75, "Applying safe system, secure, and global settings...")
            key_pattern = re.compile(r"^[a-zA-Z0-9_.:-]+$")
            for ns in ("system", "secure", "global"):
                sfile = settings_dir / f"{ns}.txt"
                if not sfile.exists():
                    continue
                applied = 0
                filtered = 0
                for line in sfile.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if self.cancel_requested:
                        break
                    if "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if not key or not key_pattern.match(key) or not val or val == "null":
                        continue
                    if key in FILTERED_SETTINGS_KEYS:
                        self.log(f"  [FILTERED] Skipping {ns}:{key}")
                        filtered += 1
                        continue
                    code, _ = self.adb(
                        target,
                        ["shell", "settings", "put", ns, key, f'"{val}"'],
                        timeout=10,
                    )
                    if code == 0:
                        applied += 1
                self.log(f"[OK] Namespace '{ns}': applied {applied} setting(s), filtered {filtered} key(s).")

        # 5. Re-disable stock launcher & bloatware, then trigger HOME intent for Projectivy
        if not self.cancel_requested and self.chk_debloat.get_active():
            self.set_progress(0.90, "Disabling stock launcher & bloatware, launching Projectivy...")
            to_disable = {STOCK_LAUNCHER}
            dis_file = packages_dir / "disabled_packages.txt"
            if dis_file.exists():
                for line in dis_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.strip():
                        to_disable.add(line.strip())

            installed_set = self.get_installed_packages_on_device(target)

            if PROJECTIVY_PKG in installed_set:
                self.adb(
                    target,
                    ["shell", "cmd", "package", "set-home-activity", f"{PROJECTIVY_PKG}/.ui.home.MainActivity"],
                )

            disabled_cnt = 0
            for pkg in sorted(to_disable):
                if pkg not in installed_set:
                    continue
                if pkg in (STOCK_LAUNCHER, "com.google.android.tvlauncher") and PROJECTIVY_PKG not in installed_set:
                    self.log(
                        f"  [WARN] Projectivy is not installed yet; keeping stock launcher enabled ({pkg}) so TV has a home screen."
                    )
                    continue
                code, _ = self.adb(target, ["shell", "pm", "disable-user", "--user", "0", pkg], timeout=20)
                if code == 0:
                    disabled_cnt += 1
                    self.log(f"  [OK] Disabled {pkg}")
                else:
                    self.log(f"  [WARN] Could not disable {pkg}")

            if SETUP_WRAITH in installed_set and PROJECTIVY_PKG in installed_set:
                self.adb(target, ["shell", "pm", "disable-user", "--user", "0", SETUP_WRAITH], timeout=20)

            self.log("Triggering HOME intent to launch Projectivy...")
            self.adb(
                target,
                ["shell", "am", "start", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME"],
            )
            self.adb(target, ["shell", "input", "keyevent", "KEYCODE_HOME"])
            self.log(f"[OK] Disabled {disabled_cnt} package(s) and triggered HOME intent.")

        # 6. Push Projectivy .plbackup files & trigger ImportSettingsActivity
        if not self.cancel_requested and self.chk_projectivy.get_active():
            self.set_progress(0.96, "Restoring Projectivy layout, app groupings & button colors...")
            self.push_and_import_projectivy_backups(target, bdir)

        if self.cancel_requested:
            self.set_progress(0.0, "Restore cancelled")
            self.log("[WARN] Restore cancelled by user.")
        else:
            self.set_progress(1.0, "Restore Complete!")
            self.log("==========================================================")
            self.log("RESTORE COMPLETED SUCCESSFULLY!")
            self.log("==========================================================")
            self.show_toast("Restore Complete!")

        self.set_busy(False)


class StreamerBackupApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = StreamerBackupWindow(self)
        win.present()


if __name__ == "__main__":
    app = StreamerBackupApp()
    app.run(None)
