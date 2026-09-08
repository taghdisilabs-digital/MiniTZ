# Native NSIS lifecycle test only; these are not Unreal/game payloads.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$FixtureDirectory)
$ErrorActionPreference = 'Stop'
$scope = 'INSTALLER_TEST_FIXTURE_NOT_GAME'
$root = [IO.Path]::GetFullPath($FixtureDirectory)
$planPath = Join-Path $root 'native-plan.json'
$reportPath = Join-Path $root 'native-validation.json'
if (Test-Path -LiteralPath $reportPath) { throw 'Preserve existing native evidence; use a fresh fixture directory.' }
$report = [ordered]@{schema='biella.d08.nsis_native_fixture/v1';task_id='D08-01';scope=$scope;result='FAIL';release_candidate=$false;game_runtime_verified=$false;observed_utc=[DateTime]::UtcNow.ToString('o');machine=[Environment]::MachineName;cases=@();invocations=@()}
function Require([bool]$condition,[string]$message) { if (!$condition) { throw $message } }
function Hash([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Record([string]$name) { $report.cases += @{case=$name;result='PASS'} }
function RunInstaller([string]$path,[int]$expected) {
    $sha = Hash $path
    $p = Start-Process -FilePath $path -ArgumentList '/S' -Wait -PassThru
    $report.invocations += @{path=$path;sha256=$sha;exit_code=$p.ExitCode;pid=$p.Id}
    Require ($p.ExitCode -eq $expected) "Installer exit code $($p.ExitCode); expected $expected"
}
function VerifyPayload($fixture,[string]$directory) {
    $payload = Join-Path $directory 'payload'
    $actual = @(Get-ChildItem -LiteralPath $payload -Recurse -File)
    Require ($actual.Count -eq $fixture.files.Count) 'Native payload membership differs'
    foreach ($row in $fixture.files) {
        $path = Join-Path $payload $row.path.Replace('/','\')
        Require ((Get-Item -LiteralPath $path).Length -eq $row.bytes -and (Hash $path) -eq $row.sha256) "Native payload differs: $($row.path)"
    }
    Require ((Hash (Join-Path $directory 'manifest.json')) -eq $fixture.manifest_sha256) 'Installed manifest differs'
}
try {
    Require ([Environment]::OSVersion.Platform -eq 'Win32NT') 'Native Windows runtime required; Linux is not a native installer test'
    $plan = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
    Require ($plan.scope -eq $scope -and $plan.fixtures.Count -eq 2) 'Only explicit installer fixtures may be tested'
    Require ((Hash $PSCommandPath) -eq $plan.script.sha256) 'Native fixture script differs from the prepared plan'
    $report.plan_sha256 = Hash $planPath
    $report.script_sha256 = Hash $PSCommandPath
    $report.fixtures = $plan.fixtures
    $base = Join-Path $env:LOCALAPPDATA 'BiellaGames-D08-InstallerFixture'
    $report.install_base = $base
    foreach ($fixture in $plan.fixtures) {
        Require ($fixture.fixture_id -cmatch '^[0-9a-f]{64}$') 'Invalid fixture identity'
        Require ($fixture.archive_name -cmatch '^BiellaGames-D08-TEST_FIXTURE-[0-9a-f]{12}-setup\.exe$') 'Not an installer fixture'
        Require ((Hash (Join-Path $root $fixture.archive_name)) -eq $fixture.archive_sha256) 'Remote installer readback differs'
        Require (!(Test-Path -LiteralPath (Join-Path $base $fixture.fixture_id))) 'Do not overwrite a previous fixture installation'
    }
    $state = Join-Path $root 'fixture-user-state'
    Require (!(Test-Path -LiteralPath $state)) 'Fixture state must be fresh; never use real player state'
    New-Item -ItemType Directory -Path $state | Out-Null
    $sentinel = Join-Path $state 'GameUserSettings.ini'
    [IO.File]::WriteAllText($sentinel, "[$scope]`r`nSensitivity=1.37`r`n")
    $stateBefore = Hash $sentinel
    $a = $plan.fixtures[0]; $b = $plan.fixtures[1]
    $dirA = Join-Path $base $a.fixture_id; $dirB = Join-Path $base $b.fixture_id
    $installerA = Join-Path $root $a.archive_name; $installerB = Join-Path $root $b.archive_name
    RunInstaller $installerA 0
    VerifyPayload $a $dirA
    Record 'native_first_install_exact_readback'
    $text = & (Join-Path $dirA 'payload\fixture.exe')
    Require ($LASTEXITCODE -eq 0 -and $text -eq 'BIELLA_D08_INSTALLER_TEST_FIXTURE_NOT_GAME') 'Native x64 fixture execution failed'
    Record 'native_x64_fixture_execution_NOT_GAME'
    RunInstaller $installerA 2
    VerifyPayload $a $dirA
    Record 'existing_version_rejected_without_changes'
    RunInstaller $installerB 0
    VerifyPayload $b $dirB
    VerifyPayload $a $dirA
    Record 'second_version_side_by_side_old_bytes_retained_NOT_GAME_UPDATE_COMPATIBILITY'
    $text = & (Join-Path $dirB 'payload\fixture.exe')
    Require ($LASTEXITCODE -eq 0 -and $text -eq 'BIELLA_D08_INSTALLER_TEST_FIXTURE_NOT_GAME') 'Second native fixture execution failed'
    Record 'second_native_fixture_execution'
    $unowned = Join-Path $dirA 'payload\user-added.txt'
    [IO.File]::WriteAllText($unowned, 'Unowned fixture sentinel; retain on uninstall.')
    $unownedBefore = Hash $unowned
    RunInstaller (Join-Path $dirA 'uninstall.exe') 0
    Require ((Hash $unowned) -eq $unownedBefore) 'Uninstaller removed an unowned file'
    foreach ($row in $a.files) { Require (!(Test-Path -LiteralPath (Join-Path (Join-Path $dirA 'payload') $row.path.Replace('/','\')))) 'Uninstaller left an owned payload member' }
    VerifyPayload $b $dirB
    Record 'uninstall_first_version_retains_unowned_file_and_second_version'
    RunInstaller (Join-Path $dirB 'uninstall.exe') 0
    Require (!(Test-Path -LiteralPath $dirB)) 'Second version did not uninstall fully'
    Require ((Hash $sentinel) -eq $stateBefore) 'External fixture state changed'
    Record 'uninstall_second_version_retains_external_fixture_state_NOT_UE_SAVE_MIGRATION'
    $report.state_sentinel = @{path=$sentinel;before_sha256=$stateBefore;after_sha256=(Hash $sentinel)}
    $report.result = 'PASS'
} catch {
    $report.error = $_.Exception.Message
} finally {
    [IO.File]::WriteAllText($reportPath, ($report | ConvertTo-Json -Depth 12), (New-Object Text.UTF8Encoding($false)))
}
$report | ConvertTo-Json -Depth 12
if ($report.result -ne 'PASS') { exit 1 }
