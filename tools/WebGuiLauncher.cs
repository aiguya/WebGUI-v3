using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Threading;
using System.Windows.Forms;

internal static class Program
{
    private const string Port = "7863";
    private const string StaticVersion = "20260612-v3-70";
    private const string HealthUrl = "http://127.0.0.1:" + Port + "/health";
    private const string AppUrl = "http://127.0.0.1:" + Port + "/?v=" + StaticVersion;

    [STAThread]
    private static int Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        Process serverProcess = null;
        bool startedServer = false;
        try
        {
            if (!HealthOk())
            {
                serverProcess = StartServer(root);
                startedServer = serverProcess != null;
            }

            if (!WaitForHealth())
            {
                string logPath = Path.Combine(root, "work", "server-runner.log");
                MessageBox.Show(
                    "WebGUI.v3 server did not start.\r\n\r\nCheck the log:\r\n" + logPath + "\r\n\r\nIf this is the first run, run run_webgork_app.bat once to install dependencies.",
                    "WebGUI.v3",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return 1;
            }

            Process chromeProcess = OpenChromeApp(root);
            if (startedServer)
            {
                WaitForChromeAppExit(chromeProcess);
                StopStartedServer(serverProcess);
            }
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

    private static bool HealthOk()
    {
        try
        {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(HealthUrl);
            request.Method = "GET";
            request.Timeout = 1500;
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            {
                return (int)response.StatusCode >= 200 && (int)response.StatusCode < 300;
            }
        }
        catch
        {
            return false;
        }
    }

    private static bool WaitForHealth()
    {
        for (int i = 0; i < 80; i++)
        {
            if (HealthOk()) return true;
            Thread.Sleep(500);
        }
        return false;
    }

    private static Process StartServer(string root)
    {
        Directory.CreateDirectory(Path.Combine(root, "work"));
        string python = FindPython();
        if (String.IsNullOrEmpty(python))
        {
            throw new InvalidOperationException("Python was not found. Install Python 3.11+ or run run_webgork_app.bat for setup.");
        }

        string script = File.Exists(Path.Combine(root, "work", "run_server.py"))
            ? "work\\run_server.py"
            : "app.py";

        ProcessStartInfo info = new ProcessStartInfo();
        info.WorkingDirectory = root;
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        info.WindowStyle = ProcessWindowStyle.Minimized;
        info.EnvironmentVariables["WEBGORK_OPEN_BROWSER"] = "0";
        info.EnvironmentVariables["WEBGORK_PORT"] = Port;

        if (Path.GetFileName(python).Equals("py.exe", StringComparison.OrdinalIgnoreCase))
        {
            info.FileName = python;
            info.Arguments = "-3 " + script;
        }
        else
        {
            info.FileName = python;
            info.Arguments = script;
        }

        return Process.Start(info);
    }

    private static string FindPython()
    {
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        string programFilesX86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        string[] candidates = new string[]
        {
            Path.Combine(localAppData, "Python", "bin", "python.exe"),
            Path.Combine(localAppData, "Python", "pythoncore-3.14-64", "python.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python314", "python.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python313", "python.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python312", "python.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python311", "python.exe"),
            Path.Combine(programFiles, "Python314", "python.exe"),
            Path.Combine(programFiles, "Python313", "python.exe"),
            Path.Combine(programFiles, "Python312", "python.exe"),
            Path.Combine(programFiles, "Python311", "python.exe"),
            Path.Combine(programFilesX86, "Python314", "python.exe"),
            Path.Combine(programFilesX86, "Python313", "python.exe"),
            Path.Combine(programFilesX86, "Python312", "python.exe"),
            Path.Combine(programFilesX86, "Python311", "python.exe")
        };

        foreach (string item in candidates)
        {
            if (AcceptPython(item, false)) return item;
        }

        foreach (string item in FindAllOnPath("python.exe"))
        {
            if (AcceptPython(item, false)) return item;
        }

        foreach (string item in FindAllOnPath("py.exe"))
        {
            if (AcceptPython(item, true)) return item;
        }

        return "";
    }

    private static bool AcceptPython(string path, bool pythonLauncher)
    {
        if (String.IsNullOrEmpty(path)) return false;
        if (!File.Exists(path)) return false;
        if (path.IndexOf("\\Microsoft\\WindowsApps\\", StringComparison.OrdinalIgnoreCase) >= 0) return false;

        ProcessStartInfo info = new ProcessStartInfo();
        info.FileName = path;
        info.Arguments = pythonLauncher
            ? "-3 -c \"import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)\""
            : "-c \"import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)\"";
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        try
        {
            using (Process process = Process.Start(info))
            {
                if (process == null) return false;
                if (!process.WaitForExit(5000))
                {
                    try { process.Kill(); } catch { }
                    return false;
                }
                return process.ExitCode == 0;
            }
        }
        catch
        {
            return false;
        }
    }

    private static string FindChrome()
    {
        string[] candidates = new string[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Google", "Chrome", "Application", "chrome.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Google", "Chrome", "Application", "chrome.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Google", "Chrome", "Application", "chrome.exe")
        };

        foreach (string item in candidates)
        {
            if (File.Exists(item)) return item;
        }

        return FindOnPath("chrome.exe");
    }

    private static string FindOnPath(string fileName)
    {
        string path = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string dir in path.Split(Path.PathSeparator))
        {
            try
            {
                if (String.IsNullOrWhiteSpace(dir)) continue;
                string full = Path.Combine(dir.Trim(), fileName);
                if (File.Exists(full)) return full;
            }
            catch
            {
            }
        }
        return "";
    }

    private static string[] FindAllOnPath(string fileName)
    {
        List<string> matches = new List<string>();
        string path = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string dir in path.Split(Path.PathSeparator))
        {
            try
            {
                if (String.IsNullOrWhiteSpace(dir)) continue;
                string full = Path.Combine(dir.Trim(), fileName);
                if (File.Exists(full)) matches.Add(full);
            }
            catch
            {
            }
        }
        return matches.ToArray();
    }

    private static Process OpenChromeApp(string root)
    {
        string chrome = FindChrome();
        if (!String.IsNullOrEmpty(chrome))
        {
            string profile = Path.Combine(root, ".webgui-chrome-app-profile");
            Directory.CreateDirectory(profile);
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = chrome;
            info.Arguments = "--user-data-dir=\"" + profile + "\" --no-first-run --app=\"" + AppUrl + "\" --new-window --class=WebGUIv3";
            info.UseShellExecute = false;
            return Process.Start(info);
        }

        ProcessStartInfo fallback = new ProcessStartInfo(AppUrl);
        fallback.UseShellExecute = true;
        Process.Start(fallback);
        return null;
    }

    private static void WaitForChromeAppExit(Process chromeProcess)
    {
        if (chromeProcess == null) return;
        try
        {
            chromeProcess.WaitForExit();
        }
        catch
        {
        }
    }

    private static void StopStartedServer(Process serverProcess)
    {
        if (serverProcess == null) return;
        try
        {
            if (serverProcess.HasExited) return;
            try
            {
                serverProcess.CloseMainWindow();
            }
            catch
            {
            }
            if (!serverProcess.WaitForExit(1500))
            {
                serverProcess.Kill();
                serverProcess.WaitForExit(5000);
            }
        }
        catch
        {
        }
    }
}
