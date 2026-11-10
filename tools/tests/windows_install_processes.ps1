param(
    [Parameter(Mandatory = $true)][string]$WrapperPath,
    [Parameter(Mandatory = $true)][string]$TestRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Execute the production function without running a build or touching real
# processes. The doubles expose window-close, exit and force-stop races.
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($WrapperPath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw "Cannot parse wrapper: $($parseErrors[0].Message)" }
$definition = $ast.Find({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -ceq "Stop-openQ4RuntimeProcesses"
}, $true)
if ($null -eq $definition) { throw "Runtime shutdown function is missing" }
Invoke-Expression $definition.Extent.Text

function Assert-True($condition, [string]$message) {
    if (-not $condition) { throw $message }
}

$script:nextId = 100
function New-ProcessRecord([string]$path) {
    $script:nextId++
    $proc = [PSCustomObject]@{
        Id = $script:nextId; Handle = $script:nextId; ProcessName = "openQ4-client_x64"; Path = $path
        MainWindowHandle = 1; HasExited = $false; Closed = $false; Killed = $false
        ExitOnClose = $false; ThrowOnClose = $false; ThrowOnKill = $false
        ExitBeforeKill = $false; AddDuringClose = $false
    }
    $proc | Add-Member ScriptMethod CloseMainWindow {
        $this.Closed = $true
        if ($this.AddDuringClose) { $script:processes += $script:lateProcess }
        if ($this.ThrowOnClose) { throw "Window close refused" }
        if ($this.ExitOnClose) { $this.HasExited = $true }
        return $true
    }
    $proc | Add-Member ScriptMethod Refresh {}
    $proc | Add-Member ScriptMethod Kill {
        if ($this.ExitBeforeKill) { $this.HasExited = $true; throw "Already exited" }
        if ($this.ThrowOnKill) { throw "Access denied" }
        $this.Killed = $true
        $this.HasExited = $true
    }
    $proc | Add-Member ScriptMethod WaitForExit { param($timeout); return $this.HasExited }
    return $proc
}
function Get-Process {
    [CmdletBinding()]
    param([string[]]$Name)
    $script:lookups++
    $script:processes | Where-Object { $Name -contains $_.ProcessName }
}
function Start-Sleep { param([int]$Milliseconds) }
# Guard the old implementation's fallback as well, so a negative control can
# never reach the operating system with the fixture's invented process IDs.
function Stop-Process {
    [CmdletBinding()]
    param([Parameter(ValueFromPipeline = $true)]$InputObject, [switch]$Force)
    process { $InputObject.Killed = $true; $InputObject.HasExited = $true }
}
function Reset-Case { $script:lookups = 0; $script:processes = @(); $script:lateProcess = $null }

$install = [System.IO.Path]::GetFullPath((Join-Path $TestRoot ".install"))
Reset-Case
Assert-True (-not (Stop-openQ4RuntimeProcesses -InstallRoot $install)) "Empty selection should report no shutdown"

Reset-Case
$own = New-ProcessRecord (Join-Path $install "openQ4-client_x64.exe")
$foreign = New-ProcessRecord (Join-Path $TestRoot "other-worktree/.install/openQ4-client_x64.exe")
$prefix = New-ProcessRecord (Join-Path ($install + "-other") "openQ4-client_x64.exe")
$nested = New-ProcessRecord (Join-Path $install "comparison/openQ4-client_x64.exe")
$unknown = New-ProcessRecord ""
$unreadable = New-ProcessRecord ""
$unreadable.PSObject.Properties.Remove("Path")
$unreadable | Add-Member ScriptProperty Path { throw "Cannot inspect process" }
$script:lateProcess = New-ProcessRecord (Join-Path $install "openQ4-client_x64.exe")
$own.AddDuringClose = $true
$script:processes = @($own, $foreign, $prefix, $nested, $unknown, $unreadable)
Assert-True (Stop-openQ4RuntimeProcesses -InstallRoot ($install + "/")) "Target process was not found"
Assert-True ($own.Closed -and $own.Killed) "Target process was not closed and stopped"
foreach ($proc in @($foreign, $prefix, $nested, $unknown, $unreadable, $script:lateProcess)) {
    Assert-True (-not $proc.Closed -and -not $proc.Killed) "Unselected process $($proc.Id) was touched"
}
Assert-True ($script:lookups -eq 1) "Shutdown performed a second name lookup"

Reset-Case
$own = New-ProcessRecord ((Join-Path $install "openQ4-client_x64.exe").ToUpperInvariant())
$own.ExitOnClose = $true
$script:processes = @($own)
Assert-True (Stop-openQ4RuntimeProcesses -InstallRoot $install) "Case-insensitive path match failed"
Assert-True ($own.Closed -and -not $own.Killed) "Gracefully exited process was force-stopped"

Reset-Case
$own = New-ProcessRecord (Join-Path $install "openQ4-client_x64.exe")
$own.ThrowOnClose = $true
$script:processes = @($own)
Assert-True (Stop-openQ4RuntimeProcesses -InstallRoot $install) "Close refusal blocked scoped fallback"
Assert-True $own.Killed "Close refusal did not use scoped fallback"

Reset-Case
$own = New-ProcessRecord (Join-Path $install "openQ4-client_x64.exe")
$own.ExitBeforeKill = $true
$script:processes = @($own)
Assert-True (Stop-openQ4RuntimeProcesses -InstallRoot $install) "Concurrent exit should be harmless"

Reset-Case
$own = New-ProcessRecord (Join-Path $install "openQ4-client_x64.exe")
$own.ThrowOnKill = $true
$script:processes = @($own)
$rejected = $false
try { $null = Stop-openQ4RuntimeProcesses -InstallRoot $install } catch {
    $rejected = $_.Exception.Message -like "Failed to stop openQ4 in*"
}
Assert-True $rejected "Failure to stop a live target did not propagate"

# Both install attempts must pass a scope; testing only the helper would miss
# a call site that accidentally reverted to name-only selection.
$calls = @($ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.CommandAst] -and
        $node.GetCommandName() -ceq "Stop-openQ4RuntimeProcesses"
}, $true))
Assert-True ($calls.Count -eq 2) "Expected initial install and retry shutdown calls"
foreach ($call in $calls) {
    Assert-True ($call.Extent.Text -match '-InstallRoot\s+\(Join-Path\s+\$repoRoot\s+"\.install"\)') "Install call lacks its checkout scope"
}
Write-Output "windows_install_processes: 6 behavioral cases passed"
