// Small Windows installer front end. Velopack remains the installer/updater.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;

internal static class Installer {
    [STAThread]
    private static int Main() {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        using (var window = new InstallWindow()) {
            Application.Run(window);
            return window.Result;
        }
    }
}

internal sealed class InstallWindow : Form {
    internal int Result = 1;
    private readonly CheckBox desktop;
    private readonly Button install;
    private readonly Button cancel;
    private readonly Label status;
    private bool installing;

    internal InstallWindow() {
        Text = "바꾸리 설치";
        Icon = Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location);
        Font = new Font("Malgun Gothic", 10);
        AutoScaleMode = AutoScaleMode.Dpi;
        ClientSize = new Size(450, 205);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false; MinimizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        var title = new Label { Text = "바꾸리를 설치합니다.", AutoSize = true, Location = new Point(24, 24) };
        desktop = new CheckBox { Text = "바탕화면에 바로가기 만들기", Checked = true, AutoSize = true, Location = new Point(24, 67) };
        status = new Label { Text = "설치가 끝나면 바꾸리가 열립니다.", AutoSize = false, Location = new Point(24, 105), Size = new Size(402, 40) };
        install = new Button { Text = "설치", Location = new Point(240, 157), Size = new Size(88, 32) };
        cancel = new Button { Text = "취소", Location = new Point(338, 157), Size = new Size(88, 32) };
        install.Click += async (sender, args) => await Install();
        cancel.Click += (sender, args) => Close();
        FormClosing += (sender, args) => { if (installing) args.Cancel = true; };
        AcceptButton = install; CancelButton = cancel;
        Controls.AddRange(new Control[] { title, desktop, status, install, cancel });
    }

    private async Task Install() {
        bool shortcut = desktop.Checked;
        installing = true; install.Enabled = false; cancel.Enabled = false; desktop.Enabled = false;
        status.Text = "설치 중입니다. 잠시 기다려 주세요.";
        string folder = Path.Combine(Path.GetTempPath(), "BakuriSetup-" + Guid.NewGuid().ToString("N"));
        try {
            int code = await Task.Run(() => {
                Directory.CreateDirectory(folder);
                string setup = Path.Combine(folder, "Setup.exe");
                using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("Bakuri.Setup"))
                using (var file = new FileStream(setup, FileMode.CreateNew, FileAccess.Write)) {
                    if (payload == null) throw new IOException("Missing installer payload");
                    payload.CopyTo(file);
                }
                var start = new ProcessStartInfo(setup, "-- --desktop-shortcut=" + (shortcut ? "1" : "0")) {
                    UseShellExecute = false, WorkingDirectory = folder
                };
                using (Process process = Process.Start(start)) { process.WaitForExit(); return process.ExitCode; }
            });
            if (code != 0) throw new IOException("Installer exit: " + code);
            Result = 0; installing = false; Close();
        } catch (Exception) {
            status.Text = "설치하지 못했습니다. 실행 중인 바꾸리를 종료한 뒤 다시 시도해 주세요.";
            installing = false; install.Enabled = true; cancel.Enabled = true; desktop.Enabled = true;
        } finally {
            try { if (Directory.Exists(folder)) Directory.Delete(folder, true); } catch (IOException) { } catch (UnauthorizedAccessException) { }
        }
    }
}
