param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('task', 'launch')]
    [string]$Kind,

    # A task label or launch configuration name, matched exactly. A number is
    # read as a position in tasks.json or launch.json instead, but positions
    # move whenever either file changes, so the Codex actions use names.
    [Parameter(Mandatory = $true, Position = 1)]
    [string]$Entry
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$workspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$tasksPath = Join-Path $workspaceRoot '.vscode\tasks.json'
$launchPath = Join-Path $workspaceRoot '.vscode\launch.json'

function Resolve-WorkspaceToken([string]$Value) {
    if ($null -eq $Value) {
        return $null
    }

    return $Value.Replace('${workspaceFolder}', $workspaceRoot)
}

function Get-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required VS Code configuration file not found: $Path"
    }

    # Windows PowerShell reads a file without a byte order mark in the ANSI code
    # page, which turns the em dash in every launch name into mojibake.
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

# Strict mode throws on a property the JSON leaves out, such as dependsOn.
function Get-OptionalProperty([object]$Object, [string]$Name) {
    if ($null -eq $Object) {
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Find-EntryIndex([object[]]$Entries, [string]$Key, [string]$Name) {
    for ($i = 0; $i -lt $Entries.Count; $i++) {
        if ([string]::Equals([string](Get-OptionalProperty $Entries[$i] $Key), $Name, [System.StringComparison]::Ordinal)) {
            return $i
        }
    }

    return -1
}

function Select-Entry([object[]]$Entries, [string]$Key, [string]$Wanted, [string]$Noun, [string]$File) {
    if ($Wanted -match '^\d+$') {
        $index = [int]$Wanted
        if ($index -ge $Entries.Count) {
            throw "$File has no $Noun at index $index."
        }

        return $index
    }

    $index = Find-EntryIndex $Entries $Key $Wanted
    if ($index -lt 0) {
        throw "No $Noun in $File has the $Key '$Wanted'."
    }

    return $index
}

function Invoke-ConfiguredCommand(
    [string]$Label,
    [string]$Command,
    [object[]]$Arguments,
    [string]$WorkingDirectory,
    [switch]$Wait
) {
    if ([string]::IsNullOrWhiteSpace($Command)) {
        return
    }

    $resolvedCommand = Resolve-WorkspaceToken $Command
    $resolvedArgs = @()
    $argumentList = @()

    if ($null -ne $Arguments) {
        $argumentList = @($Arguments)
    }

    foreach ($argument in $argumentList) {
        if ($null -eq $argument) {
            continue
        }

        $resolvedArgs += Resolve-WorkspaceToken ([string]$argument)
    }

    $resolvedWorkingDirectory = Resolve-WorkspaceToken $WorkingDirectory
    if ([string]::IsNullOrWhiteSpace($resolvedWorkingDirectory)) {
        $resolvedWorkingDirectory = $workspaceRoot
    }

    Write-Host "Running $Label"
    Push-Location -LiteralPath $resolvedWorkingDirectory
    try {
        # PowerShell does not wait for a Windows GUI program such as the client,
        # or record its exit code, unless its output goes through a pipe.
        $global:LASTEXITCODE = 0
        if ($Wait) {
            & $resolvedCommand @resolvedArgs | Out-Host
        }
        else {
            & $resolvedCommand @resolvedArgs
        }

        $exitCode = $global:LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($exitCode -ne 0) {
        Write-Host "$Label exited with code $exitCode"
        exit $exitCode
    }
}

$tasks = @((Get-JsonFile $tasksPath).tasks)
$visitedTasks = New-Object System.Collections.Generic.HashSet[int]

function Invoke-TaskByIndex([int]$TaskIndex) {
    if ($visitedTasks.Contains($TaskIndex)) {
        return
    }

    [void]$visitedTasks.Add($TaskIndex)
    $task = $tasks[$TaskIndex]
    $label = Get-OptionalProperty $task 'label'

    # dependsOn may also be a single label. Dependencies run one after another,
    # which is what dependsOrder sequence asks VS Code for.
    foreach ($dependency in @(Get-OptionalProperty $task 'dependsOn')) {
        if ($null -eq $dependency) {
            continue
        }

        $dependencyIndex = Find-EntryIndex $tasks 'label' $dependency
        if ($dependencyIndex -lt 0) {
            throw "Task '$label' depends on unknown task '$dependency'."
        }

        Invoke-TaskByIndex $dependencyIndex
    }

    $options = Get-OptionalProperty $task 'options'
    Invoke-ConfiguredCommand -Label $label -Command (Get-OptionalProperty $task 'command') -Arguments (Get-OptionalProperty $task 'args') -WorkingDirectory (Get-OptionalProperty $options 'cwd')
}

function Invoke-Launch([object]$Launch) {
    $name = Get-OptionalProperty $Launch 'name'
    $preLaunchTask = Get-OptionalProperty $Launch 'preLaunchTask'

    if (-not [string]::IsNullOrWhiteSpace($preLaunchTask)) {
        $taskIndex = Find-EntryIndex $tasks 'label' $preLaunchTask
        if ($taskIndex -lt 0) {
            throw "Launch '$name' references unknown preLaunchTask '$preLaunchTask'."
        }

        Invoke-TaskByIndex $taskIndex
    }

    # The action lasts until the game exits, as a VS Code debug session does.
    Invoke-ConfiguredCommand -Label $name -Command (Get-OptionalProperty $Launch 'program') -Arguments (Get-OptionalProperty $Launch 'args') -WorkingDirectory (Get-OptionalProperty $Launch 'cwd') -Wait
}

switch ($Kind) {
    'task' {
        Invoke-TaskByIndex (Select-Entry $tasks 'label' $Entry 'task' '.vscode\tasks.json')
    }
    'launch' {
        $configurations = @((Get-JsonFile $launchPath).configurations)
        Invoke-Launch $configurations[(Select-Entry $configurations 'name' $Entry 'configuration' '.vscode\launch.json')]
    }
}

exit 0
