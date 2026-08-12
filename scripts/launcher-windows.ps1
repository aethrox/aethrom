# Desktop launcher for Windows: a .lnk that opens the vault in Obsidian, with a 🧠 icon.
# Usage: powershell -ExecutionPolicy Bypass -File launcher-windows.ps1 -VaultName MyOS -VaultPath C:\Users\me\Documents\MyOS
param(
  [Parameter(Mandatory = $true)][string]$VaultName,
  [Parameter(Mandatory = $true)][string]$VaultPath
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$iconDir = Join-Path $VaultPath '.claude'
$pngPath = Join-Path $iconDir 'brain.png'
$icoPath = Join-Path $iconDir 'brain.ico'
$size = 256

# Render the brain emoji with Segoe UI Emoji (present on every Windows 10/11 install)
$bmp = New-Object System.Drawing.Bitmap($size, $size)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::Transparent)
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$font = New-Object System.Drawing.Font('Segoe UI Emoji', ($size * 0.62), [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$fmt = New-Object System.Drawing.StringFormat
$fmt.Alignment = [System.Drawing.StringAlignment]::Center
$fmt.LineAlignment = [System.Drawing.StringAlignment]::Center
$brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 233, 108, 160))
$g.DrawString([char]::ConvertFromUtf32(0x1F9E0), $font, $brush, (New-Object System.Drawing.RectangleF(0, 0, $size, $size)), $fmt)
$g.Dispose()
$bmp.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()

# Wrap the PNG in an ICO container (PNG-compressed icons are valid on Vista+)
$png = [System.IO.File]::ReadAllBytes($pngPath)
$ms = New-Object System.IO.MemoryStream
$bw = New-Object System.IO.BinaryWriter($ms)
$bw.Write([uint16]0); $bw.Write([uint16]1); $bw.Write([uint16]1)  # reserved, type=icon, count=1
$bw.Write([byte]0); $bw.Write([byte]0)                            # width/height, 0 means 256
$bw.Write([byte]0); $bw.Write([byte]0)                            # palette, reserved
$bw.Write([uint16]1); $bw.Write([uint16]32)                       # planes, bits per pixel
$bw.Write([uint32]$png.Length); $bw.Write([uint32]22)             # payload size, offset
$bw.Write($png); $bw.Flush()
[System.IO.File]::WriteAllBytes($icoPath, $ms.ToArray())
$bw.Dispose(); $ms.Dispose()

# explorer.exe resolves the obsidian:// protocol handler; a .lnk cannot target a URI directly
$lnkPath = Join-Path ([Environment]::GetFolderPath('Desktop')) "$VaultName.lnk"
$sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnkPath)
$sc.TargetPath = "$env:WINDIR\explorer.exe"
$sc.Arguments = "obsidian://open?vault=$VaultName"
$sc.IconLocation = "$icoPath,0"
$sc.Description = "$VaultName - second brain"
$sc.Save()

Write-Output "launcher OK -> $lnkPath"
Write-Output "note: the obsidian:// handler only resolves after the vault has been opened in Obsidian once."
