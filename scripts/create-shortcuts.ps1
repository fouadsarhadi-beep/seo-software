<#
.SYNOPSIS
    Create Desktop and Start Menu shortcuts for the SEO Analysis workbench and CLI.

.EXAMPLE
    powershell -File scripts\create-shortcuts.ps1

.EXAMPLE
    powershell -File scripts\create-shortcuts.ps1 -StartMenu

.EXAMPLE
    powershell -File scripts\create-shortcuts.ps1 -Remove

.NOTES
    Writes only into the current user's profile. No administrator rights are needed.
#>
[CmdletBinding()]
param(
    [switch]$StartMenu,
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$workbench = Join-Path $repo "SEO-Workbench.bat"
$cli = Join-Path $repo "seo.bat"
$icon = Join-Path $repo "assets\seo-analysis.ico"

foreach ($file in @($workbench, $cli)) {
    if (-not (Test-Path $file)) { throw "Missing launcher: $file" }
}

$desktop = [Environment]::GetFolderPath("Desktop")
$targets = @((Join-Path $desktop "SEO Analysis Workbench.lnk"),
             (Join-Path $desktop "SEO Analysis CLI.lnk"))
if ($StartMenu) {
    $programs = [Environment]::GetFolderPath("Programs")
    $targets += (Join-Path $programs "SEO Analysis Workbench.lnk")
    $targets += (Join-Path $programs "SEO Analysis CLI.lnk")
}

if ($Remove) {
    foreach ($path in $targets) {
        if (Test-Path $path) { Remove-Item $path -Force; Write-Host "Removed $path" }
    }
    return
}

$shell = New-Object -ComObject WScript.Shell

function New-Launcher {
    param([string]$Path, [string]$Script, [string]$Description)

    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $env:ComSpec
    $shortcut.Arguments = '/c ""{0}""' -f $Script
    $shortcut.WorkingDirectory = $repo
    $shortcut.Description = $Description
    if (Test-Path $icon) { $shortcut.IconLocation = "$icon,0" }
    $shortcut.Save()
    Write-Host "Created $Path"
}

New-Launcher -Path $targets[0] -Script $workbench -Description "Start the local SEO Analysis workbench"
New-Launcher -Path $targets[1] -Script $cli -Description "Run SEO Analysis commands"
if ($StartMenu) {
    New-Launcher -Path $targets[2] -Script $workbench -Description "Start the local SEO Analysis workbench"
    New-Launcher -Path $targets[3] -Script $cli -Description "Run SEO Analysis commands"
}
