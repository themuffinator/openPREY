param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('setup', 'compile', 'install', 'fastbuild')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$workspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$mesonWrapper = Join-Path $workspaceRoot 'tools\build\meson_setup.ps1'
$buildDir = Join-Path $workspaceRoot 'builddir'
$installDir = Join-Path $workspaceRoot '.install'
$fastStageScript = Join-Path $workspaceRoot 'tools\build\stage_fast_install.py'
$checkStagedContentScript = Join-Path $workspaceRoot 'tools\build\check_staged_content_edits.py'

if (-not (Test-Path $mesonWrapper)) {
    throw "openPREY Meson wrapper not found at '$mesonWrapper'."
}

function Invoke-openPREYMeson([string[]]$MesonArgs) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $mesonWrapper @MesonArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Invoke-PythonTool([string[]]$ToolArgs) {
    & python @ToolArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Test-MesonBuildDirectory([string]$Path) {
    $coreData = Join-Path $Path 'meson-private\coredata.dat'
    $ninjaFile = Join-Path $Path 'build.ninja'
    return (Test-Path $coreData) -and (Test-Path $ninjaFile)
}

# openPREY's standard local tree (builddir) is a debug build, so the launch
# configurations debug Prey compatibility work with full symbols and assertions.
$expectedBuildOptions = [ordered]@{
    'buildtype' = 'debug'
}

function Get-StaleBuildOptions([string]$Path) {
    $optionsFile = Join-Path $Path 'meson-info\intro-buildoptions.json'
    if (-not (Test-Path $optionsFile)) {
        return @($expectedBuildOptions.Keys)
    }
    $configured = @{}
    foreach ($option in (Get-Content $optionsFile -Raw | ConvertFrom-Json)) {
        $configured[$option.name] = "$($option.value)".ToLowerInvariant()
    }
    return @($expectedBuildOptions.Keys | Where-Object { $configured[$_] -ne $expectedBuildOptions[$_] })
}

function Invoke-openPREYSetup {
    $optionArgs = @('--backend', 'ninja', '--wrap-mode=forcefallback')
    foreach ($name in $expectedBuildOptions.Keys) {
        $optionArgs += "-D$name=$($expectedBuildOptions[$name])"
    }
    if (Test-MesonBuildDirectory $buildDir) {
        Invoke-openPREYMeson (@('setup', $buildDir, $workspaceRoot, '--reconfigure') + $optionArgs)
    } else {
        Invoke-openPREYMeson (@('setup', '--wipe', $buildDir, $workspaceRoot) + $optionArgs)
    }
}

# An existing build directory keeps whatever it was configured with, and the
# compile tasks never reconfigure on their own, so bring it up to the expected
# options before compiling.
function Invoke-openPREYCompile {
    $stale = @(Get-StaleBuildOptions $buildDir)
    if ($stale.Count -gt 0) {
        Write-Host "builddir options out of date ($($stale -join ', ')); reconfiguring."
        Invoke-openPREYSetup
    }
    Invoke-openPREYMeson @(
        'compile',
        '-C',
        $buildDir
    )
}

switch ($Action) {
    'setup' {
        Invoke-openPREYSetup
    }
    'compile' {
        Invoke-openPREYCompile
    }
    'fastbuild' {
        if (-not (Test-Path $fastStageScript)) {
            throw "openPREY fast staging script not found at '$fastStageScript'."
        }
        if (-not (Test-Path $checkStagedContentScript)) {
            throw "openPREY staged content edit check script not found at '$checkStagedContentScript'."
        }

        Invoke-openPREYCompile
        Invoke-PythonTool @(
            $checkStagedContentScript,
            '--source-root',
            $workspaceRoot
        )
        Invoke-PythonTool @(
            $fastStageScript,
            '--source-root',
            $workspaceRoot,
            '--build-dir',
            $buildDir,
            '--install-dir',
            $installDir
        )
    }
    'install' {
        Invoke-openPREYMeson @(
            'install',
            '-C',
            $buildDir,
            '--no-rebuild',
            '--skip-subprojects'
        )
    }
}
