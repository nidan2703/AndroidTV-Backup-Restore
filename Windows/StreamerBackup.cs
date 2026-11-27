using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;

namespace StreamerBackup
{
    public class MainForm : Form
    {
        [DllImport("user32.dll")]
        private static extern bool SetProcessDPIAware();

        [DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int attrValue, int attrSize);

        private const string DEFAULT_IP = "192.168.4.64:5555";
        private const string DEFAULT_PORT = "5555";
        private const string STOCK_LAUNCHER = "com.google.android.apps.tv.launcherx";
        private const string SETUP_WRAITH = "com.google.android.tungsten.setupwraith";
        private const string PROJECTIVY_PKG = "com.spocky.projengmenu";
        private const string PLAYSTORE_INSTALLER = "com.android.vending";
        private const string PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip";

        private static readonly HashSet<string> FilteredSettingsKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
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
            "wifi_saved_state"
        };

        // Known apps strictly distributed via Google Play Store (for legacy backups that lack package_installers.txt)
        private static readonly HashSet<string> KnownPlayStorePackages = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "air.com.vudu.air.DownloaderTablet",
            "ar.tvplayer.tv",
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
            "de.swr.avp.ard.tv",
            "dev.vodik7.tvquickactions",
            "org.videolan.vlc",
            "tv.pluto.android",
            "tv.wuaki.apptv"
        };

        // Friendly human-readable titles for common Android/Google TV packages
        private static readonly Dictionary<string, string> KnownAppNames = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "air.com.vudu.air.DownloaderTablet", "Fandango at Home (Vudu)" },
            { "ar.tvplayer.tv", "TiviMate IPTV Player" },
            { "cm.aptoidetv.pt", "Aptoide TV" },
            { "com.amazon.amazonvideo.livingroom", "Amazon Prime Video" },
            { "com.angel.tv", "Angel Studios" },
            { "com.apple.atve.androidtv.appletv", "Apple TV" },
            { "com.cbs.ott", "Paramount+" },
            { "com.disney.disneyplus", "Disney+" },
            { "com.esaba.downloader", "Downloader by AFTVnews" },
            { "com.espn.score_center", "ESPN" },
            { "com.fox.foxone", "FOX Sports / FOX One" },
            { "com.google.android.youtube.tv", "YouTube (Android TV)" },
            { "com.hulu.livingroomplus", "Hulu" },
            { "com.kanopy.tvapp", "Kanopy" },
            { "com.mixplorer.silver", "MiXplorer Silver File Manager" },
            { "com.moviesanywhere.goo", "Movies Anywhere" },
            { "com.nbcuni.nbc.androidtv", "NBC" },
            { "com.netflix.ninja", "Netflix" },
            { "com.nuvio.tv", "Nuvio TV" },
            { "com.peacocktv.peacockandroid", "Peacock TV" },
            { "com.phlox.tvwebbrowser", "TV Bro Web Browser" },
            { "com.plexapp.android", "Plex" },
            { "com.roku.web.trc", "The Roku Channel" },
            { "com.sling", "Sling TV" },
            { "com.spectrum.stva.androidtv", "Spectrum TV" },
            { "com.spocky.projengmenu", "Projectivy Launcher" },
            { "com.stremio.one", "Stremio" },
            { "com.surfshark.vpnclient.android", "Surfshark VPN" },
            { "com.tduk.appklr", "TDUK App Killer" },
            { "com.tduk.cacheclean", "TDUK Cache Cleaner" },
            { "com.truthsocial.android.tv.tplus", "Truth+" },
            { "com.tubitv", "Tubi TV" },
            { "com.viki.android", "Rakuten Viki" },
            { "com.wbd.stream", "Max (HBO Max)" },
            { "com.zdf.android.mediathek", "ZDFmediathek" },
            { "de.eye_interactive.atvl.playstore", "ATV Launcher Pro" },
            { "de.fcbayern.android", "FC Bayern TV" },
            { "de.swr.avp.ard.tv", "ARD Mediathek" },
            { "dev.projectivy.blueprint.app", "Projectivy Icon Pack / Blueprint" },
            { "dev.vodik7.tvquickactions", "tvQuickActions Pro" },
            { "org.videolan.vlc", "VLC Media Player" },
            { "pl.solidexplorer2", "Solid Explorer File Manager" },
            { "tv.pluto.android", "Pluto TV" },
            { "tv.wuaki.apptv", "Rakuten TV" }
        };

        private static string GetFriendlyAppName(string pkg)
        {
            string name;
            if (KnownAppNames.TryGetValue(pkg, out name)) return name;
            return pkg;
        }

        private string configDir;
        private string configFile;
        private string defaultBackupDir;
        private string adbPath;
        private volatile bool cancelRequested = false;

        // Theme colors
        private readonly Color bgMain = Color.FromArgb(24, 24, 27);
        private readonly Color bgCard = Color.FromArgb(39, 39, 42);
        private readonly Color bgInput = Color.FromArgb(16, 16, 20);
        private readonly Color fgText = Color.FromArgb(244, 244, 245);
        private readonly Color fgMuted = Color.FromArgb(161, 161, 170);
        private readonly Color accentBlue = Color.FromArgb(37, 99, 235);
        private readonly Color accentRed = Color.FromArgb(220, 38, 38);
        private readonly Color btnNeutral = Color.FromArgb(63, 63, 70);

        // Controls
        private Label lblAdbStatus;
        private Button btnDownloadAdb;
        private Button btnOpenFolder;

        private TextBox txtSourceIp;
        private Button btnTestSource;
        private TextBox txtTargetIp;
        private Button btnTestTarget;
        private TextBox txtBackupDir;
        private Button btnBrowse;
        private Label lblBackupSummary;

        private CheckBox chkApks;
        private CheckBox chkPerms;
        private CheckBox chkProjectivy;
        private CheckBox chkMedia;
        private CheckBox chkSettings;
        private CheckBox chkDebloat;
        private Button btnSelectAll;
        private Button btnSelectNone;

        private Button btnBackup;
        private Button btnRestore;
        private Button btnCancel;

        private Label lblProgressStatus;
        private ProgressBar progressBar;
        private TextBox txtLog;
        private Button btnClearLog;
        private Button btnCopyLog;

        public MainForm()
        {
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            configDir = Path.Combine(appData, "StreamerBackup");
            configFile = Path.Combine(configDir, "config.ini");
            defaultBackupDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Android Streamer Backup");

            InitializeUi();
            LoadConfig();
            RefreshAdbBadge();
            RefreshBackupSummary();
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            try
            {
                int useDark = 1;
                DwmSetWindowAttribute(this.Handle, 20, ref useDark, sizeof(int));
            }
            catch { }
        }

        private void InitializeUi()
        {
            this.Text = "Android TV Streamer Backup & Restore (Windows Native)";
            this.Size = new Size(860, 840);
            this.MinimumSize = new Size(800, 760);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.BackColor = bgMain;
            this.ForeColor = fgText;
            this.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);

            Panel rootPanel = new Panel();
            rootPanel.Dock = DockStyle.Fill;
            rootPanel.Padding = new Padding(18);
            rootPanel.BackColor = bgMain;
            this.Controls.Add(rootPanel);

            int y = 14;

            // Header
            Label lblHeader = new Label();
            lblHeader.Text = "Android TV Streamer Backup & Restore";
            lblHeader.Font = new Font("Segoe UI", 14f, FontStyle.Bold);
            lblHeader.ForeColor = fgText;
            lblHeader.AutoSize = true;
            lblHeader.Location = new Point(18, y);
            rootPanel.Controls.Add(lblHeader);

            btnOpenFolder = CreateFlatButton("Open Backup Folder", btnNeutral, 150, 30);
            btnOpenFolder.Location = new Point(rootPanel.Width - 168, y);
            btnOpenFolder.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnOpenFolder.Click += delegate { OpenBackupFolder(); };
            rootPanel.Controls.Add(btnOpenFolder);

            btnDownloadAdb = CreateFlatButton("Download ADB", accentBlue, 130, 30);
            btnDownloadAdb.Location = new Point(rootPanel.Width - 306, y);
            btnDownloadAdb.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnDownloadAdb.Click += delegate { DownloadAdbAsync(); };
            rootPanel.Controls.Add(btnDownloadAdb);

            lblAdbStatus = new Label();
            lblAdbStatus.Text = "Checking ADB...";
            lblAdbStatus.Font = new Font("Segoe UI", 9.5f, FontStyle.Bold);
            lblAdbStatus.AutoSize = true;
            lblAdbStatus.Location = new Point(rootPanel.Width - 430, y + 6);
            lblAdbStatus.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            rootPanel.Controls.Add(lblAdbStatus);

            y += 42;

            // Section 1: Devices & Storage
            Label lblSec1 = new Label();
            lblSec1.Text = "Devices and Backup Storage";
            lblSec1.Font = new Font("Segoe UI", 10.5f, FontStyle.Bold);
            lblSec1.AutoSize = true;
            lblSec1.Location = new Point(18, y);
            rootPanel.Controls.Add(lblSec1);
            y += 24;

            Panel cardConn = new Panel();
            cardConn.BackColor = bgCard;
            cardConn.Location = new Point(18, y);
            cardConn.Size = new Size(rootPanel.Width - 36, 136);
            cardConn.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            rootPanel.Controls.Add(cardConn);

            // Source IP
            Label lblSrc = new Label();
            lblSrc.Text = "Source TV IP (Backup From):";
            lblSrc.AutoSize = true;
            lblSrc.Location = new Point(14, 15);
            cardConn.Controls.Add(lblSrc);

            txtSourceIp = CreateDarkTextBox(DEFAULT_IP);
            txtSourceIp.Location = new Point(210, 12);
            txtSourceIp.Size = new Size(cardConn.Width - 340, 25);
            txtSourceIp.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            cardConn.Controls.Add(txtSourceIp);

            btnTestSource = CreateFlatButton("Test Source", btnNeutral, 105, 27);
            btnTestSource.Location = new Point(cardConn.Width - 118, 10);
            btnTestSource.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnTestSource.Click += delegate { TestConnectionAsync(txtSourceIp.Text, "Source"); };
            cardConn.Controls.Add(btnTestSource);

            // Target IP
            Label lblDst = new Label();
            lblDst.Text = "Target TV IP (Restore To):";
            lblDst.AutoSize = true;
            lblDst.Location = new Point(14, 48);
            cardConn.Controls.Add(lblDst);

            txtTargetIp = CreateDarkTextBox(DEFAULT_IP);
            txtTargetIp.Location = new Point(210, 45);
            txtTargetIp.Size = new Size(cardConn.Width - 340, 25);
            txtTargetIp.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            cardConn.Controls.Add(txtTargetIp);

            btnTestTarget = CreateFlatButton("Test Target", btnNeutral, 105, 27);
            btnTestTarget.Location = new Point(cardConn.Width - 118, 43);
            btnTestTarget.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnTestTarget.Click += delegate { TestConnectionAsync(txtTargetIp.Text, "Target"); };
            cardConn.Controls.Add(btnTestTarget);

            // Backup Dir
            Label lblDir = new Label();
            lblDir.Text = "Backup Folder:";
            lblDir.AutoSize = true;
            lblDir.Location = new Point(14, 81);
            cardConn.Controls.Add(lblDir);

            txtBackupDir = CreateDarkTextBox(defaultBackupDir);
            txtBackupDir.Location = new Point(210, 78);
            txtBackupDir.Size = new Size(cardConn.Width - 340, 25);
            txtBackupDir.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            txtBackupDir.TextChanged += delegate { RefreshBackupSummary(); };
            cardConn.Controls.Add(txtBackupDir);

            btnBrowse = CreateFlatButton("Browse...", btnNeutral, 105, 27);
            btnBrowse.Location = new Point(cardConn.Width - 118, 76);
            btnBrowse.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnBrowse.Click += delegate { BrowseBackupFolder(); };
            cardConn.Controls.Add(btnBrowse);

            lblBackupSummary = new Label();
            lblBackupSummary.Text = "Checking backup folder...";
            lblBackupSummary.ForeColor = fgMuted;
            lblBackupSummary.Font = new Font("Segoe UI", 8.5f, FontStyle.Regular);
            lblBackupSummary.AutoSize = true;
            lblBackupSummary.Location = new Point(14, 110);
            cardConn.Controls.Add(lblBackupSummary);

            y += 148;

            // Section 2: Included Components
            Label lblSec2 = new Label();
            lblSec2.Text = "Included Components (uncheck others to run a single section separately)";
            lblSec2.Font = new Font("Segoe UI", 10.5f, FontStyle.Bold);
            lblSec2.AutoSize = true;
            lblSec2.Location = new Point(18, y + 4);
            rootPanel.Controls.Add(lblSec2);

            btnSelectNone = CreateFlatButton("Select None", btnNeutral, 96, 26);
            btnSelectNone.Location = new Point(rootPanel.Width - 114, y);
            btnSelectNone.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnSelectNone.Click += delegate { SetAllCheckboxes(false); };
            rootPanel.Controls.Add(btnSelectNone);

            btnSelectAll = CreateFlatButton("Select All", btnNeutral, 90, 26);
            btnSelectAll.Location = new Point(rootPanel.Width - 212, y);
            btnSelectAll.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnSelectAll.Click += delegate { SetAllCheckboxes(true); };
            rootPanel.Controls.Add(btnSelectAll);

            y += 30;

            Panel cardComp = new Panel();
            cardComp.BackColor = bgCard;
            cardComp.Location = new Point(18, y);
            cardComp.Size = new Size(rootPanel.Width - 36, 236);
            cardComp.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            rootPanel.Controls.Add(cardComp);

            int cy = 10;
            chkApks = AddComponentRow(cardComp, ref cy,
                "Play Store Manifest & Sideloaded APK Cloning",
                "Clones sideloaded APKs via ADB; installs Play Store apps fresh from Google Play on Target TV");
            chkPerms = AddComponentRow(cardComp, ref cy,
                "Granted Runtime Permissions",
                "Exports granted=true permissions from dumpsys and re-grants them");
            chkProjectivy = AddComponentRow(cardComp, ref cy,
                "Projectivy Layout, App Groupings & Button Color Schemes (.plbackup)",
                "Pulls/pushes Projectivy .plbackup files (FUSE-safe) & auto-opens Projectivy Import");
            chkMedia = AddComponentRow(cardComp, ref cy,
                "Downloads & Wallpapers (/sdcard/Download & /sdcard/Pictures)",
                "Pulls and pushes /sdcard/Download and /sdcard/Pictures folders");
            chkSettings = AddComponentRow(cardComp, ref cy,
                "System, Secure & Global Settings",
                "Filters out android_id, bluetooth_address, wifi_on, device_name, boot_count");
            chkDebloat = AddComponentRow(cardComp, ref cy,
                "Disabled Bloatware, Stock Launcher & Projectivy HOME Intent",
                "Disables com.google.android.apps.tv.launcherx & disabled packages, then triggers HOME intent");

            y += 248;

            // Section 3: Action Buttons
            btnBackup = CreateFlatButton("Backup from Source TV", accentBlue, 210, 38);
            btnBackup.Font = new Font("Segoe UI", 10f, FontStyle.Bold);
            btnBackup.Location = new Point(170, y);
            btnBackup.Click += delegate { StartBackupAsync(); };
            rootPanel.Controls.Add(btnBackup);

            btnRestore = CreateFlatButton("Restore to Target TV", accentRed, 210, 38);
            btnRestore.Font = new Font("Segoe UI", 10f, FontStyle.Bold);
            btnRestore.Location = new Point(392, y);
            btnRestore.Click += delegate { ConfirmAndStartRestore(); };
            rootPanel.Controls.Add(btnRestore);

            btnCancel = CreateFlatButton("Stop", btnNeutral, 90, 38);
            btnCancel.Enabled = false;
            btnCancel.Location = new Point(614, y);
            btnCancel.Click += delegate
            {
                cancelRequested = true;
                AppendLog("Cancellation requested... waiting for current ADB command to finish.");
            };
            rootPanel.Controls.Add(btnCancel);

            y += 48;

            // Section 4: Progress & Live Log
            Label lblSec4 = new Label();
            lblSec4.Text = "Operation Progress & Live ADB Log";
            lblSec4.Font = new Font("Segoe UI", 10.5f, FontStyle.Bold);
            lblSec4.AutoSize = true;
            lblSec4.Location = new Point(18, y);
            rootPanel.Controls.Add(lblSec4);

            lblProgressStatus = new Label();
            lblProgressStatus.Text = "Idle";
            lblProgressStatus.ForeColor = fgMuted;
            lblProgressStatus.AutoSize = true;
            lblProgressStatus.Location = new Point(300, y + 2);
            rootPanel.Controls.Add(lblProgressStatus);

            y += 24;

            progressBar = new ProgressBar();
            progressBar.Minimum = 0;
            progressBar.Maximum = 100;
            progressBar.Value = 0;
            progressBar.Location = new Point(18, y);
            progressBar.Size = new Size(rootPanel.Width - 36, 18);
            progressBar.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            rootPanel.Controls.Add(progressBar);

            y += 26;

            txtLog = new TextBox();
            txtLog.Multiline = true;
            txtLog.ReadOnly = true;
            txtLog.ScrollBars = ScrollBars.Vertical;
            txtLog.BackColor = Color.FromArgb(9, 9, 11);
            txtLog.ForeColor = Color.FromArgb(228, 228, 231);
            txtLog.Font = new Font("Consolas", 9.25f, FontStyle.Regular);
            txtLog.BorderStyle = BorderStyle.FixedSingle;
            txtLog.Location = new Point(18, y);
            txtLog.Size = new Size(rootPanel.Width - 36, rootPanel.Height - y - 50);
            txtLog.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            rootPanel.Controls.Add(txtLog);

            btnCopyLog = CreateFlatButton("Copy Log", btnNeutral, 95, 28);
            btnCopyLog.Location = new Point(rootPanel.Width - 113, rootPanel.Height - 40);
            btnCopyLog.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            btnCopyLog.Click += delegate
            {
                if (!string.IsNullOrEmpty(txtLog.Text))
                {
                    Clipboard.SetText(txtLog.Text);
                    AppendLog("[INFO] Log copied to clipboard.");
                }
            };
            rootPanel.Controls.Add(btnCopyLog);

            btnClearLog = CreateFlatButton("Clear Log", btnNeutral, 95, 28);
            btnClearLog.Location = new Point(rootPanel.Width - 216, rootPanel.Height - 40);
            btnClearLog.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            btnClearLog.Click += delegate { txtLog.Clear(); };
            rootPanel.Controls.Add(btnClearLog);
        }

        private CheckBox AddComponentRow(Panel parent, ref int cy, string title, string subtitle)
        {
            CheckBox chk = new CheckBox();
            chk.Text = title;
            chk.Checked = true;
            chk.Font = new Font("Segoe UI", 9.5f, FontStyle.Bold);
            chk.ForeColor = fgText;
            chk.AutoSize = true;
            chk.Location = new Point(14, cy);
            parent.Controls.Add(chk);

            Label lblSub = new Label();
            lblSub.Text = subtitle;
            lblSub.Font = new Font("Segoe UI", 8.5f, FontStyle.Regular);
            lblSub.ForeColor = fgMuted;
            lblSub.AutoSize = true;
            lblSub.Location = new Point(34, cy + 19);
            parent.Controls.Add(lblSub);

            cy += 37;
            return chk;
        }

        private TextBox CreateDarkTextBox(string initial)
        {
            TextBox tb = new TextBox();
            tb.Text = initial;
            tb.BackColor = bgInput;
            tb.ForeColor = fgText;
            tb.BorderStyle = BorderStyle.FixedSingle;
            tb.Font = new Font("Consolas", 10f, FontStyle.Regular);
            return tb;
        }

        private Button CreateFlatButton(string text, Color backColor, int width, int height)
        {
            Button btn = new Button();
            btn.Text = text;
            btn.Size = new Size(width, height);
            btn.FlatStyle = FlatStyle.Flat;
            btn.FlatAppearance.BorderSize = 0;
            btn.BackColor = backColor;
            btn.ForeColor = Color.White;
            btn.Cursor = Cursors.Hand;
            return btn;
        }

        // ----------------------------------------------------------------------
        // Config & Helpers
        // ----------------------------------------------------------------------
        private void LoadConfig()
        {
            try
            {
                if (File.Exists(configFile))
                {
                    foreach (string line in File.ReadAllLines(configFile, Encoding.UTF8))
                    {
                        int eq = line.IndexOf('=');
                        if (eq > 0)
                        {
                            string k = line.Substring(0, eq).Trim();
                            string v = line.Substring(eq + 1).Trim();
                            if (k == "source_ip" && !string.IsNullOrEmpty(v)) txtSourceIp.Text = v;
                            else if (k == "target_ip" && !string.IsNullOrEmpty(v)) txtTargetIp.Text = v;
                            else if (k == "backup_dir" && !string.IsNullOrEmpty(v)) txtBackupDir.Text = v;
                        }
                    }
                }
            }
            catch { }
        }

        private void SaveConfig()
        {
            try
            {
                Directory.CreateDirectory(configDir);
                StringBuilder sb = new StringBuilder();
                sb.AppendLine("source_ip=" + txtSourceIp.Text.Trim());
                sb.AppendLine("target_ip=" + txtTargetIp.Text.Trim());
                sb.AppendLine("backup_dir=" + txtBackupDir.Text.Trim());
                File.WriteAllText(configFile, sb.ToString(), Encoding.UTF8);
            }
            catch { }
        }

        private string NormalizeTarget(string rawIp)
        {
            string raw = (rawIp ?? "").Trim();
            if (string.IsNullOrEmpty(raw)) return DEFAULT_IP;
            if (!raw.Contains(":")) return raw + ":" + DEFAULT_PORT;
            return raw;
        }

        private string FindAdb()
        {
            string appDir = AppDomain.CurrentDomain.BaseDirectory;
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);

            string[] candidates = new string[]
            {
                Path.Combine(appDir, "platform-tools", "adb.exe"),
                Path.Combine(configDir, "platform-tools", "adb.exe"),
                Path.Combine(localAppData, "Android", "Sdk", "platform-tools", "adb.exe"),
                @"C:\platform-tools\adb.exe"
            };

            foreach (string c in candidates)
            {
                if (File.Exists(c)) return c;
            }

            string pathEnv = Environment.GetEnvironmentVariable("PATH") ?? "";
            foreach (string p in pathEnv.Split(Path.PathSeparator))
            {
                try
                {
                    if (!string.IsNullOrEmpty(p))
                    {
                        string candidate = Path.Combine(p.Trim(), "adb.exe");
                        if (File.Exists(candidate)) return candidate;
                    }
                }
                catch { }
            }
            return null;
        }

        private void RefreshAdbBadge()
        {
            adbPath = FindAdb();
            if (!string.IsNullOrEmpty(adbPath))
            {
                lblAdbStatus.Text = "ADB Ready";
                lblAdbStatus.ForeColor = Color.FromArgb(74, 222, 128);
                btnDownloadAdb.Visible = false;
            }
            else
            {
                lblAdbStatus.Text = "ADB Missing!";
                lblAdbStatus.ForeColor = Color.FromArgb(248, 113, 113);
                btnDownloadAdb.Visible = true;
            }
        }

        private void RefreshBackupSummary()
        {
            string bdir = txtBackupDir.Text.Trim();
            if (string.IsNullOrEmpty(bdir)) bdir = defaultBackupDir;

            if (!Directory.Exists(bdir))
            {
                lblBackupSummary.Text = "Folder does not exist yet (will be created on first backup).";
                return;
            }

            string metaFile = Path.Combine(bdir, "backup_metadata.txt");
            string apksDir = Path.Combine(bdir, "apks");
            string playFile = Path.Combine(bdir, "packages", "playstore_packages.txt");
            string sideFile = Path.Combine(bdir, "packages", "sideloaded_packages.txt");
            string disFile = Path.Combine(bdir, "packages", "disabled_packages.txt");
            string projDir = Path.Combine(bdir, "projectivy_backups");

            int apkCount = Directory.Exists(apksDir) ? Directory.GetDirectories(apksDir).Length : 0;
            int playCount = CountNonEmptyLines(playFile);
            int sideCount = CountNonEmptyLines(sideFile);
            int plCount = Directory.Exists(projDir) ? Directory.GetFiles(projDir, "*.plbackup").Length : 0;
            int disCount = CountNonEmptyLines(disFile);

            string appSummary = (playCount > 0 || sideCount > 0)
                ? string.Format("{0} Play Store + {1} Sideloaded", playCount, sideCount)
                : string.Format("{0} Apps", apkCount);

            if (File.Exists(metaFile))
            {
                List<string> parts = new List<string>();
                foreach (string l in File.ReadAllLines(metaFile))
                {
                    if (!string.IsNullOrWhiteSpace(l)) parts.Add(l.Trim());
                }
                lblBackupSummary.Text = string.Format("{0} | {1} | {2} Projectivy .plbackup(s) | {3} Disabled",
                    string.Join(" | ", parts.ToArray()), appSummary, plCount, disCount);
            }
            else if (apkCount > 0 || playCount > 0 || plCount > 0)
            {
                lblBackupSummary.Text = string.Format("Found {0}, {1} Projectivy .plbackup(s), {2} disabled package(s).",
                    appSummary, plCount, disCount);
            }
            else
            {
                lblBackupSummary.Text = "Folder exists, no backup found yet.";
            }
        }

        private int CountNonEmptyLines(string path)
        {
            if (!File.Exists(path)) return 0;
            int c = 0;
            foreach (string l in File.ReadAllLines(path))
            {
                if (!string.IsNullOrWhiteSpace(l)) c++;
            }
            return c;
        }

        private void SetAllCheckboxes(bool active)
        {
            chkApks.Checked = active;
            chkPerms.Checked = active;
            chkProjectivy.Checked = active;
            chkMedia.Checked = active;
            chkSettings.Checked = active;
            chkDebloat.Checked = active;
        }

        private void AppendLog(string message)
        {
            if (this.InvokeRequired)
            {
                this.BeginInvoke(new Action<string>(AppendLog), message);
                return;
            }
            string ts = DateTime.Now.ToString("HH:mm:ss");
            txtLog.AppendText(string.Format("[{0}] {1}{2}", ts, message, Environment.NewLine));
        }

        private void SetProgress(int percent, string status)
        {
            if (this.InvokeRequired)
            {
                this.BeginInvoke(new Action<int, string>(SetProgress), percent, status);
                return;
            }
            progressBar.Value = Math.Max(0, Math.Min(100, percent));
            lblProgressStatus.Text = status;
        }

        private void SetBusy(bool busy)
        {
            if (this.InvokeRequired)
            {
                this.BeginInvoke(new Action<bool>(SetBusy), busy);
                return;
            }
            btnBackup.Enabled = !busy;
            btnRestore.Enabled = !busy;
            btnTestSource.Enabled = !busy;
            btnTestTarget.Enabled = !busy;
            btnBrowse.Enabled = !busy;
            btnSelectAll.Enabled = !busy;
            btnSelectNone.Enabled = !busy;
            txtSourceIp.Enabled = !busy;
            txtTargetIp.Enabled = !busy;
            txtBackupDir.Enabled = !busy;
            btnCancel.Enabled = busy;
            if (!busy)
            {
                RefreshAdbBadge();
                RefreshBackupSummary();
            }
        }

        private void OpenBackupFolder()
        {
            string bdir = txtBackupDir.Text.Trim();
            if (string.IsNullOrEmpty(bdir)) bdir = defaultBackupDir;
            Directory.CreateDirectory(bdir);
            Process.Start("explorer.exe", bdir);
        }

        private void BrowseBackupFolder()
        {
            using (FolderBrowserDialog fbd = new FolderBrowserDialog())
            {
                fbd.Description = "Select Android TV Streamer Backup Folder";
                fbd.SelectedPath = txtBackupDir.Text.Trim();
                if (fbd.ShowDialog(this) == DialogResult.OK && !string.IsNullOrEmpty(fbd.SelectedPath))
                {
                    txtBackupDir.Text = fbd.SelectedPath;
                    SaveConfig();
                }
            }
        }

        private DialogResult ShowMessageBoxOnUi(string text, string caption, MessageBoxButtons buttons, MessageBoxIcon icon)
        {
            if (this.InvokeRequired)
            {
                return (DialogResult)this.Invoke(new Func<DialogResult>(delegate
                {
                    return MessageBox.Show(this, text, caption, buttons, icon);
                }));
            }
            return MessageBox.Show(this, text, caption, buttons, icon);
        }

        private List<string> ShowPlayStoreChecklistDialogOnUi(List<string> missingPkgs)
        {
            if (this.InvokeRequired)
            {
                return (List<string>)this.Invoke(new Func<List<string>>(delegate
                {
                    return ShowPlayStoreChecklistDialogOnUi(missingPkgs);
                }));
            }

            List<string> selected = new List<string>();
            using (Form dlg = new Form())
            {
                dlg.Text = "Google Play Store Download Checklist";
                dlg.Size = new Size(640, 560);
                dlg.MinimumSize = new Size(560, 460);
                dlg.StartPosition = FormStartPosition.CenterParent;
                dlg.BackColor = bgMain;
                dlg.ForeColor = fgText;
                dlg.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
                dlg.FormBorderStyle = FormBorderStyle.FixedDialog;
                dlg.MaximizeBox = false;
                dlg.MinimizeBox = false;

                try
                {
                    int useDark = 1;
                    DwmSetWindowAttribute(dlg.Handle, 20, ref useDark, sizeof(int));
                }
                catch { }

                Label lblTitle = new Label();
                lblTitle.Text = string.Format("{0} Google Play Store App(s) Not Yet Installed on Target TV", missingPkgs.Count);
                lblTitle.Font = new Font("Segoe UI", 11.5f, FontStyle.Bold);
                lblTitle.ForeColor = fgText;
                lblTitle.AutoSize = true;
                lblTitle.Location = new Point(16, 14);
                dlg.Controls.Add(lblTitle);

                Label lblDesc = new Label();
                lblDesc.Text = "Check the apps you want to install on the Target TV. Clicking 'Yes' will open each checked app on the TV's Google Play Store, trigger Install, and fall back to local APK backup if needed.";
                lblDesc.Font = new Font("Segoe UI", 9f, FontStyle.Regular);
                lblDesc.ForeColor = fgMuted;
                lblDesc.Location = new Point(16, 40);
                lblDesc.Size = new Size(590, 36);
                dlg.Controls.Add(lblDesc);

                Button btnAll = CreateFlatButton("Select All", btnNeutral, 95, 27);
                btnAll.Location = new Point(16, 80);
                dlg.Controls.Add(btnAll);

                Button btnNone = CreateFlatButton("Select None", btnNeutral, 100, 27);
                btnNone.Location = new Point(118, 80);
                dlg.Controls.Add(btnNone);

                CheckedListBox clb = new CheckedListBox();
                clb.CheckOnClick = true;
                clb.BackColor = bgCard;
                clb.ForeColor = fgText;
                clb.BorderStyle = BorderStyle.FixedSingle;
                clb.Font = new Font("Consolas", 9.5f, FontStyle.Regular);
                clb.Location = new Point(16, 114);
                clb.Size = new Size(592, 315);

                for (int i = 0; i < missingPkgs.Count; i++)
                {
                    string pkg = missingPkgs[i];
                    string itemText = string.Format("{0,2}. {1,-34} ({2})", i + 1, GetFriendlyAppName(pkg), pkg);
                    clb.Items.Add(itemText, true);
                }
                dlg.Controls.Add(clb);

                btnAll.Click += delegate
                {
                    for (int i = 0; i < clb.Items.Count; i++) clb.SetItemChecked(i, true);
                };
                btnNone.Click += delegate
                {
                    for (int i = 0; i < clb.Items.Count; i++) clb.SetItemChecked(i, false);
                };

                Label lblQuestion = new Label();
                lblQuestion.Text = "Download and install the checked apps on the Target TV now?";
                lblQuestion.Font = new Font("Segoe UI", 10.5f, FontStyle.Bold);
                lblQuestion.ForeColor = fgText;
                lblQuestion.AutoSize = true;
                lblQuestion.Location = new Point(105, 440);
                dlg.Controls.Add(lblQuestion);

                Button btnYes = CreateFlatButton("Yes, Download Checked Apps", accentBlue, 220, 36);
                btnYes.Font = new Font("Segoe UI", 9.5f, FontStyle.Bold);
                btnYes.Location = new Point(110, 472);
                btnYes.Click += delegate
                {
                    for (int i = 0; i < clb.Items.Count; i++)
                    {
                        if (clb.GetItemChecked(i))
                            selected.Add(missingPkgs[i]);
                    }
                    dlg.DialogResult = DialogResult.Yes;
                    dlg.Close();
                };
                dlg.Controls.Add(btnYes);

                Button btnNo = CreateFlatButton("No, Skip Play Store Apps", btnNeutral, 195, 36);
                btnNo.Font = new Font("Segoe UI", 9.5f, FontStyle.Bold);
                btnNo.Location = new Point(342, 472);
                btnNo.Click += delegate
                {
                    selected.Clear();
                    dlg.DialogResult = DialogResult.No;
                    dlg.Close();
                };
                dlg.Controls.Add(btnNo);

                dlg.AcceptButton = btnYes;
                dlg.CancelButton = btnNo;
                dlg.ShowDialog(this);
            }
            return selected;
        }

        // ----------------------------------------------------------------------
        // ADB Process Execution
        // ----------------------------------------------------------------------
        private int RunProcess(string fileName, string arguments, int timeoutMs, out string output)
        {
            output = "";
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = fileName;
                psi.Arguments = arguments;
                psi.UseShellExecute = false;
                psi.RedirectStandardOutput = true;
                psi.RedirectStandardError = true;
                psi.CreateNoWindow = true;
                psi.StandardOutputEncoding = Encoding.UTF8;
                psi.StandardErrorEncoding = Encoding.UTF8;

                using (Process proc = new Process())
                {
                    proc.StartInfo = psi;
                    StringBuilder sb = new StringBuilder();
                    proc.OutputDataReceived += delegate(object s, DataReceivedEventArgs e)
                    {
                        if (e.Data != null) sb.AppendLine(e.Data);
                    };
                    proc.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e)
                    {
                        if (e.Data != null) sb.AppendLine(e.Data);
                    };

                    proc.Start();
                    proc.BeginOutputReadLine();
                    proc.BeginErrorReadLine();

                    if (!proc.WaitForExit(timeoutMs))
                    {
                        try { proc.Kill(); } catch { }
                        output = "Command timed out";
                        return 124;
                    }
                    proc.WaitForExit();
                    output = sb.ToString().Replace("\r", "");
                    return proc.ExitCode;
                }
            }
            catch (Exception ex)
            {
                output = ex.Message;
                return 1;
            }
        }

        private int Adb(string target, string subArgs, out string output, int timeoutMs = 300000)
        {
            string exe = adbPath ?? "adb.exe";
            string args = string.Format("-s \"{0}\" {1}", target, subArgs);
            return RunProcess(exe, args, timeoutMs, out output);
        }

        private string AdbOut(string target, string subArgs, int timeoutMs = 60000)
        {
            string output;
            Adb(target, subArgs, out output, timeoutMs);
            return output;
        }

        private HashSet<string> GetInstalledPackagesOnDevice(string target)
        {
            HashSet<string> set = new HashSet<string>(StringComparer.Ordinal);
            string raw = AdbOut(target, "shell pm list packages");
            foreach (string line in raw.Split('\n'))
            {
                string clean = line.Replace("package:", "").Trim();
                if (!string.IsNullOrEmpty(clean)) set.Add(clean);
            }
            return set;
        }

        private bool ConnectAndAuthorize(string target)
        {
            adbPath = FindAdb();
            if (string.IsNullOrEmpty(adbPath))
            {
                AppendLog("[WARN] 'adb.exe' not found! Click 'Download ADB' in the top-right corner to install Google Platform-Tools automatically.");
                return false;
            }

            string dummy;
            RunProcess(adbPath, "start-server", 15000, out dummy);
            AppendLog("Connecting to " + target + "...");
            RunProcess(adbPath, "connect " + target, 15000, out dummy);

            int maxAttempts = 25;
            for (int attempt = 1; attempt <= maxAttempts; attempt++)
            {
                if (cancelRequested) return false;

                string stateOut;
                Adb(target, "get-state", out stateOut, 10000);
                string state = (stateOut ?? "").Trim();

                if (state == "device")
                {
                    AppendLog("[OK] Authorized ADB session established with " + target);
                    return true;
                }
                else if (state.IndexOf("unauthorized", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    if (attempt == 1)
                    {
                        AppendLog("==========================================================");
                        AppendLog("ACTION REQUIRED ON TV: Check 'Always allow from this computer'");
                        AppendLog("and click 'Allow' on the Android/Google TV screen!");
                        AppendLog("==========================================================");
                    }
                    AppendLog(string.Format("Waiting for RSA authorization on TV screen... ({0}/{1})", attempt, maxAttempts));
                    SetProgress(5, string.Format("Waiting for TV RSA prompt ({0}/{1})...", attempt, maxAttempts));
                    Thread.Sleep(3000);
                }
                else
                {
                    RunProcess(adbPath, "disconnect " + target, 10000, out dummy);
                    string connOut;
                    RunProcess(adbPath, "connect " + target, 10000, out connOut);
                    AppendLog(string.Format("Connection attempt {0}/{1}: {2}", attempt, maxAttempts, (connOut ?? "").Trim()));
                    Thread.Sleep(2000);
                }
            }

            AppendLog("[ERROR] Failed to connect/authorize with " + target + ". Check IP & Wireless/USB Debugging.");
            return false;
        }

        // ----------------------------------------------------------------------
        // Async Actions
        // ----------------------------------------------------------------------
        private void DownloadAdbAsync()
        {
            ThreadPool.QueueUserWorkItem(delegate
            {
                SetBusy(true);
                SetProgress(10, "Downloading Google Platform-Tools (ADB) for Windows...");
                AppendLog("Downloading " + PLATFORM_TOOLS_URL + " ...");
                try
                {
                    ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072; // TLS 1.2
                    Directory.CreateDirectory(configDir);
                    string zipPath = Path.Combine(configDir, "platform-tools.zip");
                    string extractDir = Path.Combine(configDir, "platform-tools");
                    if (Directory.Exists(extractDir)) Directory.Delete(extractDir, true);

                    using (WebClient wc = new WebClient())
                    {
                        wc.DownloadFile(PLATFORM_TOOLS_URL, zipPath);
                    }

                    SetProgress(65, "Extracting platform-tools...");
                    ZipFile.ExtractToDirectory(zipPath, configDir);
                    try { File.Delete(zipPath); } catch { }

                    adbPath = FindAdb();
                    if (!string.IsNullOrEmpty(adbPath))
                    {
                        AppendLog("[OK] Installed ADB to: " + adbPath);
                        SetProgress(100, "ADB Installed & Ready!");
                    }
                    else
                    {
                        AppendLog("[ERROR] Extracted platform-tools, but adb.exe was not found.");
                        SetProgress(0, "ADB install failed");
                    }
                }
                catch (Exception ex)
                {
                    AppendLog("[ERROR] Failed to download ADB: " + ex.Message);
                    SetProgress(0, "ADB download failed");
                }
                SetBusy(false);
            });
        }

        private void TestConnectionAsync(string rawIp, string label)
        {
            SaveConfig();
            string target = NormalizeTarget(rawIp);
            ThreadPool.QueueUserWorkItem(delegate
            {
                SetBusy(true);
                SetProgress(10, string.Format("Testing connection to {0} ({1})...", label, target));
                if (ConnectAndAuthorize(target))
                {
                    string model = AdbOut(target, "shell getprop ro.product.model").Trim();
                    string ver = AdbOut(target, "shell getprop ro.build.version.release").Trim();
                    if (string.IsNullOrEmpty(model)) model = "Android TV";
                    string msg = string.Format("{0} Connected: {1} (Android {2})", label, model, ver);
                    AppendLog("[OK] " + msg);
                    SetProgress(100, msg);
                }
                else
                {
                    SetProgress(0, label + " connection failed");
                }
                SetBusy(false);
            });
        }

        private void StartBackupAsync()
        {
            SaveConfig();
            string target = NormalizeTarget(txtSourceIp.Text);
            string bdir = txtBackupDir.Text.Trim();
            if (string.IsNullOrEmpty(bdir)) bdir = defaultBackupDir;
            cancelRequested = false;

            ThreadPool.QueueUserWorkItem(delegate { RunBackupWorkflow(target, bdir); });
        }

        private void ConfirmAndStartRestore()
        {
            SaveConfig();
            string target = NormalizeTarget(txtTargetIp.Text);
            string bdir = txtBackupDir.Text.Trim();
            if (string.IsNullOrEmpty(bdir)) bdir = defaultBackupDir;

            if (!Directory.Exists(bdir))
            {
                MessageBox.Show(this, "Backup folder does not exist:\n" + bdir, "Backup Not Found", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            DialogResult dr = MessageBox.Show(
                this,
                string.Format("Restore selected components to {0}?\n\n" +
                    "- Sideloaded apps will be cloned directly via ADB.\n" +
                    "- Play Store apps missing on Target TV will open in Google Play on your TV for fresh hardware-matched installation.\n\n" +
                    "Backup Source Folder:\n{1}", target, bdir),
                "Confirm Restore to " + target,
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Warning);

            if (dr == DialogResult.Yes)
            {
                cancelRequested = false;
                ThreadPool.QueueUserWorkItem(delegate { RunRestoreWorkflow(target, bdir); });
            }
        }

        // ----------------------------------------------------------------------
        // Projectivy Backup & Restore Helpers
        // ----------------------------------------------------------------------
        private void PullProjectivyBackups(string target, string bdir)
        {
            string projDir = Path.Combine(bdir, "projectivy_backups");
            Directory.CreateDirectory(projDir);
            string remoteBackups = "/sdcard/Android/data/" + PROJECTIVY_PKG + "/files/backups";
            string remoteWallpapers = "/sdcard/Android/data/" + PROJECTIVY_PKG + "/files/wallpapers";

            AppendLog("Pulling Projectivy backups from " + remoteBackups + " ...");
            string outStr;
            int code = Adb(target, string.Format("pull -a \"{0}/.\" \"{1}\"", remoteBackups, projDir), out outStr, 120000);
            if (code == 0)
            {
                int cnt = Directory.GetFiles(projDir, "*.plbackup").Length;
                AppendLog(string.Format("[OK] Pulled {0} Projectivy .plbackup file(s) to {1}", cnt, projDir));
            }
            else
            {
                AppendLog("[WARN] Could not pull " + remoteBackups + ": " + outStr.Trim());
            }

            string wpDir = Path.Combine(bdir, "projectivy_wallpapers");
            Directory.CreateDirectory(wpDir);
            Adb(target, string.Format("pull -a \"{0}/.\" \"{1}\"", remoteWallpapers, wpDir), out outStr, 120000);

            string dlDir = Path.Combine(bdir, "sdcard", "Download");
            if (Directory.Exists(dlDir))
            {
                foreach (string f in Directory.GetFiles(dlDir, "*.pl*"))
                {
                    try { File.Copy(f, Path.Combine(projDir, Path.GetFileName(f)), true); } catch { }
                }
            }
        }

        private void PushAndImportProjectivyBackups(string target, string bdir)
        {
            string projDir = Path.Combine(bdir, "projectivy_backups");
            string dlDir = Path.Combine(bdir, "sdcard", "Download");
            Directory.CreateDirectory(projDir);

            if (Directory.Exists(dlDir))
            {
                foreach (string f in Directory.GetFiles(dlDir, "*.pl*"))
                {
                    string dst = Path.Combine(projDir, Path.GetFileName(f));
                    if (!File.Exists(dst))
                    {
                        try { File.Copy(f, dst, false); } catch { }
                    }
                }
            }

            string[] plFiles = Directory.GetFiles(projDir, "*.plbackup");
            if (plFiles.Length == 0)
            {
                AppendLog("[WARN] No Projectivy .plbackup files found in backup folder!");
                AppendLog("Tip: On your Source TV, open Projectivy Settings -> General -> Manage Settings -> Export Settings, then run Backup again.");
                return;
            }

            Array.Sort(plFiles, delegate(string a, string b)
            {
                return File.GetLastWriteTimeUtc(a).CompareTo(File.GetLastWriteTimeUtc(b));
            });

            string remoteFilesDir = "/sdcard/Android/data/" + PROJECTIVY_PKG + "/files";
            string remoteBackups = remoteFilesDir + "/backups";
            string outStr;

            string dirCheck = AdbOut(target, string.Format("shell \"[ -d '{0}' ] && echo yes\"", remoteFilesDir)).Trim();
            if (dirCheck != "yes")
            {
                AppendLog("Launching Projectivy once so Android initializes its external data directory...");
                Adb(target, "shell am start -n " + PROJECTIVY_PKG + "/.ui.home.MainActivity", out outStr, 20000);
                Thread.Sleep(2500);
            }

            // Clean shell-owned backups folder so Projectivy's UID retains full FUSE read/write access on Android 11-14
            string owner = AdbOut(target, string.Format("shell \"stat -c '%U' '{0}' 2>/dev/null\"", remoteBackups)).Trim();
            if (owner == "shell")
            {
                AppendLog("Cleaning shell-owned backups subfolder so Projectivy retains full read/write access...");
                Adb(target, string.Format("shell \"rm -rf '{0}' '{1}/wallpapers'\"", remoteBackups, remoteFilesDir), out outStr, 20000);
            }

            string newestPl = plFiles[plFiles.Length - 1];
            string newestName = Path.GetFileName(newestPl);
            string remoteTargetFile = remoteFilesDir + "/projectivy-restore.plbackup";

            AppendLog(string.Format("Pushing newest Projectivy backup ({0}) -> {1} ...", newestName, remoteTargetFile));
            Adb(target, string.Format("push \"{0}\" \"{1}\"", newestPl, remoteTargetFile), out outStr, 60000);
            Adb(target, string.Format("push \"{0}\" \"/sdcard/Download/{1}\"", newestPl, newestName), out outStr, 60000);

            string remoteUri = "file://" + remoteTargetFile;
            AppendLog("Triggering Projectivy ImportSettingsActivity with: " + remoteUri);

            int code = Adb(target,
                string.Format("shell am start -a android.intent.action.VIEW -d \"{0}\" -n {1}/.ui.launcherActivities.ImportSettingsActivity",
                    remoteUri, PROJECTIVY_PKG),
                out outStr, 20000);

            if (code == 0 && outStr.IndexOf("Error", StringComparison.OrdinalIgnoreCase) < 0)
            {
                AppendLog("==========================================================");
                AppendLog("[OK] Projectivy Import launched on Target TV with: " + newestName);
                AppendLog("ACTION ON TV: Click 'OK' on the Projectivy dialog on your TV screen!");
                AppendLog("(All app groupings, categories, layout & button color schemes will load immediately.)");
                AppendLog("==========================================================");
            }
            else
            {
                AppendLog("[WARN] Could not auto-launch ImportSettingsActivity: " + outStr.Trim());
            }
        }

        // ----------------------------------------------------------------------
        // Play Store vs Sideloaded Classification Helpers
        // ----------------------------------------------------------------------
        private void LoadPackageListsForRestore(
            string bdir,
            out List<string> playStorePkgs,
            out List<string> sideloadedPkgs)
        {
            playStorePkgs = new List<string>();
            sideloadedPkgs = new List<string>();

            string packagesDir = Path.Combine(bdir, "packages");
            string apksDir = Path.Combine(bdir, "apks");
            string playFile = Path.Combine(packagesDir, "playstore_packages.txt");
            string sideFile = Path.Combine(packagesDir, "sideloaded_packages.txt");
            string instFile = Path.Combine(packagesDir, "package_installers.txt");

            HashSet<string> playSet = new HashSet<string>(StringComparer.Ordinal);
            HashSet<string> sideSet = new HashSet<string>(StringComparer.Ordinal);

            if (File.Exists(playFile) || File.Exists(sideFile))
            {
                if (File.Exists(playFile))
                {
                    foreach (string l in File.ReadAllLines(playFile, Encoding.UTF8))
                    {
                        string p = l.Trim();
                        if (!string.IsNullOrEmpty(p)) playSet.Add(p);
                    }
                }
                if (File.Exists(sideFile))
                {
                    foreach (string l in File.ReadAllLines(sideFile, Encoding.UTF8))
                    {
                        string p = l.Trim();
                        if (!string.IsNullOrEmpty(p) && !playSet.Contains(p)) sideSet.Add(p);
                    }
                }
            }
            else if (File.Exists(instFile))
            {
                foreach (string l in File.ReadAllLines(instFile, Encoding.UTF8))
                {
                    string[] parts = l.Trim().Split(new char[] { ' ', '\t', '=' }, StringSplitOptions.RemoveEmptyEntries);
                    if (parts.Length >= 2)
                    {
                        string pkg = parts[0].Trim();
                        string inst = parts[1].Trim();
                        if (string.Equals(inst, PLAYSTORE_INSTALLER, StringComparison.OrdinalIgnoreCase))
                            playSet.Add(pkg);
                        else
                            sideSet.Add(pkg);
                    }
                }
            }
            else
            {
                // Legacy backup folder fallback: inspect apks/<pkg> and third_party_packages.txt
                AppendLog("[INFO] Legacy backup detected (no playstore_packages.txt found). Classifying Play Store vs. Sideloaded apps...");
                HashSet<string> allCandidates = new HashSet<string>(StringComparer.Ordinal);
                string thirdPartyFile = Path.Combine(packagesDir, "third_party_packages.txt");
                if (File.Exists(thirdPartyFile))
                {
                    foreach (string l in File.ReadAllLines(thirdPartyFile, Encoding.UTF8))
                    {
                        string p = l.Trim();
                        if (!string.IsNullOrEmpty(p)) allCandidates.Add(p);
                    }
                }
                if (Directory.Exists(apksDir))
                {
                    foreach (string d in Directory.GetDirectories(apksDir))
                    {
                        allCandidates.Add(Path.GetFileName(d));
                    }
                }

                foreach (string pkg in allCandidates)
                {
                    string pkgDir = Path.Combine(apksDir, pkg);
                    int apkCnt = Directory.Exists(pkgDir) ? Directory.GetFiles(pkgDir, "*.apk").Length : 0;
                    // All multi-APK split bundles (apkCnt > 1) or known Play Store apps come from Google Play Dynamic Delivery
                    if (KnownPlayStorePackages.Contains(pkg) || apkCnt > 1)
                        playSet.Add(pkg);
                    else
                        sideSet.Add(pkg);
                }

                // Persist the classified manifest files into packages/ so future runs have them
                try
                {
                    Directory.CreateDirectory(packagesDir);
                    List<string> pTmp = new List<string>(playSet);
                    pTmp.Sort(StringComparer.Ordinal);
                    List<string> sTmp = new List<string>(sideSet);
                    sTmp.Sort(StringComparer.Ordinal);
                    File.WriteAllText(playFile, string.Join("\n", pTmp.ToArray()) + (pTmp.Count > 0 ? "\n" : ""), Encoding.UTF8);
                    File.WriteAllText(sideFile, string.Join("\n", sTmp.ToArray()) + (sTmp.Count > 0 ? "\n" : ""), Encoding.UTF8);
                }
                catch { }
            }

            playStorePkgs.AddRange(playSet);
            playStorePkgs.Sort(StringComparer.Ordinal);
            sideloadedPkgs.AddRange(sideSet);
            sideloadedPkgs.Sort(StringComparer.Ordinal);
        }

        private void OpenPlayStoreForPackage(string target, string pkg)
        {
            string outStr;
            int code = Adb(target,
                string.Format("shell am start -a android.intent.action.VIEW -d \"market://details?id={0}\" -p {1}",
                    pkg, PLAYSTORE_INSTALLER),
                out outStr, 15000);

            if (code != 0 || outStr.IndexOf("Error", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                Adb(target,
                    string.Format("shell am start -a android.intent.action.VIEW -d \"https://play.google.com/store/apps/details?id={0}\"",
                        pkg),
                    out outStr, 15000);
            }
        }

        private void WriteBackupManifestChecklist(
            string bdir,
            string sourceTarget,
            string model,
            string ver,
            string ts,
            List<string> playStorePkgs,
            List<string> sideloadedPkgs)
        {
            try
            {
                StringBuilder sb = new StringBuilder();
                sb.AppendLine("==============================================================================");
                sb.AppendLine("  ANDROID / GOOGLE TV APP MANIFEST & DEVICE-A -> DEVICE-B CHECKLIST");
                sb.AppendLine("==============================================================================");
                sb.AppendLine(string.Format("Backup Timestamp     : {0}", ts));
                sb.AppendLine(string.Format("Source Device (A)    : {0} (Android {1}) @ {2}", model, ver, sourceTarget));
                sb.AppendLine(string.Format("Total 3rd-Party Apps : {0} ({1} Play Store + {2} Sideloaded)",
                    playStorePkgs.Count + sideloadedPkgs.Count, playStorePkgs.Count, sideloadedPkgs.Count));
                sb.AppendLine("==============================================================================");
                sb.AppendLine("INSTRUCTIONS FOR TARGET DEVICE (B):");
                sb.AppendLine("  1. Complete the initial Android/Google TV setup on Device B and allow it");
                sb.AppendLine("     to install your desired apps when prompted during setup.");
                sb.AppendLine("  2. Run 'Restore to Target TV' in the Backup & Restore app.");
                sb.AppendLine("  3. Use the checkboxes [ ] below (or check APP_RESTORE_VERIFICATION_REPORT.txt");
                sb.AppendLine("     after restore) to verify every app from Device A is installed on Device B.");
                sb.AppendLine("==============================================================================");
                sb.AppendLine();
                sb.AppendLine(string.Format("--- SECTION 1: GOOGLE PLAY STORE APPS ({0}) ---", playStorePkgs.Count));
                sb.AppendLine("(Installed fresh from Google Play on Device B to match its Android SDK & CPU)");
                sb.AppendLine();
                for (int i = 0; i < playStorePkgs.Count; i++)
                {
                    string pkg = playStorePkgs[i];
                    sb.AppendLine(string.Format("[ ] {0,2}. {1,-36} ({2})", i + 1, GetFriendlyAppName(pkg), pkg));
                }
                sb.AppendLine();
                sb.AppendLine(string.Format("--- SECTION 2: SIDELOADED APPS ({0}) ---", sideloadedPkgs.Count));
                sb.AppendLine("(Cloned automatically via ADB from apks/<package>/ during Restore)");
                sb.AppendLine();
                for (int i = 0; i < sideloadedPkgs.Count; i++)
                {
                    string pkg = sideloadedPkgs[i];
                    sb.AppendLine(string.Format("[ ] {0,2}. {1,-36} ({2})", i + 1, GetFriendlyAppName(pkg), pkg));
                }
                sb.AppendLine();
                sb.AppendLine("==============================================================================");

                string checklistPath = Path.Combine(bdir, "APP_MANIFEST_CHECKLIST.txt");
                File.WriteAllText(checklistPath, sb.ToString(), Encoding.UTF8);
                AppendLog("[OK] Created printable user checklist: " + checklistPath);
            }
            catch (Exception ex)
            {
                AppendLog("[WARN] Could not write APP_MANIFEST_CHECKLIST.txt: " + ex.Message);
            }
        }

        private void WriteRestoreVerificationReport(
            string bdir,
            string targetAddr,
            List<string> playStorePkgs,
            List<string> sideloadedPkgs,
            Dictionary<string, string> statusNotes)
        {
            try
            {
                string model = AdbOut(targetAddr, "shell getprop ro.product.model").Trim();
                string ver = AdbOut(targetAddr, "shell getprop ro.build.version.release").Trim();
                if (string.IsNullOrEmpty(model)) model = "Unknown";
                string ts = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");

                HashSet<string> finalInstalled = GetInstalledPackagesOnDevice(targetAddr);
                int totalApps = playStorePkgs.Count + sideloadedPkgs.Count;
                int confirmedInstalled = 0;
                foreach (string p in playStorePkgs) if (finalInstalled.Contains(p)) confirmedInstalled++;
                foreach (string p in sideloadedPkgs) if (finalInstalled.Contains(p)) confirmedInstalled++;

                StringBuilder sb = new StringBuilder();
                sb.AppendLine("==============================================================================");
                sb.AppendLine("  DEVICE-A -> DEVICE-B APP RESTORE VERIFICATION REPORT & CHECKLIST");
                sb.AppendLine("==============================================================================");
                sb.AppendLine(string.Format("Restore Timestamp    : {0}", ts));
                sb.AppendLine(string.Format("Target Device (B)    : {0} (Android {1}) @ {2}", model, ver, targetAddr));
                sb.AppendLine(string.Format("Verification Summary : {0} / {1} app(s) confirmed installed on Device B", confirmedInstalled, totalApps));
                sb.AppendLine("                       (Note: Play Store apps queued in background may still be downloading)");
                sb.AppendLine("==============================================================================");
                sb.AppendLine("LEGEND:");
                sb.AppendLine("  [x] = Confirmed installed on Device B");
                sb.AppendLine("  [~] = Opened/Queued in Google Play on Device B (check TV download queue)");
                sb.AppendLine("  [ ] = Not installed / Skipped / Failed");
                sb.AppendLine("==============================================================================");
                sb.AppendLine();
                sb.AppendLine(string.Format("--- SECTION 1: GOOGLE PLAY STORE APPS ({0}) ---", playStorePkgs.Count));
                sb.AppendLine();
                for (int i = 0; i < playStorePkgs.Count; i++)
                {
                    string pkg = playStorePkgs[i];
                    bool isInst = finalInstalled.Contains(pkg);
                    string note;
                    if (!statusNotes.TryGetValue(pkg, out note)) note = "";
                    string box = isInst ? "[x]" : (note.IndexOf("Queued", StringComparison.OrdinalIgnoreCase) >= 0 ? "[~]" : "[ ]");
                    string statusText = isInst
                        ? (string.IsNullOrEmpty(note) ? "INSTALLED ON DEVICE B" : note)
                        : (string.IsNullOrEmpty(note) ? "NOT INSTALLED" : note);
                    sb.AppendLine(string.Format("{0} {1,2}. {2,-34} ({3}) -> {4}",
                        box, i + 1, GetFriendlyAppName(pkg), pkg, statusText));
                }
                sb.AppendLine();
                sb.AppendLine(string.Format("--- SECTION 2: SIDELOADED APPS ({0}) ---", sideloadedPkgs.Count));
                sb.AppendLine();
                for (int i = 0; i < sideloadedPkgs.Count; i++)
                {
                    string pkg = sideloadedPkgs[i];
                    bool isInst = finalInstalled.Contains(pkg);
                    string note;
                    if (!statusNotes.TryGetValue(pkg, out note)) note = "";
                    string box = isInst ? "[x]" : "[ ]";
                    string statusText = isInst
                        ? (string.IsNullOrEmpty(note) ? "CLONED & INSTALLED ON DEVICE B" : note)
                        : (string.IsNullOrEmpty(note) ? "NOT INSTALLED" : note);
                    sb.AppendLine(string.Format("{0} {1,2}. {2,-34} ({3}) -> {4}",
                        box, i + 1, GetFriendlyAppName(pkg), pkg, statusText));
                }
                sb.AppendLine();
                sb.AppendLine("==============================================================================");

                string reportPath = Path.Combine(bdir, "APP_RESTORE_VERIFICATION_REPORT.txt");
                File.WriteAllText(reportPath, sb.ToString(), Encoding.UTF8);
                // Also ensure APP_MANIFEST_CHECKLIST.txt exists if this was a legacy backup folder
                string checklistPath = Path.Combine(bdir, "APP_MANIFEST_CHECKLIST.txt");
                if (!File.Exists(checklistPath))
                {
                    WriteBackupManifestChecklist(bdir, "Backup Folder", "Source TV", "?", ts, playStorePkgs, sideloadedPkgs);
                }
                AppendLog("==========================================================");
                AppendLog(string.Format("[OK] Verification Checklist saved to: {0}", reportPath));
                AppendLog(string.Format("     ({0}/{1} apps confirmed installed on Target TV; click 'Open Backup Folder' to view)", confirmedInstalled, totalApps));
                AppendLog("==========================================================");
            }
            catch (Exception ex)
            {
                AppendLog("[WARN] Could not write APP_RESTORE_VERIFICATION_REPORT.txt: " + ex.Message);
            }
        }

        // ----------------------------------------------------------------------
        // BACKUP WORKFLOW
        // ----------------------------------------------------------------------
        private void RunBackupWorkflow(string target, string bdir)
        {
            SetBusy(true);
            AppendLog("==========================================================");
            AppendLog("STARTING BACKUP FROM " + target);
            AppendLog("Destination: " + bdir);
            AppendLog("==========================================================");

            if (!ConnectAndAuthorize(target))
            {
                SetProgress(0, "Backup aborted: Connection failed");
                SetBusy(false);
                return;
            }

            string apksDir = Path.Combine(bdir, "apks");
            string permsDir = Path.Combine(bdir, "permissions");
            string sdcardDir = Path.Combine(bdir, "sdcard");
            string settingsDir = Path.Combine(bdir, "settings");
            string packagesDir = Path.Combine(bdir, "packages");

            Directory.CreateDirectory(apksDir);
            Directory.CreateDirectory(permsDir);
            Directory.CreateDirectory(sdcardDir);
            Directory.CreateDirectory(settingsDir);
            Directory.CreateDirectory(packagesDir);

            string model = AdbOut(target, "shell getprop ro.product.model").Trim();
            string ver = AdbOut(target, "shell getprop ro.build.version.release").Trim();
            if (string.IsNullOrEmpty(model)) model = "Unknown";
            string ts = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");

            File.WriteAllText(Path.Combine(bdir, "backup_metadata.txt"),
                string.Format("Timestamp: {0}\nSource: {1}\nModel: {2} (Android {3})\n", ts, target, model, ver),
                Encoding.UTF8);

            AppendLog(string.Format("Detected Source Device: {0} (Android {1})", model, ver));

            // 1. Classify 3rd-Party Packages (Play Store Manifest vs. Sideloaded APKs) & Permissions
            if (chkApks.Checked || chkPerms.Checked)
            {
                SetProgress(15, "Listing 3rd-party packages & installer origins...");
                string rawPkgs = AdbOut(target, "shell pm list packages -3 -i");
                List<string> pkgs = new List<string>();
                List<string> playStorePkgs = new List<string>();
                List<string> sideloadedPkgs = new List<string>();
                List<string> installerLines = new List<string>();

                Regex pkgInstRegex = new Regex(@"^package:(\S+)\s+installer=(\S+)");

                foreach (string line in rawPkgs.Split('\n'))
                {
                    string t = line.Trim();
                    if (string.IsNullOrEmpty(t)) continue;

                    string pkgName = "";
                    string installer = "null";
                    Match m = pkgInstRegex.Match(t);
                    if (m.Success)
                    {
                        pkgName = m.Groups[1].Value.Trim();
                        installer = m.Groups[2].Value.Trim();
                    }
                    else if (t.StartsWith("package:"))
                    {
                        string rest = t.Substring("package:".Length).Trim();
                        string[] tokens = rest.Split(new char[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                        if (tokens.Length > 0) pkgName = tokens[0];
                        for (int k = 1; k < tokens.Length; k++)
                        {
                            if (tokens[k].StartsWith("installer="))
                                installer = tokens[k].Substring("installer=".Length).Trim();
                        }
                    }

                    if (!string.IsNullOrEmpty(pkgName))
                    {
                        pkgs.Add(pkgName);
                        installerLines.Add(pkgName + " " + installer);
                        if (string.Equals(installer, PLAYSTORE_INSTALLER, StringComparison.OrdinalIgnoreCase))
                            playStorePkgs.Add(pkgName);
                        else
                            sideloadedPkgs.Add(pkgName);
                    }
                }

                pkgs.Sort(StringComparer.Ordinal);
                playStorePkgs.Sort(StringComparer.Ordinal);
                sideloadedPkgs.Sort(StringComparer.Ordinal);
                installerLines.Sort(StringComparer.Ordinal);

                File.WriteAllText(Path.Combine(packagesDir, "third_party_packages.txt"),
                    pkgs.Count > 0 ? string.Join("\n", pkgs.ToArray()) + "\n" : "", Encoding.UTF8);
                File.WriteAllText(Path.Combine(packagesDir, "playstore_packages.txt"),
                    playStorePkgs.Count > 0 ? string.Join("\n", playStorePkgs.ToArray()) + "\n" : "", Encoding.UTF8);
                File.WriteAllText(Path.Combine(packagesDir, "sideloaded_packages.txt"),
                    sideloadedPkgs.Count > 0 ? string.Join("\n", sideloadedPkgs.ToArray()) + "\n" : "", Encoding.UTF8);
                File.WriteAllText(Path.Combine(packagesDir, "package_installers.txt"),
                    installerLines.Count > 0 ? string.Join("\n", installerLines.ToArray()) + "\n" : "", Encoding.UTF8);

                WriteBackupManifestChecklist(bdir, target, model, ver, ts, playStorePkgs, sideloadedPkgs);

                AppendLog(string.Format("Found {0} 3rd-party app(s): {1} Play Store app(s) (manifest), {2} Sideloaded app(s) (APK clone).",
                    pkgs.Count, playStorePkgs.Count, sideloadedPkgs.Count));

                HashSet<string> sideloadSet = new HashSet<string>(sideloadedPkgs, StringComparer.Ordinal);
                List<string> allPerms = new List<string>();
                Regex permRegex = new Regex(@"^\s*(android\.permission\.[a-zA-Z0-9._]+):\s*granted=true");

                for (int i = 0; i < pkgs.Count; i++)
                {
                    if (cancelRequested) break;
                    string pkg = pkgs[i];
                    bool isSideloaded = sideloadSet.Contains(pkg);
                    int pct = 15 + (int)(45.0 * (i + 1) / Math.Max(1, pkgs.Count));
                    SetProgress(pct, string.Format("[{0}/{1}] Processing {2}...", i + 1, pkgs.Count, pkg));

                    if (chkApks.Checked)
                    {
                        if (isSideloaded)
                        {
                            AppendLog(string.Format("[{0}/{1}] Cloning sideloaded app: {2}...", i + 1, pkgs.Count, pkg));
                            string pkgDir = Path.Combine(apksDir, pkg);
                            Directory.CreateDirectory(pkgDir);
                            foreach (string oldApk in Directory.GetFiles(pkgDir, "*.apk"))
                            {
                                try { File.Delete(oldApk); } catch { }
                            }

                            string rawPaths = AdbOut(target, "shell pm path " + pkg);
                            List<string> apkPaths = new List<string>();
                            foreach (string line in rawPaths.Split('\n'))
                            {
                                string t = line.Trim();
                                if (t.StartsWith("package:"))
                                    apkPaths.Add(t.Substring("package:".Length).Trim());
                            }

                            for (int s = 0; s < apkPaths.Count; s++)
                            {
                                string remoteApk = apkPaths[s];
                                string baseName = Path.GetFileName(remoteApk);
                                string localApk = Path.Combine(pkgDir, baseName);
                                if (File.Exists(localApk))
                                    localApk = Path.Combine(pkgDir, string.Format("{0}_{1}", s + 1, baseName));

                                string pullOut;
                                int code = Adb(target, string.Format("pull \"{0}\" \"{1}\"", remoteApk, localApk), out pullOut, 300000);
                                if (code != 0)
                                    AppendLog("  [WARN] Failed pulling " + remoteApk + ": " + pullOut.Trim());
                            }
                            AppendLog(string.Format("  [OK] Pulled {0} APK file(s) for sideloaded app {1}", apkPaths.Count, pkg));
                        }
                        else
                        {
                            AppendLog(string.Format("[{0}/{1}] Recorded Play Store app in manifest: {2}", i + 1, pkgs.Count, pkg));
                        }
                    }

                    if (chkPerms.Checked)
                    {
                        string dumpOut = AdbOut(target, "shell dumpsys package " + pkg, 60000);
                        HashSet<string> granted = new HashSet<string>(StringComparer.Ordinal);
                        foreach (string line in dumpOut.Split('\n'))
                        {
                            if (line.Contains("granted=true"))
                            {
                                Match m = permRegex.Match(line);
                                if (m.Success) granted.Add(m.Groups[1].Value);
                            }
                        }
                        if (granted.Count > 0)
                        {
                            List<string> sortedG = new List<string>(granted);
                            sortedG.Sort(StringComparer.Ordinal);
                            File.WriteAllText(Path.Combine(permsDir, pkg + ".permissions"), string.Join("\n", sortedG.ToArray()) + "\n", Encoding.UTF8);
                            foreach (string perm in sortedG)
                                allPerms.Add(pkg + " " + perm);
                            AppendLog(string.Format("  [OK] Exported {0} granted runtime permission(s) for {1}", sortedG.Count, pkg));
                        }
                    }
                }

                if (chkPerms.Checked)
                {
                    File.WriteAllText(Path.Combine(permsDir, "granted_permissions.txt"),
                        allPerms.Count > 0 ? string.Join("\n", allPerms.ToArray()) + "\n" : "",
                        Encoding.UTF8);
                }
            }

            // 2. Projectivy .plbackup files
            if (!cancelRequested && chkProjectivy.Checked)
            {
                SetProgress(64, "Pulling Projectivy layout & color backups (.plbackup)...");
                PullProjectivyBackups(target, bdir);
            }

            // 3. Pull /sdcard/Download & /sdcard/Pictures
            if (!cancelRequested && chkMedia.Checked)
            {
                string[] folders = new string[] { "Download", "Pictures" };
                for (int i = 0; i < folders.Length; i++)
                {
                    string folder = folders[i];
                    SetProgress(70 + i * 7, "Pulling /sdcard/" + folder + "...");
                    string localDest = Path.Combine(sdcardDir, folder);
                    Directory.CreateDirectory(localDest);
                    AppendLog(string.Format("Pulling /sdcard/{0} -> {1} ...", folder, localDest));
                    string outStr;
                    int code = Adb(target, string.Format("pull -a \"/sdcard/{0}/.\" \"{1}\"", folder, localDest), out outStr, 300000);
                    if (code == 0)
                        AppendLog("[OK] Pulled /sdcard/" + folder);
                    else
                        AppendLog("[WARN] Pull /sdcard/" + folder + ": " + outStr.Trim());
                }
            }

            // 4. Dump system / secure / global settings
            if (!cancelRequested && chkSettings.Checked)
            {
                SetProgress(86, "Dumping system, secure, and global settings...");
                foreach (string ns in new string[] { "system", "secure", "global" })
                {
                    string outStr = AdbOut(target, "shell settings list " + ns);
                    List<string> lines = new List<string>();
                    foreach (string l in outStr.Split('\n'))
                    {
                        if (!string.IsNullOrWhiteSpace(l)) lines.Add(l.Trim());
                    }
                    lines.Sort(StringComparer.Ordinal);
                    File.WriteAllText(Path.Combine(settingsDir, ns + ".txt"), string.Join("\n", lines.ToArray()) + "\n", Encoding.UTF8);
                    AppendLog(string.Format("[OK] Saved {0} '{1}' settings", lines.Count, ns));
                }
            }

            // 5. Disabled packages list
            if (!cancelRequested && chkDebloat.Checked)
            {
                SetProgress(95, "Saving disabled packages list...");
                string rawDis = AdbOut(target, "shell pm list packages -d");
                List<string> disPkgs = new List<string>();
                foreach (string l in rawDis.Split('\n'))
                {
                    string clean = l.Replace("package:", "").Trim();
                    if (!string.IsNullOrEmpty(clean)) disPkgs.Add(clean);
                }
                disPkgs.Sort(StringComparer.Ordinal);
                File.WriteAllText(Path.Combine(packagesDir, "disabled_packages.txt"), string.Join("\n", disPkgs.ToArray()) + "\n", Encoding.UTF8);
                AppendLog(string.Format("[OK] Saved {0} disabled package(s)", disPkgs.Count));
            }

            if (cancelRequested)
            {
                SetProgress(0, "Backup cancelled");
                AppendLog("[WARN] Backup cancelled by user.");
            }
            else
            {
                SetProgress(100, "Backup Complete!");
                AppendLog("==========================================================");
                AppendLog("BACKUP COMPLETED SUCCESSFULLY!");
                AppendLog("==========================================================");
            }

            SetBusy(false);
        }

        // ----------------------------------------------------------------------
        // RESTORE WORKFLOW
        // ----------------------------------------------------------------------
        private void RunRestoreWorkflow(string target, string bdir)
        {
            SetBusy(true);
            AppendLog("==========================================================");
            AppendLog("STARTING RESTORE TO " + target);
            AppendLog("Backup Source: " + bdir);
            AppendLog("==========================================================");

            if (!ConnectAndAuthorize(target))
            {
                SetProgress(0, "Restore aborted: Connection failed");
                SetBusy(false);
                return;
            }

            string apksDir = Path.Combine(bdir, "apks");
            string permsDir = Path.Combine(bdir, "permissions");
            string sdcardDir = Path.Combine(bdir, "sdcard");
            string settingsDir = Path.Combine(bdir, "settings");
            string packagesDir = Path.Combine(bdir, "packages");
            string outStr;

            // 1. Push /sdcard/Download & /sdcard/Pictures FIRST
            if (!cancelRequested && chkMedia.Checked)
            {
                string[] folders = new string[] { "Download", "Pictures" };
                for (int i = 0; i < folders.Length; i++)
                {
                    string folder = folders[i];
                    SetProgress(5 + i * 5, "Pushing /sdcard/" + folder + "...");
                    string localSrc = Path.Combine(sdcardDir, folder);
                    if (Directory.Exists(localSrc) && Directory.GetFileSystemEntries(localSrc).Length > 0)
                    {
                        Adb(target, "shell mkdir -p /sdcard/" + folder, out outStr, 15000);
                        AppendLog(string.Format("Pushing {0} -> /sdcard/{1}/ ...", localSrc, folder));
                        int code = Adb(target, string.Format("push \"{0}\\.\" \"/sdcard/{1}/\"", localSrc, folder), out outStr, 300000);
                        if (code == 0)
                            AppendLog("[OK] Restored /sdcard/" + folder);
                        else
                            AppendLog("[WARN] Push /sdcard/" + folder + ": " + outStr.Trim());
                    }
                    else
                    {
                        AppendLog(string.Format("[INFO] {0} is empty or not present; skipping.", localSrc));
                    }
                }
            }

            // 2. Restore Sideloaded APKs via ADB & Install Play Store Apps Fresh from Google Play (Mode A)
            List<string> playStorePkgs;
            List<string> sideloadedPkgs;
            LoadPackageListsForRestore(bdir, out playStorePkgs, out sideloadedPkgs);
            Dictionary<string, string> restoreStatusNotes = new Dictionary<string, string>(StringComparer.Ordinal);

            if (!cancelRequested && chkApks.Checked)
            {
                AppendLog(string.Format("Manifest Summary: {0} Sideloaded app(s) to clone via ADB, {1} Play Store app(s) to verify/install via Google Play.",
                    sideloadedPkgs.Count, playStorePkgs.Count));

                // 2A. Clone Sideloaded Apps via install-multiple -r -g
                int sideloadInstalled = 0;
                int sideloadAttempted = 0;
                for (int i = 0; i < sideloadedPkgs.Count; i++)
                {
                    if (cancelRequested) break;
                    string pkgName = sideloadedPkgs[i];
                    string pkgDir = Path.Combine(apksDir, pkgName);
                    if (!Directory.Exists(pkgDir))
                    {
                        restoreStatusNotes[pkgName] = "SKIPPED (APK folder missing in backup)";
                        AppendLog(string.Format("  [WARN] Sideloaded APK folder missing for {0}, skipping.", pkgName));
                        continue;
                    }
                    string[] apkFiles = Directory.GetFiles(pkgDir, "*.apk");
                    if (apkFiles.Length == 0)
                    {
                        restoreStatusNotes[pkgName] = "SKIPPED (No APK files in folder)";
                        continue;
                    }

                    sideloadAttempted++;
                    Array.Sort(apkFiles, StringComparer.Ordinal);
                    int pct = 15 + (int)(20.0 * (i + 1) / Math.Max(1, sideloadedPkgs.Count));
                    SetProgress(pct, string.Format("[Sideload {0}/{1}] Installing {2}...", i + 1, sideloadedPkgs.Count, pkgName));
                    AppendLog(string.Format("[Sideload {0}/{1}] Cloning {2} ({3} APK(s))...", i + 1, sideloadedPkgs.Count, pkgName, apkFiles.Length));

                    StringBuilder quotedApks = new StringBuilder();
                    foreach (string apk in apkFiles)
                    {
                        quotedApks.Append(" \"").Append(apk).Append("\"");
                    }

                    int code = Adb(target, "install-multiple -r -g" + quotedApks.ToString(), out outStr, 300000);
                    if (code == 0)
                    {
                        sideloadInstalled++;
                        restoreStatusNotes[pkgName] = "CLONED & INSTALLED VIA ADB";
                        AppendLog("  [OK] Cloned sideloaded app: " + pkgName);
                    }
                    else
                    {
                        AppendLog("  [WARN] Retrying " + pkgName + " without -g...");
                        string outStr2;
                        int code2 = Adb(target, "install-multiple -r" + quotedApks.ToString(), out outStr2, 300000);
                        if (code2 == 0)
                        {
                            sideloadInstalled++;
                            restoreStatusNotes[pkgName] = "CLONED & INSTALLED VIA ADB (without -g)";
                            AppendLog("  [OK] Cloned sideloaded app: " + pkgName + " (without -g)");
                        }
                        else
                        {
                            restoreStatusNotes[pkgName] = "FAILED ADB CLONE (" + outStr2.Trim().Replace("\n", " ") + ")";
                            AppendLog("  [ERROR] Failed to clone sideloaded app " + pkgName + ": " + outStr2.Trim());
                        }
                    }
                }
                AppendLog(string.Format("[OK] Sideloaded APK cloning finished: {0}/{1} succeeded.", sideloadInstalled, sideloadAttempted));

                // 2B. Play Store Manifest Queue (Mode A: Fresh Install from Target TV's Google Play Store)
                if (!cancelRequested && playStorePkgs.Count > 0)
                {
                    HashSet<string> currentlyInstalled = GetInstalledPackagesOnDevice(target);
                    List<string> missingPlayPkgs = new List<string>();
                    int alreadyInstalledPlay = 0;

                    // Put Projectivy first if it's missing so the custom launcher is ready right away
                    if (playStorePkgs.Contains(PROJECTIVY_PKG) && !currentlyInstalled.Contains(PROJECTIVY_PKG))
                    {
                        missingPlayPkgs.Add(PROJECTIVY_PKG);
                    }

                    foreach (string pkg in playStorePkgs)
                    {
                        if (currentlyInstalled.Contains(pkg))
                        {
                            alreadyInstalledPlay++;
                            restoreStatusNotes[pkg] = "ALREADY INSTALLED ON DEVICE B (Setup / Pre-installed)";
                        }
                        else if (pkg != PROJECTIVY_PKG)
                        {
                            missingPlayPkgs.Add(pkg);
                        }
                    }

                    AppendLog("==========================================================");
                    AppendLog(string.Format("PLAY STORE MANIFEST CHECK: {0} already installed, {1} to install from Google Play.",
                        alreadyInstalledPlay, missingPlayPkgs.Count));
                    AppendLog("==========================================================");

                    if (missingPlayPkgs.Count > 0)
                    {
                        List<string> selectedPlayPkgs = ShowPlayStoreChecklistDialogOnUi(missingPlayPkgs);
                        HashSet<string> selectedSet = new HashSet<string>(selectedPlayPkgs, StringComparer.Ordinal);
                        foreach (string pkg in missingPlayPkgs)
                        {
                            if (!selectedSet.Contains(pkg))
                                restoreStatusNotes[pkg] = "UNCHECKED / SKIPPED BY USER IN PLAY STORE CHECKLIST";
                        }

                        if (selectedPlayPkgs.Count == 0)
                        {
                            AppendLog("[INFO] User chose not to download missing Play Store apps.");
                        }
                        else
                        {
                            AppendLog(string.Format("[INFO] User selected {0}/{1} Play Store app(s) to download.",
                                selectedPlayPkgs.Count, missingPlayPkgs.Count));
                            int playInstalledCount = 0;

                            for (int i = 0; i < selectedPlayPkgs.Count; i++)
                            {
                                if (cancelRequested) break;
                                string pkg = selectedPlayPkgs[i];
                                string friendly = GetFriendlyAppName(pkg);

                                currentlyInstalled = GetInstalledPackagesOnDevice(target);
                                if (currentlyInstalled.Contains(pkg))
                                {
                                    playInstalledCount++;
                                    restoreStatusNotes[pkg] = "INSTALLED FROM GOOGLE PLAY ON DEVICE B";
                                    AppendLog(string.Format("[Play Store {0}/{1}] {2} ({3}) is already installed!",
                                        i + 1, selectedPlayPkgs.Count, friendly, pkg));
                                    continue;
                                }

                                int pct = 35 + (int)(20.0 * (i + 1) / Math.Max(1, selectedPlayPkgs.Count));
                                SetProgress(pct, string.Format("[Play Store {0}/{1}] Queuing {2} on TV Play Store...",
                                    i + 1, selectedPlayPkgs.Count, friendly));
                                AppendLog(string.Format("[Play Store {0}/{1}] Opening Google Play Store on TV for: {2} ({3})",
                                    i + 1, selectedPlayPkgs.Count, friendly, pkg));

                                OpenPlayStoreForPackage(target, pkg);

                                // Wait 3.5s for Play Store page to load, then auto-press focused 'Install' button
                                Thread.Sleep(3500);
                                Adb(target, "shell input keyevent KEYCODE_DPAD_CENTER", out outStr, 10000);

                                bool installedNow = false;
                                for (int poll = 0; poll < 4; poll++)
                                {
                                    if (cancelRequested) break;
                                    Thread.Sleep(2000);
                                    if (GetInstalledPackagesOnDevice(target).Contains(pkg))
                                    {
                                        installedNow = true;
                                        break;
                                    }
                                }

                                if (installedNow)
                                {
                                    playInstalledCount++;
                                    restoreStatusNotes[pkg] = "INSTALLED FROM GOOGLE PLAY ON DEVICE B";
                                    AppendLog("  [OK] Confirmed installed: " + friendly + " (" + pkg + ")");
                                }
                                else
                                {
                                    restoreStatusNotes[pkg] = "QUEUED IN GOOGLE PLAY ON DEVICE B";
                                    AppendLog("  [INFO] Triggered Install in Google Play queue: " + friendly + " (" + pkg + ")");
                                }
                            }

                            // Automatic Local APK Backup Fallback for any checked app that Play Store did not finish installing
                            HashSet<string> afterPlayInstalled = GetInstalledPackagesOnDevice(target);
                            List<string> stillMissing = new List<string>();
                            foreach (string p in selectedPlayPkgs)
                            {
                                if (!afterPlayInstalled.Contains(p)) stillMissing.Add(p);
                            }

                            if (stillMissing.Count > 0 && !cancelRequested && Directory.Exists(apksDir))
                            {
                                AppendLog("==========================================================");
                                AppendLog(string.Format("Checking local APK backup fallback for {0} app(s) not yet completed by Play Store...",
                                    stillMissing.Count));
                                AppendLog("==========================================================");

                                foreach (string pkg in stillMissing)
                                {
                                    if (cancelRequested) break;
                                    string pkgDir = Path.Combine(apksDir, pkg);
                                    if (!Directory.Exists(pkgDir)) continue;
                                    string[] apkFiles = Directory.GetFiles(pkgDir, "*.apk");
                                    if (apkFiles.Length == 0) continue;

                                    Array.Sort(apkFiles, StringComparer.Ordinal);
                                    string friendly = GetFriendlyAppName(pkg);
                                    AppendLog(string.Format("  [Fallback ADB Install] Installing {0} ({1}) from local backup APKs...", friendly, pkg));

                                    StringBuilder quotedApks = new StringBuilder();
                                    foreach (string apk in apkFiles)
                                    {
                                        quotedApks.Append(" \"").Append(apk).Append("\"");
                                    }

                                    int fCode = Adb(target, "install-multiple -r -g" + quotedApks.ToString(), out outStr, 300000);
                                    if (fCode != 0)
                                    {
                                        fCode = Adb(target, "install-multiple -r" + quotedApks.ToString(), out outStr, 300000);
                                    }

                                    if (fCode == 0)
                                    {
                                        playInstalledCount++;
                                        restoreStatusNotes[pkg] = "INSTALLED VIA LOCAL APK BACKUP FALLBACK";
                                        AppendLog("  [OK] Installed " + friendly + " (" + pkg + ") from local APK backup!");
                                    }
                                    else
                                    {
                                        AppendLog("  [INFO] " + friendly + " (" + pkg + ") requires Play Store download (" + outStr.Trim() + ")");
                                    }
                                }
                            }

                            AppendLog(string.Format("[OK] Play Store manifest install finished ({0}/{1} confirmed installed).",
                                playInstalledCount, selectedPlayPkgs.Count));
                        }
                    }
                }
            }

            // 3. Re-grant runtime permissions
            if (!cancelRequested && chkPerms.Checked)
            {
                SetProgress(65, "Re-granting runtime permissions...");
                string permFile = Path.Combine(permsDir, "granted_permissions.txt");
                int grantedCnt = 0;
                if (File.Exists(permFile))
                {
                    HashSet<string> installedNow = GetInstalledPackagesOnDevice(target);
                    foreach (string line in File.ReadAllLines(permFile, Encoding.UTF8))
                    {
                        if (cancelRequested) break;
                        string[] parts = line.Trim().Split(new char[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                        if (parts.Length == 2 && installedNow.Contains(parts[0]))
                        {
                            int code = Adb(target, string.Format("shell pm grant {0} {1}", parts[0], parts[1]), out outStr, 15000);
                            if (code == 0) grantedCnt++;
                        }
                    }
                    AppendLog(string.Format("[OK] Re-applied {0} runtime permission grant(s).", grantedCnt));
                }
            }

            // 4. Apply safe settings
            if (!cancelRequested && chkSettings.Checked)
            {
                SetProgress(75, "Applying safe system, secure, and global settings...");
                Regex keyPattern = new Regex(@"^[a-zA-Z0-9_.:-]+$");
                foreach (string ns in new string[] { "system", "secure", "global" })
                {
                    string sfile = Path.Combine(settingsDir, ns + ".txt");
                    if (!File.Exists(sfile)) continue;
                    int applied = 0;
                    int filtered = 0;

                    foreach (string line in File.ReadAllLines(sfile, Encoding.UTF8))
                    {
                        if (cancelRequested) break;
                        int eq = line.IndexOf('=');
                        if (eq <= 0) continue;
                        string key = line.Substring(0, eq).Trim();
                        string val = line.Substring(eq + 1).Trim();
                        if (string.IsNullOrEmpty(key) || !keyPattern.IsMatch(key) || string.IsNullOrEmpty(val) || val == "null")
                            continue;

                        if (FilteredSettingsKeys.Contains(key))
                        {
                            AppendLog("  [FILTERED] Skipping " + ns + ":" + key);
                            filtered++;
                            continue;
                        }

                        int code = Adb(target, string.Format("shell settings put {0} {1} \"{2}\"", ns, key, val.Replace("\"", "\\\"")), out outStr, 10000);
                        if (code == 0) applied++;
                    }
                    AppendLog(string.Format("[OK] Namespace '{0}': applied {1} setting(s), filtered {2} key(s).", ns, applied, filtered));
                }
            }

            // 5. Re-disable stock launcher & bloatware, then trigger HOME intent
            if (!cancelRequested && chkDebloat.Checked)
            {
                SetProgress(90, "Disabling stock launcher & bloatware, launching Projectivy...");
                HashSet<string> toDisable = new HashSet<string>(StringComparer.Ordinal);
                toDisable.Add(STOCK_LAUNCHER);

                string disFile = Path.Combine(packagesDir, "disabled_packages.txt");
                if (File.Exists(disFile))
                {
                    foreach (string line in File.ReadAllLines(disFile, Encoding.UTF8))
                    {
                        if (!string.IsNullOrWhiteSpace(line)) toDisable.Add(line.Trim());
                    }
                }

                HashSet<string> installedSet = GetInstalledPackagesOnDevice(target);

                if (installedSet.Contains(PROJECTIVY_PKG))
                {
                    Adb(target, string.Format("shell cmd package set-home-activity {0}/.ui.home.MainActivity", PROJECTIVY_PKG), out outStr, 20000);
                }

                int disabledCnt = 0;
                List<string> sortedDis = new List<string>(toDisable);
                sortedDis.Sort(StringComparer.Ordinal);
                foreach (string pkg in sortedDis)
                {
                    if (!installedSet.Contains(pkg)) continue;
                    // Safety check: do not disable the stock launcher unless Projectivy is installed!
                    if ((pkg == STOCK_LAUNCHER || pkg == "com.google.android.tvlauncher") && !installedSet.Contains(PROJECTIVY_PKG))
                    {
                        AppendLog("  [WARN] Projectivy is not installed yet; keeping stock launcher enabled (" + pkg + ") so TV has a home screen.");
                        continue;
                    }
                    int code = Adb(target, "shell pm disable-user --user 0 " + pkg, out outStr, 20000);
                    if (code == 0)
                    {
                        disabledCnt++;
                        AppendLog("  [OK] Disabled " + pkg);
                    }
                    else
                    {
                        AppendLog("  [WARN] Could not disable " + pkg);
                    }
                }

                if (installedSet.Contains(SETUP_WRAITH) && installedSet.Contains(PROJECTIVY_PKG))
                {
                    Adb(target, "shell pm disable-user --user 0 " + SETUP_WRAITH, out outStr, 20000);
                }

                AppendLog("Triggering HOME intent to launch Projectivy...");
                Adb(target, "shell am start -a android.intent.action.MAIN -c android.intent.category.HOME", out outStr, 15000);
                Adb(target, "shell input keyevent KEYCODE_HOME", out outStr, 15000);
                AppendLog(string.Format("[OK] Disabled {0} package(s) and triggered HOME intent.", disabledCnt));
            }

            // 6. Push Projectivy .plbackup files & trigger ImportSettingsActivity
            if (!cancelRequested && chkProjectivy.Checked)
            {
                SetProgress(96, "Restoring Projectivy layout, app groupings & button colors...");
                PushAndImportProjectivyBackups(target, bdir);
            }

            // 7. Write Final Device-A -> Device-B Verification Checklist Report
            if (!cancelRequested && (playStorePkgs.Count > 0 || sideloadedPkgs.Count > 0))
            {
                WriteRestoreVerificationReport(bdir, target, playStorePkgs, sideloadedPkgs, restoreStatusNotes);
            }

            if (cancelRequested)
            {
                SetProgress(0, "Restore cancelled");
                AppendLog("[WARN] Restore cancelled by user.");
            }
            else
            {
                SetProgress(100, "Restore Complete!");
                AppendLog("==========================================================");
                AppendLog("RESTORE COMPLETED SUCCESSFULLY!");
                AppendLog("==========================================================");
            }

            SetBusy(false);
        }

        [STAThread]
        public static void Main()
        {
            try { SetProcessDPIAware(); } catch { }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm());
        }
    }
}
