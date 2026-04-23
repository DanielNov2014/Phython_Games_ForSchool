# --- 0. THE AUTO-RELAY: FORCE POWERSHELL 5.1 (STA MODE) & ADMIN RIGHTS ---
$isAdmin = [Security.Principal.WindowsIdentity]::GetCurrent().Groups -match 'S-1-5-32-544'
if ($PSVersionTable.PSVersion.Major -ge 6 -or ([System.Threading.Thread]::CurrentThread.GetApartmentState() -ne 'STA') -or -not $isAdmin) {
    Write-Host "Relaunching as Administrator in native PowerShell 5.1 (STA Mode)..." -ForegroundColor Cyan
    Start-Sleep -Seconds 1
    Start-Process powershell.exe -ArgumentList "-STA -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# --- 1. CLEANUP, IMPORTS & C# INJECTIONS ---
Remove-Variable Form, TitleLabel, SubTitleLabel, StatusLabel, ConnectBtn, CredLabel, ExitBtn, WMP, AppWindow, DesktopWindow, TweaksWindow, SoundPlayer -ErrorAction SilentlyContinue

Add-Type -ReferencedAssemblies "System.Windows.Forms", "System.Drawing" -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public class SmoothForm : Form {
    protected override CreateParams CreateParams {
        get {
            CreateParams cp = base.CreateParams;
            cp.ExStyle |= 0x02000000; // WS_EX_COMPOSITED
            return cp;
        }
    }
}

public class WinAPI {
    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);
    public static void SetWallpaper(string path) {
        SystemParametersInfo(20, 0, path, 3); 
    }
}
"@

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Set-DoubleBuffered ($Control) {
    $Flags = [System.Reflection.BindingFlags]::NonPublic -bor [System.Reflection.BindingFlags]::Instance
    [System.Windows.Forms.Control].GetProperty("DoubleBuffered", $Flags).SetValue($Control, $true, $null)
}

# --- SMART DNS BYPASS ROUTINE ---
function Set-GoogleDNS {
    $ActiveAdapters = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Up' }
    if ($ActiveAdapters) {
        foreach ($Adapter in $ActiveAdapters) {
            Set-DnsClientServerAddress -InterfaceAlias $Adapter.Name -ServerAddresses ("8.8.8.8", "8.8.4.4") -ErrorAction SilentlyContinue
        }
    }
}

function Get-SafeSavePath {
    $Desktop = [System.Environment]::GetFolderPath('Desktop')
    $Downloads = Join-Path [System.Environment]::GetFolderPath('UserProfile') "Downloads"
    $Profile = [System.Environment]::GetFolderPath('UserProfile')
    if (Test-Path $Desktop) { return $Desktop }
    if (Test-Path $Downloads) { return $Downloads }
    return $Profile
}

function Test-AppInstalled ($AppID) {
    switch ($AppID) {
        "steam"  { return (Test-Path "${env:ProgramFiles(x86)}\Steam\steam.exe") -or (Test-Path "$env:ProgramFiles\Steam\steam.exe") }
        "roblox" { 
            if (Get-Process "RobloxPlayerBeta" -ErrorAction SilentlyContinue) { return $true }
            $RbxPath = "$env:LOCALAPPDATA\Roblox\Versions"
            if (Test-Path $RbxPath) { return [bool](Get-ChildItem -Path $RbxPath -Filter "RobloxPlayerBeta.exe" -Recurse -ErrorAction SilentlyContinue) }
            return $false
        }
        "pegidle" { return (Test-Path (Join-Path (Get-SafeSavePath) "pegidle.py")) }
        "ballsim" { return (Test-Path (Join-Path (Get-SafeSavePath) "ball_sim.py")) }
        "python"  { return [bool](Get-Command python -ErrorAction SilentlyContinue) }
        "node"    { return [bool](Get-Command node -ErrorAction SilentlyContinue) }
        "chrome"  { return (Test-Path "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe") -or (Test-Path "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe") }
        "firefox" { return (Test-Path "${env:ProgramFiles}\Mozilla Firefox\firefox.exe") }
        "freetube"{ return (Test-Path "$env:LOCALAPPDATA\Programs\FreeTube\FreeTube.exe") -or (Test-Path "${env:ProgramFiles}\FreeTube\FreeTube.exe") }
    }
    return $false
}

function Uninstall-App ($TargetApp) {
    if ($TargetApp.Type -eq "PythonGame") {
        $DestFile = Join-Path (Get-SafeSavePath) $TargetApp.File
        Remove-Item $DestFile -Force -ErrorAction SilentlyContinue
        return
    }

    $SearchStrings = @{ "steam"="Steam"; "roblox"="Roblox"; "python"="Python 3*"; "node"="Node.js*"; "chrome"="Google Chrome"; "firefox"="Mozilla Firefox"; "freetube"="FreeTube" }
    $SearchName = $SearchStrings[$TargetApp.ID]

    $RegPaths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    $InstalledApp = Get-ItemProperty $RegPaths -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like $SearchName } | Select-Object -First 1

    if ($InstalledApp) {
        $UninstallStr = $InstalledApp.QuietUninstallString
        if (-not $UninstallStr) { $UninstallStr = $InstalledApp.UninstallString }

        if ($UninstallStr) {
            if ($UninstallStr -match "msiexec") {
                $Guid = ($UninstallStr -replace ".*/I","") -replace ".*/X",""
                $Guid = $Guid.Trim()
                Start-Process "msiexec.exe" -ArgumentList "/X $Guid /qn" -Wait -ErrorAction SilentlyContinue
            } else {
                $Executable = $UninstallStr
                $Args = ""
                if ($Executable -match '^"(.*?)"\s*(.*)') {
                    $Executable = $matches[1]
                    $Args = $matches[2]
                }
                if ($TargetApp.ID -eq "steam" -or $TargetApp.ID -eq "firefox") { $Args += " /S" }
                if ($TargetApp.ID -eq "roblox") { $Args += " -uninstall" }
                if ($TargetApp.ID -eq "freetube") { $Args += " /S" }
                Start-Process -FilePath $Executable -ArgumentList $Args -Wait -ErrorAction SilentlyContinue
            }
        }
    }
}

function Start-XpMusic {
    try {
        $UsbDrive = (Get-PSDrive -PSProvider FileSystem | Where-Object { Test-Path "$($_.Root)xpmusic.wav" } | Select-Object -First 1).Root
        if ($UsbDrive) {
            $MusicPath = Join-Path $UsbDrive "xpmusic.wav"
        } else {
            $MusicPath = Join-Path $env:TEMP "xpmusic.wav"
            if (-not (Test-Path $MusicPath)) {
                $MusicUrl = "https://github.com/DanielNov2014/Phython_Games_ForSchool/raw/refs/heads/main/xpmusic.wav"
                Invoke-WebRequest -Uri $MusicUrl -OutFile $MusicPath -UseBasicParsing -TimeoutSec 15 -ErrorAction SilentlyContinue
            }
        }
        if (Test-Path $MusicPath) {
            if ($global:WMP) { $global:WMP.controls.stop() } 
            $global:SoundPlayer = New-Object System.Media.SoundPlayer($MusicPath)
            $global:SoundPlayer.PlayLooping()
        }
    } catch {}
}

# --- 2. SETUP FULL-SCREEN FORM ---
$Form = New-Object SmoothForm
$Form.WindowState = 'Maximized'
$Form.FormBorderStyle = 'None' 
$Form.BackColor = 'Black'

$global:ScaledImg = $null
$WallPath = "C:\Windows\Web\Wallpaper\Windows\img0.jpg"
if (Test-Path $WallPath) {
    $OriginalImg = [System.Drawing.Image]::FromFile($WallPath)
    $ScreenW = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width
    $ScreenH = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
    $global:ScaledImg = New-Object System.Drawing.Bitmap($OriginalImg, $ScreenW, $ScreenH)
    $Form.BackgroundImage = $global:ScaledImg
    $Form.BackgroundImageLayout = 'None' 
    $OriginalImg.Dispose() 
}

# --- 3. INTRO PANEL ---
$IntroPanel = New-Object System.Windows.Forms.Panel
$IntroPanel.Dock = 'Fill'
$IntroPanel.BackColor = [System.Drawing.Color]::Transparent
Set-DoubleBuffered $IntroPanel

$TitleLabel = New-Object System.Windows.Forms.Label
$TitleLabel.Text = "Windows 11 ❖"
$TitleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 48, [System.Drawing.FontStyle]::Bold)
$TitleLabel.ForeColor = [System.Drawing.Color]::White
$TitleLabel.AutoSize = $true

$SubTitleLabel = New-Object System.Windows.Forms.Label
$SubTitleLabel.Text = "Introduction"
$SubTitleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 32)
$SubTitleLabel.ForeColor = [System.Drawing.Color]::White
$SubTitleLabel.AutoSize = $true

$IntroPanel.Controls.Add($TitleLabel)
$IntroPanel.Controls.Add($SubTitleLabel)
$Form.Controls.Add($IntroPanel)

# --- 4. NETWORK PANEL ---
$NetPanel = New-Object System.Windows.Forms.Panel
$NetPanel.Dock = 'Fill'
$NetPanel.BackColor = [System.Drawing.Color]::Transparent
$NetPanel.Visible = $false
Set-DoubleBuffered $NetPanel

$StatusLabel = New-Object System.Windows.Forms.Label
$StatusLabel.Text = "Checking Connection..."
$StatusLabel.Font = New-Object System.Drawing.Font("Segoe UI", 24, [System.Drawing.FontStyle]::Bold)
$StatusLabel.ForeColor = [System.Drawing.Color]::White
$StatusLabel.AutoSize = $true

$ConnectBtn = New-Object System.Windows.Forms.Button
$ConnectBtn.Text = "Connect to Wi-Fi"
$ConnectBtn.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$ConnectBtn.Size = New-Object System.Drawing.Size(250, 50)
$ConnectBtn.BackColor = [System.Drawing.Color]::DodgerBlue
$ConnectBtn.ForeColor = [System.Drawing.Color]::White
$ConnectBtn.FlatStyle = 'Flat'
$ConnectBtn.Visible = $false

$CredLabel = New-Object System.Windows.Forms.Label
$CredLabel.Text = ""
$CredLabel.Font = New-Object System.Drawing.Font("Segoe UI", 18)
$CredLabel.ForeColor = [System.Drawing.Color]::LightPink
$CredLabel.AutoSize = $true
$CredLabel.TextAlign = 'MiddleCenter'

$NetPanel.Controls.Add($StatusLabel)
$NetPanel.Controls.Add($ConnectBtn)
$NetPanel.Controls.Add($CredLabel)
$Form.Controls.Add($NetPanel)


# ==========================================
# --- 5. SYSTEM TWEAKS WINDOW (PAGE 5) ---
# ==========================================
$TweaksWindow = New-Object System.Windows.Forms.Panel
$TweaksWindow.Size = New-Object System.Drawing.Size(800, 520)
$TweaksWindow.BackColor = [System.Drawing.Color]::FromArgb(245, 25, 25, 25) 
$TweaksWindow.Visible = $false
Set-DoubleBuffered $TweaksWindow

$TweakTitle = New-Object System.Windows.Forms.Label
$TweakTitle.Text = "Pro System Tweaks"
$TweakTitle.Font = New-Object System.Drawing.Font("Segoe UI", 24, [System.Drawing.FontStyle]::Bold)
$TweakTitle.ForeColor = [System.Drawing.Color]::White
$TweakTitle.AutoSize = $true
$TweakTitle.Location = New-Object System.Drawing.Point(20, 20)
$TweaksWindow.Controls.Add($TweakTitle)

$TweakSubTitle = New-Object System.Windows.Forms.Label
$TweakSubTitle.Text = "Configure advanced Windows behavior. (Checked = Enabled)"
$TweakSubTitle.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$TweakSubTitle.ForeColor = [System.Drawing.Color]::LightGray
$TweakSubTitle.AutoSize = $true
$TweakSubTitle.Location = New-Object System.Drawing.Point(24, 65)
$TweaksWindow.Controls.Add($TweakSubTitle)

$TweakFlow = New-Object System.Windows.Forms.FlowLayoutPanel
$TweakFlow.Location = New-Object System.Drawing.Point(25, 110)
$TweakFlow.Size = New-Object System.Drawing.Size(750, 320)
$TweakFlow.FlowDirection = 'TopDown'
$TweakFlow.WrapContents = $true
$TweaksWindow.Controls.Add($TweakFlow)

# Dynamic Registry Hunter & Configurator
$SysTweaks = @(
    @{
        Name = "Enable 'End Task' on Taskbar Right-Click"
        Check = { 
            $reg = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarEndTask" -ErrorAction SilentlyContinue
            if ($null -ne $reg -and $reg.TaskbarEndTask -eq 1) { return $true } else { return $false }
        }
        Apply = { Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarEndTask" -Value 1 -Force }
        Revert = { Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarEndTask" -Value 0 -Force }
    },
    @{
        Name = "Restore Classic Right-Click Menu"
        Check = { (Get-ItemProperty "HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32" -ErrorAction SilentlyContinue) -ne $null }
        Apply = { New-Item -Path "HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32" -Force | Set-ItemProperty -Name "(Default)" -Value "" }
        Revert = { Remove-Item -Path "HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}" -Recurse -Force -ErrorAction SilentlyContinue }
    },
    @{
        Name = "Force Windows Dark Mode"
        Check = { 
            $reg = Get-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name "AppsUseLightTheme" -ErrorAction SilentlyContinue
            if ($null -ne $reg -and $reg.AppsUseLightTheme -eq 0) { return $true } else { return $false }
        }
        Apply = {
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name "AppsUseLightTheme" -Value 0 -Force
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name "SystemUsesLightTheme" -Value 0 -Force
        }
        Revert = {
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name "AppsUseLightTheme" -Value 1 -Force
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name "SystemUsesLightTheme" -Value 1 -Force
        }
    },
    @{
        Name = "Show Hidden Files & Folders"
        Check = { 
            $reg = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "Hidden" -ErrorAction SilentlyContinue
            if ($null -ne $reg -and $reg.Hidden -eq 1) { return $true } else { return $false }
        }
        Apply = { Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "Hidden" -Value 1 -Force }
        Revert = { Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "Hidden" -Value 2 -Force }
    },
    @{
        Name = "Show File Extensions (.exe, .txt)"
        Check = { 
            $reg = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "HideFileExt" -ErrorAction SilentlyContinue
            if ($null -ne $reg -and $reg.HideFileExt -eq 0) { return $true } else { return $false }
        }
        Apply = { Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "HideFileExt" -Value 0 -Force }
        Revert = { Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "HideFileExt" -Value 1 -Force }
    },
    @{
        Name = "Disable Bing Web Search in Start Menu"
        Check = { 
            $reg = Get-ItemProperty "HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer" -Name "DisableSearchBoxSuggestions" -ErrorAction SilentlyContinue
            if ($null -ne $reg -and $reg.DisableSearchBoxSuggestions -eq 1) { return $true } else { return $false }
        }
        Apply = {
            if (-not (Test-Path "HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer")) { New-Item -Path "HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer" -Force | Out-Null }
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer" -Name "DisableSearchBoxSuggestions" -Value 1 -Force
        }
        Revert = { Set-ItemProperty -Path "HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer" -Name "DisableSearchBoxSuggestions" -Value 0 -Force -ErrorAction SilentlyContinue }
    },
    @{
        Name = "Disable UI Animations (Speed Boost)"
        Check = { 
            $reg = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" -Name "VisualFXSetting" -ErrorAction SilentlyContinue
            if ($null -ne $reg -and $reg.VisualFXSetting -eq 2) { return $true } else { return $false }
        }
        Apply = { Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" -Name "VisualFXSetting" -Value 2 -Force }
        Revert = { Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" -Name "VisualFXSetting" -Value 0 -Force }
    }
)

$AllTweakChecks = @()
foreach ($tweak in $SysTweaks) {
    $chk = New-Object System.Windows.Forms.CheckBox
    $chk.Text = $tweak.Name
    $chk.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
    $chk.ForeColor = [System.Drawing.Color]::White
    $chk.AutoSize = $true
    $chk.Margin = New-Object System.Windows.Forms.Padding(10, 15, 30, 10)
    $chk.BackColor = [System.Drawing.Color]::Transparent
    $chk.Tag = $tweak
    
    if (& $tweak.Check) { 
        $chk.Checked = $true
        $chk.ForeColor = [System.Drawing.Color]::LimeGreen
    }
    
    $TweakFlow.Controls.Add($chk)
    $AllTweakChecks += $chk
}

$ApplyTweaksBtn = New-Object System.Windows.Forms.Button
$ApplyTweaksBtn.Text = "Apply Tweaks"
$ApplyTweaksBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$ApplyTweaksBtn.Size = New-Object System.Drawing.Size(160, 45)
$ApplyTweaksBtn.Location = New-Object System.Drawing.Point(400, 450)
$ApplyTweaksBtn.BackColor = [System.Drawing.Color]::DodgerBlue
$ApplyTweaksBtn.ForeColor = [System.Drawing.Color]::White
$ApplyTweaksBtn.FlatStyle = 'Flat'

$FinishBtn = New-Object System.Windows.Forms.Button
$FinishBtn.Text = "Finish Setup"
$FinishBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$FinishBtn.Size = New-Object System.Drawing.Size(160, 45)
$FinishBtn.Location = New-Object System.Drawing.Point(580, 450)
$FinishBtn.BackColor = [System.Drawing.Color]::Crimson
$FinishBtn.ForeColor = [System.Drawing.Color]::White
$FinishBtn.FlatStyle = 'Flat'

$ApplyTweaksBtn.Add_Click({
    $ApplyTweaksBtn.Text = "Applying..."
    $ApplyTweaksBtn.Enabled = $false
    [System.Windows.Forms.Application]::DoEvents()

    foreach ($chk in $AllTweakChecks) {
        if ($chk.Checked) { & $chk.Tag.Apply } else { & $chk.Tag.Revert }
        
        if ($chk.Checked) { $chk.ForeColor = [System.Drawing.Color]::LimeGreen } 
        else { $chk.ForeColor = [System.Drawing.Color]::White }
    }
    
    Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    
    $ApplyTweaksBtn.Text = "Apply Tweaks"
    $ApplyTweaksBtn.Enabled = $true
})

$FinishBtn.Add_Click({ $Form.Close() })

$TweaksWindow.Controls.Add($ApplyTweaksBtn)
$TweaksWindow.Controls.Add($FinishBtn)
$Form.Controls.Add($TweaksWindow)


# ==========================================
# --- 6. DESKTOP CUSTOMIZATION WINDOW (PAGE 4) ---
# ==========================================
$DesktopWindow = New-Object System.Windows.Forms.Panel
$DesktopWindow.Size = New-Object System.Drawing.Size(750, 520)
$DesktopWindow.BackColor = [System.Drawing.Color]::FromArgb(245, 25, 25, 25) 
$DesktopWindow.Visible = $false
Set-DoubleBuffered $DesktopWindow

$DeskTitle = New-Object System.Windows.Forms.Label
$DeskTitle.Text = "Personalize your workspace"
$DeskTitle.Font = New-Object System.Drawing.Font("Segoe UI", 24, [System.Drawing.FontStyle]::Bold)
$DeskTitle.ForeColor = [System.Drawing.Color]::White
$DeskTitle.AutoSize = $true
$DeskTitle.Location = New-Object System.Drawing.Point(20, 20)
$DesktopWindow.Controls.Add($DeskTitle)

# --- LEFT COLUMN: WALLPAPER & TASKBAR ---
$TaskGroup = New-Object System.Windows.Forms.GroupBox
$TaskGroup.Text = "Taskbar Alignment"
$TaskGroup.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$TaskGroup.ForeColor = [System.Drawing.Color]::White
$TaskGroup.Size = New-Object System.Drawing.Size(320, 80)
$TaskGroup.Location = New-Object System.Drawing.Point(25, 90)

$AlignLeftChk = New-Object System.Windows.Forms.CheckBox
$AlignLeftChk.Text = "Align Taskbar to Left (Classic)"
$AlignLeftChk.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$AlignLeftChk.Location = New-Object System.Drawing.Point(20, 35)
$AlignLeftChk.AutoSize = $true
$TaskGroup.Controls.Add($AlignLeftChk)
$DesktopWindow.Controls.Add($TaskGroup)

$WallGroup = New-Object System.Windows.Forms.GroupBox
$WallGroup.Text = "Desktop Wallpaper"
$WallGroup.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$WallGroup.ForeColor = [System.Drawing.Color]::White
$WallGroup.Size = New-Object System.Drawing.Size(320, 260)
$WallGroup.Location = New-Object System.Drawing.Point(25, 190)

$WallLabel = New-Object System.Windows.Forms.Label
$WallLabel.Text = "1. Select Preset:"
$WallLabel.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$WallLabel.Location = New-Object System.Drawing.Point(15, 30)
$WallLabel.AutoSize = $true
$WallGroup.Controls.Add($WallLabel)

$PresetCombo = New-Object System.Windows.Forms.ComboBox
$PresetCombo.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$PresetCombo.Location = New-Object System.Drawing.Point(18, 55)
$PresetCombo.Size = New-Object System.Drawing.Size(280, 30)
$PresetCombo.DropDownStyle = 'DropDownList'
$PresetCombo.Items.Add("None (Skip)") | Out-Null
$PresetCombo.Items.Add("Unsplash: 4K Starry Mountains") | Out-Null
$PresetCombo.Items.Add("Unsplash: 4K Nature") | Out-Null
$PresetCombo.Items.Add("Unsplash: 4K Abstract") | Out-Null
$PresetCombo.Items.Add("Unsplash: 4K Space") | Out-Null
$PresetCombo.Items.Add("Unsplash: 4K Cyberpunk") | Out-Null
$PresetCombo.SelectedIndex = 0
$WallGroup.Controls.Add($PresetCombo)

$WallLabel2 = New-Object System.Windows.Forms.Label
$WallLabel2.Text = "2. Or Custom Image URL / Local File:"
$WallLabel2.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$WallLabel2.Location = New-Object System.Drawing.Point(15, 100)
$WallLabel2.AutoSize = $true
$WallGroup.Controls.Add($WallLabel2)

$WallPathTxt = New-Object System.Windows.Forms.TextBox
$WallPathTxt.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$WallPathTxt.Location = New-Object System.Drawing.Point(18, 125)
$WallPathTxt.Size = New-Object System.Drawing.Size(200, 25)
$WallGroup.Controls.Add($WallPathTxt)

$BrowseBtn = New-Object System.Windows.Forms.Button
$BrowseBtn.Text = "Browse"
$BrowseBtn.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$BrowseBtn.Location = New-Object System.Drawing.Point(228, 124)
$BrowseBtn.Size = New-Object System.Drawing.Size(70, 27)
$BrowseBtn.BackColor = [System.Drawing.Color]::Gray
$BrowseBtn.FlatStyle = 'Flat'
$BrowseBtn.Add_Click({
    $OpenFileDialog = New-Object System.Windows.Forms.OpenFileDialog
    $OpenFileDialog.Filter = "Image Files|*.jpg;*.jpeg;*.png;*.bmp"
    if ($OpenFileDialog.ShowDialog() -eq 'OK') {
        $WallPathTxt.Text = $OpenFileDialog.FileName
        $PresetCombo.SelectedIndex = 0
    }
})
$WallGroup.Controls.Add($BrowseBtn)

$PreviewBtn = New-Object System.Windows.Forms.Button
$PreviewBtn.Text = "Preview Wallpaper"
$PreviewBtn.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$PreviewBtn.Location = New-Object System.Drawing.Point(18, 190)
$PreviewBtn.Size = New-Object System.Drawing.Size(280, 45)
$PreviewBtn.BackColor = [System.Drawing.Color]::RoyalBlue
$PreviewBtn.FlatStyle = 'Flat'
$WallGroup.Controls.Add($PreviewBtn)
$DesktopWindow.Controls.Add($WallGroup)

$PreviewBtn.Add_Click({
    $ImagePath = ""
    if ($WallPathTxt.Text -ne "") {
        $ImagePath = $WallPathTxt.Text
    } elseif ($PresetCombo.SelectedIndex -gt 0) {
        $ImagePath = Join-Path $env:TEMP "preview_wall.jpg"
        $PreviewBtn.Text = "Downloading Preview..."
        [System.Windows.Forms.Application]::DoEvents()
        
        $Urls = @(
            "", 
            "https://images.unsplash.com/photo-1519681393784-d120267933ba?w=2400",
            "https://images.unsplash.com/photo-1472214103451-9374bd1c798e?auto=format&fit=crop&w=1920&q=80", 
            "https://images.unsplash.com/photo-1550684848-fac1c5b4e853?auto=format&fit=crop&w=1920&q=80", 
            "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?auto=format&fit=crop&w=1920&q=80", 
            "https://images.unsplash.com/photo-1555680202-c86f0e12f086?auto=format&fit=crop&w=1920&q=80"
        )
        try { Invoke-WebRequest -Uri $Urls[$PresetCombo.SelectedIndex] -OutFile $ImagePath -UseBasicParsing } catch {}
        $PreviewBtn.Text = "Preview Wallpaper"
    }

    if ($ImagePath -and (Test-Path $ImagePath)) {
        $PrevForm = New-Object SmoothForm
        $PrevForm.WindowState = 'Maximized'
        $PrevForm.FormBorderStyle = 'None'
        $PrevForm.BackgroundImage = [System.Drawing.Image]::FromFile($ImagePath)
        $PrevForm.BackgroundImageLayout = 'Zoom'
        $PrevForm.Add_Click({ $this.BackgroundImage.Dispose(); $this.Close() })
        $PrevForm.ShowDialog()
    }
})

# --- RIGHT COLUMN: DYNAMIC SHORTCUTS ---
$IconGroup = New-Object System.Windows.Forms.GroupBox
$IconGroup.Text = "Desktop Shortcuts (Check = Keep/Create)"
$IconGroup.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$IconGroup.ForeColor = [System.Drawing.Color]::White
$IconGroup.Size = New-Object System.Drawing.Size(360, 360)
$IconGroup.Location = New-Object System.Drawing.Point(365, 90)

$FlowPanel = New-Object System.Windows.Forms.FlowLayoutPanel
$FlowPanel.Dock = 'Top'
$FlowPanel.Height = 220
$FlowPanel.FlowDirection = 'TopDown'
$FlowPanel.WrapContents = $false
$FlowPanel.AutoScroll = $true
$IconGroup.Controls.Add($FlowPanel)

$AllDeskChecks = @()
$DeskPath = [System.Environment]::GetFolderPath('Desktop')

$IconsList = @(
    @{ Name="YouTube"; URL="https://www.youtube.com" },
    @{ Name="GitHub"; URL="https://github.com" },
    @{ Name="ChatGPT"; URL="https://chatgpt.com" }
)

foreach ($icon in $IconsList) {
    $chk = New-Object System.Windows.Forms.CheckBox
    $chk.Text = $icon.Name
    $chk.Font = New-Object System.Drawing.Font("Segoe UI", 11)
    $chk.AutoSize = $true
    $chk.Tag = $icon
    if (Test-Path (Join-Path $DeskPath "$($icon.Name).url")) { $chk.Checked = $true }
    $FlowPanel.Controls.Add($chk)
    $AllDeskChecks += $chk
}

# --- CUSTOM PIN CREATOR ---
$CustomLabel = New-Object System.Windows.Forms.Label
$CustomLabel.Text = "Add Custom Pin:"
$CustomLabel.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$CustomLabel.Location = New-Object System.Drawing.Point(15, 260)
$CustomLabel.AutoSize = $true
$IconGroup.Controls.Add($CustomLabel)

$PinNameTxt = New-Object System.Windows.Forms.TextBox
$PinNameTxt.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$PinNameTxt.Location = New-Object System.Drawing.Point(18, 285)
$PinNameTxt.Size = New-Object System.Drawing.Size(120, 23)
$PinNameTxt.Text = "Name"
$IconGroup.Controls.Add($PinNameTxt)

$PinUrlTxt = New-Object System.Windows.Forms.TextBox
$PinUrlTxt.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$PinUrlTxt.Location = New-Object System.Drawing.Point(145, 285)
$PinUrlTxt.Size = New-Object System.Drawing.Size(160, 23)
$PinUrlTxt.Text = "https://"
$IconGroup.Controls.Add($PinUrlTxt)

$AddPinBtn = New-Object System.Windows.Forms.Button
$AddPinBtn.Text = "+"
$AddPinBtn.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$AddPinBtn.Location = New-Object System.Drawing.Point(315, 283)
$AddPinBtn.Size = New-Object System.Drawing.Size(35, 28)
$AddPinBtn.BackColor = [System.Drawing.Color]::DodgerBlue
$AddPinBtn.FlatStyle = 'Flat'
$AddPinBtn.Add_Click({
    if ($PinNameTxt.Text -and $PinUrlTxt.Text -ne "https://") {
        $chk = New-Object System.Windows.Forms.CheckBox
        $chk.Text = $PinNameTxt.Text
        $chk.Font = New-Object System.Drawing.Font("Segoe UI", 11)
        $chk.AutoSize = $true
        $chk.Checked = $true 
        $chk.Tag = @{ Name=$PinNameTxt.Text; URL=$PinUrlTxt.Text }
        
        $FlowPanel.Controls.Add($chk)
        $global:AllDeskChecks += $chk
        $PinNameTxt.Text = "Name"
        $PinUrlTxt.Text = "https://"
    }
})
$IconGroup.Controls.Add($AddPinBtn)
$DesktopWindow.Controls.Add($IconGroup)

# SEPARATE APPLY & NEXT BUTTONS
$ApplyDeskBtn = New-Object System.Windows.Forms.Button
$ApplyDeskBtn.Text = "Apply Changes"
$ApplyDeskBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$ApplyDeskBtn.Size = New-Object System.Drawing.Size(160, 45)
$ApplyDeskBtn.Location = New-Object System.Drawing.Point(380, 460)
$ApplyDeskBtn.BackColor = [System.Drawing.Color]::DodgerBlue
$ApplyDeskBtn.ForeColor = [System.Drawing.Color]::White
$ApplyDeskBtn.FlatStyle = 'Flat'

$NextTweaksBtn = New-Object System.Windows.Forms.Button
$NextTweaksBtn.Text = "Next Page ->"
$NextTweaksBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$NextTweaksBtn.Size = New-Object System.Drawing.Size(160, 45)
$NextTweaksBtn.Location = New-Object System.Drawing.Point(560, 460)
$NextTweaksBtn.BackColor = [System.Drawing.Color]::LimeGreen
$NextTweaksBtn.ForeColor = [System.Drawing.Color]::White
$NextTweaksBtn.FlatStyle = 'Flat'

$ApplyDeskBtn.Add_Click({
    $ApplyDeskBtn.Text = "Applying..."
    $ApplyDeskBtn.Enabled = $false
    [System.Windows.Forms.Application]::DoEvents()

    if ($AlignLeftChk.Checked) { Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarAl" -Value 0 -ErrorAction SilentlyContinue }

    $WshShell = New-Object -ComObject WScript.Shell
    foreach ($chk in $AllDeskChecks) {
        $FilePath = Join-Path $DeskPath "$($chk.Tag.Name).url"
        if ($chk.Checked) {
            $Shortcut = $WshShell.CreateShortcut($FilePath)
            $Shortcut.TargetPath = $chk.Tag.URL
            $Shortcut.Save()
        } else {
            if (Test-Path $FilePath) { Remove-Item $FilePath -Force }
        }
    }

    $ImagePath = ""
    if ($WallPathTxt.Text -ne "") { $ImagePath = $WallPathTxt.Text } 
    elseif ($PresetCombo.SelectedIndex -gt 0) {
        $ImagePath = Join-Path $env:TEMP "applied_wall.jpg"
        $Urls = @(
            "", 
            "https://images.unsplash.com/photo-1519681393784-d120267933ba?w=2400",
            "https://images.unsplash.com/photo-1472214103451-9374bd1c798e?auto=format&fit=crop&w=1920&q=80", 
            "https://images.unsplash.com/photo-1550684848-fac1c5b4e853?auto=format&fit=crop&w=1920&q=80", 
            "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?auto=format&fit=crop&w=1920&q=80", 
            "https://images.unsplash.com/photo-1555680202-c86f0e12f086?auto=format&fit=crop&w=1920&q=80"
        )
        try { Invoke-WebRequest -Uri $Urls[$PresetCombo.SelectedIndex] -OutFile $ImagePath -UseBasicParsing } catch {}
    }

    if ($ImagePath -and (Test-Path $ImagePath)) { [WinAPI]::SetWallpaper($ImagePath) }
    
    Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    
    $ApplyDeskBtn.Text = "Apply Changes"
    $ApplyDeskBtn.Enabled = $true
})

$NextTweaksBtn.Add_Click({
    $DesktopWindow.Visible = $false
    $TweaksWindow.Visible = $true
})

$DesktopWindow.Controls.Add($ApplyDeskBtn)
$DesktopWindow.Controls.Add($NextTweaksBtn)
$Form.Controls.Add($DesktopWindow)

# ==========================================
# --- 7. APP INSTALLER WINDOW (PAGE 3) ---
# ==========================================
$AppWindow = New-Object System.Windows.Forms.Panel
$AppWindow.Size = New-Object System.Drawing.Size(750, 520)
$AppWindow.BackColor = [System.Drawing.Color]::FromArgb(245, 25, 25, 25)
$AppWindow.Visible = $false
Set-DoubleBuffered $AppWindow

$AppTitle = New-Object System.Windows.Forms.Label
$AppTitle.Text = "Let's customize your experience"
$AppTitle.Font = New-Object System.Drawing.Font("Segoe UI", 24, [System.Drawing.FontStyle]::Bold)
$AppTitle.ForeColor = [System.Drawing.Color]::White
$AppTitle.AutoSize = $true
$AppTitle.Location = New-Object System.Drawing.Point(20, 20)
$AppWindow.Controls.Add($AppTitle)

$AppSubTitle = New-Object System.Windows.Forms.Label
$AppSubTitle.Text = "Check to install. Uncheck to uninstall."
$AppSubTitle.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$AppSubTitle.ForeColor = [System.Drawing.Color]::LightGray
$AppSubTitle.AutoSize = $true
$AppSubTitle.Location = New-Object System.Drawing.Point(24, 65)
$AppWindow.Controls.Add($AppSubTitle)

$GameGroup = New-Object System.Windows.Forms.GroupBox
$GameGroup.Text = "Gaming"
$GameGroup.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$GameGroup.ForeColor = [System.Drawing.Color]::White
$GameGroup.Size = New-Object System.Drawing.Size(320, 300)
$GameGroup.Location = New-Object System.Drawing.Point(25, 110)
$AppWindow.Controls.Add($GameGroup) 

$DevGroup = New-Object System.Windows.Forms.GroupBox
$DevGroup.Text = "Web & Dev"
$DevGroup.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$DevGroup.ForeColor = [System.Drawing.Color]::White
$DevGroup.Size = New-Object System.Drawing.Size(320, 300)
$DevGroup.Location = New-Object System.Drawing.Point(375, 110)
$AppWindow.Controls.Add($DevGroup) 

$AppCatalog = @(
    @{ Name="Steam"; ID="steam"; Cat=$GameGroup; Y=40; URL="https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe"; Args="/S"; File="Steam_Setup.exe"; Type="Exe" },
    @{ Name="Roblox"; ID="roblox"; Cat=$GameGroup; Y=80; URL="https://www.roblox.com/download/client"; Args=""; File="Roblox_Setup.exe"; Type="Roblox" },
    @{ Name="Pegidle (Python)"; ID="pegidle"; Cat=$GameGroup; Y=120; URL="https://raw.githubusercontent.com/DanielNov2014/Phython_Games_ForSchool/refs/heads/main/pegidle.py"; Req="pygame-ce"; File="pegidle.py"; Type="PythonGame" },
    @{ Name="Ball Sim (Python)"; ID="ballsim"; Cat=$GameGroup; Y=160; URL="https://raw.githubusercontent.com/DanielNov2014/Phython_Games_ForSchool/refs/heads/main/ball_sim.py"; Req="pygame"; File="ball_sim.py"; Type="PythonGame" },
    @{ Name="Google Chrome"; ID="chrome"; Cat=$DevGroup; Y=40; URL="https://dl.google.com/chrome/install/GoogleChromeStandaloneEnterprise64.msi"; Args="/qn"; File="Chrome_Setup.msi"; Type="Msi" },
    @{ Name="Mozilla Firefox"; ID="firefox"; Cat=$DevGroup; Y=80; URL="https://download.mozilla.org/?product=firefox-latest-ssl&os=win64&lang=en-US"; Args="/S"; File="Firefox_Setup.exe"; Type="Exe" },
    @{ Name="Python (Latest)"; ID="python"; Cat=$DevGroup; Y=120; URL="https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe"; Args="/quiet InstallAllUsers=1 PrependPath=1"; File="Python_Setup.exe"; Type="Exe" },
    @{ Name="Node.js"; ID="node"; Cat=$DevGroup; Y=160; URL="https://nodejs.org/dist/v20.12.2/node-v20.12.2-x64.msi"; Args="/qn"; File="Node_Setup.msi"; Type="Msi" },
    @{ Name="FreeTube"; ID="freetube"; Cat=$DevGroup; Y=200; URL="DYNAMIC"; Args="/S"; File="FreeTube_Setup.exe"; Type="Exe" }
)

$AllCheckboxes = @() 

foreach ($app in $AppCatalog) {
    $chk = New-Object System.Windows.Forms.CheckBox
    $chk.Text = $app.Name
    $chk.Font = New-Object System.Drawing.Font("Segoe UI", 11)
    $chk.Location = New-Object System.Drawing.Point(20, $app.Y)
    $chk.AutoSize = $true
    $chk.BackColor = [System.Drawing.Color]::Transparent
    $chk.Tag = $app 
    
    if (Test-AppInstalled $app.ID) {
        $chk.Checked = $true
        $chk.ForeColor = [System.Drawing.Color]::LimeGreen
    } else {
        $chk.Checked = $false
        $chk.ForeColor = [System.Drawing.Color]::White
    }

    $app.Cat.Controls.Add($chk)
    $AllCheckboxes += $chk
}

$ProgressLabel = New-Object System.Windows.Forms.Label
$ProgressLabel.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$ProgressLabel.ForeColor = [System.Drawing.Color]::Cyan
$ProgressLabel.Location = New-Object System.Drawing.Point(24, 150)
$ProgressLabel.Size = New-Object System.Drawing.Size(650, 200) 
$ProgressLabel.BackColor = [System.Drawing.Color]::Transparent
$ProgressLabel.Visible = $false
$AppWindow.Controls.Add($ProgressLabel)

# SEPARATE APPLY & NEXT BUTTONS
$ApplyAppBtn = New-Object System.Windows.Forms.Button
$ApplyAppBtn.Text = "Apply Changes"
$ApplyAppBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$ApplyAppBtn.Size = New-Object System.Drawing.Size(160, 45)
$ApplyAppBtn.Location = New-Object System.Drawing.Point(380, 460)
$ApplyAppBtn.BackColor = [System.Drawing.Color]::DodgerBlue
$ApplyAppBtn.ForeColor = [System.Drawing.Color]::White
$ApplyAppBtn.FlatStyle = 'Flat'

$NextPageBtn = New-Object System.Windows.Forms.Button
$NextPageBtn.Text = "Next Page ->"
$NextPageBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$NextPageBtn.Size = New-Object System.Drawing.Size(160, 45)
$NextPageBtn.Location = New-Object System.Drawing.Point(560, 460)
$NextPageBtn.BackColor = [System.Drawing.Color]::LimeGreen
$NextPageBtn.ForeColor = [System.Drawing.Color]::White
$NextPageBtn.FlatStyle = 'Flat'


$ApplyAppBtn.Add_Click({
    $AppsToInstall = @()
    $AppsToUninstall = @()

    foreach ($chk in $AllCheckboxes) {
        $isInst = Test-AppInstalled $chk.Tag.ID
        if ($chk.Checked -and -not $isInst) { $AppsToInstall += $chk.Tag }
        if (-not $chk.Checked -and $isInst) { $AppsToUninstall += $chk.Tag }
    }

    if ($AppsToInstall.Count -eq 0 -and $AppsToUninstall.Count -eq 0) { return }

    $ApplyAppBtn.Visible = $false
    $NextPageBtn.Visible = $false
    $GameGroup.Visible = $false
    $DevGroup.Visible = $false
    
    $AppTitle.Text = "Applying your changes..."
    $AppSubTitle.Text = "Please do not turn off your PC."
    $ProgressLabel.Visible = $true
    
    [System.Windows.Forms.Application]::DoEvents() 
    $WebAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    $GameSavePaths = @() 

    foreach ($TargetApp in $AppsToUninstall) {
        $ProgressLabel.Text = "Uninstalling $($TargetApp.Name)..."
        [System.Windows.Forms.Application]::DoEvents()
        Uninstall-App $TargetApp
        Start-Sleep -Seconds 2 
    }

    foreach ($TargetApp in $AppsToInstall) {
        # --- DYNAMIC FREETUBE FETCHER ---
        if ($TargetApp.ID -eq "freetube" -and $TargetApp.URL -eq "DYNAMIC") {
            $ProgressLabel.Text = "Finding latest FreeTube version..."
            [System.Windows.Forms.Application]::DoEvents()
            try {
                $FT_Rel = Invoke-RestMethod "https://api.github.com/repos/FreeTubeApp/FreeTube/releases/latest" -UseBasicParsing
                $TargetApp.URL = ($FT_Rel.assets | Where-Object { $_.name -match 'setup\.exe' -or $_.name -match 'windows-x64-setup\.exe' })[0].browser_download_url
            } catch {
                $TargetApp.URL = "https://github.com/FreeTubeApp/FreeTube/releases/download/v0.21.3-beta/freetube-0.21.3-windows-x64-setup.exe"
            }
        }

        if ($TargetApp.Type -eq "PythonGame") {
            $SavePath = Get-SafeSavePath
            $DestFile = Join-Path $SavePath $TargetApp.File
            
            $ProgressLabel.Text = "Downloading $($TargetApp.Name)..."
            [System.Windows.Forms.Application]::DoEvents()

            try {
                Invoke-WebRequest -Uri $TargetApp.URL -OutFile $DestFile -UseBasicParsing -UserAgent $WebAgent
                $GameSavePaths += "$($TargetApp.Name) -> $DestFile" 

                $ProgressLabel.Text = "Installing Python modules for $($TargetApp.Name)..."
                [System.Windows.Forms.Application]::DoEvents()

                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
                $PipProc = Start-Process "python" -ArgumentList "-m pip install $($TargetApp.Req)" -PassThru -WindowStyle Hidden -ErrorAction SilentlyContinue
                while ($PipProc -and -not $PipProc.HasExited) {
                    [System.Windows.Forms.Application]::DoEvents()
                    Start-Sleep -Milliseconds 250
                }
            } catch {}
        } 
        else {
            $ProgressLabel.Text = "Downloading $($TargetApp.Name)..."
            [System.Windows.Forms.Application]::DoEvents()

            $UniquePath = Join-Path $env:TEMP $TargetApp.File
            Invoke-WebRequest -Uri $TargetApp.URL -OutFile $UniquePath -UseBasicParsing -UserAgent $WebAgent

            $ProgressLabel.Text = "Installing $($TargetApp.Name)..."
            [System.Windows.Forms.Application]::DoEvents()

            if ($TargetApp.Type -eq "Roblox") {
                Start-Process -FilePath $UniquePath -ArgumentList $TargetApp.Args
                $MaxWait = 240 
                $Attempt = 0
                while (-not (Test-AppInstalled "roblox") -and ($Attempt -lt $MaxWait)) {
                    [System.Windows.Forms.Application]::DoEvents()
                    Start-Sleep -Milliseconds 500
                    $Attempt++
                }
                Stop-Process -Name "RobloxPlayerBeta" -Force -ErrorAction SilentlyContinue

            } else {
                $Proc = $null
                if ($TargetApp.Type -eq "Msi") {
                    $Proc = Start-Process "msiexec.exe" -ArgumentList "/i `"$UniquePath`" $($TargetApp.Args)" -PassThru
                } else {
                    $Proc = Start-Process -FilePath $UniquePath -ArgumentList $TargetApp.Args -PassThru
                }
                while ($Proc -and -not $Proc.HasExited) {
                    [System.Windows.Forms.Application]::DoEvents()
                    Start-Sleep -Milliseconds 250
                }
            }
            Remove-Item $UniquePath -Force -ErrorAction SilentlyContinue
        }
    }

    $ProgressLabel.ForeColor = [System.Drawing.Color]::LimeGreen
    $FinalText = "All app changes complete!`n"
    if ($GameSavePaths.Count -gt 0) { $FinalText += "`nNew games saved to:`n" + ($GameSavePaths -join "`n") }
    
    $ProgressLabel.Text = $FinalText
    [System.Windows.Forms.Application]::DoEvents()
    Start-Sleep -Seconds 3

    $AppTitle.Text = "Let's customize your experience"
    $AppSubTitle.Text = "Check to install. Uncheck to uninstall."
    $ProgressLabel.Visible = $false
    $ProgressLabel.ForeColor = [System.Drawing.Color]::Cyan 

    $ApplyAppBtn.Visible = $true
    $NextPageBtn.Visible = $true
    $GameGroup.Visible = $true
    $DevGroup.Visible = $true
    
    foreach ($chk in $AllCheckboxes) {
        if (Test-AppInstalled $chk.Tag.ID) {
            $chk.Checked = $true
            $chk.ForeColor = [System.Drawing.Color]::LimeGreen
        } else {
            $chk.Checked = $false
            $chk.ForeColor = [System.Drawing.Color]::White
        }
    }
})

$NextPageBtn.Add_Click({
    $AppWindow.Visible = $false
    $DesktopWindow.Visible = $true
})

$AppWindow.Controls.Add($ApplyAppBtn)
$AppWindow.Controls.Add($NextPageBtn)
$Form.Controls.Add($AppWindow)

# --- 8. CENTERING LOGIC ---
function Center-Elements {
    $fw = [int]$Form.ClientSize.Width
    $fh = [int]$Form.ClientSize.Height
    
    $TitleLabel.Location = New-Object System.Drawing.Point([int](($fw - $TitleLabel.Width) / 2), [int](($fh / 2) - 150))
    $SubTitleLabel.Location = New-Object System.Drawing.Point([int](($fw - $SubTitleLabel.Width) / 2), [int]($fh / 2))
    
    $StatusLabel.Location = New-Object System.Drawing.Point([int](($fw - $StatusLabel.Width) / 2), [int](($fh / 2) - 100))
    $ConnectBtn.Location = New-Object System.Drawing.Point([int](($fw - $ConnectBtn.Width) / 2), [int]($fh / 2))
    $CredLabel.Location = New-Object System.Drawing.Point([int](($fw - $CredLabel.Width) / 2), [int](($fh / 2) + 80))
    
    $AppWindow.Location = New-Object System.Drawing.Point([int](($fw - $AppWindow.Width) / 2), [int](($fh - $AppWindow.Height) / 2))
    $DesktopWindow.Location = New-Object System.Drawing.Point([int](($fw - $DesktopWindow.Width) / 2), [int](($fh - $DesktopWindow.Height) / 2))
    $TweaksWindow.Location = New-Object System.Drawing.Point([int](($fw - $TweaksWindow.Width) / 2), [int](($fh - $TweaksWindow.Height) / 2))
}
$Form.Add_Load({ Center-Elements })

# --- 9. TIMERS AND LOGIC ---
$IntroTimer = New-Object System.Windows.Forms.Timer
$IntroTimer.Interval = 4500 
$IntroTimer.Add_Tick({
    $IntroTimer.Stop()
    
    # Try setting DNS silently before connectivity check!
    Set-GoogleDNS

    $IntroPanel.Visible = $false
    $NetPanel.Visible = $true
    
    $Ping = Test-Connection -ComputerName "8.8.8.8" -Count 1 -Quiet -ErrorAction SilentlyContinue
    if ($Ping) {
        $StatusLabel.Text = "Status: Connected to Internet!"
        Center-Elements
        [System.Windows.Forms.Application]::DoEvents()
        Start-XpMusic 
        Start-Sleep -Seconds 2
        $NetPanel.Visible = $false
        $AppWindow.Visible = $true
    } else {
        $StatusLabel.Text = "Status: No Internet Connection"
        Center-Elements
        [System.Windows.Forms.Application]::DoEvents()
        $ConnectBtn.Visible = $true
    }
})

$ConnectBtn.Add_Click({
    $ConnectBtn.Enabled = $false
    $StatusLabel.Text = "Attempting to connect to profile..."
    Center-Elements
    [System.Windows.Forms.Application]::DoEvents()
    
    $NetshOutput = netsh wlan connect name="BIT_Hotspot25" 2>&1
    Start-Sleep -Seconds 3 
    
    # Run DNS Setup again in case the adapter just came online!
    Set-GoogleDNS

    $Ping2 = Test-Connection -ComputerName "8.8.8.8" -Count 1 -Quiet -ErrorAction SilentlyContinue
    if ($Ping2) {
        $StatusLabel.Text = "Status: Connected successfully!"
        Center-Elements
        [System.Windows.Forms.Application]::DoEvents()
        Start-XpMusic 
        Start-Sleep -Seconds 2
        $NetPanel.Visible = $false
        $AppWindow.Visible = $true
    } else {
        $StatusLabel.Text = "Status: Connection Failed."
        $CredLabel.Text = "Network: BIT_Hotspot25`nPassword: SPLURuST"
        Center-Elements
        $ConnectBtn.Enabled = $true
    }
})

# --- 10. AUDIO ENGINE ---
$Form.Add_Shown({
    $OobeMp4Path = "C:\Windows\SystemApps\Microsoft.Windows.CloudExperienceHost_cw5n1h2txyewy\media\oobe-intro.mp4"
    if (Test-Path $OobeMp4Path) {
        $global:WMP = New-Object -ComObject WMPlayer.OCX
        $global:WMP.uiMode = "none" 
        $global:WMP.settings.volume = 100
        $global:WMP.URL = $OobeMp4Path
        $global:WMP.controls.play()
    }
    $IntroTimer.Start()
})

$Form.Add_FormClosed({
    if ($global:WMP) {
        $global:WMP.close()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($global:WMP) | Out-Null
    }
    if ($global:SoundPlayer) {
        $global:SoundPlayer.Stop()
        $global:SoundPlayer.Dispose()
    }
})

[void]$Form.ShowDialog()