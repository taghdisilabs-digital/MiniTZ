# Platform-neutral source-transfer verification. This does not build or run Unreal.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BundleDirectory,
    [Parameter(Mandatory=$true)][string]$ManifestSha256,
    [Parameter(Mandatory=$true)][string]$Output,
    [string]$RequiredEngineVersion='5.8.2'
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($BundleDirectory)
$outputPath = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $outputPath) { throw 'Preserve previous evidence; use a new output file.' }
$report = [ordered]@{schema='biella.d08.source_transfer_check/v1';task_id='D08-01';result='FAIL';scope='SOURCE_TRANSFER_ONLY';release_candidate=$false;native_win64_build_verified=$false;observed_utc=[DateTime]::UtcNow.ToString('o');platform=[Environment]::OSVersion.Platform.ToString();powershell_version=$PSVersionTable.PSVersion.ToString();bundle_directory=$root}
function Require([bool]$condition,[string]$message) { if (!$condition) { throw $message } }
function Hash([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
try {
    $prefix = $root.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    Require (!$outputPath.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) 'Write verification evidence outside the source bundle'
    Require ($ManifestSha256 -cmatch '^[0-9a-f]{64}$') 'Expected exact manifest SHA256 required'
    $manifestPath = Join-Path $root 'handoff-manifest.json'
    Require ((Hash $manifestPath) -ceq $ManifestSha256) 'Source transfer manifest digest differs'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    Require ($manifest.schema -eq 'biella.d08.source_transfer/v1' -and $manifest.scope -eq 'SOURCE_TRANSFER_ONLY') 'Unsupported source transfer manifest'
    Require ($manifest.required_engine_version -ceq $RequiredEngineVersion) 'Incompatible required engine version'
    Require ($manifest.files.Count -gt 0) 'Empty source transfer'
    $expected = @{}
    foreach ($row in $manifest.files) {
        $name = [string]$row.path
        Require ($name -cmatch '^(project|tooling)/[^\\:]+$' -or $name -ceq 'source-build-manifest.json') 'Unexpected transfer path'
        Require ($name -notmatch '(^|/)\.\.?(/|$)|//|[\x00-\x1f<>"|?*]' -and $name -notmatch '(^|/)[^/]*[ .](/|$)') 'Noncanonical source transfer path'
        Require (!$expected.ContainsKey($name)) 'Duplicate or case-colliding source member'
        Require ($row.sha256 -cmatch '^[0-9a-f]{64}$' -and $row.bytes -ge 0) 'Invalid source member identity'
        $expected[$name] = $row
    }
    Require (!(Get-Item -LiteralPath $root).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) 'Source root is a reparse point'
    $items = @(Get-ChildItem -LiteralPath $root -Recurse -Force)
    foreach ($item in $items) { Require (!$item.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) 'Source transfer contains a reparse point' }
    $actual = @($items | Where-Object { !$_.PSIsContainer })
    Require ($actual.Count -eq ($expected.Count + 1)) 'Source transfer file membership differs'
    foreach ($file in $actual) {
        $relative = $file.FullName.Substring($prefix.Length).Replace('\','/')
        if ($relative -ceq 'handoff-manifest.json') { continue }
        Require ($expected.ContainsKey($relative) -and $expected[$relative].path -ceq $relative) 'Unexpected source transfer member or path casing'
        $row = $expected[$relative]
        Require ($file.Length -eq $row.bytes -and (Hash $file.FullName) -ceq $row.sha256) "Source transfer bytes differ: $relative"
    }
    $source = Get-Content -LiteralPath (Join-Path $root 'source-build-manifest.json') -Raw | ConvertFrom-Json
    Require ($source.material_input_digest -ceq $manifest.material_input_digest) 'Source material identity differs'
    $projectRows = @($manifest.files | Where-Object { $_.path.StartsWith('project/') })
    Require ($projectRows.Count -eq $source.material_inputs.Count) 'Project material membership differs'
    foreach ($row in $source.material_inputs) {
        $entry = $expected['project/' + $row.path]
        Require ($null -ne $entry -and $entry.sha256 -ceq $row.sha256 -and $entry.bytes -eq $row.bytes) 'Project material differs from retained source manifest'
    }
    foreach ($name in @('Binaries','Intermediate','Saved','DerivedDataCache')) {
        Require (!(Test-Path -LiteralPath (Join-Path $root ('project/' + $name)))) 'Build output, player state or cache is present in the clean source input'
    }
    $report.manifest_sha256 = Hash $manifestPath
    $report.material_input_digest = $manifest.material_input_digest
    $report.project_files = $projectRows.Count
    $report.verified_files = $expected.Count
    $report.verified_bytes = ($manifest.files | Measure-Object -Property bytes -Sum).Sum
    $report.project_file = Join-Path $root 'project/BiellaGames.uproject'
    $report.result = 'PASS'
} catch {
    $report.error = $_.Exception.Message
} finally {
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($outputPath)) | Out-Null
    [IO.File]::WriteAllText($outputPath,($report | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
}
$report | ConvertTo-Json -Depth 8
if ($report.result -ne 'PASS') { exit 1 }
