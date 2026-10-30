param([string]$Exe,[string]$Corpus,[string]$Screenshot)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class TrialWindowCapture {
 [StructLayout(LayoutKind.Sequential)] public struct Rect {public int Left,Top,Right,Bottom;}
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd,out Rect rect);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd,IntPtr dc,uint flags);
}
'@
$Process=Start-Process $Exe -ArgumentList @('--ui-smoke',('"'+$Corpus+'"')) -PassThru
try {
 $Ready=$false
 for($Attempt=0;$Attempt -lt 35;$Attempt++) {
  Start-Sleep -Milliseconds 300;$Process.Refresh()
  if($Process.HasExited){throw "Packaged C# application exited: $($Process.ExitCode)"}
  if($Process.MainWindowHandle -ne 0 -and $Process.MainWindowTitle -like '*C#*'){$Ready=$true;break}
 }
 if(-not $Ready){throw 'Packaged C# window was not found.'}
 Start-Sleep -Milliseconds 800
 $Rect=New-Object TrialWindowCapture+Rect
 [TrialWindowCapture]::GetWindowRect($Process.MainWindowHandle,[ref]$Rect)|Out-Null
 $Bitmap=New-Object Drawing.Bitmap(($Rect.Right-$Rect.Left),($Rect.Bottom-$Rect.Top))
 $Graphics=[Drawing.Graphics]::FromImage($Bitmap);$Dc=$Graphics.GetHdc()
 try{[TrialWindowCapture]::PrintWindow($Process.MainWindowHandle,$Dc,2)|Out-Null}finally{$Graphics.ReleaseHdc($Dc)}
 $Bitmap.Save($Screenshot,[Drawing.Imaging.ImageFormat]::Png);$Graphics.Dispose();$Bitmap.Dispose()
 Write-Host 'Packaged native WPF window startup verification passed.'
}finally{if(-not $Process.HasExited){Stop-Process -Id $Process.Id -Force}}
