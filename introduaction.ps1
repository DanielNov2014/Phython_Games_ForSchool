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

# --- SHARED LOOK & FEEL (Windows 11 style) ---
$Accent      = [System.Drawing.Color]::FromArgb(0, 120, 215)   # Windows 11 blue
$AccentHover = [System.Drawing.Color]::FromArgb(0, 145, 245)
$GoColor     = [System.Drawing.Color]::FromArgb(16, 137, 62)   # green "next / go"
$DangerColor = [System.Drawing.Color]::FromArgb(196, 43, 28)   # red "finish / close"
$PanelBack   = [System.Drawing.Color]::FromArgb(250, 32, 32, 34)

# Pick the nicest UI font that's actually installed, once
$UiFontName = "Segoe UI"
foreach ($n in @("Segoe UI Variable Text", "Segoe UI")) {
    try { $probe = New-Object System.Drawing.FontFamily($n); $probe.Dispose(); $UiFontName = $n; break } catch {}
}

# Load an image without keeping a lock on the file (the live wallpaper is often in use)
function Load-ImageNoLock ($Path) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $ms = New-Object System.IO.MemoryStream(, $bytes)
    try {
        $tmp = [System.Drawing.Image]::FromStream($ms)
        $bmp = New-Object System.Drawing.Bitmap($tmp)
        $tmp.Dispose()
        return $bmp
    } finally { $ms.Dispose() }
}

# The wallpaper the PC is actually using right now, with sensible fallbacks
function Get-CurrentWallpaper {
    $candidates = @()
    try {
        $w = (Get-ItemProperty 'HKCU:\Control Panel\Desktop' -Name WallPaper -ErrorAction SilentlyContinue).WallPaper
        if ($w) { $candidates += $w }
    } catch {}
    $candidates += (Join-Path $env:AppData 'Microsoft\Windows\Themes\TranscodedWallpaper')  # spotlight / slideshow cache
    $candidates += 'C:\Windows\Web\Wallpaper\Windows\img0.jpg'                                # default Win11 bloom
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) {
            try { return Load-ImageNoLock $c } catch {}
        }
    }
    return $null
}

# Round a control's corners (used for the cards and buttons)
function Set-RoundedRegion ($Control, $Radius) {
    $d = $Radius * 2
    $w = $Control.Width; $h = $Control.Height
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddArc(0, 0, $d, $d, 180, 90)
    $path.AddArc(($w - $d), 0, $d, $d, 270, 90)
    $path.AddArc(($w - $d), ($h - $d), $d, $d, 0, 90)
    $path.AddArc(0, ($h - $d), $d, $d, 90, 90)
    $path.CloseFigure()
    $Control.Region = New-Object System.Drawing.Region($path)
}

# Give a button the flat, rounded, hover-highlight look. Keeps its own colour.
function Set-ModernButton ($Button, $BackColor) {
    if (-not $BackColor) { $BackColor = $Accent }
    $Button.FlatStyle = 'Flat'
    $Button.FlatAppearance.BorderSize = 0
    $Button.FlatAppearance.MouseOverBackColor = [System.Windows.Forms.ControlPaint]::Light($BackColor, 0.15)
    $Button.FlatAppearance.MouseDownBackColor = [System.Windows.Forms.ControlPaint]::Dark($BackColor, 0.05)
    $Button.BackColor = $BackColor
    $Button.ForeColor = [System.Drawing.Color]::White
    $Button.Cursor = 'Hand'
    if ($Button.Width -gt 0 -and $Button.Height -gt 0) { Set-RoundedRegion $Button ([Math]::Min(10, [int]($Button.Height / 3))) }
}

# Walk a container and modernise every button inside it
function Style-AllButtons ($Container) {
    foreach ($c in $Container.Controls) {
        if ($c -is [System.Windows.Forms.Button]) { Set-ModernButton $c $c.BackColor }
        if ($c.Controls.Count -gt 0) { Style-AllButtons $c }
    }
}

# Accent bar + step counter that make each setup page feel like part of one flow
function Add-PageChrome ($Window, $StepText) {
    $bar = New-Object System.Windows.Forms.Panel
    $bar.Size = New-Object System.Drawing.Size(5, 40)
    $bar.Location = New-Object System.Drawing.Point(8, 22)
    $bar.BackColor = $Accent
    $Window.Controls.Add($bar); $bar.BringToFront()

    $step = New-Object System.Windows.Forms.Label
    $step.Text = $StepText
    $step.Font = New-Object System.Drawing.Font($UiFontName, 10, [System.Drawing.FontStyle]::Bold)
    $step.ForeColor = $Accent
    $step.BackColor = [System.Drawing.Color]::Transparent
    $step.AutoSize = $true
    $Window.Controls.Add($step)
    $step.Location = New-Object System.Drawing.Point(($Window.Width - $step.PreferredWidth - 24), 34)
    $step.BringToFront()
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

# --- WI-FI NETWORK (the one place to change it) ---
$WifiSsid = "BIT_Hotspot26"
$WifiPass = "DENTErAv"

# Saves the Wi-Fi profile so 'netsh wlan connect' works on a PC that has never joined this network.
# Same profile the autounattend.xml installs, so a fresh PC and the intro agree.
function Install-WifiProfile {
    $hex = ([System.Text.Encoding]::UTF8.GetBytes($WifiSsid) | ForEach-Object { $_.ToString("X2") }) -join ''
    $xml = @"
<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>$WifiSsid</name>
    <SSIDConfig><SSID><hex>$hex</hex><name>$WifiSsid</name></SSID></SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>$WifiPass</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>
"@
    $path = Join-Path $env:TEMP "$WifiSsid.xml"
    try {
        $xml | Out-File -FilePath $path -Encoding UTF8 -Force
        netsh wlan add profile filename="$path" user=all 2>&1 | Out-Null
    } catch {} finally {
        Remove-Item $path -Force -ErrorAction SilentlyContinue   # don't leave the password lying in TEMP
    }
}

function Get-SafeSavePath {
    $Desktop = [System.Environment]::GetFolderPath('Desktop')
    $Downloads = Join-Path ([System.Environment]::GetFolderPath('UserProfile')) "Downloads"
    $Profile = [System.Environment]::GetFolderPath('UserProfile')
    if (Test-Path $Desktop) { return $Desktop }
    if (Test-Path $Downloads) { return $Downloads }
    return $Profile
}

# Roblox refuses to run in a virtual machine, so there's no point installing it there
function Test-IsVM {
    try {
        $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
        $bios = Get-CimInstance Win32_BIOS -ErrorAction SilentlyContinue
        $blob = "$($cs.Manufacturer) $($cs.Model) $($bios.Manufacturer) $($bios.SerialNumber) $($bios.Version)"
        if ($blob -match 'VMware|VirtualBox|VBOX|Virtual Machine|Hyper-V|KVM|QEMU|Xen|Parallels|Bochs|innotek') { return $true }
        if ($env:COMPUTERNAME -match 'WINDEV|MININT') { return $true }   # Microsoft eval VMs
    } catch {}
    return $false
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

# ==========================================
# --- USER ACCOUNT & ADMIN ACTIVATION BACKEND ---
# ==========================================
# A new standard (non-admin) local account is created here. A password-gated
# command, "activateadmin <password>", later promotes that account to admin.
# The promotion runs from a SYSTEM scheduled task (a standard user can't add
# themselves to Administrators), and the password is only ever stored as a
# salted SHA-256 hash - never in plain text.
$AdminCfgDir = Join-Path $env:ProgramData "Win11Intro"
$AdminReqDir = Join-Path $AdminCfgDir "requests"

function Get-PasswordHash ($Salt, $Password) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = $Salt + [System.Text.Encoding]::UTF8.GetBytes($Password)
    return [Convert]::ToBase64String($sha.ComputeHash($bytes))
}

function New-IntroUserAccount ($User, $Password, $BlockAdminPrompts, $OtherUser) {
    $sec = ConvertTo-SecureString $Password -AsPlainText -Force
    if (Get-LocalUser -Name $User -ErrorAction SilentlyContinue) {
        Set-LocalUser -Name $User -Password $sec
    } else {
        New-LocalUser -Name $User -Password $sec -FullName $User -Description "Created by Windows 11 Introduction" -PasswordNeverExpires -AccountNeverExpires -ErrorAction Stop | Out-Null
    }
    # Standard user (NOT an administrator) - that's the whole point of activateadmin
    Add-LocalGroupMember -Group "Users" -Member $User -ErrorAction SilentlyContinue
    # Hyper-V "Enhanced Session" signs in over Remote Desktop, and "Other user" forces that
    # path - a plain standard user gets "you need the right to sign in through Remote Desktop
    # Services". Granting the sign-in right (not admin) fixes it. Looked up by SID so it works
    # in any language.
    try { Add-LocalGroupMember -Group (Get-LocalGroup -SID "S-1-5-32-555") -Member $User -ErrorAction SilentlyContinue } catch {}

    $sys = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
    if (-not (Test-Path $sys)) { New-Item -Path $sys -Force | Out-Null }

    $userList = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\SpecialAccounts\UserList"
    if (Test-Path $userList) { Remove-ItemProperty -Path $userList -Name $User -ErrorAction SilentlyContinue }

    # "Other user" sign-in: a blank username + password box instead of account tiles.
    # Two settings are needed for it to be consistent - one covers the sign-in screen after a
    # sign-out, the other covers the lock screen after a timeout (which caused the earlier flip-flop).
    if ($OtherUser) {
        Set-ItemProperty -Path $sys -Name "dontdisplaylastusername" -Value 1 -Force
        Set-ItemProperty -Path $sys -Name "DontDisplayLockedUserId" -Value 3 -Force
    } else {
        Set-ItemProperty -Path $sys -Name "dontdisplaylastusername" -Value 0 -Force
        Remove-ItemProperty -Path $sys -Name "DontDisplayLockedUserId" -ErrorAction SilentlyContinue
    }

    # Skip the first-sign-in setup for new accounts ("Hi, preparing Windows", privacy pages)
    Set-ItemProperty -Path $sys -Name "EnableFirstLogonAnimation" -Value 0 -Force
    $oobe = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\OOBE"
    if (-not (Test-Path $oobe)) { New-Item -Path $oobe -Force | Out-Null }
    Set-ItemProperty -Path $oobe -Name "DisablePrivacyExperience" -Value 1 -Force

    # When a standard user launches something that needs admin, just deny it silently
    # instead of popping a prompt that asks for an admin password.
    # 0 = automatically deny elevation requests.
    if ($BlockAdminPrompts) {
        Set-ItemProperty -Path $sys -Name "ConsentPromptBehaviorUser" -Value 0 -Force
    }
}

function Install-AdminActivator ($User, $AdminPassword) {
    New-Item -ItemType Directory -Force -Path $AdminCfgDir | Out-Null
    New-Item -ItemType Directory -Force -Path $AdminReqDir | Out-Null

    # Standard users may drop a request + read the result here, but not touch the config or helper above
    $acl = Get-Acl $AdminReqDir
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Users", "Modify", "ContainerInherit,ObjectInherit", "None", "Allow")
    $acl.AddAccessRule($rule)
    Set-Acl -Path $AdminReqDir -AclObject $acl

    # Store the target user + a salted hash of the unlock password (never the password itself)
    $salt = New-Object byte[] 16
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($salt)
    $cfg = [ordered]@{ User = $User; Salt = [Convert]::ToBase64String($salt); Hash = (Get-PasswordHash $salt $AdminPassword) }
    $cfg | ConvertTo-Json | Set-Content -Path (Join-Path $AdminCfgDir "admin.cfg") -Encoding UTF8

    # Helper that runs as SYSTEM: check the password, then add OR remove admin rights
    $helper = @'
$ErrorActionPreference = "Stop"
$dir = "__CFGDIR__"; $reqDir = "__REQDIR__"
$res = Join-Path $reqDir "result.txt"
$actReq = Join-Path $reqDir "activate.txt"
$deactReq = Join-Path $reqDir "deactivate.txt"
$action = $null; $req = $null
if (Test-Path $actReq) { $action = "activate"; $req = $actReq }
elseif (Test-Path $deactReq) { $action = "deactivate"; $req = $deactReq }
else { return }
try { $pw = ([System.IO.File]::ReadAllText($req)).Trim() } catch { return }
Remove-Item $req -Force -ErrorAction SilentlyContinue
try {
    $cfg  = Get-Content (Join-Path $dir "admin.cfg") -Raw | ConvertFrom-Json
    $salt = [Convert]::FromBase64String($cfg.Salt)
    $sha  = [System.Security.Cryptography.SHA256]::Create()
    $hash = [Convert]::ToBase64String($sha.ComputeHash($salt + [System.Text.Encoding]::UTF8.GetBytes($pw)))
    if ($hash -ne $cfg.Hash) {
        Set-Content $res "DENIED - wrong password." -Encoding UTF8
        return
    }
    $ual = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\SpecialAccounts\UserList"
    if (-not (Test-Path $ual)) { New-Item -Path $ual -Force | Out-Null }
    if ($action -eq "activate") {
        # Hand control back to the pre-existing admin account: hide + disable this one
        Set-ItemProperty -Path $ual -Name $cfg.User -Value 0 -Type DWord -Force
        Disable-LocalUser -Name $cfg.User -ErrorAction SilentlyContinue
        Set-Content $res "SUCCESS - '$($cfg.User)' hidden. Signing you out to the admin account." -Encoding UTF8
    } else {
        # Bring this account back to the sign-in screen
        Set-ItemProperty -Path $ual -Name $cfg.User -Value 1 -Type DWord -Force
        Enable-LocalUser -Name $cfg.User -ErrorAction SilentlyContinue
        Set-Content $res "SUCCESS - '$($cfg.User)' is visible again." -Encoding UTF8
    }
} catch {
    Set-Content $res ("ERROR - " + $_.Exception.Message) -Encoding UTF8
}
'@
    $helper = $helper.Replace("__CFGDIR__", $AdminCfgDir).Replace("__REQDIR__", $AdminReqDir)
    $helperPath = Join-Path $AdminCfgDir "activate-admin.ps1"
    Set-Content -Path $helperPath -Value $helper -Encoding UTF8

    # Event source so the commands can trigger the task instantly
    try {
        if (-not [System.Diagnostics.EventLog]::SourceExists("Win11Intro")) {
            [System.Diagnostics.EventLog]::CreateEventSource("Win11Intro", "Application")
        }
    } catch {}

    # SYSTEM task: fires on that event, and also polls once a minute as a fallback
    $taskName = "Win11Intro-ActivateAdmin"
    $xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Adds or removes admin rights when the correct password is supplied via 'activateadmin' / 'deactivateadmin'.</Description></RegistrationInfo>
  <Triggers>
    <EventTrigger><Enabled>true</Enabled><Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="Application"&gt;&lt;Select Path="Application"&gt;*[System[Provider[@Name='Win11Intro'] and (EventID=4001)]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription></EventTrigger>
    <TimeTrigger><Enabled>true</Enabled><StartBoundary>2020-01-01T00:00:00</StartBoundary><Repetition><Interval>PT1M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition></TimeTrigger>
  </Triggers>
  <Principals><Principal id="Author"><UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><StartWhenAvailable>true</StartWhenAvailable><Enabled>true</Enabled><ExecutionTimeLimit>PT5M</ExecutionTimeLimit><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries></Settings>
  <Actions Context="Author"><Exec><Command>powershell.exe</Command><Arguments>-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "__HELPER__"</Arguments></Exec></Actions>
</Task>
"@
    $xml = $xml.Replace("__HELPER__", $helperPath)
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $taskName -Xml $xml -Force | Out-Null

    # Template for the two commands. On SUCCESS they sign the user out so the group change applies.
    $cmdTemplate = @'
@echo off
setlocal enabledelayedexpansion
if "%~1"=="" (
  echo Usage: __VERB__ ^<password^>
  echo __DESC__
  exit /b 1
)
set "REQ=__REQDIR__\__REQFILE__"
set "RES=__REQDIR__\result.txt"
del "%RES%" >nul 2>&1
> "%REQ%" echo %*
powershell -NoProfile -Command "try { Write-EventLog -LogName Application -Source 'Win11Intro' -EventId 4001 -EntryType Information -Message '__VERB__' } catch {}" >nul 2>&1
echo Please wait...
set /a n=0
:loop
>nul ping -n 2 127.0.0.1
if exist "%RES%" ( type "%RES%" & echo. & goto done )
set /a n+=1
if !n! lss 40 goto loop
echo Timed out - please try again in a moment.
goto end
:done
findstr /c:"SUCCESS" "%RES%" >nul 2>&1
if !errorlevel! equ 0 (
  echo Signing you out so the change takes effect...
  >nul ping -n 4 127.0.0.1
  shutdown /l
)
:end
del "%REQ%" >nul 2>&1
endlocal
'@

    $activateCmd = $cmdTemplate.Replace("__REQDIR__", $AdminReqDir).Replace("__VERB__", "activateadmin").Replace("__REQFILE__", "activate.txt").Replace("__DESC__", "Grants your account administrator rights when the password is correct.")
    Set-Content -Path (Join-Path $env:WINDIR "activateadmin.cmd") -Value $activateCmd -Encoding Ascii

    $deactivateCmd = $cmdTemplate.Replace("__REQDIR__", $AdminReqDir).Replace("__VERB__", "deactivateadmin").Replace("__REQFILE__", "deactivate.txt").Replace("__DESC__", "Removes administrator rights from your account when the password is correct.")
    Set-Content -Path (Join-Path $env:WINDIR "deactivateadmin.cmd") -Value $deactivateCmd -Encoding Ascii
}

# ==========================================
# --- WELCOME-BACK SPLASH BACKEND ---
# ==========================================
# A short Satisfactory-style "Welcome back, <name>" animation that plays at sign-in.
# It's a standalone script dropped in ProgramData and launched by a logon scheduled task.
$WelcomeDir = Join-Path $env:ProgramData "Win11Intro"
$WelcomePath = Join-Path $WelcomeDir "welcome.ps1"
$WelcomeTask = "Win11Intro-Welcome"

$WelcomeScript = @'
param(
    [string]$UserName = $env:USERNAME,
    [string]$Logo = "Satisfactory",   # "Satisfactory" or "Windows11"
    [string]$RenderTo = ""            # if set, render frames to this dir instead of showing a window
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# --- Background: the current wallpaper, sharp (the animation reveals it) ---
function Load-ImageNoLock ($Path) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $ms = New-Object System.IO.MemoryStream(, $bytes)
    try { $t = [System.Drawing.Image]::FromStream($ms); $b = New-Object System.Drawing.Bitmap($t); $t.Dispose(); return $b } finally { $ms.Dispose() }
}
function Get-Wallpaper {
    $c = @()
    try { $w = (Get-ItemProperty 'HKCU:\Control Panel\Desktop' -Name WallPaper -EA SilentlyContinue).WallPaper; if ($w) { $c += $w } } catch {}
    $c += (Join-Path $env:AppData 'Microsoft\Windows\Themes\TranscodedWallpaper')
    $c += 'C:\Windows\Web\Wallpaper\Windows\img0.jpg'
    foreach ($p in $c) { if ($p -and (Test-Path $p)) { try { return Load-ImageNoLock $p } catch {} } }
    return $null
}

$SW = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width
$SH = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
if ($RenderTo) { $SW = 1920; $SH = 1080 }
$rawBg = Get-Wallpaper
$Bg = New-Object System.Drawing.Bitmap($SW, $SH)
$bgg = [System.Drawing.Graphics]::FromImage($Bg)
if ($rawBg) { $bgg.DrawImage($rawBg, 0, 0, $SW, $SH); $rawBg.Dispose() } else { $bgg.Clear([System.Drawing.Color]::FromArgb(20, 20, 24)) }
$bgg.Dispose()

# A heavily blurred copy of the wallpaper (shrink it right down, then scale it back up smoothly).
# Precomputed once; the band shows this through a clip so only the strip looks frosted.
$tiny = New-Object System.Drawing.Bitmap([Math]::Max(8, [int]($SW / 24)), [Math]::Max(8, [int]($SH / 24)))
$tg = [System.Drawing.Graphics]::FromImage($tiny)
$tg.InterpolationMode = 'HighQualityBicubic'
$tg.DrawImage($Bg, 0, 0, $tiny.Width, $tiny.Height)
$tg.Dispose()
$BgBlur = New-Object System.Drawing.Bitmap($SW, $SH)
$bb = [System.Drawing.Graphics]::FromImage($BgBlur)
$bb.InterpolationMode = 'HighQualityBilinear'
$ia = New-Object System.Drawing.Imaging.ImageAttributes
$ia.SetWrapMode([System.Drawing.Drawing2D.WrapMode]::TileFlipXY)   # no dark fringe at the edges
$bb.DrawImage($tiny, (New-Object System.Drawing.Rectangle(0, 0, $SW, $SH)), 0, 0, $tiny.Width, $tiny.Height, [System.Drawing.GraphicsUnit]::Pixel, $ia)
$bb.Dispose(); $tiny.Dispose()

$Orange = [System.Drawing.Color]::FromArgb(245, 158, 32)
function Font-Try ($names, $size, $style) {
    foreach ($n in $names) { try { return New-Object System.Drawing.Font($n, $size, $style) } catch {} }
    return New-Object System.Drawing.Font("Segoe UI", $size, $style)
}
$FLogo = Font-Try @("Segoe UI Semibold", "Segoe UI") 58 ([System.Drawing.FontStyle]::Bold)
$FSmall = Font-Try @("Segoe UI Semibold", "Segoe UI") 20 ([System.Drawing.FontStyle]::Bold)
$FTm = Font-Try @("Segoe UI") 14 ([System.Drawing.FontStyle]::Regular)
$FWelcome = Font-Try @("Segoe UI") 15 ([System.Drawing.FontStyle]::Regular)

$Duration = 2900
function E ($t, $a, $b) { $p = [Math]::Min(1.0, [Math]::Max(0.0, ($t - $a) / ($b - $a))); return 1 - [Math]::Pow(1 - $p, 3) }
function Lerp ($a, $b, $p) { return $a + ($b - $a) * $p }

# Frosted-glass strip across the middle: blurred + darkened wallpaper inside the strip only.
# Collapsing $half toward 0 closes it to a thin line.
function Draw-Band ($g, $cy, $half, $tintA) {
    if ($half -lt 1) { return }
    $top = [int]($cy - $half); $h = [int](2 * $half)
    $rect = New-Object System.Drawing.Rectangle(0, $top, $SW, $h)
    $g.SetClip($rect)
    $g.DrawImage($BgBlur, 0, 0, $SW, $SH)
    $g.ResetClip()

    # dark tint, with a short soft edge at the top and bottom so the strip doesn't look cut out
    $f = [int][Math]::Min(14, $half)
    $dark = [System.Drawing.Color]::FromArgb([int]$tintA, 8, 10, 14)
    $clear = [System.Drawing.Color]::FromArgb(0, 8, 10, 14)
    if ($h - 2 * $f -gt 0) {
        $sb = New-Object System.Drawing.SolidBrush($dark)
        $g.FillRectangle($sb, 0, ($top + $f), $SW, ($h - 2 * $f)); $sb.Dispose()
    }
    if ($f -gt 0) {
        $rT = New-Object System.Drawing.RectangleF(0, $top, $SW, $f)
        $bT = New-Object System.Drawing.Drawing2D.LinearGradientBrush($rT, $clear, $dark, [System.Drawing.Drawing2D.LinearGradientMode]::Vertical)
        $bT.WrapMode = 'TileFlipXY'
        $g.FillRectangle($bT, 0, $top, $SW, $f); $bT.Dispose()
        $rB = New-Object System.Drawing.RectangleF(0, ($top + $h - $f), $SW, $f)
        $bB = New-Object System.Drawing.Drawing2D.LinearGradientBrush($rB, $dark, $clear, [System.Drawing.Drawing2D.LinearGradientMode]::Vertical)
        $bB.WrapMode = 'TileFlipXY'
        $g.FillRectangle($bB, 0, ($top + $h - $f), $SW, $f); $bB.Dispose()
    }
}

function Draw-Center ($g, $text, $font, $brush, $cx, $y) {
    $sz = $g.MeasureString($text, $font)
    $g.DrawString($text, $font, $brush, [float]($cx - $sz.Width / 2), [float]$y)
    return $sz
}

# Draw a wordmark centred at (cx,cy), scaled + faded.
function Draw-Wordmark ($g, $kind, $cx, $cy, $scale, $alpha, $font) {
    if ($alpha -le 0.01 -or $scale -le 0.001) { return }
    $state = $g.Save()
    $g.TranslateTransform([float]$cx, [float]$cy)
    $g.ScaleTransform([float]$scale, [float]$scale)
    $a = [int](255 * [Math]::Min(1.0, $alpha))
    $white = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb($a, 245, 245, 245))
    $orange = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb($a, $Orange.R, $Orange.G, $Orange.B))
    $pen = New-Object System.Drawing.Pen((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb([int]($a * 0.8), 235, 235, 235))), 1.6)
    $h = $font.Height

    if ($kind -eq "Windows11") {
        $ts = $h * 0.5; $gap = $ts * 0.16
        $lx = -($ts + $gap / 2); $ly = -($h * 0.95)
        $tb = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb($a, 60, 160, 240))
        foreach ($p in @(@(0, 0), @(1, 0), @(0, 1), @(1, 1))) {
            $g.FillRectangle($tb, [float]($lx + $p[0] * ($ts + $gap)), [float]($ly + $p[1] * ($ts + $gap)), [float]$ts, [float]$ts)
        }
        $tb.Dispose()
        [void](Draw-Center $g "Windows 11" $font $white 0 (-$h / 2))
    }
    elseif ($kind -eq "FICSIT") {
        $chk = [string][char]0x2713
        $wF = $g.MeasureString("FICS", $font).Width
        $wC = $g.MeasureString($chk, $font).Width
        $wT = $g.MeasureString("T", $font).Width
        $total = $wF + $wC + $wT
        $x = -$total / 2; $y = -$h / 2
        $g.DrawString("FICS", $font, $white, [float]$x, $y); $x += $wF
        $g.DrawString($chk, $font, $orange, [float]$x, $y); $x += $wC
        $g.DrawString("T", $font, $white, [float]$x, $y)
    }
    else {
        $wH = $g.MeasureString("hud", $font).Width
        $wO = $g.MeasureString("OS", $font).Width
        $total = $wH + $wO
        $x = -$total / 2; $y = -$h / 2
        $g.DrawString("hud", $font, $white, [float]$x, $y)
        $g.DrawString("OS", $font, $orange, [float]($x + $wH), $y)
        $g.DrawString([char]0x2122 + "", $FTm, $white, [float]($x + $total + 2), ($y + $h * 0.08))
    }
    $white.Dispose(); $orange.Dispose(); $pen.Dispose()
    $g.Restore($state)
}

function Draw-Frame ($g, $t) {
    $g.SmoothingMode = 'AntiAlias'
    $g.TextRenderingHint = 'AntiAliasGridFit'
    $g.InterpolationMode = 'HighQualityBilinear'
    $cx = $SW / 2; $cy = $SH / 2

    # Sharp desktop the whole time - only the strip is frosted
    $g.DrawImage($Bg, 0, 0, $SW, $SH)

    # Stages, strictly one after the other:
    #  A  fade in and hold                                             (0 - 1000)
    #  B  the two lines close on each other and swallow the big logo   (1000 - 1650)
    #  C  the single line left shrinks to nothing on X, anchored centre (1650 - 2050)
    #  D  the frosted strip collapses on Y while the small logo fades   (2050 - 2800)
    $In = E $t 0 350
    $pB = E $t 1000 1650
    $pC = E $t 1650 2050
    $pD = E $t 2050 2800

    $half = Lerp 105 0 $pD
    $tintA = 135 * $In * (1 - $pD)
    Draw-Band $g $cy $half $tintA

    # Where the big logo sits and where its two lines start (just above and below it)
    $isWin = ($Logo -eq "Windows11")
    $h = $FLogo.Height
    if ($isWin) {
        $bigCy = $cy - 4
        $top0 = $bigCy - $h * 0.95 - 6
        $bot0 = $bigCy + $h / 2 + 6
        $hw = $g.MeasureString("Windows 11", $FLogo).Width / 2 + 40
    } else {
        $bigCy = $cy + 6
        $top0 = $bigCy - $h / 2 - 4
        $bot0 = $bigCy + $h / 2 + 2
        $hw = ($g.MeasureString("hud", $FLogo).Width + $g.MeasureString("OS", $FLogo).Width) / 2 + 40
    }
    $mid = ($top0 + $bot0) / 2
    $yTop = Lerp $top0 $mid $pB
    $yBot = Lerp $bot0 $mid $pB

    # small FICSIT sits above the lines and only fades in stage D
    if (-not $isWin) { Draw-Wordmark $g "FICSIT" $cx ($cy - 72) 1 ($In * (1 - $pD)) $FSmall }

    # big logo: only the part between the two lines is drawn, so the lines swallow it as they close
    if ($pB -lt 0.999 -and $In -gt 0.01) {
        $g.SetClip((New-Object System.Drawing.RectangleF(0, [float]$yTop, [float]$SW, [float][Math]::Max(0, $yBot - $yTop))))
        $kind = if ($isWin) { "Windows11" } else { "hudOS" }
        Draw-Wordmark $g $kind $cx $bigCy 1 $In $FLogo
        $g.ResetClip()
    }

    # the lines: two closing on each other (B), then the one that's left shrinks on X (C)
    $lw = Lerp $hw 0 $pC
    if ($lw -gt 0.5 -and $In -gt 0.01) {
        $lp = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb([int](220 * $In), 235, 235, 235), 1.6)
        if ($pB -lt 0.999) {
            $g.DrawLine($lp, [float]($cx - $lw), [float]$yTop, [float]($cx + $lw), [float]$yTop)
            $g.DrawLine($lp, [float]($cx - $lw), [float]$yBot, [float]($cx + $lw), [float]$yBot)
        } else {
            $g.DrawLine($lp, [float]($cx - $lw), [float]$mid, [float]($cx + $lw), [float]$mid)
        }
        $lp.Dispose()
    }

    $welcomeA = $In * (1 - (E $t 1000 1300))
    if ($welcomeA -gt 0.01) {
        $wb = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb([int](235 * $welcomeA), 235, 235, 235))
        Draw-Center $g ("WELCOME BACK, " + $UserName.ToUpper()) $FWelcome $wb $cx ($cy + 56) | Out-Null
        $wb.Dispose()
    }
}

if ($RenderTo) {
    New-Item -ItemType Directory -Force $RenderTo | Out-Null
    $times = 250, 900, 1350, 1800, 2300, 2700
    $cols = 3; $rows = 2; $tw = 640; $th = 360
    $sheet = New-Object System.Drawing.Bitmap(($cols * $tw), ($rows * $th))
    $sg = [System.Drawing.Graphics]::FromImage($sheet)
    $lf = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
    for ($i = 0; $i -lt $times.Count; $i++) {
        $bmp = New-Object System.Drawing.Bitmap($SW, $SH)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        Draw-Frame $g $times[$i]
        $g.Dispose()
        $x = ($i % $cols) * $tw; $y = [Math]::Floor($i / $cols) * $th
        $sg.InterpolationMode = 'HighQualityBicubic'
        $sg.DrawImage($bmp, $x, $y, $tw, $th)
        $sg.DrawString("t=$($times[$i])ms", $lf, [System.Drawing.Brushes]::Yellow, ($x + 8), ($y + 6))
        $bmp.Dispose()
    }
    $sheet.Save((Join-Path $RenderTo "welcome_sheet.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    # one full-size frame too, to judge the blur properly
    $full = New-Object System.Drawing.Bitmap($SW, $SH)
    $fg = [System.Drawing.Graphics]::FromImage($full); Draw-Frame $fg 1350; $fg.Dispose()
    $full.Save((Join-Path $RenderTo "welcome_full.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    "rendered $Logo -> $RenderTo"
    return
}

# --- Live: full-screen splash ---
# At sign-in the logon task can fire before the desktop exists - wait for the shell first
$deadline = (Get-Date).AddSeconds(25)
while (-not (Get-Process explorer -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 300 }
Start-Sleep -Milliseconds 1200

$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = 'None'
$form.WindowState = 'Maximized'
$form.TopMost = $true
$form.BackColor = 'Black'
$form.ShowInTaskbar = $false
$form.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
$flags = [System.Reflection.BindingFlags]::NonPublic -bor [System.Reflection.BindingFlags]::Instance
[System.Windows.Forms.Control].GetProperty("DoubleBuffered", $flags).SetValue($form, $true, $null)

$clock = New-Object System.Diagnostics.Stopwatch
$form.Add_Paint({ Draw-Frame $_.Graphics $clock.ElapsedMilliseconds })
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 15
$timer.Add_Tick({
    if ($clock.ElapsedMilliseconds -ge $Duration) { $timer.Stop(); $form.Close(); return }
    $form.Invalidate()
})
$form.Add_Shown({ $clock.Start(); $timer.Start() })
[void]$form.ShowDialog()
'@

function Save-WelcomeScript {
    New-Item -ItemType Directory -Force -Path $WelcomeDir | Out-Null
    Set-Content -Path $WelcomePath -Value $WelcomeScript -Encoding UTF8
    return $WelcomePath
}

function Install-WelcomeScreen ($Logo) {
    $path = Save-WelcomeScript
    Set-Content -Path (Join-Path $WelcomeDir "welcome.cfg") -Value $Logo -Encoding UTF8
    # Logon task: runs interactively for anyone in the Users group at sign-in
    $xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Win11 Introduction welcome-back splash at sign-in.</Description></RegistrationInfo>
  <Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers>
  <Principals><Principal id="Author"><GroupId>S-1-5-32-545</GroupId><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>Parallel</MultipleInstancesPolicy><StartWhenAvailable>true</StartWhenAvailable><Enabled>true</Enabled><ExecutionTimeLimit>PT2M</ExecutionTimeLimit><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries></Settings>
  <Actions Context="Author"><Exec><Command>powershell.exe</Command><Arguments>-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "__PATH__" -Logo "__LOGO__"</Arguments></Exec></Actions>
</Task>
"@
    $xml = $xml.Replace("__PATH__", $path).Replace("__LOGO__", $Logo)
    Unregister-ScheduledTask -TaskName $WelcomeTask -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $WelcomeTask -Xml $xml -Force | Out-Null
}

function Remove-WelcomeScreen {
    Unregister-ScheduledTask -TaskName $WelcomeTask -Confirm:$false -ErrorAction SilentlyContinue
}

function Show-WelcomePreview ($Logo) {
    $path = Save-WelcomeScript
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$path`" -Logo `"$Logo`""
}

function Start-XpMusic ($MusicUrl = "https://github.com/DanielNov2014/Phython_Games_ForSchool/raw/refs/heads/main/xpmusic.wav") {
    # Already playing, or already downloading? Nothing to do.
    if ($global:MediaPlayer -or $global:MusicDownload) { return }

    # New file name on purpose: old versions of this script could leave a cut-off xpmusic.wav behind
    $MusicPath = Join-Path $env:TEMP "xpmusic_v2.wav"

    if (-not (Test-Path $MusicPath)) {
        # Download on a background runspace so the window never freezes.
        # It saves to a .part file first, so a cut-off download is never mistaken for the real song.
        $global:MusicDownload = [PowerShell]::Create()
        [void]$global:MusicDownload.AddScript({
            param($Url, $Dest)
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            $Part = "$Dest.part"
            $Client = New-Object System.Net.WebClient
            try {
                $Client.DownloadFile($Url, $Part)
                # A dropped connection can end the download early without an error, so check the size
                $Expected = $Client.ResponseHeaders["Content-Length"]
                if ($Expected -and (New-Object System.IO.FileInfo($Part)).Length -ne [long]$Expected) { throw "Download incomplete" }
                [System.IO.File]::Move($Part, $Dest)
            } finally {
                $Client.Dispose()
                [System.IO.File]::Delete($Part)
            }
        }).AddArgument($MusicUrl).AddArgument($MusicPath)
        $global:MusicDownloadHandle = $global:MusicDownload.BeginInvoke()

        # Check back every 250ms (the UI keeps running in between) and play once the file is there
        $global:MusicPoll = New-Object System.Windows.Forms.Timer
        $global:MusicPoll.Interval = 250
        $global:MusicPoll.Add_Tick({
            if (-not $global:MusicDownloadHandle.IsCompleted) { return }
            $global:MusicPoll.Stop()
            $global:MusicPoll.Dispose()
            $global:MusicDownload.Dispose()
            $global:MusicDownload = $null
            # Silent fail: if the download didn't work, there's simply no music
            if (Test-Path (Join-Path $env:TEMP "xpmusic_v2.wav")) { Start-XpMusic }
        })
        $global:MusicPoll.Start()
        return
    }

    try {
        # We need to load this for the modern Media Player to work
        Add-Type -AssemblyName PresentationCore
        $global:MediaPlayer = New-Object System.Windows.Media.MediaPlayer
        $global:MediaPlayer.Volume = 1.0  # Max Volume

        # Loop forever: jump back to the start whenever the song ends
        $global:MediaPlayer.Add_MediaEnded({
            $global:MediaPlayer.Position = [System.TimeSpan]::Zero
            $global:MediaPlayer.Play()
        })
        $global:MediaPlayer.Open((New-Object System.Uri($MusicPath)))
        $global:MediaPlayer.Play()
    } catch {
        # Silent fail
    }
}

# --- 2. SETUP FULL-SCREEN FORM ---
$Form = New-Object SmoothForm
$Form.WindowState = 'Maximized'
$Form.FormBorderStyle = 'None' 
$Form.BackColor = 'Black'

$global:ScaledImg = $null
# Use the wallpaper the PC is actually set to, scaled to fill the screen
$OriginalImg = Get-CurrentWallpaper
if ($OriginalImg) {
    $ScreenW = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width
    $ScreenH = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
    $global:ScaledImg = New-Object System.Drawing.Bitmap($OriginalImg, $ScreenW, $ScreenH)
    $Form.BackgroundImage = $global:ScaledImg
    $Form.BackgroundImageLayout = 'None'
    $OriginalImg.Dispose()
}

# --- 3. INTRO PANEL ---
# The intro is drawn by hand (Draw-Intro) so it can animate: the Windows logo and title fade in
# over the dimmed wallpaper, a loading spinner turns, then it all fades out before the network check.
$IntroDuration = 4500  # ms before the network check starts
$IntroClock = New-Object System.Diagnostics.Stopwatch

$IntroPanel = New-Object System.Windows.Forms.Panel
$IntroPanel.Dock = 'Fill'
$IntroPanel.BackColor = [System.Drawing.Color]::Black
$IntroPanel.BackgroundImage = $global:ScaledImg
$IntroPanel.BackgroundImageLayout = 'None'
Set-DoubleBuffered $IntroPanel

# Use the Windows 11 fonts when they exist, otherwise fall back to classic Segoe UI
function New-IntroFont ($Names, $Size) {
    foreach ($Name in $Names) {
        try { return New-Object System.Drawing.Font((New-Object System.Drawing.FontFamily($Name)), $Size) } catch {}
    }
    return New-Object System.Drawing.Font("Segoe UI", $Size)
}
$IntroTitleFont = New-IntroFont @("Segoe UI Variable Display Semib", "Segoe UI Semibold") 44
$IntroSubFont = New-IntroFont @("Segoe UI Variable Display Light", "Segoe UI Light") 22
$IntroStatusFont = New-IntroFont @("Segoe UI Variable Text", "Segoe UI") 11
$IntroBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
$IntroCenter = New-Object System.Drawing.StringFormat
$IntroCenter.Alignment = 'Center'

# 0..1 progress of an animation that runs from $Start to $End ms, eased so it glides to a stop
function Get-IntroEase ($Now, $Start, $End) {
    $p = [Math]::Min(1.0, [Math]::Max(0.0, ($Now - $Start) / ($End - $Start)))
    return 1 - [Math]::Pow(1 - $p, 3)
}

# Where everything sits: the logo and title just above the middle, the spinner below
function Get-IntroLayout ($W, $H) {
    $cy = $H / 2
    $L = @{ CX = $W / 2; LogoY = $cy - 150; TitleY = $cy - 82; SubY = $cy + 2; SpinY = $cy + 150; StatusY = $cy + 184 }
    # The areas that change while animating. Repainting only these keeps it smooth -
    # repainting the whole full-screen form is slow (only ~13 fps).
    $L.Content = New-Object System.Drawing.Rectangle([int]($L.CX - 360), [int]($L.LogoY - 175), 720, [int]($L.StatusY - $L.LogoY + 215))
    $L.Spinner = New-Object System.Drawing.Rectangle([int]($L.CX - 30), [int]($L.SpinY - 30), 60, 60)
    return $L
}

function Draw-IntroText ($g, $Text, $Font, $Y, $Alpha, $W, $Shadow) {
    if ($Alpha -le 0) { return }
    if ($Shadow) {
        $IntroBrush.Color = [System.Drawing.Color]::FromArgb([int]($Alpha * 0.35), 0, 0, 0)
        $g.DrawString($Text, $Font, $IntroBrush, (New-Object System.Drawing.RectangleF(0, ($Y + 2), $W, ($Font.Height * 2))), $IntroCenter)
    }
    $IntroBrush.Color = [System.Drawing.Color]::FromArgb([int]$Alpha, 255, 255, 255)
    $g.DrawString($Text, $Font, $IntroBrush, (New-Object System.Drawing.RectangleF(0, $Y, $W, ($Font.Height * 2))), $IntroCenter)
}

# Draws one frame of the intro, $t ms after it started (the wallpaper itself is the panel's background)
function Draw-Intro ($g, $W, $H, $t) {
    $L = Get-IntroLayout $W $H
    $Out = 1 - (Get-IntroEase $t ($IntroDuration - 600) ($IntroDuration - 100))  # 1 -> 0 as the intro ends
    $g.SmoothingMode = 'AntiAlias'
    $g.TextRenderingHint = 'AntiAliasGridFit'

    # Dim the wallpaper so the white text stands out
    $IntroBrush.Color = [System.Drawing.Color]::FromArgb(150, 4, 8, 20)
    $g.FillRectangle($IntroBrush, 0, 0, $W, $H)

    # Windows logo with a soft blue glow, fading in while it grows to full size
    $p = Get-IntroEase $t 150 900
    $a = $p * $Out
    if ($a -gt 0) {
        $Glow = New-Object System.Drawing.Drawing2D.GraphicsPath
        $Glow.AddEllipse([float]($L.CX - 170), [float]($L.LogoY - 170), [float]340, [float]340)
        $GlowBrush = New-Object System.Drawing.Drawing2D.PathGradientBrush($Glow)
        $GlowBrush.CenterColor = [System.Drawing.Color]::FromArgb([int](70 * $a), 0, 120, 215)
        $GlowBrush.SurroundColors = [System.Drawing.Color[]]@([System.Drawing.Color]::FromArgb(0, 0, 120, 215))
        $g.FillPath($GlowBrush, $Glow)
        $GlowBrush.Dispose()
        $Glow.Dispose()

        $Size = 92 * (0.8 + 0.2 * $p)
        $Gap = $Size * 0.06
        $Tile = ($Size - $Gap) / 2
        $x = $L.CX - $Size / 2
        $y = $L.LogoY - $Size / 2
        $From = New-Object System.Drawing.PointF($x, $y)
        $To = New-Object System.Drawing.PointF(($x + $Size), ($y + $Size))
        $Light = [System.Drawing.Color]::FromArgb([int](255 * $a), 110, 210, 255)
        $Deep = [System.Drawing.Color]::FromArgb([int](255 * $a), 0, 103, 192)
        $TileBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($From, $To, $Light, $Deep)
        foreach ($Pos in @(@(0, 0), @(1, 0), @(0, 1), @(1, 1))) {
            $g.FillRectangle($TileBrush, [float]($x + $Pos[0] * ($Tile + $Gap)), [float]($y + $Pos[1] * ($Tile + $Gap)), [float]$Tile, [float]$Tile)
        }
        $TileBrush.Dispose()
    }

    # Title and subtitle fade in while sliding up into place
    $p = Get-IntroEase $t 400 1100
    Draw-IntroText $g "Windows 11" $IntroTitleFont ($L.TitleY + 24 * (1 - $p)) (255 * $p * $Out) $W $true
    $p = Get-IntroEase $t 650 1350
    Draw-IntroText $g "Introduction" $IntroSubFont ($L.SubY + 24 * (1 - $p)) (215 * $p * $Out) $W $false

    # Windows-style spinner: five dots chasing each other, slow at the bottom and fast over the top
    $a = (Get-IntroEase $t 1100 1700) * $Out
    if ($a -gt 0) {
        $IntroBrush.Color = [System.Drawing.Color]::FromArgb([int](255 * $a), 255, 255, 255)
        for ($i = 0; $i -lt 5; $i++) {
            $DotTime = $t - 1100 - $i * 120
            if ($DotTime -lt 0) { continue }
            $Phase = ($DotTime % 1700) / 1700
            $Angle = ($Phase * 360 - 45 * [Math]::Sin(2 * [Math]::PI * $Phase) + 90) * [Math]::PI / 180
            $g.FillEllipse($IntroBrush, [float]($L.CX + 18 * [Math]::Cos($Angle) - 3), [float]($L.SpinY + 18 * [Math]::Sin($Angle) - 3), [float]6, [float]6)
        }
        Draw-IntroText $g "Getting things ready" $IntroStatusFont $L.StatusY (190 * $a) $W $false
    }
}

$IntroPanel.Add_Paint({
    param($sender, $e)
    Draw-Intro $e.Graphics $IntroPanel.ClientSize.Width $IntroPanel.ClientSize.Height $IntroClock.ElapsedMilliseconds
})
$Form.Controls.Add($IntroPanel)

# --- 4. NETWORK PANEL ---
$NetPanel = New-Object System.Windows.Forms.Panel
$NetPanel.Dock = 'Fill'
$NetPanel.BackColor = [System.Drawing.Color]::Transparent
$NetPanel.Visible = $false
Set-DoubleBuffered $NetPanel

# A centred card keeps the text readable over any wallpaper
$NetCard = New-Object System.Windows.Forms.Panel
$NetCard.Size = New-Object System.Drawing.Size(480, 360)
$NetCard.BackColor = $PanelBack
Set-DoubleBuffered $NetCard

$NetIcon = New-Object System.Windows.Forms.Label
$NetIcon.Text = [char]0xE701   # Wi-Fi glyph
$NetIcon.Font = New-Object System.Drawing.Font("Segoe MDL2 Assets", 34)
$NetIcon.ForeColor = [System.Drawing.Color]::White
$NetIcon.BackColor = [System.Drawing.Color]::Transparent
$NetIcon.TextAlign = 'MiddleCenter'
$NetIcon.Size = New-Object System.Drawing.Size(480, 64)
$NetIcon.Location = New-Object System.Drawing.Point(0, 30)
$NetCard.Controls.Add($NetIcon)

$StatusLabel = New-Object System.Windows.Forms.Label
$StatusLabel.Text = "Connecting to Wi-Fi..."
$StatusLabel.Font = New-Object System.Drawing.Font($UiFontName, 19, [System.Drawing.FontStyle]::Bold)
$StatusLabel.ForeColor = [System.Drawing.Color]::White
$StatusLabel.BackColor = [System.Drawing.Color]::Transparent
$StatusLabel.TextAlign = 'MiddleCenter'
$StatusLabel.AutoSize = $false
$StatusLabel.Size = New-Object System.Drawing.Size(440, 34)
$StatusLabel.Location = New-Object System.Drawing.Point(20, 104)
$NetCard.Controls.Add($StatusLabel)

$NetDesc = New-Object System.Windows.Forms.Label
$NetDesc.Text = "Getting you online..."
$NetDesc.Font = New-Object System.Drawing.Font($UiFontName, 11)
$NetDesc.ForeColor = [System.Drawing.Color]::Gainsboro
$NetDesc.BackColor = [System.Drawing.Color]::Transparent
$NetDesc.TextAlign = 'MiddleCenter'
$NetDesc.AutoSize = $false
$NetDesc.Size = New-Object System.Drawing.Size(440, 40)
$NetDesc.Location = New-Object System.Drawing.Point(20, 142)
$NetCard.Controls.Add($NetDesc)

# Wi-Fi name + password, shown above the button only after a manual attempt fails
$CredLabel = New-Object System.Windows.Forms.Label
$CredLabel.Text = ""
$CredLabel.Font = New-Object System.Drawing.Font("Consolas", 13, [System.Drawing.FontStyle]::Bold)
$CredLabel.ForeColor = [System.Drawing.Color]::FromArgb(120, 210, 255)
$CredLabel.BackColor = [System.Drawing.Color]::Transparent
$CredLabel.TextAlign = 'MiddleCenter'
$CredLabel.AutoSize = $false
$CredLabel.Size = New-Object System.Drawing.Size(440, 52)
$CredLabel.Location = New-Object System.Drawing.Point(20, 188)
$CredLabel.Visible = $false
$NetCard.Controls.Add($CredLabel)

$ConnectBtn = New-Object System.Windows.Forms.Button
$ConnectBtn.Text = "Connect to Wi-Fi"
$ConnectBtn.Font = New-Object System.Drawing.Font($UiFontName, 12, [System.Drawing.FontStyle]::Bold)
$ConnectBtn.Size = New-Object System.Drawing.Size(240, 48)
$ConnectBtn.Location = New-Object System.Drawing.Point(120, 262)
$ConnectBtn.BackColor = $Accent
$ConnectBtn.ForeColor = [System.Drawing.Color]::White
$ConnectBtn.FlatStyle = 'Flat'
$ConnectBtn.Visible = $false
$NetCard.Controls.Add($ConnectBtn)

Set-RoundedRegion $NetCard 18
$NetPanel.Controls.Add($NetCard)
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
$TweakFlow.Size = New-Object System.Drawing.Size(415, 335)
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
    $chk.Margin = New-Object System.Windows.Forms.Padding(10, 9, 20, 7)
    $chk.BackColor = [System.Drawing.Color]::Transparent
    $chk.Tag = $tweak
    
    if (& $tweak.Check) { 
        $chk.Checked = $true
        $chk.ForeColor = [System.Drawing.Color]::LimeGreen
    }
    
    $TweakFlow.Controls.Add($chk)
    $AllTweakChecks += $chk
}

# --- WELCOME-BACK SCREEN (right column) ---
$WelcomeGroup = New-Object System.Windows.Forms.GroupBox
$WelcomeGroup.Text = "Welcome-back screen"
$WelcomeGroup.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$WelcomeGroup.ForeColor = [System.Drawing.Color]::White
$WelcomeGroup.Size = New-Object System.Drawing.Size(325, 305)
$WelcomeGroup.Location = New-Object System.Drawing.Point(455, 105)
$TweaksWindow.Controls.Add($WelcomeGroup)

$WelcomeChk = New-Object System.Windows.Forms.CheckBox
$WelcomeChk.Text = "Show it when anyone signs in"
$WelcomeChk.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$WelcomeChk.ForeColor = [System.Drawing.Color]::White
$WelcomeChk.AutoSize = $true
$WelcomeChk.Location = New-Object System.Drawing.Point(18, 34)
$WelcomeGroup.Controls.Add($WelcomeChk)

$WelcomeLogoLbl = New-Object System.Windows.Forms.Label
$WelcomeLogoLbl.Text = "Logo:"
$WelcomeLogoLbl.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$WelcomeLogoLbl.ForeColor = [System.Drawing.Color]::Gainsboro
$WelcomeLogoLbl.AutoSize = $true
$WelcomeLogoLbl.Location = New-Object System.Drawing.Point(18, 74)
$WelcomeGroup.Controls.Add($WelcomeLogoLbl)

$WelcomeCombo = New-Object System.Windows.Forms.ComboBox
$WelcomeCombo.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$WelcomeCombo.Location = New-Object System.Drawing.Point(18, 98)
$WelcomeCombo.Size = New-Object System.Drawing.Size(285, 28)
$WelcomeCombo.DropDownStyle = 'DropDownList'
$WelcomeCombo.Items.Add("Satisfactory (hudOS / FICSIT)") | Out-Null
$WelcomeCombo.Items.Add("Windows 11") | Out-Null
$WelcomeCombo.SelectedIndex = 0
$WelcomeGroup.Controls.Add($WelcomeCombo)

$WelcomeDesc = New-Object System.Windows.Forms.Label
$WelcomeDesc.Text = "Plays a short 'Welcome back, <name>' animation - the logo appears, then the screen de-blurs into your desktop."
$WelcomeDesc.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)
$WelcomeDesc.ForeColor = [System.Drawing.Color]::Gray
$WelcomeDesc.AutoSize = $false
$WelcomeDesc.Size = New-Object System.Drawing.Size(290, 60)
$WelcomeDesc.Location = New-Object System.Drawing.Point(18, 138)
$WelcomeGroup.Controls.Add($WelcomeDesc)

$WelcomePreviewBtn = New-Object System.Windows.Forms.Button
$WelcomePreviewBtn.Text = "Preview now"
$WelcomePreviewBtn.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$WelcomePreviewBtn.Size = New-Object System.Drawing.Size(285, 44)
$WelcomePreviewBtn.Location = New-Object System.Drawing.Point(18, 210)
$WelcomePreviewBtn.BackColor = $Accent
$WelcomePreviewBtn.ForeColor = [System.Drawing.Color]::White
$WelcomePreviewBtn.FlatStyle = 'Flat'
$WelcomeGroup.Controls.Add($WelcomePreviewBtn)

# Reflect the current state (task installed? which logo?)
try {
    if (Get-ScheduledTask -TaskName $WelcomeTask -ErrorAction SilentlyContinue) { $WelcomeChk.Checked = $true }
    $wCfg = Join-Path $WelcomeDir "welcome.cfg"
    if ((Test-Path $wCfg) -and ((Get-Content $wCfg -Raw).Trim() -eq "Windows11")) { $WelcomeCombo.SelectedIndex = 1 }
} catch {}

$WelcomePreviewBtn.Add_Click({
    $logo = if ($WelcomeCombo.SelectedIndex -eq 1) { "Windows11" } else { "Satisfactory" }
    Show-WelcomePreview $logo
})

$ApplyTweaksBtn = New-Object System.Windows.Forms.Button
$ApplyTweaksBtn.Text = "Apply Tweaks"
$ApplyTweaksBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$ApplyTweaksBtn.Size = New-Object System.Drawing.Size(160, 45)
$ApplyTweaksBtn.Location = New-Object System.Drawing.Point(400, 450)
$ApplyTweaksBtn.BackColor = [System.Drawing.Color]::DodgerBlue
$ApplyTweaksBtn.ForeColor = [System.Drawing.Color]::White
$ApplyTweaksBtn.FlatStyle = 'Flat'

$FinishBtn = New-Object System.Windows.Forms.Button
$FinishBtn.Text = "Next Page ->"
$FinishBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$FinishBtn.Size = New-Object System.Drawing.Size(160, 45)
$FinishBtn.Location = New-Object System.Drawing.Point(580, 450)
$FinishBtn.BackColor = $GoColor
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

    # Welcome-back screen: install/remove the logon task per the checkbox + logo choice
    try {
        $wLogo = if ($WelcomeCombo.SelectedIndex -eq 1) { "Windows11" } else { "Satisfactory" }
        if ($WelcomeChk.Checked) { Install-WelcomeScreen $wLogo } else { Remove-WelcomeScreen }
    } catch {}

    Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    
    $ApplyTweaksBtn.Text = "Apply Tweaks"
    $ApplyTweaksBtn.Enabled = $true
})

$FinishBtn.Add_Click({
    $TweaksWindow.Visible = $false
    $UserWindow.Visible = $true
})

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
        # Roblox can't run in a VM - say so and skip it instead of hanging on the installer
        if ($TargetApp.ID -eq "roblox" -and (Test-IsVM)) {
            $ProgressLabel.ForeColor = [System.Drawing.Color]::Orange
            $ProgressLabel.Text = "Roblox can't run in a virtual machine - skipping it."
            [System.Windows.Forms.Application]::DoEvents()
            Start-Sleep -Seconds 3
            $ProgressLabel.ForeColor = [System.Drawing.Color]::Cyan
            continue
        }

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

# ==========================================
# --- 7b. USER / ADMIN MODE WINDOW (PAGE 4) ---
# ==========================================
$UserWindow = New-Object System.Windows.Forms.Panel
$UserWindow.Size = New-Object System.Drawing.Size(800, 540)
$UserWindow.BackColor = [System.Drawing.Color]::FromArgb(245, 25, 25, 25)
$UserWindow.Visible = $false
Set-DoubleBuffered $UserWindow

$UserTitle = New-Object System.Windows.Forms.Label
$UserTitle.Text = "User / Admin Mode"
$UserTitle.Font = New-Object System.Drawing.Font("Segoe UI", 24, [System.Drawing.FontStyle]::Bold)
$UserTitle.ForeColor = [System.Drawing.Color]::White
$UserTitle.AutoSize = $true
$UserTitle.Location = New-Object System.Drawing.Point(20, 20)
$UserWindow.Controls.Add($UserTitle)

$UserSubTitle = New-Object System.Windows.Forms.Label
$UserSubTitle.Text = "Create a sign-in account, plus an admin unlock command for it."
$UserSubTitle.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$UserSubTitle.ForeColor = [System.Drawing.Color]::LightGray
$UserSubTitle.AutoSize = $true
$UserSubTitle.Location = New-Object System.Drawing.Point(24, 68)
$UserWindow.Controls.Add($UserSubTitle)

# --- LEFT: the new standard account ---
$AcctGroup = New-Object System.Windows.Forms.GroupBox
$AcctGroup.Text = "New user account"
$AcctGroup.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$AcctGroup.ForeColor = [System.Drawing.Color]::White
$AcctGroup.Size = New-Object System.Drawing.Size(350, 250)
$AcctGroup.Location = New-Object System.Drawing.Point(25, 110)
$UserWindow.Controls.Add($AcctGroup)

$UserNameLbl = New-Object System.Windows.Forms.Label
$UserNameLbl.Text = "Username"
$UserNameLbl.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$UserNameLbl.ForeColor = [System.Drawing.Color]::Gainsboro
$UserNameLbl.AutoSize = $true
$UserNameLbl.Location = New-Object System.Drawing.Point(20, 34)
$AcctGroup.Controls.Add($UserNameLbl)

$UserNameTxt = New-Object System.Windows.Forms.TextBox
$UserNameTxt.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$UserNameTxt.Location = New-Object System.Drawing.Point(20, 57)
$UserNameTxt.Size = New-Object System.Drawing.Size(305, 26)
$AcctGroup.Controls.Add($UserNameTxt)

$UserPassLbl = New-Object System.Windows.Forms.Label
$UserPassLbl.Text = "Password"
$UserPassLbl.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$UserPassLbl.ForeColor = [System.Drawing.Color]::Gainsboro
$UserPassLbl.AutoSize = $true
$UserPassLbl.Location = New-Object System.Drawing.Point(20, 96)
$AcctGroup.Controls.Add($UserPassLbl)

$UserPassTxt = New-Object System.Windows.Forms.TextBox
$UserPassTxt.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$UserPassTxt.Location = New-Object System.Drawing.Point(20, 119)
$UserPassTxt.Size = New-Object System.Drawing.Size(305, 26)
$UserPassTxt.UseSystemPasswordChar = $true
$AcctGroup.Controls.Add($UserPassTxt)

$ShowPassChk = New-Object System.Windows.Forms.CheckBox
$ShowPassChk.Text = "Show passwords"
$ShowPassChk.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$ShowPassChk.ForeColor = [System.Drawing.Color]::Gainsboro
$ShowPassChk.AutoSize = $true
$ShowPassChk.Location = New-Object System.Drawing.Point(20, 152)
$AcctGroup.Controls.Add($ShowPassChk)

$BlockUacChk = New-Object System.Windows.Forms.CheckBox
$BlockUacChk.Text = "Block admin prompts (deny elevation)"
$BlockUacChk.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$BlockUacChk.ForeColor = [System.Drawing.Color]::Gainsboro
$BlockUacChk.AutoSize = $true
$BlockUacChk.Checked = $true
$BlockUacChk.Location = New-Object System.Drawing.Point(20, 180)
$AcctGroup.Controls.Add($BlockUacChk)

$OtherUserChk = New-Object System.Windows.Forms.CheckBox
$OtherUserChk.Text = "Sign-in shows ""Other user"" (type a username)"
$OtherUserChk.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$OtherUserChk.ForeColor = [System.Drawing.Color]::Gainsboro
$OtherUserChk.AutoSize = $true
$OtherUserChk.Checked = $true
$OtherUserChk.Location = New-Object System.Drawing.Point(20, 208)
$AcctGroup.Controls.Add($OtherUserChk)

# --- RIGHT: the admin unlock command ---
$AdminGroup = New-Object System.Windows.Forms.GroupBox
$AdminGroup.Text = "Admin activation"
$AdminGroup.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$AdminGroup.ForeColor = [System.Drawing.Color]::White
$AdminGroup.Size = New-Object System.Drawing.Size(350, 250)
$AdminGroup.Location = New-Object System.Drawing.Point(400, 110)
$UserWindow.Controls.Add($AdminGroup)

$AdminDesc = New-Object System.Windows.Forms.Label
$AdminDesc.Text = "From the new account, open Command Prompt and run:"
$AdminDesc.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$AdminDesc.ForeColor = [System.Drawing.Color]::Gainsboro
$AdminDesc.AutoSize = $false
$AdminDesc.Size = New-Object System.Drawing.Size(320, 42)
$AdminDesc.Location = New-Object System.Drawing.Point(18, 32)
$AdminGroup.Controls.Add($AdminDesc)

$AdminCmdLbl = New-Object System.Windows.Forms.Label
$AdminCmdLbl.Text = "activateadmin <password>"
$AdminCmdLbl.Font = New-Object System.Drawing.Font("Consolas", 12, [System.Drawing.FontStyle]::Bold)
$AdminCmdLbl.ForeColor = [System.Drawing.Color]::FromArgb(120, 210, 255)
$AdminCmdLbl.BackColor = [System.Drawing.Color]::FromArgb(255, 12, 12, 14)
$AdminCmdLbl.AutoSize = $false
$AdminCmdLbl.TextAlign = 'MiddleCenter'
$AdminCmdLbl.Size = New-Object System.Drawing.Size(315, 34)
$AdminCmdLbl.Location = New-Object System.Drawing.Point(18, 82)
$AdminGroup.Controls.Add($AdminCmdLbl)

$AdminHint = New-Object System.Windows.Forms.Label
$AdminHint.Text = "...hides this account and signs into the admin account. deactivateadmin restores it."
$AdminHint.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$AdminHint.ForeColor = [System.Drawing.Color]::Gray
$AdminHint.AutoSize = $false
$AdminHint.Size = New-Object System.Drawing.Size(315, 30)
$AdminHint.Location = New-Object System.Drawing.Point(18, 118)
$AdminGroup.Controls.Add($AdminHint)

$AdminPassLbl = New-Object System.Windows.Forms.Label
$AdminPassLbl.Text = "Admin unlock password"
$AdminPassLbl.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$AdminPassLbl.ForeColor = [System.Drawing.Color]::Gainsboro
$AdminPassLbl.AutoSize = $true
$AdminPassLbl.Location = New-Object System.Drawing.Point(18, 152)
$AdminGroup.Controls.Add($AdminPassLbl)

$AdminPassTxt = New-Object System.Windows.Forms.TextBox
$AdminPassTxt.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$AdminPassTxt.Location = New-Object System.Drawing.Point(18, 175)
$AdminPassTxt.Size = New-Object System.Drawing.Size(315, 26)
$AdminPassTxt.UseSystemPasswordChar = $true
$AdminGroup.Controls.Add($AdminPassTxt)

$AdminNote = New-Object System.Windows.Forms.Label
$AdminNote.Text = "Keep this password private - anyone who knows it can gain admin."
$AdminNote.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$AdminNote.ForeColor = [System.Drawing.Color]::Gray
$AdminNote.AutoSize = $false
$AdminNote.Size = New-Object System.Drawing.Size(315, 34)
$AdminNote.Location = New-Object System.Drawing.Point(18, 208)
$AdminGroup.Controls.Add($AdminNote)

$ShowPassChk.Add_CheckedChanged({
    $UserPassTxt.UseSystemPasswordChar = -not $ShowPassChk.Checked
    $AdminPassTxt.UseSystemPasswordChar = -not $ShowPassChk.Checked
})

$UserStatus = New-Object System.Windows.Forms.Label
$UserStatus.Text = ""
$UserStatus.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$UserStatus.ForeColor = [System.Drawing.Color]::Gainsboro
$UserStatus.AutoSize = $false
$UserStatus.Size = New-Object System.Drawing.Size(750, 58)
$UserStatus.Location = New-Object System.Drawing.Point(25, 372)
$UserWindow.Controls.Add($UserStatus)

$CreateUserBtn = New-Object System.Windows.Forms.Button
$CreateUserBtn.Text = "Create Account"
$CreateUserBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$CreateUserBtn.Size = New-Object System.Drawing.Size(180, 45)
$CreateUserBtn.Location = New-Object System.Drawing.Point(400, 470)
$CreateUserBtn.BackColor = $Accent
$CreateUserBtn.ForeColor = [System.Drawing.Color]::White
$CreateUserBtn.FlatStyle = 'Flat'

$UserFinishBtn = New-Object System.Windows.Forms.Button
$UserFinishBtn.Text = "Finish Setup"
$UserFinishBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$UserFinishBtn.Size = New-Object System.Drawing.Size(160, 45)
$UserFinishBtn.Location = New-Object System.Drawing.Point(600, 470)
$UserFinishBtn.BackColor = $DangerColor
$UserFinishBtn.ForeColor = [System.Drawing.Color]::White
$UserFinishBtn.FlatStyle = 'Flat'

$CreateUserBtn.Add_Click({
    $u = $UserNameTxt.Text.Trim()
    $p = $UserPassTxt.Text
    $ap = $AdminPassTxt.Text

    $UserStatus.ForeColor = [System.Drawing.Color]::Salmon
    if (-not $u)  { $UserStatus.Text = "Enter a username for the new account."; return }
    if ($u -match '[\\/\[\]:;|=,+*?<>@"]') { $UserStatus.Text = "That username contains characters Windows doesn't allow."; return }
    if (-not $p)  { $UserStatus.Text = "Enter a password for the account."; return }
    if (-not $ap) { $UserStatus.Text = "Enter an admin unlock password."; return }

    $CreateUserBtn.Enabled = $false
    $UserFinishBtn.Enabled = $false
    $CreateUserBtn.Text = "Working..."
    $UserStatus.ForeColor = [System.Drawing.Color]::Gainsboro
    $UserStatus.Text = "Creating the account and installing the admin command..."
    [System.Windows.Forms.Application]::DoEvents()

    try {
        New-IntroUserAccount $u $p ($BlockUacChk.Checked) ($OtherUserChk.Checked)
        Install-AdminActivator $u $ap
        $UserStatus.ForeColor = [System.Drawing.Color]::LimeGreen
        $UserStatus.Text = "Done. '$u' is ready on the sign-in screen (standard user).`r`nFrom that account run  activateadmin <password>  to hide it and sign back into the admin account (deactivateadmin restores it)."
    } catch {
        $UserStatus.ForeColor = [System.Drawing.Color]::Salmon
        $UserStatus.Text = "Couldn't finish: $($_.Exception.Message)"
    }

    $CreateUserBtn.Enabled = $true
    $UserFinishBtn.Enabled = $true
    $CreateUserBtn.Text = "Create Account"
})

$UserFinishBtn.Add_Click({ $Form.Close() })

$UserWindow.Controls.Add($CreateUserBtn)
$UserWindow.Controls.Add($UserFinishBtn)
$Form.Controls.Add($UserWindow)

# ==========================================
# --- APPLY SHARED STYLING TO EVERY PAGE ---
# ==========================================
Add-PageChrome $AppWindow     "STEP 1 / 4"
Add-PageChrome $DesktopWindow "STEP 2 / 4"
Add-PageChrome $TweaksWindow  "STEP 3 / 4"
Add-PageChrome $UserWindow    "STEP 4 / 4"
foreach ($win in @($AppWindow, $DesktopWindow, $TweaksWindow, $UserWindow)) { Set-RoundedRegion $win 16 }
Style-AllButtons $Form

# --- 8. CENTERING LOGIC ---
function Center-Elements {
    $fw = [int]$Form.ClientSize.Width
    $fh = [int]$Form.ClientSize.Height

    $NetCard.Location = New-Object System.Drawing.Point([int](($fw - $NetCard.Width) / 2), [int](($fh - $NetCard.Height) / 2))

    $AppWindow.Location = New-Object System.Drawing.Point([int](($fw - $AppWindow.Width) / 2), [int](($fh - $AppWindow.Height) / 2))
    $DesktopWindow.Location = New-Object System.Drawing.Point([int](($fw - $DesktopWindow.Width) / 2), [int](($fh - $DesktopWindow.Height) / 2))
    $TweaksWindow.Location = New-Object System.Drawing.Point([int](($fw - $TweaksWindow.Width) / 2), [int](($fh - $TweaksWindow.Height) / 2))
    $UserWindow.Location = New-Object System.Drawing.Point([int](($fw - $UserWindow.Width) / 2), [int](($fh - $UserWindow.Height) / 2))
}
$Form.Add_Load({ Center-Elements })

# --- 9. TIMERS AND LOGIC ---
# Redraws the intro ~60 times a second while it animates
$IntroAnimTimer = New-Object System.Windows.Forms.Timer
$IntroAnimTimer.Interval = 15
$IntroAnimTimer.Add_Tick({
    $t = $IntroClock.ElapsedMilliseconds
    $L = Get-IntroLayout $IntroPanel.ClientSize.Width $IntroPanel.ClientSize.Height
    # While the title fades in or out repaint that area, otherwise only the spinner is moving
    if ($t -lt 1750 -or $t -gt ($IntroDuration - 650)) {
        $IntroPanel.Invalidate($L.Content)
    } else {
        $IntroPanel.Invalidate($L.Spinner)
    }
})

# Shows the "Connected" message for 2 seconds, then opens the app window - without freezing the UI
$ConnectedTimer = New-Object System.Windows.Forms.Timer
$ConnectedTimer.Interval = 2000
$ConnectedTimer.Add_Tick({
    $ConnectedTimer.Stop()
    $NetPanel.Visible = $false
    $AppWindow.Visible = $true
})

$IntroTimer = New-Object System.Windows.Forms.Timer
$IntroTimer.Interval = $IntroDuration
$IntroTimer.Add_Tick({
    $IntroTimer.Stop()
    $IntroAnimTimer.Stop()

    # Move from the intro to the network card, starting on "Connecting to Wi-Fi..."
    $IntroPanel.Visible = $false
    $ConnectBtn.Visible = $false
    $CredLabel.Visible = $false
    $NetIcon.ForeColor = [System.Drawing.Color]::White
    $StatusLabel.Text = "Connecting to Wi-Fi..."
    $NetDesc.Text = "Getting you online..."
    $NetPanel.Visible = $true
    Center-Elements
    $Form.Refresh()

    # Silent DNS fix, then check whether we already have a connection
    Set-GoogleDNS
    $Ping = Test-Connection -ComputerName "8.8.8.8" -Count 1 -Quiet -ErrorAction SilentlyContinue

    if ($Ping) {
        $StatusLabel.Text = "Connected"
        $NetDesc.Text = "You're online."
        $Form.Refresh()
        Start-XpMusic
        $ConnectedTimer.Start()
    } else {
        # No connection - offer the manual connect button
        $NetIcon.ForeColor = [System.Drawing.Color]::FromArgb(255, 185, 60)
        $StatusLabel.Text = "No internet connection"
        $NetDesc.Text = "Couldn't connect automatically."
        $ConnectBtn.Text = "Connect to Wi-Fi"
        $ConnectBtn.Enabled = $true
        $ConnectBtn.Visible = $true
        $Form.Refresh()
    }
})

$ConnectBtn.Add_Click({
    $ConnectBtn.Enabled = $false
    $ConnectBtn.Text = "Connecting..."
    $CredLabel.Visible = $false
    $NetIcon.ForeColor = [System.Drawing.Color]::White
    $StatusLabel.Text = "Connecting to Wi-Fi..."
    $NetDesc.Text = "Joining $WifiSsid..."
    $Form.Refresh()

    Install-WifiProfile   # so the connect below works even if this PC has never joined the network
    $NetshOutput = netsh wlan connect name="$WifiSsid" 2>&1
    Start-Sleep -Seconds 3

    # Run DNS Setup again in case the adapter just came online!
    Set-GoogleDNS
    $Ping2 = Test-Connection -ComputerName "8.8.8.8" -Count 1 -Quiet -ErrorAction SilentlyContinue

    if ($Ping2) {
        $StatusLabel.Text = "Connected"
        $NetDesc.Text = "You're online."
        $ConnectBtn.Visible = $false
        $Form.Refresh()
        Start-XpMusic
        $ConnectedTimer.Start()
    } else {
        # Still failing - show the network name + password above the button so it can be joined by hand
        $NetIcon.ForeColor = [System.Drawing.Color]::FromArgb(255, 185, 60)
        $StatusLabel.Text = "Connection failed"
        $NetDesc.Text = "Join this network manually, then press Connect again:"
        $CredLabel.Text = "Network:  $WifiSsid`r`nPassword:  $WifiPass"
        $CredLabel.Visible = $true
        $ConnectBtn.Text = "Connect to Wi-Fi"
        $ConnectBtn.Enabled = $true
        $Form.Refresh()
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
    $IntroClock.Start()
    $IntroAnimTimer.Start()
    $IntroTimer.Start()
})

$Form.Add_FormClosed({
    if ($global:WMP) {
        $global:WMP.close()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($global:WMP) | Out-Null
    }
    if ($global:MusicPoll) { $global:MusicPoll.Stop() }
    if ($global:MediaPlayer) {
        $global:MediaPlayer.Stop()
        $global:MediaPlayer.Close()
    }
    # Forget the music state so running the script again in the same window starts fresh
    $global:MediaPlayer = $null
    $global:MusicDownload = $null
})

[void]$Form.ShowDialog()
