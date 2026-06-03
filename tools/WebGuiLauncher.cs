using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    private static int Main()
    {
        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        string launcherBat = Path.Combine(baseDir, "run_webgork_app.bat");

        if (!File.Exists(launcherBat))
        {
            MessageBox.Show(
                "run_webgork_app.bat was not found next to this launcher.",
                "WebGUI.v3",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 1;
        }

        try
        {
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = launcherBat,
                WorkingDirectory = baseDir,
                UseShellExecute = true,
                WindowStyle = ProcessWindowStyle.Minimized,
            };
            Process.Start(startInfo);
            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "Failed to start WebGUI.v3.\r\n\r\n" + ex.Message,
                "WebGUI.v3",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 1;
        }
    }
}
