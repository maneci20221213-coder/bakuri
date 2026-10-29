// Windows installer front end. Installation and app launch are separate phases.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;

internal static class Installer {
    [STAThread]
    private static int Main(string[] args) {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        if (Array.IndexOf(args, "--silent") >= 0) {
            string destination = null;
            int index = Array.IndexOf(args, "--installto");
            if (index >= 0 && index + 1 < args.Length) destination = args[index + 1];
            var job = new InstallJob(destination);
            try { job.Run(Array.IndexOf(args, "--desktop-shortcut=0") < 0, true, delegate(string text) {}); return 0; }
            catch (Exception error) { job.Record(error.ToString()); return 1; }
        }
        using (var window = new InstallWindow()) {
            Application.Run(window);
            return window.Result;
        }
    }
}

internal sealed class InstallJob {
    internal readonly string LogFolder;
    private readonly string destination;
    internal InstallJob(string target = null) {
        destination = target ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Bakuri.FileConverter");
        LogFolder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Bakuri", "SetupLogs", DateTime.Now.ToString("yyyyMMdd-HHmmss") + "-" + Guid.NewGuid().ToString("N"));
    }
    internal void Record(string text) {
        try { Directory.CreateDirectory(LogFolder); File.AppendAllText(Path.Combine(LogFolder, "installer.log"), DateTime.Now.ToString("O") + " " + text + Environment.NewLine); } catch (IOException) {} catch (UnauthorizedAccessException) {}
    }
    internal static int WaitForCompletion(Process process, int timeoutMilliseconds) {
        if (!process.WaitForExit(timeoutMilliseconds)) throw new TimeoutException("The installation process is still running. Its files and logs were preserved.");
        return process.ExitCode;
    }
    internal void Run(bool shortcut, bool background, Action<string> progress) {
        Record("Destination: " + destination);
        // Silent repair can stop installed processes. Refuse to start while the
        // app is running, rather than silently interrupting a conversion.
        foreach (var process in Process.GetProcessesByName("BakuriFileConverter")) {
            using (process) { if (!process.HasExited) throw new InvalidOperationException("바꾸리를 완전 종료한 뒤 다시 설치해 주세요."); }
        }
        string folder = Path.Combine(Path.GetTempPath(), "BakuriSetup-" + Guid.NewGuid().ToString("N"));
        bool keepPayload = false;
        try {
            progress("설치 파일을 준비하고 있습니다."); Record("Preparing payload: " + folder);
            Directory.CreateDirectory(folder);
            string setup = Path.Combine(folder, "Setup.exe");
            using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("Bakuri.Setup"))
            using (var file = new FileStream(setup, FileMode.CreateNew, FileAccess.Write)) {
                if (payload == null) throw new IOException("Missing installer payload");
                payload.CopyTo(file);
            }
            progress("프로그램을 설치하고 있습니다."); Record("Starting inner installer");
            // A single visible front end; no hidden repair/hook warning dialog
            // and no implicit first app launch inside the installer process.
            string arguments = "--silent --log \"" + Path.Combine(LogFolder, "velopack.log") + "\" --installto \"" + destination.TrimEnd('\\') + "\"";
            var start = new ProcessStartInfo(setup, arguments) { UseShellExecute = false, WorkingDirectory = folder, CreateNoWindow = true };
            int code;
            using (Process process = Process.Start(start)) {
                Record("Inner installer PID: " + process.Id);
                try { code = WaitForCompletion(process, 180000); }
                catch (TimeoutException) { keepPayload = true; throw; }
            }
            Record("Inner installer exit: " + code);
            if (code != 0) throw new IOException("Installer exit: " + code);
            string executable = Path.Combine(destination, "current", "BakuriFileConverter.exe");
            if (!File.Exists(executable) || !File.Exists(Path.Combine(destination, "Update.exe"))) throw new IOException("Installed executable missing");
            progress("설치가 끝났습니다. 바꾸리를 실행합니다."); Record("Installation complete; starting app separately");
            using (Process app = Process.Start(new ProcessStartInfo(executable, "--desktop-shortcut=" + (shortcut ? "1" : "0") + (background ? " --background" : "")) { UseShellExecute = false, WorkingDirectory = Path.GetDirectoryName(executable) })) {
                Record("Started app PID: " + app.Id);
            }
        } catch (Exception error) { Record(error.ToString()); throw; }
        finally {
            if (!keepPayload) { try { if (Directory.Exists(folder)) Directory.Delete(folder, true); } catch (IOException) {} catch (UnauthorizedAccessException) {} }
        }
    }
}

internal sealed class InstallWindow : Form {
    internal int Result = 1;
    private readonly CheckBox desktop;
    private readonly Button install;
    private readonly Button cancel;
    private readonly Button logs;
    private readonly Label status;
    private bool installing;
    private string phase;
    private readonly Timer timer;
    private readonly Stopwatch elapsed = new Stopwatch();
    private InstallJob job;

    internal InstallWindow() {
        Text = "바꾸리 설치";
        Icon = Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location);
        Font = new Font("Malgun Gothic", 10);
        AutoScaleMode = AutoScaleMode.Dpi;
        ClientSize = new Size(450, 240);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false; MinimizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        var title = new Label { Text = "바꾸리를 설치합니다.", AutoSize = true, Location = new Point(24, 24) };
        desktop = new CheckBox { Text = "바탕화면에 바로가기 만들기", Checked = true, AutoSize = true, Location = new Point(24, 67) };
        status = new Label { Text = "작업 중인 바꾸리를 완전 종료한 뒤 설치해 주세요.", AutoSize = false, Location = new Point(24, 105), Size = new Size(402, 80) };
        logs = new Button { Text = "설치 기록", Enabled = false, Location = new Point(24, 195), Size = new Size(100, 32) };
        install = new Button { Text = "설치", Location = new Point(240, 195), Size = new Size(88, 32) };
        cancel = new Button { Text = "취소", Location = new Point(338, 195), Size = new Size(88, 32) };
        timer = new Timer { Interval = 1000 };
        timer.Tick += (sender, args) => { status.Text = phase + "\n경과 시간: " + (int)elapsed.Elapsed.TotalSeconds + "초"; };
        logs.Click += (sender, args) => { try { Directory.CreateDirectory(job.LogFolder); Process.Start(new ProcessStartInfo(job.LogFolder) { UseShellExecute = true }); } catch (Exception) { MessageBox.Show(this, "설치 기록 폴더를 열지 못했습니다.", "바꾸리 설치"); } };
        install.Click += async (sender, args) => await Install();
        cancel.Click += (sender, args) => Close();
        FormClosing += (sender, args) => { if (installing) args.Cancel = true; };
        AcceptButton = install; CancelButton = cancel;
        Controls.AddRange(new Control[] { title, desktop, status, logs, install, cancel });
    }

    private async Task Install() {
        bool shortcut = desktop.Checked;
        job = new InstallJob(); logs.Enabled = true;
        installing = true; install.Enabled = false; cancel.Enabled = false; desktop.Enabled = false;
        phase = "설치 파일을 준비하고 있습니다."; status.Text = phase; elapsed.Restart(); timer.Start();
        var progress = new Progress<string>(text => phase = text);
        bool timedOut = false;
        bool succeeded = false;
        try {
            await Task.Run(() => job.Run(shortcut, false, text => ((IProgress<string>)progress).Report(text)));
            Result = 0; succeeded = true;
        } catch (TimeoutException) {
            timedOut = true;
            status.Text = "설치가 3분 안에 끝나지 않았습니다. 설치 기록을 확인해 주세요.\n내부 설치가 계속 실행 중일 수 있으니 설치를 반복하지 마세요.";
        } catch (Exception error) {
            job.Record(error.ToString());
            status.Text = error is InvalidOperationException ? error.Message : "설치 또는 프로그램 실행을 완료하지 못했습니다.\n설치 기록을 확인해 주세요.";
        } finally {
            timer.Stop(); elapsed.Stop(); installing = false;
            install.Enabled = !timedOut; cancel.Enabled = true; desktop.Enabled = !timedOut; cancel.Text = "닫기";
        }
        if (succeeded) Close();
    }
    protected override void Dispose(bool disposing) { if (disposing) timer.Dispose(); base.Dispose(disposing); }
}
