using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal static class Program
{
    private const string Port = "7863";
    private const string StaticVersion = "20260614-v3-71";
    private const string HealthUrl = "http://127.0.0.1:" + Port + "/startup";
    private const string AppUrl = "http://127.0.0.1:" + Port + "/?v=" + StaticVersion;
    private static string LastHealthError = "";

    [STAThread]
    private static int Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        Process serverProcess = null;
        bool startedServer = false;
        try
        {
            Log(root, "launcher start version=" + StaticVersion + " root=" + root);
            if (!HealthOk())
            {
                Log(root, "initial startup check failed: " + LastHealthError);
                serverProcess = StartServer(root);
                startedServer = serverProcess != null;
                Log(root, "server start requested pid=" + (serverProcess == null ? "none" : serverProcess.Id.ToString()));
            }
            else
            {
                Log(root, "initial startup check ok");
            }

            if (!WaitForHealth(root))
            {
                MessageBox.Show(
                    "WebGUI.v3 server did not start.\r\n\r\n" + ReadFailureLogs(root) + "\r\n\r\nIf this is the first run, run run_webgork_app.bat once to install dependencies.",
                    "WebGUI.v3",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return 1;
            }

            Log(root, "startup check ok");
            Process chromeProcess = OpenChromeApp(root);
            Log(root, "chrome app opened pid=" + (chromeProcess == null ? "external-or-default-browser" : chromeProcess.Id.ToString()));
            if (startedServer)
            {
                WaitForChromeAppExit(chromeProcess);
                Log(root, "chrome app exited; stopping started server");
                StopStartedServer(serverProcess);
            }
            Log(root, "launcher finished");
            return 0;
        }
        catch (Exception ex)
        {
            Log(root, "fatal exception: " + ex.ToString());
            MessageBox.Show(
                "Failed to start WebGUI.v3.\r\n\r\n" + ex.Message + "\r\n\r\n" + ReadFailureLogs(root),
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
        catch (Exception ex)
        {
            LastHealthError = ex.GetType().Name + ": " + ex.Message;
            return false;
        }
    }

    private static bool WaitForHealth(string root)
    {
        for (int i = 0; i < 80; i++)
        {
            if (HealthOk()) return true;
            if (i == 0 || i % 10 == 9)
            {
                Log(root, "waiting for startup attempt=" + (i + 1).ToString() + " last_error=" + LastHealthError);
            }
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
            Log(root, "python not found before server start");
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

        Log(root, "starting server with " + info.FileName + " " + info.Arguments);
        return Process.Start(info);
    }

    private static string ReadFailureLogs(string root)
    {
        string launcher = TailFile(Path.Combine(root, "work", "webgui-launcher.log"), 5000);
        string server = TailFile(Path.Combine(root, "work", "server-runner.log"), 5000);
        string message = "";
        if (!String.IsNullOrEmpty(launcher))
        {
            message += "Recent webgui-launcher.log:\r\n" + launcher + "\r\n\r\n";
        }
        if (!String.IsNullOrEmpty(server))
        {
            message += "Recent server-runner.log:\r\n" + server + "\r\n";
        }
        if (String.IsNullOrEmpty(message))
        {
            message = "No launcher/server log was found yet. Check the work folder.";
        }
        return message;
    }

    private static string TailFile(string path, int maxChars)
    {
        try
        {
            if (!File.Exists(path)) return "";
            string text = Encoding.UTF8.GetString(ReadAllBytesShared(path));
            text = text.Replace("\n", "\r\n").Replace("\r\r\n", "\r\n");
            if (text.Length <= maxChars) return text;
            return text.Substring(text.Length - maxChars);
        }
        catch (Exception ex)
        {
            return "Could not read " + path + ": " + ex.Message;
        }
    }

    private static byte[] ReadAllBytesShared(string path)
    {
        using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
        using (MemoryStream memory = new MemoryStream())
        {
            stream.CopyTo(memory);
            return memory.ToArray();
        }
    }

    private static void Log(string root, string message)
    {
        try
        {
            string work = Path.Combine(root, "work");
            Directory.CreateDirectory(work);
            string path = Path.Combine(work, "webgui-launcher.log");
            string line = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff zzz") + " " + message + Environment.NewLine;
            byte[] bytes = Encoding.UTF8.GetBytes(line);
            using (FileStream stream = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.ReadWrite | FileShare.Delete))
            {
                stream.Write(bytes, 0, bytes.Length);
            }
        }
        catch
        {
        }
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
