[CmdletBinding()]
param(
    [string]$OutputPath = "WebGUI.v3.exe",
    [string]$IconPath = "static\icon.ico"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

function New-WebGuiIcon {
    param([string]$TargetPath)

    Add-Type -AssemblyName System.Drawing
    $iconDir = Split-Path -Parent $TargetPath
    if ($iconDir) {
        New-Item -ItemType Directory -Force -Path $iconDir | Out-Null
    }

    $bitmap = New-Object System.Drawing.Bitmap 256, 256
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([System.Drawing.Color]::Transparent)

    $bg = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#050505"))
    $fg = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml("#f4f4f2"))

    $rect = New-Object System.Drawing.RectangleF 8, 8, 240, 240
    $radius = 52
    $roundPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $roundPath.AddArc($rect.X, $rect.Y, $radius, $radius, 180, 90)
    $roundPath.AddArc($rect.Right - $radius, $rect.Y, $radius, $radius, 270, 90)
    $roundPath.AddArc($rect.Right - $radius, $rect.Bottom - $radius, $radius, $radius, 0, 90)
    $roundPath.AddArc($rect.X, $rect.Bottom - $radius, $radius, $radius, 90, 90)
    $roundPath.CloseFigure()
    $graphics.FillPath($bg, $roundPath)

    $points = @(
        [System.Drawing.PointF]::new(58, 178),
        [System.Drawing.PointF]::new(58, 78),
        [System.Drawing.PointF]::new(89, 78),
        [System.Drawing.PointF]::new(128, 135),
        [System.Drawing.PointF]::new(167, 78),
        [System.Drawing.PointF]::new(198, 78),
        [System.Drawing.PointF]::new(198, 178),
        [System.Drawing.PointF]::new(168, 178),
        [System.Drawing.PointF]::new(168, 123),
        [System.Drawing.PointF]::new(141, 164),
        [System.Drawing.PointF]::new(116, 164),
        [System.Drawing.PointF]::new(88, 123),
        [System.Drawing.PointF]::new(88, 178)
    )
    $graphics.FillPolygon($fg, $points)
    $graphics.FillEllipse($fg, 184, 42, 30, 30)

    $pngStream = New-Object System.IO.MemoryStream
    $bitmap.Save($pngStream, [System.Drawing.Imaging.ImageFormat]::Png)
    $pngBytes = $pngStream.ToArray()

    $file = [System.IO.File]::Open($TargetPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
    $writer = New-Object System.IO.BinaryWriter $file
    try {
        $writer.Write([UInt16]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]1)
        $writer.Write([Byte]0)
        $writer.Write([Byte]0)
        $writer.Write([Byte]0)
        $writer.Write([Byte]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]32)
        $writer.Write([UInt32]$pngBytes.Length)
        $writer.Write([UInt32]22)
        $writer.Write($pngBytes)
    }
    finally {
        $writer.Dispose()
        $file.Dispose()
        $pngStream.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
        $bg.Dispose()
        $fg.Dispose()
        $roundPath.Dispose()
    }
}

$cscCandidates = @(
    "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework64\v3.5\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v3.5\csc.exe"
)
$csc = $cscCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $csc) {
    throw "C# compiler was not found."
}

New-WebGuiIcon -TargetPath $IconPath

$source = Join-Path $root "tools\WebGuiLauncher.cs"
if (-not (Test-Path -LiteralPath $source)) {
    throw "Launcher source was not found: $source"
}

$compilerArgs = @(
    "/nologo",
    "/target:winexe",
    "/platform:anycpu",
    "/optimize+",
    "/win32icon:$IconPath",
    "/out:$OutputPath",
    "/reference:System.dll",
    "/reference:System.Windows.Forms.dll",
    $source
)

& $csc @compilerArgs
if ($LASTEXITCODE -ne 0) {
    throw "Launcher build failed."
}

Get-Item -LiteralPath $OutputPath
