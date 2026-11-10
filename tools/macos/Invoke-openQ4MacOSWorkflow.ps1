[CmdletBinding()]
param(
    [ValidateSet("Probe", "Bootstrap", "Assets", "Sync", "Build", "Smoke", "Renderer", "Launcher", "Signoff", "CollectResults", "All")]
    [string[]]$Action = @("All"),
    [Parameter(Mandatory = $true)]
    [string]$MacHost,
    [string]$MacUser = "codex",
    [ValidateRange(1, 65535)]
    [int]$SshPort = 22,
    [string]$IdentityFile,
    [string]$MacWorkspace = "~/openq4-work",
    [string]$MacHome = "",
    [string]$MacBasePath = "~/openq4-work/Quake4",
    [string]$HostQuake4Path = "C:\Program Files (x86)\Steam\steamapps\common\Quake 4",
    [string]$HostGameLibsPath,
    [string]$TmpRoot,
    [string]$ResultCollectionDir,
    [string]$MacOSRunId,
    [ValidateSet("opengl", "metal", "both")]
    [string]$MacOSGraphicsBridge = "opengl",
    [ValidateSet("apple_framework", "system")]
    [string]$MacOSOpenALProvider = "system",
    [ValidateSet("current-manual-signoff", "current-hosted-ci-runner", "floor-candidate", "latest-public-macos")]
    [string]$MacOSOSMatrixRole = "current-manual-signoff",
    [ValidateSet("plain", "debug", "debugoptimized", "release", "minsize", "custom")]
    [string]$BuildType = "debug",
    [string]$BuildDir = "builddir",
    [ValidateRange(1, 100000)]
    [int]$SmokeLimit = 1,
    [switch]$SkipAssets,
    [switch]$SkipSync,
    [switch]$SkipResultCollection,
    [switch]$SkipResultArchiveValidation,
    [switch]$RequireCompletedSignoffChecklist
)

$ErrorActionPreference = "Stop"
$script:MacOSResultTokenMaxLength = 80
$script:RemoteTempRoot = ""

function Get-RepoRoot {
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).ProviderPath
}

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Quote-Sh {
    param([AllowNull()][string]$Value)
    if ($null -eq $Value) {
        $Value = ""
    }
    return "'" + $Value.Replace("'", "'\''") + "'"
}

function Assert-NoShellTokenHazards {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [AllowNull()][string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -match '[\x00-\x20\x7f]') {
        throw "Invalid ${Label} '$Value'. Use a non-empty value without whitespace or control characters."
    }
    if ($Value.StartsWith("-")) {
        throw "Invalid ${Label} '$Value'. Values must not begin with '-'."
    }
}

function Assert-ValidMacUser {
    Assert-NoShellTokenHazards -Label "MacUser" -Value $MacUser
    if ($MacUser -notmatch '^[A-Za-z_][A-Za-z0-9._-]*$') {
        throw "Invalid MacUser '$MacUser'. Use a macOS short user name made from letters, digits, dots, underscores, or dashes."
    }
}

function Assert-ValidMacHost {
    Assert-NoShellTokenHazards -Label "MacHost" -Value $MacHost
    if ($MacHost -match '[@/\\''"`]') {
        throw "Invalid MacHost '$MacHost'. Use only a host name, host alias, IPv4 address, or bracketed IPv6 address."
    }
    if ($MacHost -match ':') {
        if ($MacHost -notmatch '^\[[0-9A-Fa-f:.%]+\]$') {
            throw "Invalid MacHost '$MacHost'. IPv6 addresses must be bracketed for scp, for example [fe80::1]."
        }
        return
    }
    if ($MacHost -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
        throw "Invalid MacHost '$MacHost'. Use a host name, host alias, IPv4 address, or bracketed IPv6 address."
    }
}

function Assert-SafeRemoteWorkflowPath {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [AllowNull()][string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -match '[\x00-\x1f\x7f]') {
        throw "Invalid ${Label} '$Value'. Use a non-empty single-line POSIX path."
    }
    if ($Value.StartsWith("-") -or $Value -match '\\') {
        throw "Invalid ${Label} '$Value'. Use a POSIX path that does not begin with '-' or contain backslashes."
    }
    if (-not ($Value.StartsWith("/") -or $Value.StartsWith("~/"))) {
        throw "Invalid ${Label} '$Value'. Use an absolute POSIX path or a ~/ path so SSH shell working directories cannot change the workflow target."
    }
    if ($Value -match '//') {
        throw "Invalid ${Label} '$Value'. Empty POSIX path segments are not allowed."
    }

    $trimmed = $Value.TrimEnd("/")
    if ($trimmed -in @("", ".", "..", "~", "/")) {
        throw "Invalid ${Label} '$Value'. Refusing to use a home, root, or relative traversal path."
    }
    if ($Value -match '(^|/)\.($|/)') {
        throw "Invalid ${Label} '$Value'. Dot path segments are not allowed."
    }
    if ($Value -match '(^|/)\.\.($|/)') {
        throw "Invalid ${Label} '$Value'. Parent-directory traversal is not allowed."
    }
}

function Assert-SafeRemoteGuestHomePath {
    param([AllowNull()][string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -match '[\x00-\x1f\x7f]') {
        throw "Invalid MacHome '$Value'. Use a non-empty single-line absolute POSIX path."
    }
    if ($Value.StartsWith("-") -or $Value -match '\\') {
        throw "Invalid MacHome '$Value'. Use an absolute POSIX path that does not begin with '-' or contain backslashes."
    }
    if (-not $Value.StartsWith("/")) {
        throw "Invalid MacHome '$Value'. Use an absolute POSIX path such as /Users/codex."
    }
    if ($Value -match '//') {
        throw "Invalid MacHome '$Value'. Empty POSIX path segments are not allowed."
    }

    $trimmed = $Value.TrimEnd("/")
    if ($trimmed -in @("", ".", "..", "/")) {
        throw "Invalid MacHome '$Value'. Refusing to use the filesystem root or a relative traversal path."
    }
    if ($Value -match '(^|/)\.($|/)') {
        throw "Invalid MacHome '$Value'. Dot path segments are not allowed."
    }
    if ($Value -match '(^|/)\.\.($|/)') {
        throw "Invalid MacHome '$Value'. Parent-directory traversal is not allowed."
    }
}

function ConvertTo-RemoteWorkflowComparisonPath {
    param([Parameter(Mandatory = $true)][string]$Value)

    $path = $Value.TrimEnd("/")
    if ($MacHome -and $path.StartsWith("~/", [System.StringComparison]::Ordinal)) {
        $path = "$($MacHome.TrimEnd("/"))/$($path.Substring(2))"
    }
    return $path.Normalize([System.Text.NormalizationForm]::FormC).ToLowerInvariant()
}

function Join-RemotePosixPath {
    param(
        [Parameter(Mandatory = $true)][string]$Base,
        [Parameter(Mandatory = $true)][string]$Child
    )

    return "$($Base.TrimEnd("/"))/$Child"
}

function Assert-SafeMacOSBuildDir {
    param([AllowNull()][string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -match '[\x00-\x20\x7f]') {
        throw "Invalid BuildDir '$Value'. Use a non-empty relative build output path without whitespace or control characters."
    }
    if ($Value.StartsWith("-") -or $Value.StartsWith("/") -or $Value.StartsWith("~/") -or $Value -match '\\') {
        throw "Invalid BuildDir '$Value'. Use a relative POSIX path under builddir* or .tmp/."
    }
    if ($Value -match '//') {
        throw "Invalid BuildDir '$Value'. Empty POSIX path segments are not allowed."
    }
    if ($Value -match '(^|/)\.($|/)') {
        throw "Invalid BuildDir '$Value'. Dot path segments are not allowed."
    }
    if ($Value -match '(^|/)\.\.($|/)') {
        throw "Invalid BuildDir '$Value'. Parent-directory traversal is not allowed."
    }
    if (-not ($Value -like "builddir*" -or $Value -like ".tmp/*")) {
        throw "Invalid BuildDir '$Value'. BuildDir must live under .tmp/ or use a builddir* name."
    }
}

function Assert-MacBasePathNotReservedWorkspaceChild {
    $workspace = ConvertTo-RemoteWorkflowComparisonPath -Value $MacWorkspace
    $basePath = ConvertTo-RemoteWorkflowComparisonPath -Value $MacBasePath
    $reservedChildren = @("openQ4", "openQ4-game", "incoming-quake4", "results")

    foreach ($child in $reservedChildren) {
        $reservedPath = "${workspace}/${child}".Normalize([System.Text.NormalizationForm]::FormC).ToLowerInvariant()
        if (
            $basePath.Equals($reservedPath, [System.StringComparison]::OrdinalIgnoreCase) -or
            $basePath.StartsWith("${reservedPath}/", [System.StringComparison]::OrdinalIgnoreCase)
        ) {
            throw "MacBasePath must not target reserved workflow directory '${child}' or one of its children; asset installation uses rsync --delete."
        }
    }
}

function Assert-LocalRegularFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $fullPath = Get-FullPath $Path
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "${Label} was not found or is not a file: $fullPath"
    }
    $item = Get-Item -LiteralPath $fullPath -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "${Label} must not be a symlink, junction, or reparse point: $fullPath"
    }
}

function Assert-LocalOutputFileTarget {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label,
        [switch]$MustNotExist
    )

    $fullPath = Get-FullPath $Path
    $parent = Split-Path -Parent $fullPath
    Initialize-LocalDirectory -Path $parent -Label "${Label} parent directory" | Out-Null
    if (Test-Path -LiteralPath $fullPath) {
        $item = Get-Item -LiteralPath $fullPath -Force
        if ($item.PSIsContainer) {
            throw "${Label} target exists but is a directory: $fullPath"
        }
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "${Label} target must not be a symlink, junction, or reparse point: $fullPath"
        }
        if ($MustNotExist) {
            throw "${Label} target already exists; refusing to overwrite: $fullPath"
        }
    }
}

function New-LocalOutputTempPath {
    param(
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $destinationFullPath = Get-FullPath $DestinationPath
    $parent = Split-Path -Parent $destinationFullPath
    $leaf = Split-Path -Leaf $destinationFullPath
    Initialize-LocalDirectory -Path $parent -Label "${Label} parent directory" | Out-Null

    for ($attempt = 0; $attempt -lt 100; $attempt++) {
        $candidate = Join-Path $parent ".${leaf}.$([System.Guid]::NewGuid().ToString("N")).tmp"
        try {
            $stream = [System.IO.File]::Open(
                $candidate,
                [System.IO.FileMode]::CreateNew,
                [System.IO.FileAccess]::Write,
                [System.IO.FileShare]::None
            )
            $stream.Close()
            return $candidate
        } catch [System.IO.IOException] {
            continue
        }
    }

    throw "Unable to create ${Label} temporary file beside: $destinationFullPath"
}

function Initialize-LocalDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $fullPath = Get-FullPath $Path
    if (Test-Path -LiteralPath $fullPath) {
        $item = Get-Item -LiteralPath $fullPath -Force
        if (-not $item.PSIsContainer) {
            throw "${Label} path exists but is not a directory: $fullPath"
        }
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "${Label} must not be a symlink, junction, or reparse point: $fullPath"
        }
    }
    New-Item -ItemType Directory -Force -Path $fullPath | Out-Null
    $created = Get-Item -LiteralPath $fullPath -Force
    if (($created.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "${Label} must not be a symlink, junction, or reparse point: $fullPath"
    }
    return $fullPath
}

function Assert-MacOSWorkflowInputs {
    Assert-ValidMacUser
    Assert-ValidMacHost
    Assert-SafeRemoteWorkflowPath -Label "MacWorkspace" -Value $MacWorkspace
    Assert-SafeRemoteWorkflowPath -Label "MacBasePath" -Value $MacBasePath
    if ($MacHome) {
        Assert-SafeRemoteGuestHomePath -Value $MacHome
    }
    Assert-SafeMacOSBuildDir -Value $BuildDir
    if ((ConvertTo-RemoteWorkflowComparisonPath -Value $MacWorkspace) -eq (ConvertTo-RemoteWorkflowComparisonPath -Value $MacBasePath)) {
        throw "MacBasePath must not be the same directory as MacWorkspace; asset installation uses rsync --delete."
    }
    Assert-MacBasePathNotReservedWorkspaceChild
    if ($IdentityFile) {
        Assert-LocalRegularFile -Path $IdentityFile -Label "IdentityFile"
    }
}

function Get-SshArgs {
    $args = @("-p", [string]$SshPort, "-o", "BatchMode=yes")
    if ($IdentityFile) {
        $args += @("-i", (Get-FullPath $IdentityFile))
    }
    return $args
}

function Get-ScpArgs {
    $args = @("-P", [string]$SshPort, "-o", "BatchMode=yes")
    if ($IdentityFile) {
        $args += @("-i", (Get-FullPath $IdentityFile))
    }
    return $args
}

function Invoke-MacSsh {
    param([Parameter(Mandatory = $true)][string]$Command)
    $target = "${MacUser}@${MacHost}"
    & ssh @(Get-SshArgs) $target $Command
    if ($LASTEXITCODE -ne 0) {
        throw "ssh failed with exit code ${LASTEXITCODE}: $Command"
    }
}

function Remove-RemoteTempRoot {
    if (-not $script:RemoteTempRoot) {
        return
    }

    $remoteTempRoot = $script:RemoteTempRoot
    $script:RemoteTempRoot = ""

    if ($remoteTempRoot -notmatch '\A/tmp/openq4-macos-[0-9a-fA-F]{32}\z') {
        Write-Warning "Refusing to remove unexpected macOS remote temp root: $remoteTempRoot"
        return
    }

    try {
        Invoke-MacSsh -Command "rm -rf $(Quote-Sh $remoteTempRoot)"
    } catch {
        Write-Warning "Failed to remove macOS remote temp root '$remoteTempRoot': $_"
    }
}

function Copy-ToMac {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$RemotePath
    )
    Assert-LocalRegularFile -Path $Source -Label "macOS copy source"
    $target = "${MacUser}@${MacHost}:$RemotePath"
    & scp @(Get-ScpArgs) $Source $target
    if ($LASTEXITCODE -ne 0) {
        throw "scp failed with exit code ${LASTEXITCODE}: $Source -> $RemotePath"
    }
}

function Copy-FromMac {
    param(
        [Parameter(Mandatory = $true)][string]$RemotePath,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $destinationFullPath = Get-FullPath $Destination
    Assert-LocalOutputFileTarget -Path $destinationFullPath -Label "macOS copy destination" -MustNotExist
    $temporaryDestination = New-LocalOutputTempPath -DestinationPath $destinationFullPath -Label "macOS copy destination"
    $target = "${MacUser}@${MacHost}:$RemotePath"
    $published = $false
    try {
        & scp @(Get-ScpArgs) $target $temporaryDestination
        if ($LASTEXITCODE -ne 0) {
            throw "scp failed with exit code ${LASTEXITCODE}: $RemotePath -> $destinationFullPath"
        }
        Assert-LocalRegularFile -Path $temporaryDestination -Label "macOS temporary copy destination"
        $temporaryItem = Get-Item -LiteralPath $temporaryDestination -Force
        if ($temporaryItem.Length -le 0) {
            throw "macOS temporary copy destination is empty after scp: $temporaryDestination"
        }
        Assert-LocalOutputFileTarget -Path $destinationFullPath -Label "macOS copy destination" -MustNotExist
        [System.IO.File]::Move($temporaryDestination, $destinationFullPath)
        $published = $true
    } finally {
        if (-not $published -and (Test-Path -LiteralPath $temporaryDestination)) {
            Remove-Item -LiteralPath $temporaryDestination -Force
        }
    }
}

function Assert-NoArchiveLinks {
    param([Parameter(Mandatory = $true)][string]$SourceDir)

    $sourceFullPath = Get-FullPath $SourceDir
    $badEntries = @()
    $sourceItem = Get-Item -LiteralPath $sourceFullPath -Force
    if (($sourceItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        $badEntries += $sourceItem.FullName
    }
    Get-ChildItem -LiteralPath $sourceFullPath -Recurse -Force | ForEach-Object {
        if (($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            $badEntries += $_.FullName
        }
    }

    if ($badEntries.Count -ne 0) {
        $sample = ($badEntries | Select-Object -First 10) -join "`n  - "
        throw "Refusing to archive symlink/junction/reparse-point entries from ${sourceFullPath}:`n  - $sample"
    }
}

function Assert-NoCaseInsensitiveArchiveCollisions {
    param([Parameter(Mandatory = $true)][string]$SourceDir)

    $sourceFullPath = Get-FullPath $SourceDir
    $seen = @{}
    Get-ChildItem -LiteralPath $sourceFullPath -Recurse -Force | ForEach-Object {
        $fullPath = $_.FullName
        $relative = $fullPath.Substring($sourceFullPath.Length).TrimStart('\', '/') -replace '\\', '/'
        if ($relative) {
            $key = $relative.Normalize([System.Text.NormalizationForm]::FormC).ToLowerInvariant()
            if ($seen.ContainsKey($key) -and $seen[$key] -ne $relative) {
                throw "Refusing to archive case-insensitive path collision from ${sourceFullPath}: $($seen[$key]) <-> $relative"
            }
            $seen[$key] = $relative
        }
    }
}

function Assert-NoMacOSMetadataEntries {
    param([Parameter(Mandatory = $true)][string]$SourceDir)

    $sourceFullPath = Get-FullPath $SourceDir
    $badEntries = @()
    Get-ChildItem -LiteralPath $sourceFullPath -Recurse -Force | ForEach-Object {
        $name = $_.Name
        if (
            $name -ieq ".DS_Store" -or
            $name -ieq "__MACOSX" -or
            $name -ieq ".fseventsd" -or
            $name -ieq ".Spotlight-V100" -or
            $name -ieq ".Trashes" -or
            $name -eq "Icon`r" -or
            $name.StartsWith("._", [System.StringComparison]::OrdinalIgnoreCase) -or
            $name.EndsWith(".dSYM", [System.StringComparison]::OrdinalIgnoreCase)
        ) {
            $badEntries += $_.FullName
        }
    }

    if ($badEntries.Count -ne 0) {
        $sample = ($badEntries | Select-Object -First 10) -join "`n  - "
        throw "Refusing to archive non-runtime macOS metadata/debug entries from ${sourceFullPath}:`n  - $sample"
    }
}

function New-TransferArchive {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDir,
        [Parameter(Mandatory = $true)][string]$ArchivePath,
        [string[]]$Exclude = @()
    )

    if (-not (Test-Path -LiteralPath $SourceDir)) {
        throw "Source directory was not found: $SourceDir"
    }
    if (-not (Test-Path -LiteralPath $SourceDir -PathType Container)) {
        throw "Source path was not a directory: $SourceDir"
    }
    Assert-NoArchiveLinks -SourceDir $SourceDir
    Assert-NoCaseInsensitiveArchiveCollisions -SourceDir $SourceDir
    Assert-NoMacOSMetadataEntries -SourceDir $SourceDir

    $archiveFullPath = Get-FullPath $ArchivePath
    $archiveParent = Split-Path -Parent $archiveFullPath
    Initialize-LocalDirectory -Path $archiveParent -Label "macOS transfer archive directory" | Out-Null
    Assert-LocalOutputFileTarget -Path $archiveFullPath -Label "macOS transfer archive"
    if (Test-Path -LiteralPath $archiveFullPath) {
        Remove-Item -LiteralPath $archiveFullPath -Force
    }

    $parent = Split-Path -Parent (Get-FullPath $SourceDir)
    $leaf = Split-Path -Leaf (Get-FullPath $SourceDir)
    $tarArgs = @("-C", $parent, "-cf", $archiveFullPath)
    foreach ($pattern in $Exclude) {
        $tarArgs += "--exclude=$pattern"
    }
    $tarArgs += $leaf

    & tar @tarArgs
    if ($LASTEXITCODE -ne 0) {
        throw "tar failed with exit code $LASTEXITCODE while archiving $SourceDir"
    }

    return $archiveFullPath
}

function Expand-RemoteArchive {
    param(
        [Parameter(Mandatory = $true)][string]$RemoteArchive,
        [Parameter(Mandatory = $true)][string]$RemoteTarget
    )

    $guestHomeQ = Quote-Sh $MacHome
$script = @"
set -euo pipefail

guest_home_raw=$guestHomeQ

require_remote_home() {
    local home_value="`$guest_home_raw"
    if [[ -z "`$home_value" ]]; then
        home_value="`${HOME:-}"
    fi
    if [[ -z "`$home_value" ]]; then
        echo "HOME must be set or MacHome must provide the macOS guest home directory." >&2
        exit 2
    fi
    if LC_ALL=C printf '%s' "`$home_value" | LC_ALL=C grep -q '[[:cntrl:]]'; then
        echo "MacHome/HOME must not contain control characters." >&2
        exit 2
    fi
    case "`$home_value" in
        /*)
            ;;
        *)
            echo "MacHome/HOME must be an absolute POSIX path: `$home_value" >&2
            exit 2
            ;;
    esac
    case "`$home_value" in
        "/"|"."|".."|*\\*|*//*|*/./*|*/../*|*/.|*/..)
            echo "MacHome/HOME must be a clean absolute POSIX path: `$home_value" >&2
            exit 2
            ;;
    esac
    if [[ ! -d "`$home_value" ]]; then
        echo "macOS guest home directory does not exist: `$home_value" >&2
        exit 2
    fi
    printf '%s\n' "`${home_value%/}"
}

REMOTE_HOME="`$(require_remote_home)"
export HOME="`$REMOTE_HOME"

expand_remote_path() {
    case "`$1" in
        "~")
            printf '%s\n' "`$REMOTE_HOME"
            ;;
        "~/"*)
            printf '%s/%s\n' "`$REMOTE_HOME" "`${1#~/}"
            ;;
        *)
            printf '%s\n' "`$1"
            ;;
    esac
}

require_regular_remote_archive() {
    local archive_path="`$1"
    if [[ -L "`$archive_path" || ! -f "`$archive_path" ]]; then
        echo "Remote archive must be a regular file, not a symlink or special path: `$archive_path" >&2
        exit 1
    fi
}

prepare_remote_extract_target() {
    local target_path="`$1"
    if [[ -z "`$target_path" || "`$target_path" == "/" || "`$target_path" == "`$REMOTE_HOME" ]]; then
        echo "Refusing unsafe remote extraction target: `$target_path" >&2
        exit 1
    fi
    if [[ -L "`$target_path" ]]; then
        echo "Remote extraction target must not be a symlink: `$target_path" >&2
        exit 1
    fi
    if [[ -e "`$target_path" && ! -d "`$target_path" ]]; then
        echo "Remote extraction target must be a directory: `$target_path" >&2
        exit 1
    fi
    mkdir -p "`$target_path"
    if [[ -L "`$target_path" || ! -d "`$target_path" ]]; then
        echo "Remote extraction target must be a real directory: `$target_path" >&2
        exit 1
    fi
}

require_single_archive_root() {
    local archive_path="`$1"
    local archive_roots archive_root_count
    archive_roots="`$(COPYFILE_DISABLE=1 tar -tf "`$archive_path" | awk -F/ 'NF && `$1 != "" {print `$1}' | sort -u)"
    archive_root_count="`$(printf '%s\n' "`$archive_roots" | sed '/^$/d' | wc -l | tr -d '[:space:]')"
    if [[ "`$archive_root_count" != "1" ]]; then
        echo "Archive must contain exactly one top-level source root before stripping components: `$archive_path" >&2
        printf '%s\n' "`$archive_roots" >&2
        exit 1
    fi
}

reject_unsafe_remote_archive_entries() {
    local tar_path="`$1"
    python3 - "`$tar_path" <<'PY'
import pathlib
import sys
import tarfile
import unicodedata

archive_path = pathlib.Path(sys.argv[1])
forbidden_metadata_names = {
    ".ds_store",
    "__macosx",
    ".fseventsd",
    ".spotlight-v100",
    ".trashes",
    "icon\r",
}
seen_entries = set()
seen_casefold_entries = {}
top_roots = set()


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def is_macos_metadata_path(parts):
    for part in parts:
        normalized = part.casefold()
        if normalized in forbidden_metadata_names:
            return True
        if normalized.startswith("._") or normalized.endswith(".dsym"):
            return True
    return False


try:
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive.getmembers():
            raw_entry = member.name
            entry = raw_entry.rstrip("/") if member.isdir() else raw_entry
            parts = entry.split("/")
            if (
                entry in {"", ".", ".."}
                or entry.startswith(("./", "/", "../"))
                or "\\" in entry
                or any(ord(character) < 32 or ord(character) == 127 for character in entry)
                or "/../" in f"/{entry}/"
                or "" in parts
                or any(part in {".", ".."} for part in parts)
            ):
                fail(f"Unsafe archive path: {entry!r}")
            if not (member.isfile() or member.isdir()):
                fail(f"Archive contains a symlink or special file (including hardlinks): {entry}")
            if is_macos_metadata_path(parts):
                fail(f"Archive contains non-runtime macOS metadata/debug entry: {entry}")
            if entry in seen_entries:
                fail(f"Archive contains duplicate member: {entry}")
            casefold_entry = unicodedata.normalize("NFC", entry).casefold()
            previous = seen_casefold_entries.get(casefold_entry)
            if previous is not None and previous != entry:
                fail(f"Archive contains case-insensitive path collision: {previous}, {entry}")
            seen_entries.add(entry)
            seen_casefold_entries[casefold_entry] = entry
            top_roots.add(parts[0])
        if len(top_roots) != 1:
            fail(f"Archive must contain exactly one top-level source root before stripping components: {archive_path}")
except tarfile.TarError as exc:
    fail(f"Unable to inspect remote archive: {archive_path}: {exc}")
PY
}

archive_raw=$(Quote-Sh $RemoteArchive)
target_raw=$(Quote-Sh $RemoteTarget)
archive="`$(expand_remote_path "`$archive_raw")"
target="`$(expand_remote_path "`$target_raw")"

require_regular_remote_archive "`$archive"
prepare_remote_extract_target "`$target"
tmp_dir="`$(mktemp -d /tmp/openq4-extract.XXXXXX)"
trap 'rm -rf "`$tmp_dir"' EXIT

reject_unsafe_remote_archive_entries "`$archive"

COPYFILE_DISABLE=1 tar -tf "`$archive" | while IFS= read -r entry; do
    case "`$entry" in
        ""|"."|".."|./*|*/./*|*//*|/*|../*|*/../*|*/..|*\\*)
            echo "Unsafe archive path: `$entry" >&2
            exit 1
            ;;
    esac
done

require_single_archive_root "`$archive"

COPYFILE_DISABLE=1 tar -tvf "`$archive" | while IFS= read -r listing; do
    entry_type="`${listing:0:1}"
    case "`$entry_type" in
        -|d)
            ;;
        *)
            echo "Archive contains a symlink or special file (including hardlinks): `$listing" >&2
            exit 1
            ;;
    esac
done

COPYFILE_DISABLE=1 tar -xf "`$archive" -C "`$tmp_dir" --strip-components 1
bad_entry="`$(find "`$tmp_dir" \( -type l -o \( ! -type f -a ! -type d \) \) -print -quit)"
if [[ -n "`$bad_entry" ]]; then
    echo "Archive contains a symlink or special file: `$bad_entry" >&2
    exit 1
fi

case_collision="`$(python3 - "`$tmp_dir" <<'PY'
import pathlib
import sys
import unicodedata

root = pathlib.Path(sys.argv[1])
seen = {}
for path in sorted(root.rglob("*")):
    rel = path.relative_to(root).as_posix()
    key = unicodedata.normalize("NFC", rel).casefold()
    previous = seen.get(key)
    if previous is not None and previous != rel:
        print(previous)
        print(rel)
        raise SystemExit(0)
    seen[key] = rel
PY
)"
if [[ -n "`$case_collision" ]]; then
    echo "Archive contains a case-insensitive path collision:" >&2
    printf '%s\n' "`$case_collision" >&2
    exit 1
fi

rsync -a --delete "`$tmp_dir/" "`$target/"
"@
    Invoke-MacSsh -Command "bash -lc $(Quote-Sh $script)"
}

function Copy-GuestScript {
    param([Parameter(Mandatory = $true)][string]$ScriptName)

    $localScript = Join-Path (Join-Path $PSScriptRoot "guest") $ScriptName
    if (-not (Test-Path -LiteralPath $localScript)) {
        throw "Guest script was not found: $localScript"
    }
    Assert-LocalRegularFile -Path $localScript -Label "Guest script"

    if (-not $script:RemoteTempRoot) {
        throw "Remote temporary root was not initialized."
    }

    Invoke-MacSsh -Command "umask 077 && mkdir -p $(Quote-Sh $script:RemoteTempRoot)"
    $remoteScript = "$script:RemoteTempRoot/$ScriptName"
    Copy-ToMac -Source $localScript -RemotePath $remoteScript
    Invoke-MacSsh -Command "chmod +x $(Quote-Sh $remoteScript)"
    return $remoteScript
}

function Invoke-GuestScript {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptName,
        [string]$ScriptAction = "",
        [hashtable]$Environment = @{}
    )

    $remoteScript = Copy-GuestScript -ScriptName $ScriptName
    $envParts = @(
        "OPENQ4_GUEST_WORKSPACE=$(Quote-Sh $MacWorkspace)",
        "OPENQ4_BASEPATH=$(Quote-Sh $MacBasePath)"
    )
    if ($MacHome) {
        $envParts += "OPENQ4_GUEST_HOME=$(Quote-Sh $MacHome)"
    }
    foreach ($key in $Environment.Keys) {
        $envParts += "$key=$(Quote-Sh ([string]$Environment[$key]))"
    }

    $cmd = (@("/usr/bin/env") + $envParts + @("bash", (Quote-Sh $remoteScript))) -join " "
    if ($ScriptAction) {
        $cmd += " $(Quote-Sh $ScriptAction)"
    }
    Invoke-MacSsh -Command $cmd
}

function Sync-SourceTrees {
    $transferRoot = Join-Path $TmpRoot "transfer"
    $transferRoot = Initialize-LocalDirectory -Path $transferRoot -Label "macOS transfer root"

    $repoArchive = New-TransferArchive `
        -SourceDir $repoRoot `
        -ArchivePath (Join-Path $transferRoot "openQ4.tar") `
        -Exclude @(
            "openQ4/.git",
            "openQ4/.claude",
            "openQ4/.codex",
            "openQ4/.home",
            "openQ4/.install",
            "openQ4/.tmp",
            "openQ4/.vscode",
            "openQ4/.voice_eng",
            "openQ4/builddir",
            "openQ4/builddir_*",
            "openQ4/builddir-*",
            "openQ4/tmp-game-libs"
        )

    $remoteRepoArchive = "$script:RemoteTempRoot/openQ4-source.tar"
    Copy-ToMac -Source $repoArchive -RemotePath $remoteRepoArchive
    Expand-RemoteArchive -RemoteArchive $remoteRepoArchive -RemoteTarget (Join-RemotePosixPath -Base $MacWorkspace -Child "openQ4")

}

function Install-Assets {
    if (-not (Test-Path -LiteralPath (Join-Path $HostQuake4Path "q4base"))) {
        throw "Quake 4 assets were not found at '$HostQuake4Path'. Expected q4base under that directory."
    }

    $transferRoot = Join-Path $TmpRoot "transfer"
    $transferRoot = Initialize-LocalDirectory -Path $transferRoot -Label "macOS transfer root"
    $assetRootName = Split-Path -Leaf (Get-FullPath $HostQuake4Path)
    $assetArchive = New-TransferArchive `
        -SourceDir $HostQuake4Path `
        -ArchivePath (Join-Path $transferRoot "Quake4-assets.tar") `
        -Exclude @(
            "$assetRootName/.tmp",
            "$assetRootName/CrashReports",
            "$assetRootName/q4base/generated",
            "$assetRootName/q4base/*.cfg",
            "$assetRootName/q4base/*.log",
            "$assetRootName/q4base/q4key",
            "$assetRootName/q4base/quake4key",
            "$assetRootName/q4base/savegames",
            "$assetRootName/q4base/screenshots",
            "$assetRootName/q4mp/*.cfg",
            "$assetRootName/q4mp/*.log",
            "$assetRootName/q4mp/screenshots"
        )

    $remoteAssetArchive = "$script:RemoteTempRoot/Quake4-assets.tar"
    Copy-ToMac -Source $assetArchive -RemotePath $remoteAssetArchive
    Invoke-GuestScript `
        -ScriptName "openq4-macos-install-quake4-assets.sh" `
        -Environment @{ "OPENQ4_Q4_TAR" = $remoteAssetArchive }
}

function Get-MacOSGraphicsBridgeRuns {
    if ($MacOSGraphicsBridge -eq "both") {
        return @("opengl", "metal")
    }
    return @($MacOSGraphicsBridge)
}

function Get-MacOSBridgeBuildDir {
    param([Parameter(Mandatory = $true)][string]$Bridge)

    if ($MacOSGraphicsBridge -ne "both") {
        return $BuildDir
    }
    return "${BuildDir}-${Bridge}"
}

function Invoke-BuildTestActionForBridge {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptAction,
        [Parameter(Mandatory = $true)][string]$Bridge,
        [hashtable]$ExtraEnvironment = @{}
    )

    $environment = @{
        "OPENQ4_MACOS_GRAPHICS_BRIDGE" = $Bridge
        "OPENQ4_MACOS_OPENAL_PROVIDER" = $MacOSOpenALProvider
        "OPENQ4_MACOS_OS_MATRIX_ROLE" = $MacOSOSMatrixRole
        "OPENQ4_MACOS_RUN_ID" = $MacOSRunId
        "OPENQ4_BUILDDIR" = (Get-MacOSBridgeBuildDir -Bridge $Bridge)
    }
    foreach ($key in $ExtraEnvironment.Keys) {
        $environment[$key] = $ExtraEnvironment[$key]
    }

    Invoke-GuestScript `
        -ScriptName "openq4-macos-sync-build-test.sh" `
        -ScriptAction $ScriptAction `
        -Environment $environment
}

function Assert-SingleMacOSGraphicsBridge {
    param([Parameter(Mandatory = $true)][string]$ActionName)

    if ($MacOSGraphicsBridge -eq "both") {
        throw "-MacOSGraphicsBridge both is supported for Build, Signoff, and All. Use Signoff for smoke/renderer/launcher evidence across both bridge variants."
    }
}

function Collect-MacOSResults {
    param([Parameter(Mandatory = $true)][string]$RunId)

    $archiveName = "openq4-macos-results-${RunId}.tar.gz"
    $remoteArchive = "$script:RemoteTempRoot/$archiveName"
    $workspaceQ = Quote-Sh $MacWorkspace
    $guestHomeQ = Quote-Sh $MacHome
    $runIdQ = Quote-Sh $RunId
    $archiveQ = Quote-Sh $remoteArchive
    $bridgesQ = ((Get-MacOSGraphicsBridgeRuns) | ForEach-Object { Quote-Sh $_ }) -join " "
$script = @'
set -euo pipefail

guest_home_raw=__GUEST_HOME__

require_remote_home() {
    local home_value="${guest_home_raw}"
    if [[ -z "${home_value}" ]]; then
        home_value="${HOME:-}"
    fi
    if [[ -z "${home_value}" ]]; then
        echo "HOME must be set or MacHome must provide the macOS guest home directory." >&2
        exit 2
    fi
    if LC_ALL=C printf '%s' "${home_value}" | LC_ALL=C grep -q '[[:cntrl:]]'; then
        echo "MacHome/HOME must not contain control characters." >&2
        exit 2
    fi
    case "${home_value}" in
        /*)
            ;;
        *)
            echo "MacHome/HOME must be an absolute POSIX path: ${home_value}" >&2
            exit 2
            ;;
    esac
    case "${home_value}" in
        "/"|"."|".."|*\\*|*//*|*/./*|*/../*|*/.|*/..)
            echo "MacHome/HOME must be a clean absolute POSIX path: ${home_value}" >&2
            exit 2
            ;;
    esac
    if [[ ! -d "${home_value}" ]]; then
        echo "macOS guest home directory does not exist: ${home_value}" >&2
        exit 2
    fi
    printf '%s\n' "${home_value%/}"
}

REMOTE_HOME="$(require_remote_home)"
export HOME="${REMOTE_HOME}"

expand_remote_path() {
    case "$1" in
        "~")
            printf '%s\n' "$REMOTE_HOME"
            ;;
        "~/"*)
            printf '%s/%s\n' "$REMOTE_HOME" "${1#~/}"
            ;;
        *)
            printf '%s\n' "$1"
            ;;
    esac
}

workspace_raw=__WORKSPACE__
workspace="$(expand_remote_path "${workspace_raw}")"
run_id=__RUN_ID__
archive=__ARCHIVE__
expected_bridges=(__BRIDGES__)
if [[ -z "${workspace}" || "${workspace}" == "/" || "${workspace}" == "${REMOTE_HOME}" || -L "${workspace}" || ! -d "${workspace}" ]]; then
    echo "Unsafe macOS workspace path for result collection: ${workspace}" >&2
    exit 1
fi
results_dir="${workspace%/}/results"
if [[ -L "${results_dir}" || ! -d "${results_dir}" ]]; then
    echo "No macOS results directory exists yet: ${results_dir}" >&2
    exit 1
fi
cd "${results_dir}"

reject_unsafe_result_tree() {
    local path="$1"
    local bad_entry
    bad_entry="$(find "${path}" \( -type l -o \( ! -type f -a ! -type d \) \) -print -quit)"
    if [[ -n "${bad_entry}" ]]; then
        echo "macOS signoff result directory contains a symlink or special file: ${results_dir}/${bad_entry}" >&2
        exit 1
    fi
    bad_entry="$(find "${path}" \( -iname '.DS_Store' -o -name '._*' -o -iname '__MACOSX' -o -iname '.fseventsd' -o -iname '.Spotlight-V100' -o -iname '.Trashes' -o -name $'Icon\r' -o -iname '*.dSYM' \) -print -quit)"
    if [[ -n "${bad_entry}" ]]; then
        echo "macOS signoff result directory contains non-runtime metadata/debug entry: ${results_dir}/${bad_entry}" >&2
        exit 1
    fi
}

require_result_file_under() {
    local path="$1"
    local relative_dir="$2"
    local dir="${path}/${relative_dir}"
    if [[ ! -d "${dir}" ]]; then
        echo "macOS signoff result directory is missing ${relative_dir}: ${results_dir}/${dir}" >&2
        exit 1
    fi
    if ! find "${dir}" -type f -print -quit | grep -q .; then
        echo "macOS signoff result directory has no file evidence under ${relative_dir}: ${results_dir}/${dir}" >&2
        exit 1
    fi
}

reject_result_case_collisions() {
    python3 - "$@" <<'PY'
import pathlib
import sys
import unicodedata

seen = {}
for selected_root in sys.argv[1:]:
    root = pathlib.Path(selected_root)
    for path in sorted(root.rglob("*")):
        rel = path.as_posix()
        key = unicodedata.normalize("NFC", rel).casefold()
        previous = seen.get(key)
        if previous is not None and previous != rel:
            print("macOS signoff result directories contain a case-insensitive path collision:", file=sys.stderr)
            print(previous, file=sys.stderr)
            print(rel, file=sys.stderr)
            raise SystemExit(1)
        seen[key] = rel
PY
}

matches=()
for bridge in "${expected_bridges[@]}"; do
    path="${run_id}-signoff-${bridge}"
    if [[ ! -d "${path}" ]]; then
        echo "No macOS result directories matched required signoff path: ${results_dir}/${path}" >&2
        exit 1
    fi
    reject_unsafe_result_tree "${path}"
    if [[ ! -s "${path}/macos-runtime-signoff.md" || ! -s "${path}/openq4-macos-workflow.log" ]]; then
        echo "macOS signoff result directory is incomplete: ${results_dir}/${path}" >&2
        exit 1
    fi
    require_result_file_under "${path}" "renderer-smoke"
    require_result_file_under "${path}" "renderer-mp-smoke"
    require_result_file_under "${path}" "renderer-matrix"
    matches+=("${path}")
done
if (( ${#matches[@]} == 0 )); then
    echo "No macOS result directories matched ${results_dir}/${run_id}-*" >&2
    exit 1
fi
reject_result_case_collisions "${matches[@]}"
archive_parent="${archive%/*}"
if [[ -z "${archive_parent}" || "${archive_parent}" == "${archive}" || -L "${archive_parent}" || ! -d "${archive_parent}" ]]; then
    echo "Unsafe macOS result archive directory: ${archive_parent}" >&2
    exit 1
fi
if [[ -e "${archive}" ]]; then
    if [[ -L "${archive}" || ! -f "${archive}" ]]; then
        echo "Unsafe macOS result archive target: ${archive}" >&2
    else
        echo "macOS result archive target already exists: ${archive}" >&2
    fi
    exit 1
fi
archive_tmp=""
cleanup_result_archive_tmp() {
    if [[ -n "${archive_tmp}" && -e "${archive_tmp}" ]]; then
        rm -f "${archive_tmp}"
    fi
}
trap cleanup_result_archive_tmp EXIT
archive_tmp="$(mktemp "${archive_parent}/.${archive##*/}.XXXXXX.tmp")"
COPYFILE_DISABLE=1 tar -czf "${archive_tmp}" -- "${matches[@]}"
if [[ ! -s "${archive_tmp}" ]]; then
    echo "macOS result archive is empty before publish: ${archive_tmp}" >&2
    exit 1
fi
if ! COPYFILE_DISABLE=1 tar -tzf "${archive_tmp}" >/dev/null; then
    echo "macOS result archive validation failed before publish: ${archive_tmp}" >&2
    exit 1
fi
ln "${archive_tmp}" "${archive}"
rm -f "${archive_tmp}"
archive_tmp=""
'@
    $script = $script.Replace("__GUEST_HOME__", $guestHomeQ).Replace("__WORKSPACE__", $workspaceQ).Replace("__RUN_ID__", $runIdQ).Replace("__ARCHIVE__", $archiveQ).Replace("__BRIDGES__", $bridgesQ)
    Invoke-MacSsh -Command "bash -lc $(Quote-Sh $script)"

    $localArchive = Join-Path $ResultCollectionDir $archiveName
    Copy-FromMac -RemotePath $remoteArchive -Destination $localArchive
    $localArchive = Get-FullPath $localArchive
    Write-Host "Collected macOS signoff results: $localArchive"
    return $localArchive
}

function Test-MacOSResultArchive {
    param(
        [Parameter(Mandatory = $true)][string]$ArchivePath,
        [Parameter(Mandatory = $true)][string]$RunId
    )

    $validator = Join-Path $repoRoot "tools\macos\validate_signoff_archive.py"
    if (-not (Test-Path -LiteralPath $validator)) {
        throw "macOS signoff archive validator was not found: $validator"
    }

    $bridgeList = $MacOSGraphicsBridge
    if ($MacOSGraphicsBridge -eq "both") {
        $bridgeList = "opengl,metal"
    }

    $python = $env:PYTHON
    if (-not $python) {
        $python = "python"
    }

    $args = @(
        $validator,
        $ArchivePath,
        "--run-id",
        $RunId,
        "--bridges",
        $bridgeList
    )
    if ($RequireCompletedSignoffChecklist) {
        $args += "--require-completed-checklist"
    }

    & $python @args
    if ($LASTEXITCODE -ne 0) {
        throw "macOS signoff archive validation failed for $ArchivePath"
    }
}

function Invoke-MacOSWorkflowMain {
    $repoRoot = Get-RepoRoot
    Assert-MacOSWorkflowInputs
    if (-not $TmpRoot) {
        $TmpRoot = Join-Path (Join-Path $repoRoot ".tmp") "macos-vm"
    }
    $TmpRoot = Initialize-LocalDirectory -Path $TmpRoot -Label "TmpRoot"
    if (-not $ResultCollectionDir) {
        $ResultCollectionDir = Join-Path $TmpRoot "results"
    }
    $ResultCollectionDir = Initialize-LocalDirectory -Path $ResultCollectionDir -Label "ResultCollectionDir"
    if (-not $MacOSRunId) {
        if ($Action -contains "CollectResults") {
            throw "-Action CollectResults requires -MacOSRunId <id> so the existing guest result directories can be selected."
        }
        $MacOSRunId = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
    }
    if ($MacOSRunId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
        throw "Invalid MacOSRunId '$MacOSRunId'. Use letters, digits, dots, underscores, or dashes, starting with a letter or digit."
    }
    if ($MacOSRunId.Length -gt $script:MacOSResultTokenMaxLength) {
        throw "Invalid MacOSRunId '$MacOSRunId'. Use at most $script:MacOSResultTokenMaxLength characters."
    }
    $script:RemoteTempRoot = "/tmp/openq4-macos-$([System.Guid]::NewGuid().ToString("N"))"
    Invoke-MacSsh -Command "umask 077 && mkdir -p $(Quote-Sh $script:RemoteTempRoot)"

    if (-not $HostGameLibsPath) {
        $HostGameLibsPath = $repoRoot
    }
    $HostGameLibsPath = Get-FullPath $HostGameLibsPath
    if ($HostGameLibsPath -ine $repoRoot) {
        throw "Game sources now travel with openQ4. HostGameLibsPath must name this checkout."
    }

    $shouldCollectResults = $false
    foreach ($item in $Action) {
        switch ($item) {
            "Probe" {
                Invoke-MacSsh -Command "uname -a && sw_vers && xcode-select -p 2>/dev/null || true && command -v brew 2>/dev/null || true"
            }
            "Bootstrap" {
                Invoke-GuestScript -ScriptName "openq4-macos-bootstrap.sh"
            }
            "Assets" {
                if (-not $SkipAssets) {
                    Install-Assets
                }
            }
            "Sync" {
                if (-not $SkipSync) {
                    Sync-SourceTrees
                }
            }
            "Build" {
                foreach ($bridge in (Get-MacOSGraphicsBridgeRuns)) {
                    Invoke-BuildTestActionForBridge `
                        -ScriptAction "build" `
                        -Bridge $bridge `
                        -ExtraEnvironment @{
                            "OPENQ4_BUILDTYPE" = $BuildType
                        }
                }
            }
            "Smoke" {
                Assert-SingleMacOSGraphicsBridge -ActionName "Smoke"
                Invoke-BuildTestActionForBridge `
                    -ScriptAction "smoke" `
                    -Bridge $MacOSGraphicsBridge `
                    -ExtraEnvironment @{ "OPENQ4_SMOKE_LIMIT" = [string]$SmokeLimit }
            }
            "Renderer" {
                Assert-SingleMacOSGraphicsBridge -ActionName "Renderer"
                Invoke-BuildTestActionForBridge `
                    -ScriptAction "renderer" `
                    -Bridge $MacOSGraphicsBridge
            }
            "Launcher" {
                Assert-SingleMacOSGraphicsBridge -ActionName "Launcher"
                Invoke-BuildTestActionForBridge `
                    -ScriptAction "launcher" `
                    -Bridge $MacOSGraphicsBridge
            }
            "Signoff" {
                foreach ($bridge in (Get-MacOSGraphicsBridgeRuns)) {
                    Invoke-BuildTestActionForBridge `
                        -ScriptAction "signoff" `
                        -Bridge $bridge `
                        -ExtraEnvironment @{
                            "OPENQ4_BUILDTYPE" = $BuildType
                            "OPENQ4_SMOKE_LIMIT" = [string]$SmokeLimit
                        }
                }
                $shouldCollectResults = $true
            }
            "CollectResults" {
                $shouldCollectResults = $true
            }
            "All" {
                Invoke-GuestScript -ScriptName "openq4-macos-bootstrap.sh"
                if (-not $SkipAssets) {
                    Install-Assets
                }
                if (-not $SkipSync) {
                    Sync-SourceTrees
                }
                foreach ($bridge in (Get-MacOSGraphicsBridgeRuns)) {
                    Invoke-BuildTestActionForBridge `
                        -ScriptAction "signoff" `
                        -Bridge $bridge `
                        -ExtraEnvironment @{
                            "OPENQ4_BUILDTYPE" = $BuildType
                            "OPENQ4_SMOKE_LIMIT" = [string]$SmokeLimit
                        }
                }
                $shouldCollectResults = $true
            }
        }
    }

    if ($shouldCollectResults) {
        if ($SkipResultCollection) {
            Write-Host "Skipping macOS result collection for run ID '${MacOSRunId}'."
        } else {
            $archivePath = Collect-MacOSResults -RunId $MacOSRunId
            if ($SkipResultArchiveValidation) {
                Write-Host "Skipping macOS signoff archive validation for $archivePath"
            } else {
                Test-MacOSResultArchive -ArchivePath $archivePath -RunId $MacOSRunId
            }
        }
    }
}

try {
    Invoke-MacOSWorkflowMain
} finally {
    Remove-RemoteTempRoot
}
