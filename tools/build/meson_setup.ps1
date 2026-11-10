$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-VsDevCmdPath {
    param([string]$TargetArch)

    if ($env:VSINSTALLDIR) {
        $candidate = Join-Path $env:VSINSTALLDIR "Common7\Tools\VsDevCmd.bat"
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) {
        throw "Could not locate vswhere.exe."
    }

    $component = if ($TargetArch -eq "arm64") {
        "Microsoft.VisualStudio.Component.VC.Tools.ARM64"
    } else {
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64"
    }
    # Prefer Visual Studio 2026+ (major 18) when installed.
    $installPathRaw = & $vswhere -latest -prerelease -version "[18.0,19.0)" -products * -requires $component -property installationPath
    $installPath = if ($null -eq $installPathRaw) { "" } else { "$installPathRaw".Trim() }
    if ([string]::IsNullOrWhiteSpace($installPath)) {
        $installPathRaw = & $vswhere -latest -prerelease -products * -requires $component -property installationPath
        $installPath = if ($null -eq $installPathRaw) { "" } else { "$installPathRaw".Trim() }
        if (-not [string]::IsNullOrWhiteSpace($installPath)) {
            Write-Host "Visual Studio 2026+ was not found. Falling back to latest available toolchain at '$installPath'."
        }
    }

    if ([string]::IsNullOrWhiteSpace($installPath)) {
        throw "No Visual Studio installation with C++ tools was found."
    }

    $vsDevCmd = Join-Path $installPath "Common7\Tools\VsDevCmd.bat"
    if (-not (Test-Path $vsDevCmd)) {
        throw "Could not locate VsDevCmd.bat at '$vsDevCmd'."
    }

    return $vsDevCmd
}

function Quote-CmdArg([string]$Value) {
    if ($Value -match '[\s"&<>|()]') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

function Get-openPREYVsProcessArch {
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString().ToLowerInvariant()
    switch ($arch) {
        "x64" { return "x64" }
        "x86" { return "x86" }
        "arm64" { return "arm64" }
        default { return "x64" }
    }
}

function Get-openPREYVsTargetArch {
    if (-not [string]::IsNullOrWhiteSpace($env:OPENPREY_VS_TARGET_ARCH)) {
        return $env:OPENPREY_VS_TARGET_ARCH.Trim().ToLowerInvariant()
    }
    if (-not [string]::IsNullOrWhiteSpace($env:OPENQ4_VS_TARGET_ARCH)) {
        return $env:OPENQ4_VS_TARGET_ARCH.Trim().ToLowerInvariant()
    }

    return Get-openPREYVsProcessArch
}

function Get-openPREYVsHostArch {
    if (-not [string]::IsNullOrWhiteSpace($env:OPENPREY_VS_HOST_ARCH)) {
        return $env:OPENPREY_VS_HOST_ARCH.Trim().ToLowerInvariant()
    }
    if (-not [string]::IsNullOrWhiteSpace($env:OPENQ4_VS_HOST_ARCH)) {
        return $env:OPENQ4_VS_HOST_ARCH.Trim().ToLowerInvariant()
    }

    return Get-openPREYVsProcessArch
}

function Get-MesonCommand {
    $pythonCandidates = @("python", "python3")
    foreach ($candidate in $pythonCandidates) {
        $pythonCommand = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($null -eq $pythonCommand) {
            continue
        }

        & $pythonCommand.Source -c "import mesonbuild.mesonmain" *> $null
        if ($LASTEXITCODE -eq 0) {
            return [PSCustomObject]@{
                Executable = $pythonCommand.Source
                Arguments  = @("-m", "mesonbuild.mesonmain")
            }
        }
    }

    $mesonCommand = Get-Command "meson" -ErrorAction SilentlyContinue
    if ($null -ne $mesonCommand) {
        return [PSCustomObject]@{
            Executable = $mesonCommand.Source
            Arguments  = @()
        }
    }

    throw "Could not find Meson. Install it into the active Python environment or make 'meson' available on PATH."
}

function Invoke-Meson {
    param(
        [string[]]$MesonArgs,
        [string]$VsDevCmdPath,
        [pscustomobject]$MesonCommand,
        [string]$VsTargetArch,
        [string]$VsHostArch
    )

    $mesonInvocation = @($MesonCommand.Arguments) + $MesonArgs
    if ([string]::IsNullOrWhiteSpace($VsDevCmdPath)) {
        & $MesonCommand.Executable @mesonInvocation
        return
    }

    $mesonCommandLine = @($MesonCommand.Executable) + $MesonCommand.Arguments + $MesonArgs
    $mesonCmd = ($mesonCommandLine | ForEach-Object { Quote-CmdArg $_ }) -join " "
    $fullCmd = 'call "' + $VsDevCmdPath + '" -arch=' + $VsTargetArch + ' -host_arch=' + $VsHostArch + ' >nul && ' + $mesonCmd
    & $env:ComSpec /d /c $fullCmd
}

function Get-CompileBuildDirInfo {
    param(
        [string[]]$MesonArgs,
        [string]$DefaultBuildDir
    )

    $result = [PSCustomObject]@{
        BuildDir = $DefaultBuildDir
        HasExplicit = $false
    }

    for ($i = 0; $i -lt $MesonArgs.Length; $i++) {
        $arg = $MesonArgs[$i]
        if ($arg -eq "-C" -and ($i + 1) -lt $MesonArgs.Length) {
            $result.BuildDir = $MesonArgs[$i + 1]
            $result.HasExplicit = $true
            break
        }

        if ($arg.StartsWith("-C") -and $arg.Length -gt 2) {
            $result.BuildDir = $arg.Substring(2)
            $result.HasExplicit = $true
            break
        }
    }

    $result.BuildDir = [System.IO.Path]::GetFullPath($result.BuildDir)
    return $result
}

function Test-MesonBuildDirectory {
    param([string]$BuildDir)

    $coreData = Join-Path $BuildDir "meson-private\coredata.dat"
    $ninjaFile = Join-Path $BuildDir "build.ninja"
    return (Test-Path $coreData) -and (Test-Path $ninjaFile)
}

function Get-MesonBuildOptionValue {
    param(
        [string]$BuildDir,
        [string]$OptionName
    )

    $introOptionsPath = Join-Path $BuildDir "meson-info\intro-buildoptions.json"
    if (Test-Path $introOptionsPath) {
        $introOptions = Get-Content $introOptionsPath -Raw | ConvertFrom-Json
        foreach ($option in $introOptions) {
            if ($option.name -eq $OptionName) {
                return $option.value
            }
        }
    }

    $cmdLinePath = Join-Path $BuildDir "meson-private\cmd_line.txt"
    if (-not (Test-Path $cmdLinePath)) {
        return $null
    }

    $inOptionsSection = $false
    foreach ($rawLine in Get-Content $cmdLinePath) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        if ($line.StartsWith("[") -and $line.EndsWith("]")) {
            $inOptionsSection = $line -eq "[options]"
            continue
        }

        if (-not $inOptionsSection) {
            continue
        }

        $delimiterIndex = $line.IndexOf("=")
        if ($delimiterIndex -lt 0) {
            continue
        }

        $name = $line.Substring(0, $delimiterIndex).Trim()
        if ($name -ne $OptionName) {
            continue
        }

        $value = $line.Substring($delimiterIndex + 1).Trim()
        switch ($value.ToLowerInvariant()) {
            "true" { return $true }
            "false" { return $false }
            default { return $value }
        }
    }

    return $null
}

function Test-GitHubActionsEnvironment {
    return $env:GITHUB_ACTIONS -eq "true"
}

function Test-WindowsHost {
    return [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT
}

function Get-RequiredWindowsCRTOptionValue {
    return "static_from_buildtype"
}

function Ensure-WindowsStaticCRTSetupArgs {
    param([string[]]$MesonArgs)

    if (-not (Test-WindowsHost)) {
        return @($MesonArgs)
    }

    $requiredValue = Get-RequiredWindowsCRTOptionValue
    $requiredArg = "-Db_vscrt=$requiredValue"
    $updatedArgs = @()
    $found = $false

    foreach ($arg in $MesonArgs) {
        if ($arg -like "-Db_vscrt=*") {
            $found = $true
            if ($arg -ne $requiredArg) {
                Write-Host "Overriding Meson b_vscrt option to '$requiredValue' to satisfy openPREY Windows static CRT policy."
            }
            $updatedArgs += $requiredArg
            continue
        }

        $updatedArgs += $arg
    }

    if (-not $found) {
        $updatedArgs += $requiredArg
    }

    return @($updatedArgs)
}

function Test-WindowsStaticCRTReconfigureNeeded {
    param([string]$BuildDir)

    if (-not (Test-WindowsHost) -or -not (Test-MesonBuildDirectory $BuildDir)) {
        return $false
    }

    $configuredValue = Get-MesonBuildOptionValue -BuildDir $BuildDir -OptionName "b_vscrt"
    $requiredValue = Get-RequiredWindowsCRTOptionValue
    return [string]$configuredValue -ne $requiredValue
}

function Test-GameSourcesRefreshNeeded {
    param([string]$BuildDir, [string]$RepoRoot)
    if (-not (Test-MesonBuildDirectory $BuildDir)) { return $false }
    $buildGames = Get-MesonBuildOptionValue -BuildDir $BuildDir -OptionName "build_games"
    if ($buildGames -eq $false) { return $false }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
    if ($null -eq $python) { throw "Python is required to check canonical game sources." }
    # Content and git-state drift only refresh the snapshot; a membership change reconfigures.
    & $python.Source (Join-Path $RepoRoot "tools\build\game_source_inventory.py") $RepoRoot --refresh (Join-Path $BuildDir "openq4_game_sources.json") | Out-Null
    return ($LASTEXITCODE -ne 0)
}

function Remove-NonRuntimeInstallArtifacts {
    param([string]$InstallRoot)

    if ([string]::IsNullOrWhiteSpace($InstallRoot) -or -not (Test-Path $InstallRoot)) {
        return
    }

    $rootPatterns = @(
        "*.lib",
        "*.exp",
        "*.ilk",
        "*.map",
        "*.zip",
        "mgscope_sendinput.cfg",
        "scope_autotest*.cfg"
    )

    foreach ($pattern in $rootPatterns) {
        $matches = @(Get-ChildItem -Path $InstallRoot -Filter $pattern -File -ErrorAction SilentlyContinue)
        foreach ($match in $matches) {
            Write-Host "Removing non-runtime staged artifact '$($match.FullName)'"
            Remove-Item -LiteralPath $match.FullName -Force
        }
    }

    $gameDirPatterns = @(
        "*.lib",
        "*.exp",
        "*.ilk",
        "*.map",
        "*.so",
        "*.dylib",
        "game_x86.dll"
    )

    # basepr and every staged mod game directory that
    # carries game modules
    $installGameDirs = @(Get-ChildItem -Path $InstallRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "basepr" -or (Test-Path -LiteralPath (Join-Path $_.FullName "mod.json") -PathType Leaf) })
    foreach ($installGameDir in $installGameDirs) {
        foreach ($pattern in $gameDirPatterns) {
            $matches = @(Get-ChildItem -Path $installGameDir.FullName -Filter $pattern -File -ErrorAction SilentlyContinue)
            foreach ($match in $matches) {
                Write-Host "Removing non-runtime staged artifact '$($match.FullName)'"
                Remove-Item -LiteralPath $match.FullName -Force
            }
        }
    }
}

function Copy-WindowsDiagnosticSymbols {
    param(
        [string]$BuildDir,
        [string]$InstallRoot
    )

    if (-not (Test-WindowsHost)) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($BuildDir) -or -not (Test-Path $BuildDir)) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($InstallRoot) -or -not (Test-Path $InstallRoot)) {
        return
    }

    $rootPatterns = @(
        "openPREY-client_*.pdb",
        "openPREY-ded_*.pdb"
    )

    foreach ($pattern in $rootPatterns) {
        $matches = @(Get-ChildItem -Path $BuildDir -Filter $pattern -File -ErrorAction SilentlyContinue)
        foreach ($match in $matches) {
            $destination = Join-Path $InstallRoot $match.Name
            Write-Host "Staging diagnostic symbol '$destination'"
            Copy-Item -LiteralPath $match.FullName -Destination $destination -Force
        }
    }

    $installGameDir = Join-Path $InstallRoot "basepr"
    New-Item -Path $installGameDir -ItemType Directory -Force | Out-Null
    $stagedGameSymbols = @{}

    $gameBuildDirs = @(
        (Join-Path $BuildDir "content\basepr"),
        (Join-Path $BuildDir "basepr")
    )
    $gamePatterns = @(
        "game_*.pdb"
    )

    foreach ($gameBuildDir in $gameBuildDirs) {
        if (-not (Test-Path $gameBuildDir)) {
            continue
        }

        foreach ($pattern in $gamePatterns) {
            $matches = @(Get-ChildItem -Path $gameBuildDir -Filter $pattern -File -ErrorAction SilentlyContinue)
            foreach ($match in $matches) {
                $destination = Join-Path $installGameDir $match.Name
                if ($stagedGameSymbols.ContainsKey($destination)) {
                    continue
                }
                $stagedGameSymbols[$destination] = $true
                Write-Host "Staging diagnostic symbol '$destination'"
                Copy-Item -LiteralPath $match.FullName -Destination $destination -Force
            }
        }
    }
}

function Stop-openPREYRuntimeProcesses {
    [OutputType([bool])]
    param([Parameter(Mandatory = $true)][string]$InstallRoot)

    $targetDirectory = [System.IO.Path]::GetFullPath($InstallRoot).TrimEnd('\', '/')

    $processNames = @(
        "openPREY-client_x64",
        "openPREY-client_x86",
        "openPREY-client_arm64",
        "openPREY-ded_x64",
        "openPREY-ded_x86",
        "openPREY-ded_arm64"
    )

    $running = @(Get-Process -Name $processNames -ErrorAction SilentlyContinue | Where-Object {
        try {
            # A name match alone includes other worktrees and installed games.
            # An unreadable executable path is not permission to stop a process.
            $null = $_.Handle
            $executablePath = $_.Path
            if ([string]::IsNullOrWhiteSpace($executablePath)) { return $false }
            $directory = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($executablePath))
            return [string]::Equals($directory, $targetDirectory, [StringComparison]::OrdinalIgnoreCase)
        } catch {
            return $false
        }
    })
    if ($running.Count -eq 0) {
        return $false
    }

    Write-Host "Stopping openPREY processes in '$targetDirectory' before install: $($running.ProcessName -join ', ')"

    foreach ($proc in $running) {
        try {
            if ($proc.MainWindowHandle -ne 0) {
                $null = $proc.CloseMainWindow()
            }
        } catch {
            # Ignore close-window failures and fall back to force stop below.
        }
    }

    Start-Sleep -Milliseconds 500

    # Retain the selected process objects/handles. A second lookup by name could
    # stop another checkout or a new process started during the close interval.
    foreach ($proc in $running) {
        try {
            $proc.Refresh()
            if (-not $proc.HasExited) {
                $proc.Kill()
                if (-not $proc.WaitForExit(5000)) {
                    throw "Process $($proc.Id) did not exit."
                }
            }
        } catch {
            # A process can finish between Refresh and Kill.
            if (-not $proc.HasExited) {
                throw "Failed to stop openPREY in '$targetDirectory'. Close it manually and retry install. Details: $($_.Exception.Message)"
            }
        }
    }

    return $true
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDir "..\.."))
$defaultBuildDir = Join-Path $repoRoot "builddir"

# Android uses the NDK compiler recorded in its cross file/build metadata.
# Dispatch through this same Windows entry point, without desktop-only CRT,
# companion Windows builds, process shutdown or runtime staging side effects.
[string[]]$androidMesonArgs = @($args)
$isAndroidCross = $false
$androidBuildInfo = Get-CompileBuildDirInfo -MesonArgs $androidMesonArgs -DefaultBuildDir $defaultBuildDir
$androidMachineInfo = Join-Path $androidBuildInfo.BuildDir "meson-info/intro-machines.json"
if ($androidMesonArgs.Count -gt 0 -and $androidMesonArgs[0] -in @("compile", "install", "test") -and
        (Test-Path -LiteralPath $androidMachineInfo -PathType Leaf)) {
    $androidMachines = Get-Content -LiteralPath $androidMachineInfo -Raw | ConvertFrom-Json
    $isAndroidCross = $androidMachines.host.system -eq "android"
}
for ($index = 0; $index -lt $androidMesonArgs.Count; $index++) {
    $argument = $androidMesonArgs[$index]
    $crossFile = $null
    if ($argument -eq "--cross-file" -and ($index + 1) -lt $androidMesonArgs.Count) {
        $crossFile = $androidMesonArgs[$index + 1]
    } elseif ($argument.StartsWith("--cross-file=")) {
        $crossFile = $argument.Substring("--cross-file=".Length)
    }
    if ($crossFile -and (Test-Path -LiteralPath $crossFile -PathType Leaf)) {
        if ((Get-Content -LiteralPath $crossFile -Raw) -match '(?m)^\s*system\s*=\s*''android''\s*$') {
            $isAndroidCross = $true
        }
    }
    if (-not $argument.StartsWith("-")) {
        $machineInfo = Join-Path $argument "meson-info/intro-machines.json"
        if (Test-Path -LiteralPath $machineInfo -PathType Leaf) {
            $machines = Get-Content -LiteralPath $machineInfo -Raw | ConvertFrom-Json
            if ($machines.host.system -eq "android") { $isAndroidCross = $true }
        }
    }
}
if ($isAndroidCross) {
    if ($androidMesonArgs[0] -eq "install" -and -not ($androidMesonArgs -contains "--skip-subprojects")) {
        $androidMesonArgs += "--skip-subprojects"
    }
    $androidMesonCommand = Get-MesonCommand
    if ($androidMesonArgs[0] -eq "compile" -or $androidMesonArgs[0] -eq "install") {
        if (Test-GameSourcesRefreshNeeded -BuildDir $androidBuildInfo.BuildDir -RepoRoot $repoRoot) {
            Write-Host "Canonical game source membership changed. Reconfiguring '$($androidBuildInfo.BuildDir)'..."
            Invoke-Meson -MesonArgs @("setup", "--reconfigure", $androidBuildInfo.BuildDir, $repoRoot) `
                -VsDevCmdPath "" -MesonCommand $androidMesonCommand -VsTargetArch "" -VsHostArch ""
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
    }
    Invoke-Meson -MesonArgs $androidMesonArgs -VsDevCmdPath "" -MesonCommand $androidMesonCommand -VsTargetArch "" -VsHostArch ""
    exit $LASTEXITCODE
}

$rcWrapper = Join-Path $scriptDir "rc.cmd"
if (-not (Test-Path $rcWrapper)) {
    throw "WINDRES wrapper not found at '$rcWrapper'."
}

$env:WINDRES = $rcWrapper

$vsTargetArch = Get-openPREYVsTargetArch
$vsHostArch = Get-openPREYVsHostArch
$vsDevCmd = $null
if (Test-WindowsHost) {
    $vsDevCmd = Get-VsDevCmdPath -TargetArch $vsTargetArch
}
$mesonCommand = Get-MesonCommand

[string[]]$effectiveArgs = @($args)
if ($effectiveArgs.Count -eq 0) {
    throw "No Meson arguments were provided to meson_setup.ps1."
}

$commandName = $effectiveArgs[0].ToLowerInvariant()
$stageWindowsRuntimeScript = Join-Path $scriptDir "stage_windows_runtime.py"
$syncIconsScript = Join-Path $scriptDir "sync_icons.py"
$checkStagedContentScript = Join-Path $scriptDir "check_staged_content_edits.py"

if ($commandName -eq "setup") {
    $effectiveArgs = Ensure-WindowsStaticCRTSetupArgs -MesonArgs $effectiveArgs
}




if ($effectiveArgs.Length -gt 0 -and ($effectiveArgs[0] -eq "compile" -or $effectiveArgs[0] -eq "install")) {
    $isCompile = $effectiveArgs[0] -eq "compile"
    $isInstall = $effectiveArgs[0] -eq "install"
    $buildInfo = Get-CompileBuildDirInfo -MesonArgs $effectiveArgs -DefaultBuildDir $defaultBuildDir

    if ($isCompile -and -not (Test-MesonBuildDirectory $buildInfo.BuildDir)) {
        Write-Host "Meson build directory '$($buildInfo.BuildDir)' is missing or invalid. Running meson setup..."
        $setupArgs = @(
            "setup",
            $buildInfo.BuildDir,
            $repoRoot,
            "--backend",
            "ninja",
            "--buildtype=debug",
            "--wrap-mode=forcefallback"
        )
        $setupArgs = Ensure-WindowsStaticCRTSetupArgs -MesonArgs $setupArgs

        Invoke-Meson -MesonArgs $setupArgs -VsDevCmdPath $vsDevCmd -MesonCommand $mesonCommand -VsTargetArch $vsTargetArch -VsHostArch $vsHostArch
        $setupCode = [int]$LASTEXITCODE
        if ($setupCode -ne 0) {
            exit $setupCode
        }
    }

    $reconfigureReasons = @()
    $needsWindowsStaticCRTRefresh = Test-WindowsStaticCRTReconfigureNeeded -BuildDir $buildInfo.BuildDir
    if ($needsWindowsStaticCRTRefresh) {
        $configuredCRT = Get-MesonBuildOptionValue -BuildDir $buildInfo.BuildDir -OptionName "b_vscrt"
        if ([string]::IsNullOrWhiteSpace([string]$configuredCRT)) {
            $configuredCRT = "unset"
        }
        Write-Host "Meson build directory '$($buildInfo.BuildDir)' uses b_vscrt='$configuredCRT'. Reconfiguring for openPREY's required Windows static CRT policy..."
        $reconfigureReasons += "Windows static CRT policy"
    }

    $needsGameLibsRefresh = Test-GameSourcesRefreshNeeded -BuildDir $buildInfo.BuildDir -RepoRoot $repoRoot
    if ($needsGameLibsRefresh) {
        Write-Host "Canonical game source membership changed since the last snapshot. Reconfiguring '$($buildInfo.BuildDir)'..."
        $reconfigureReasons += "canonical game source membership"
    }

    if ($reconfigureReasons.Count -gt 0) {
        $reconfigureArgs = @(
            "setup",
            "--reconfigure",
            $buildInfo.BuildDir,
            $repoRoot
        )
        $reconfigureArgs = Ensure-WindowsStaticCRTSetupArgs -MesonArgs $reconfigureArgs
        Invoke-Meson -MesonArgs $reconfigureArgs -VsDevCmdPath $vsDevCmd -MesonCommand $mesonCommand -VsTargetArch $vsTargetArch -VsHostArch $vsHostArch
        $reconfigureCode = [int]$LASTEXITCODE
        if ($reconfigureCode -ne 0) {
            exit $reconfigureCode
        }
    }

    if (-not $buildInfo.HasExplicit) {
        $remainingArgs = @()
        if ($effectiveArgs.Length -gt 1) {
            $remainingArgs = $effectiveArgs[1..($effectiveArgs.Length - 1)]
        }
        $effectiveArgs = @($effectiveArgs[0], "-C", $buildInfo.BuildDir) + $remainingArgs
    }

    if ($isInstall -and -not ($effectiveArgs -contains "--skip-subprojects")) {
        $effectiveArgs += "--skip-subprojects"
    }
}

if ($commandName -eq "install" -and $env:OPENQ4_INSTALL_CLOSE_RUNNING -ne "0") {
    Stop-openPREYRuntimeProcesses -InstallRoot (Join-Path $repoRoot ".install") | Out-Null
}

if (@("setup", "compile", "install").Contains($commandName) -and $env:OPENQ4_SKIP_ICON_SYNC -ne "1") {
    if (-not (Test-Path $syncIconsScript)) {
        throw "Icon sync script not found: '$syncIconsScript'."
    }

    & python $syncIconsScript "--source-root" $repoRoot
    $syncIconExit = [int]$LASTEXITCODE
    if ($syncIconExit -ne 0) {
        exit $syncIconExit
    }
}

if ($commandName -eq "install") {
    if (-not (Test-Path $checkStagedContentScript)) {
        throw "Staged content edit check script not found: '$checkStagedContentScript'."
    }

    & python $checkStagedContentScript "--source-root" $repoRoot
    $checkStagedContentExit = [int]$LASTEXITCODE
    if ($checkStagedContentExit -ne 0) {
        exit $checkStagedContentExit
    }
}

Invoke-Meson -MesonArgs $effectiveArgs -VsDevCmdPath $vsDevCmd -MesonCommand $mesonCommand -VsTargetArch $vsTargetArch -VsHostArch $vsHostArch
$exitCode = [int]$LASTEXITCODE

if ($commandName -eq "install" -and $exitCode -ne 0 -and $env:OPENQ4_INSTALL_RETRY_ON_FAILURE -ne "0") {
    Write-Host "Meson install failed; retrying once..."
    if ($env:OPENQ4_INSTALL_CLOSE_RUNNING -ne "0") {
        Stop-openPREYRuntimeProcesses -InstallRoot (Join-Path $repoRoot ".install") | Out-Null
    }
    Start-Sleep -Milliseconds 500
    Invoke-Meson -MesonArgs $effectiveArgs -VsDevCmdPath $vsDevCmd -MesonCommand $mesonCommand -VsTargetArch $vsTargetArch -VsHostArch $vsHostArch
    $exitCode = [int]$LASTEXITCODE
}

if ($exitCode -eq 0 -and ($commandName -eq "compile" -or $commandName -eq "install")) {
    $includeInstallRoot = $commandName -eq "install"
    $buildInfo = Get-CompileBuildDirInfo -MesonArgs $effectiveArgs -DefaultBuildDir $defaultBuildDir
    $installRootPath = Join-Path $repoRoot ".install"
    Remove-NonRuntimeInstallArtifacts -InstallRoot $installRootPath

    if (-not (Test-Path $stageWindowsRuntimeScript)) {
        throw "Windows runtime staging script not found: '$stageWindowsRuntimeScript'."
    }

    $runtimeArgs = @(
        "--source-root", $repoRoot,
        "--build-dir", $buildInfo.BuildDir
    )
    if ($includeInstallRoot) {
        $runtimeArgs += @("--install-dir", $installRootPath)
    }

    & python $stageWindowsRuntimeScript @runtimeArgs
    $runtimeExit = [int]$LASTEXITCODE
    if ($runtimeExit -ne 0) {
        exit $runtimeExit
    }

    if ($includeInstallRoot) {
        Copy-WindowsDiagnosticSymbols -BuildDir $buildInfo.BuildDir -InstallRoot $installRootPath
    }
}

exit $exitCode
