#!/usr/bin/env python3
"""
Android / Google TV Streamer Backup & Restore Manager (Windows & Cross-Platform Edition)
Built with Python 3 + Tkinter / TTK (Zero external dependencies, Windows 10/11 DPI & Dark Mode aware)
Includes automatic Google ADB (platform-tools) downloader for Windows.
"""

import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "Android TV Streamer Backup & Restore"
DEFAULT_IP = "192.168.4.64:5555"
DEFAULT_PORT = "5555"
DEFAULT_BACKUP_DIR = str(Path.home() / "Android Streamer Backup")
SCRIPT_DIR = Path(__file__).resolve().parent

if platform.system() == "Windows":
    CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "StreamerBackup"
else:
    CONFIG_DIR = Path.home() / ".config" / "streamer-backup"
CONFIG_PATH = CONFIG_DIR / "config.json"

PLATFORM_TOOLS_WIN_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"

STOCK_LAUNCHER = "com.google.android.apps.tv.launcherx"
SETUP_WRAITH = "com.google.android.tungsten.setupwraith"
PROJECTIVY_PKG = "com.spocky.projengmenu"

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


def normalize_target(raw_ip: str) -> str:
    raw = raw_ip.strip()
    if not raw:
        return DEFAULT_IP
    if ":" not in raw:
        return f"{raw}:{DEFAULT_PORT}"
    return raw


def enable_windows_dpi_and_dark_bar(root: tk.Tk):
    if platform.system() != "Windows":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1)
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass


class StreamerBackupWindowsApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("820x800")
        self.root.minsize(740, 700)

        self.bg_main = "#18181b"
        self.bg_card = "#27272a"
        self.fg_text = "#f4f4f5"
        self.fg_muted = "#a1a1aa"
        self.accent_blue = "#2563eb"
        self.accent_red = "#dc2626"
        self.accent_green = "#16a34a"

        self.root.configure(bg=self.bg_main)
        enable_windows_dpi_and_dark_bar(self.root)

        self.config = self.load_config()
        self.cancel_requested = False
        self.adb_path = self.find_adb()

        self._setup_styles()
        self._build_ui()
        self.refresh_adb_badge()
        self.refresh_backup_summary()

    # --------------------------------------------------------------------------
    # Config & ADB Discovery
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
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self.config["source_ip"] = self.var_source_ip.get().strip() or DEFAULT_IP
            self.config["target_ip"] = self.var_target_ip.get().strip() or DEFAULT_IP
            self.config["backup_dir"] = self.var_backup_dir.get().strip() or DEFAULT_BACKUP_DIR
            CONFIG_PATH.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        except Exception:
            pass

    def find_adb(self) -> str | None:
        exe_name = "adb.exe" if platform.system() == "Windows" else "adb"
        candidates = [
            SCRIPT_DIR / "platform-tools" / exe_name,
            CONFIG_DIR / "platform-tools" / exe_name,
        ]
        if platform.system() == "Windows":
            local_app = os.environ.get("LOCALAPPDATA", "")
            if local_app:
                candidates.append(Path(local_app) / "Android" / "Sdk" / "platform-tools" / "adb.exe")
            candidates.append(Path("C:/platform-tools/adb.exe"))

        for c in candidates:
            if c.exists():
                return str(c)

        which_adb = shutil.which("adb")
        if which_adb:
            return which_adb
        return None

    # --------------------------------------------------------------------------
    # Styles & UI Construction
    # --------------------------------------------------------------------------
    def _setup_styles(self):
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("TFrame", background=self.bg_main)
        style.configure("Card.TFrame", background=self.bg_card)
        style.configure("TLabel", background=self.bg_main, foreground=self.fg_text, font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=self.bg_card, foreground=self.fg_text, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.bg_card, foreground=self.fg_muted, font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=self.bg_main, foreground=self.fg_text, font=("Segoe UI", 13, "bold"))
        style.configure("Section.TLabel", background=self.bg_main, foreground=self.fg_text, font=("Segoe UI", 11, "bold"))

        style.configure(
            "Card.TCheckbutton",
            background=self.bg_card,
            foreground=self.fg_text,
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Card.TCheckbutton", background=[("active", self.bg_card)])

        style.configure(
            "TButton",
            background="#3f3f46",
            foreground=self.fg_text,
            font=("Segoe UI", 10),
            padding=(10, 5),
        )
        style.map("TButton", background=[("active", "#52525b"), ("disabled", "#27272a")])

        style.configure(
            "Primary.TButton",
            background=self.accent_blue,
            foreground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            padding=(16, 8),
        )
        style.map("Primary.TButton", background=[("active", "#1d4ed8"), ("disabled", "#3f3f46")])

        style.configure(
            "Danger.TButton",
            background=self.accent_red,
            foreground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            padding=(16, 8),
        )
        style.map("Danger.TButton", background=[("active", "#b91c1c"), ("disabled", "#3f3f46")])

        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=self.bg_card,
            background=self.accent_blue,
            thickness=18,
        )

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        # Header Row
        hdr = ttk.Frame(outer)
        hdr.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(hdr, text=APP_TITLE, style="Header.TLabel").pack(side=tk.LEFT)

        self.btn_open_folder = ttk.Button(hdr, text="Open Backup Folder", command=self.on_open_backup_folder)
        self.btn_open_folder.pack(side=tk.RIGHT, padx=(8, 0))

        self.btn_install_adb = ttk.Button(hdr, text="Download ADB (Windows)", command=self.on_download_adb)
        self.lbl_adb_status = ttk.Label(hdr, text="Checking ADB...")
        self.lbl_adb_status.pack(side=tk.RIGHT, padx=(8, 8))

        # 1. Devices & Backup Storage Card
        ttk.Label(outer, text="Devices and Backup Storage", style="Section.TLabel").pack(anchor=tk.W, pady=(0, 6))
        conn_card = ttk.Frame(outer, style="Card.TFrame", padding=12)
        conn_card.pack(fill=tk.X, pady=(0, 14))
        conn_card.columnconfigure(1, weight=1)

        # Source IP
        ttk.Label(conn_card, text="Source TV IP (Backup From):", style="Card.TLabel").grid(
            row=0, column=0, sticky=tk.W, pady=4, padx=(0, 10)
        )
        self.var_source_ip = tk.StringVar(value=self.config.get("source_ip", DEFAULT_IP))
        self.ent_source_ip = tk.Entry(
            conn_card,
            textvariable=self.var_source_ip,
            bg="#18181b",
            fg=self.fg_text,
            insertbackground=self.fg_text,
            relief=tk.FLAT,
            font=("Consolas", 10),
        )
        self.ent_source_ip.grid(row=0, column=1, sticky=tk.EW, pady=4, ipady=4)
        self.btn_test_src = ttk.Button(
            conn_card,
            text="Test Source",
            command=lambda: self.on_test_connection(self.var_source_ip.get(), "Source"),
        )
        self.btn_test_src.grid(row=0, column=2, padx=(8, 0), pady=4)

        # Target IP
        ttk.Label(conn_card, text="Target TV IP (Restore To):", style="Card.TLabel").grid(
            row=1, column=0, sticky=tk.W, pady=4, padx=(0, 10)
        )
        self.var_target_ip = tk.StringVar(value=self.config.get("target_ip", DEFAULT_IP))
        self.ent_target_ip = tk.Entry(
            conn_card,
            textvariable=self.var_target_ip,
            bg="#18181b",
            fg=self.fg_text,
            insertbackground=self.fg_text,
            relief=tk.FLAT,
            font=("Consolas", 10),
        )
        self.ent_target_ip.grid(row=1, column=1, sticky=tk.EW, pady=4, ipady=4)
        self.btn_test_dst = ttk.Button(
            conn_card,
            text="Test Target",
            command=lambda: self.on_test_connection(self.var_target_ip.get(), "Target"),
        )
        self.btn_test_dst.grid(row=1, column=2, padx=(8, 0), pady=4)

        # Backup Folder
        ttk.Label(conn_card, text="Backup Folder:", style="Card.TLabel").grid(
            row=2, column=0, sticky=tk.W, pady=4, padx=(0, 10)
        )
        self.var_backup_dir = tk.StringVar(value=self.config.get("backup_dir", DEFAULT_BACKUP_DIR))
        self.var_backup_dir.trace_add("write", lambda *_: self.refresh_backup_summary())
        self.ent_backup_dir = tk.Entry(
            conn_card,
            textvariable=self.var_backup_dir,
            bg="#18181b",
            fg=self.fg_text,
            insertbackground=self.fg_text,
            relief=tk.FLAT,
            font=("Consolas", 10),
        )
        self.ent_backup_dir.grid(row=2, column=1, sticky=tk.EW, pady=4, ipady=4)
        self.btn_browse = ttk.Button(conn_card, text="Browse...", command=self.on_browse_folder)
        self.btn_browse.grid(row=2, column=2, padx=(8, 0), pady=4)

        # Existing backup summary label
        self.lbl_backup_summary = ttk.Label(conn_card, text="Checking backup folder...", style="Muted.TLabel")
        self.lbl_backup_summary.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))

        # 2. Included Components Header + Select All / Select None
        comp_hdr = ttk.Frame(outer)
        comp_hdr.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(comp_hdr, text="Included Components", style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Button(comp_hdr, text="Select None", command=lambda: self.set_all_checkboxes(False)).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        ttk.Button(comp_hdr, text="Select All", command=lambda: self.set_all_checkboxes(True)).pack(side=tk.RIGHT)

        comp_card = ttk.Frame(outer, style="Card.TFrame", padding=12)
        comp_card.pack(fill=tk.X, pady=(0, 14))

        self.var_chk_apks = tk.BooleanVar(value=True)
        self.var_chk_perms = tk.BooleanVar(value=True)
        self.var_chk_projectivy = tk.BooleanVar(value=True)
        self.var_chk_media = tk.BooleanVar(value=True)
        self.var_chk_settings = tk.BooleanVar(value=True)
        self.var_chk_debloat = tk.BooleanVar(value=True)

        items = [
            (
                self.var_chk_apks,
                "3rd-Party APKs & Split APKs",
                "Pulls via pm path; restores via batch install-multiple -r -g",
            ),
            (
                self.var_chk_perms,
                "Granted Runtime Permissions",
                "Exports granted=true permissions from dumpsys and re-grants them",
            ),
            (
                self.var_chk_projectivy,
                "Projectivy Layout, App Groupings & Button Color Schemes (.plbackup)",
                "Pulls/pushes /sdcard/Android/data/com.spocky.projengmenu/files/backups & auto-opens Projectivy Import",
            ),
            (
                self.var_chk_media,
                "Downloads & Wallpapers (/sdcard/Download & /sdcard/Pictures)",
                "Pulls and pushes /sdcard/Download and /sdcard/Pictures folders",
            ),
            (
                self.var_chk_settings,
                "System, Secure & Global Settings",
                "Filters out android_id, bluetooth_address, wifi_on, device_name, boot_count",
            ),
            (
                self.var_chk_debloat,
                "Disabled Bloatware, Stock Launcher & Projectivy HOME Intent",
                f"Disables {STOCK_LAUNCHER} & disabled packages, then triggers HOME intent",
            ),
        ]

        for idx, (var, title, subtitle) in enumerate(items):
            row_frame = ttk.Frame(comp_card, style="Card.TFrame")
            row_frame.pack(fill=tk.X, pady=3)
            ttk.Checkbutton(row_frame, text=title, variable=var, style="Card.TCheckbutton").pack(anchor=tk.W)
            ttk.Label(row_frame, text=f"      {subtitle}", style="Muted.TLabel").pack(anchor=tk.W)

        # 3. Action Buttons Row
        act_frame = ttk.Frame(outer)
        act_frame.pack(fill=tk.X, pady=(0, 12))

        btn_center = ttk.Frame(act_frame)
        btn_center.pack(anchor=tk.CENTER)

        self.btn_backup = ttk.Button(
            btn_center, text="Backup from Source TV", style="Primary.TButton", command=self.on_start_backup
        )
        self.btn_backup.pack(side=tk.LEFT, padx=6)

        self.btn_restore = ttk.Button(
            btn_center, text="Restore to Target TV", style="Danger.TButton", command=self.on_confirm_restore
        )
        self.btn_restore.pack(side=tk.LEFT, padx=6)

        self.btn_cancel = ttk.Button(btn_center, text="Stop", state=tk.DISABLED, command=self.on_cancel_task)
        self.btn_cancel.pack(side=tk.LEFT, padx=6)

        # 4. Progress & Live Console Output
        prog_hdr = ttk.Frame(outer)
        prog_hdr.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(prog_hdr, text="Operation Progress & Live ADB Log", style="Section.TLabel").pack(side=tk.LEFT)
        self.lbl_prog_text = ttk.Label(prog_hdr, text="Idle")
        self.lbl_prog_text.pack(side=tk.RIGHT)

        self.progress_bar = ttk.Progressbar(outer, orient=tk.HORIZONTAL, mode="determinate", maximum=100.0)
        self.progress_bar.pack(fill=tk.X, pady=(0, 8))

        log_container = ttk.Frame(outer, style="Card.TFrame")
        log_container.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            log_container,
            bg="#09090b",
            fg="#e4e4e7",
            insertbackground="#ffffff",
            font=("Consolas", 9),
            relief=tk.FLAT,
            wrap=tk.WORD,
            state=tk.DISABLED,
            padx=10,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_btns = ttk.Frame(outer)
        log_btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(log_btns, text="Copy Log", command=self.on_copy_log).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(log_btns, text="Clear Log", command=self.on_clear_log).pack(side=tk.RIGHT)

    # --------------------------------------------------------------------------
    # UI Helpers
    # --------------------------------------------------------------------------
    def refresh_adb_badge(self):
        self.adb_path = self.find_adb()
        if self.adb_path:
            self.lbl_adb_status.configure(text="ADB Ready", foreground="#4ade80")
            self.btn_install_adb.pack_forget()
        else:
            self.lbl_adb_status.configure(text="ADB Missing!", foreground="#f87171")
            if platform.system() == "Windows":
                self.btn_install_adb.pack(side=tk.RIGHT, padx=(6, 0))

    def set_all_checkboxes(self, active: bool):
        for v in (
            self.var_chk_apks,
            self.var_chk_perms,
            self.var_chk_projectivy,
            self.var_chk_media,
            self.var_chk_settings,
            self.var_chk_debloat,
        ):
            v.set(active)

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"

        def _append():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, line)
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

        self.root.after(0, _append)

    def set_progress(self, fraction: float, text: str):
        def _update():
            self.progress_bar["value"] = max(0.0, min(100.0, fraction * 100.0))
            self.lbl_prog_text.configure(text=text)

        self.root.after(0, _update)

    def set_busy(self, busy: bool):
        def _update():
            state = tk.DISABLED if busy else tk.NORMAL
            self.btn_backup.configure(state=state)
            self.btn_restore.configure(state=state)
            self.btn_test_src.configure(state=state)
            self.btn_test_dst.configure(state=state)
            self.btn_browse.configure(state=state)
            self.ent_source_ip.configure(state=state)
            self.ent_target_ip.configure(state=state)
            self.ent_backup_dir.configure(state=state)
            self.btn_cancel.configure(state=tk.NORMAL if busy else tk.DISABLED)
            if not busy:
                self.refresh_adb_badge()
                self.refresh_backup_summary()

        self.root.after(0, _update)

    def refresh_backup_summary(self):
        bdir = Path(self.var_backup_dir.get().strip() or DEFAULT_BACKUP_DIR)
        meta_file = bdir / "backup_metadata.txt"
        apks_dir = bdir / "apks"
        disabled_file = bdir / "packages" / "disabled_packages.txt"
        proj_dir = bdir / "projectivy_backups"

        if not bdir.exists():
            self.lbl_backup_summary.configure(text="Folder does not exist yet (will be created on first backup).")
            return

        apk_count = len([p for p in apks_dir.iterdir() if p.is_dir()]) if apks_dir.exists() else 0
        dis_count = (
            len(
                [
                    line
                    for line in disabled_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                    if line.strip()
                ]
            )
            if disabled_file.exists()
            else 0
        )
        pl_count = len(list(proj_dir.glob("*.plbackup"))) if proj_dir.exists() else 0

        if meta_file.exists():
            meta_lines = [
                l.strip() for l in meta_file.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()
            ]
            summary = " | ".join(meta_lines)
            self.lbl_backup_summary.configure(
                text=f"{summary} | {apk_count} Apps | {pl_count} Projectivy .plbackup(s) | {dis_count} Disabled"
            )
        elif apk_count > 0 or pl_count > 0:
            self.lbl_backup_summary.configure(
                text=f"Found {apk_count} backed-up app(s), {pl_count} Projectivy .plbackup(s), {dis_count} disabled package(s)."
            )
        else:
            self.lbl_backup_summary.configure(text="Folder exists, no backup found yet.")

    # --------------------------------------------------------------------------
    # Button Callbacks
    # --------------------------------------------------------------------------
    def on_open_backup_folder(self):
        bdir = Path(self.var_backup_dir.get().strip() or DEFAULT_BACKUP_DIR)
        bdir.mkdir(parents=True, exist_ok=True)
        if platform.system() == "Windows":
            os.startfile(str(bdir))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(bdir)])
        else:
            subprocess.Popen(["xdg-open", str(bdir)])

    def on_browse_folder(self):
        initial = self.var_backup_dir.get().strip() or DEFAULT_BACKUP_DIR
        selected = filedialog.askdirectory(title="Select Backup Folder", initialdir=initial)
        if selected:
            self.var_backup_dir.set(selected)
            self.save_config()

    def on_clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def on_copy_log(self):
        text = self.log_text.get("1.0", tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log("[INFO] Log copied to clipboard.")

    def on_cancel_task(self):
        self.cancel_requested = True
        self.log("Cancellation requested by user... waiting for current ADB command to finish.")

    def on_download_adb(self):
        def _worker():
            self.set_busy(True)
            self.set_progress(0.1, "Downloading Google Platform-Tools (ADB) for Windows...")
            self.log(f"Downloading {PLATFORM_TOOLS_WIN_URL} ...")
            try:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                zip_path = CONFIG_DIR / "platform-tools.zip"
                urllib.request.urlretrieve(PLATFORM_TOOLS_WIN_URL, str(zip_path))
                self.set_progress(0.6, "Extracting platform-tools...")
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(str(CONFIG_DIR))
                zip_path.unlink(missing_ok=True)
                self.adb_path = self.find_adb()
                if self.adb_path:
                    self.log(f"[OK] Installed ADB to: {self.adb_path}")
                    self.set_progress(1.0, "ADB Installed Ready!")
                else:
                    self.log("[ERROR] Extracted platform-tools, but adb.exe was not found.")
                    self.set_progress(0.0, "ADB install failed")
            except Exception as e:
                self.log(f"[ERROR] Failed to download ADB: {e}")
                self.set_progress(0.0, "ADB download failed")
            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

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
            else:
                self.set_progress(0.0, f"{label} connection failed")
            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    def on_start_backup(self):
        self.save_config()
        target = normalize_target(self.var_source_ip.get())
        bdir = Path(self.var_backup_dir.get().strip() or DEFAULT_BACKUP_DIR)
        self.cancel_requested = False
        threading.Thread(target=self.run_backup_workflow, args=(target, bdir), daemon=True).start()

    def on_confirm_restore(self):
        self.save_config()
        target = normalize_target(self.var_target_ip.get())
        bdir = Path(self.var_backup_dir.get().strip() or DEFAULT_BACKUP_DIR)

        if not bdir.exists():
            messagebox.showerror("Backup Folder Not Found", f"Backup directory does not exist:\n{bdir}")
            return

        confirm = messagebox.askyesno(
            f"Restore to {target}?",
            f"Restore selected components to {target}?\n\nBackup Source Folder:\n{bdir}",
        )
        if confirm:
            self.cancel_requested = False
            threading.Thread(target=self.run_restore_workflow, args=(target, bdir), daemon=True).start()

    # --------------------------------------------------------------------------
    # ADB Helpers
    # --------------------------------------------------------------------------
    def run_cmd(self, args: list[str], timeout: int = 300) -> tuple[int, str]:
        creationflags = 0x08000000 if platform.system() == "Windows" else 0
        try:
            proc = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=creationflags,
            )
            return proc.returncode, (proc.stdout or "").replace("\r", "")
        except subprocess.TimeoutExpired:
            return 124, "Command timed out"
        except Exception as e:
            return 1, str(e)

    def adb(self, target: str, subargs: list[str], timeout: int = 300) -> tuple[int, str]:
        adb_bin = self.adb_path or "adb"
        return self.run_cmd([adb_bin, "-s", target] + subargs, timeout=timeout)

    def adb_out(self, target: str, subargs: list[str], timeout: int = 60) -> str:
        _, out = self.adb(target, subargs, timeout=timeout)
        return out

    def connect_and_authorize(self, target: str) -> bool:
        self.adb_path = self.find_adb()
        if not self.adb_path:
            if platform.system() == "Windows":
                self.log("[WARN] 'adb.exe' not found — click 'Download ADB (Windows)' in the top right!")
            else:
                self.log("[ERROR] 'adb' is not installed! Run: sudo apt update && sudo apt install -y adb")
            return False

        self.run_cmd([self.adb_path, "start-server"], timeout=15)
        self.log(f"Connecting to {target}...")
        self.run_cmd([self.adb_path, "connect", target], timeout=15)

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
                self.log(f"Waiting for RSA authorization on TV screen... ({attempt}/{max_attempts})")
                self.set_progress(0.05, f"Waiting for TV RSA prompt ({attempt}/{max_attempts})...")
                threading.Event().wait(3.0)
            else:
                self.run_cmd([self.adb_path, "disconnect", target], timeout=10)
                _, conn_out = self.run_cmd([self.adb_path, "connect", target], timeout=10)
                self.log(f"Connection attempt {attempt}/{max_attempts}: {conn_out.strip()}")
                threading.Event().wait(2.0)

        self.log(f"[ERROR] Failed to connect/authorize with {target}. Check IP & Wireless/USB Debugging.")
        return False

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

        wp_dir = bdir / "projectivy_wallpapers"
        wp_dir.mkdir(parents=True, exist_ok=True)
        self.adb(target, ["pull", "-a", f"{remote_wallpapers}/.", str(wp_dir)], timeout=120)

        dl_dir = bdir / "sdcard" / "Download"
        if dl_dir.exists():
            for f in dl_dir.glob("*.pl*"):
                shutil.copy2(f, proj_dir / f.name)

    def push_and_import_projectivy_backups(self, target: str, bdir: Path):
        proj_dir = bdir / "projectivy_backups"
        dl_dir = bdir / "sdcard" / "Download"

        proj_dir.mkdir(parents=True, exist_ok=True)
        if dl_dir.exists():
            for f in dl_dir.glob("*.pl*"):
                if not (proj_dir / f.name).exists():
                    shutil.copy2(f, proj_dir / f.name)

        pl_files = sorted(proj_dir.glob("*.plbackup"), key=lambda p: p.stat().st_mtime)
        if not pl_files:
            self.log("[WARN] No Projectivy .plbackup files found in backup folder!")
            self.log(
                "Tip: On your Source TV, open Projectivy Settings -> General -> Manage Settings -> Export Settings, then run Backup again."
            )
            return

        remote_files_dir = f"/sdcard/Android/data/{PROJECTIVY_PKG}/files"
        remote_backups = f"{remote_files_dir}/backups"

        if not self.adb_out(target, ["shell", f"[ -d '{remote_files_dir}' ] && echo yes"]).strip():
            self.log("Launching Projectivy once so Android initializes its external data directory...")
            self.adb(target, ["shell", "am", "start", "-n", f"{PROJECTIVY_PKG}/.ui.home.MainActivity"])
            threading.Event().wait(2.0)

        # Clean shell-owned backups folder so Projectivy's UID retains full FUSE read/write access on Android 11-14
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

        # 1. 3rd-party APKs & Permissions
        if self.var_chk_apks.get() or self.var_chk_perms.get():
            self.set_progress(0.15, "Listing 3rd-party packages...")
            raw_pkgs = self.adb_out(target, ["shell", "pm", "list", "packages", "-3"])
            pkgs = sorted([line.replace("package:", "").strip() for line in raw_pkgs.splitlines() if line.strip()])
            (packages_dir / "third_party_packages.txt").write_text("\n".join(pkgs) + "\n", encoding="utf-8")
            self.log(f"Found {len(pkgs)} 3rd-party package(s).")

            all_perms_lines = []
            for idx, pkg in enumerate(pkgs, start=1):
                if self.cancel_requested:
                    break
                frac = 0.15 + (0.45 * (idx / max(1, len(pkgs))))
                self.set_progress(frac, f"[{idx}/{len(pkgs)}] Backing up {pkg}...")
                self.log(f"[{idx}/{len(pkgs)}] Processing {pkg}...")

                if self.var_chk_apks.get():
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
                    self.log(f"  [OK] Pulled {len(apk_paths)} APK file(s) for {pkg}")

                if self.var_chk_perms.get():
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
                        self.log(f"  [OK] Exported {len(sorted_g)} granted runtime permission(s)")

            if self.var_chk_perms.get():
                (perms_dir / "granted_permissions.txt").write_text(
                    "\n".join(all_perms_lines) + ("\n" if all_perms_lines else ""),
                    encoding="utf-8",
                )

        # 2. Pull Projectivy .plbackup files
        if not self.cancel_requested and self.var_chk_projectivy.get():
            self.set_progress(0.64, "Pulling Projectivy layout & color backups (.plbackup)...")
            self.pull_projectivy_backups(target, bdir)

        # 3. Pull /sdcard/Download & /sdcard/Pictures
        if not self.cancel_requested and self.var_chk_media.get():
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
        if not self.cancel_requested and self.var_chk_settings.get():
            self.set_progress(0.85, "Dumping system, secure, and global settings...")
            for ns in ("system", "secure", "global"):
                out = self.adb_out(target, ["shell", "settings", "list", ns])
                lines = sorted([l for l in out.splitlines() if l.strip()])
                (settings_dir / f"{ns}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
                self.log(f"[OK] Saved {len(lines)} '{ns}' settings")

        # 5. Disabled packages list
        if not self.cancel_requested and self.var_chk_debloat.get():
            self.set_progress(0.95, "Saving disabled packages list...")
            raw_dis = self.adb_out(target, ["shell", "pm", "list", "packages", "-d"])
            dis_pkgs = sorted([line.replace("package:", "").strip() for line in raw_dis.splitlines() if line.strip()])
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
        if not self.cancel_requested and self.var_chk_media.get():
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

        # 2. Batch install APKs via install-multiple -r -g
        if not self.cancel_requested and self.var_chk_apks.get() and apks_dir.exists():
            pkg_dirs = sorted([d for d in apks_dir.iterdir() if d.is_dir()])
            installed_ok = 0
            for idx, pkg_dir in enumerate(pkg_dirs, start=1):
                if self.cancel_requested:
                    break
                apk_files = sorted([str(f) for f in pkg_dir.glob("*.apk")])
                if not apk_files:
                    continue
                frac = 0.15 + (0.45 * (idx / max(1, len(pkg_dirs))))
                self.set_progress(frac, f"[{idx}/{len(pkg_dirs)}] Installing {pkg_dir.name}...")
                self.log(f"[{idx}/{len(pkg_dirs)}] Installing {pkg_dir.name} ({len(apk_files)} APK(s))...")

                code, out = self.adb(target, ["install-multiple", "-r", "-g"] + apk_files, timeout=300)
                if code == 0:
                    installed_ok += 1
                    self.log(f"  [OK] Installed {pkg_dir.name}")
                else:
                    self.log(f"  [WARN] Retrying {pkg_dir.name} without -g...")
                    code2, out2 = self.adb(target, ["install-multiple", "-r"] + apk_files, timeout=300)
                    if code2 == 0:
                        installed_ok += 1
                        self.log(f"  [OK] Installed {pkg_dir.name} (without -g)")
                    else:
                        self.log(f"  [ERROR] Failed to install {pkg_dir.name}: {out2.strip()}")
            self.log(f"[OK] Batch APK install finished: {installed_ok}/{len(pkg_dirs)} succeeded.")

        # 3. Re-grant runtime permissions
        if not self.cancel_requested and self.var_chk_perms.get():
            self.set_progress(0.65, "Re-granting runtime permissions...")
            perm_file = perms_dir / "granted_permissions.txt"
            granted_cnt = 0
            if perm_file.exists():
                for line in perm_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if self.cancel_requested:
                        break
                    parts = line.strip().split()
                    if len(parts) == 2:
                        pkg, perm = parts
                        code, _ = self.adb(target, ["shell", "pm", "grant", pkg, perm], timeout=15)
                        if code == 0:
                            granted_cnt += 1
                self.log(f"[OK] Re-applied {granted_cnt} runtime permission grant(s).")

        # 4. Apply safe settings
        if not self.cancel_requested and self.var_chk_settings.get():
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
        if not self.cancel_requested and self.var_chk_debloat.get():
            self.set_progress(0.90, "Disabling stock launcher & bloatware, launching Projectivy...")
            to_disable = {STOCK_LAUNCHER}
            dis_file = packages_dir / "disabled_packages.txt"
            if dis_file.exists():
                for line in dis_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.strip():
                        to_disable.add(line.strip())

            installed_raw = self.adb_out(target, ["shell", "pm", "list", "packages"])
            installed_set = {l.replace("package:", "").strip() for l in installed_raw.splitlines() if l.strip()}

            if PROJECTIVY_PKG in installed_set:
                self.adb(
                    target,
                    ["shell", "cmd", "package", "set-home-activity", f"{PROJECTIVY_PKG}/.ui.home.MainActivity"],
                )

            disabled_cnt = 0
            for pkg in sorted(to_disable):
                if pkg not in installed_set:
                    continue
                code, _ = self.adb(target, ["shell", "pm", "disable-user", "--user", "0", pkg], timeout=20)
                if code == 0:
                    disabled_cnt += 1
                    self.log(f"  [OK] Disabled {pkg}")
                else:
                    self.log(f"  [WARN] Could not disable {pkg}")

            if SETUP_WRAITH in installed_set:
                self.adb(target, ["shell", "pm", "disable-user", "--user", "0", SETUP_WRAITH], timeout=20)

            self.log("Triggering HOME intent to launch Projectivy...")
            self.adb(
                target,
                ["shell", "am", "start", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME"],
            )
            self.adb(target, ["shell", "input", "keyevent", "KEYCODE_HOME"])
            self.log(f"[OK] Disabled {disabled_cnt} package(s) and triggered HOME intent.")

        # 6. Push Projectivy .plbackup files & trigger ImportSettingsActivity
        if not self.cancel_requested and self.var_chk_projectivy.get():
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

        self.set_busy(False)


if __name__ == "__main__":
    root = tk.Tk()
    app = StreamerBackupWindowsApp(root)
    root.mainloop()
