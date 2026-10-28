// Compile beside installer.cs with /main:VerifyInstaller; never bundled.
using System;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
internal static class VerifyInstaller {
    [STAThread]
    static int Main() {
        Application.EnableVisualStyles();
        using (var form = new InstallWindow()) {
            form.Show(); Application.DoEvents();
            var checkbox = form.Controls.OfType<CheckBox>().Single();
            if (!checkbox.Checked || !checkbox.Visible) throw new Exception("Missing default desktop choice");
            checkbox.Checked = false;
            if (checkbox.Checked) throw new Exception("Cannot opt out");
            using (var bitmap = new Bitmap(form.Width, form.Height)) {
                form.DrawToBitmap(bitmap, new Rectangle(0, 0, form.Width, form.Height));
                bitmap.Save("installer-preview.png");
            }
            form.Controls.OfType<Button>().Single(b => b.Text == "취소").PerformClick();
            if (form.Result != 1 || form.Visible) throw new Exception("Cancel must not install");
        }
        Console.WriteLine("Installer choice and cancellation verification passed.");
        return 0;
    }
}
