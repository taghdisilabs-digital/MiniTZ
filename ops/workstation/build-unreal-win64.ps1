[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$EngineRoot,
 [Parameter(Mandatory=$true)][string]$ProjectFile,
 [Parameter(Mandatory=$true)][string]$ArchiveDirectory,
 [Parameter(Mandatory=$true)][string]$RequiredEngineVersion,
 [ValidateSet('Development','Shipping')][string]$Configuration='Development'
)
$ErrorActionPreference='Stop'
$EngineRoot=(Resolve-Path -LiteralPath $EngineRoot).Path
$ProjectFile=(Resolve-Path -LiteralPath $ProjectFile).Path
if ([IO.Path]::GetExtension($ProjectFile) -ne '.uproject') { throw 'ProjectFile must be an existing Unreal project.' }
if (Test-Path -LiteralPath $ArchiveDirectory) { throw 'Use a new task-scoped output directory; retain/reuse previous evidence rather than overwriting it.' }
New-Item -ItemType Directory -Path $ArchiveDirectory | Out-Null
$ArchiveDirectory=(Resolve-Path -LiteralPath $ArchiveDirectory).Path
$setup=Join-Path $PSScriptRoot 'setup-unreal-win64.ps1';$ps=Join-Path $PSHOME 'powershell.exe'
$args='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$setup+'" -RequiredEngineVersion "'+$RequiredEngineVersion+'" -EngineRoot "'+$EngineRoot+'" -WorkRoot "'+(Join-Path $ArchiveDirectory 'toolchain')+'"'
$probe=Start-Process -FilePath $ps -ArgumentList $args -Wait -PassThru -NoNewWindow
if ($probe.ExitCode -ne 0) { throw 'Read toolchain/setup-result.json; do not repeat an unchanged missing-resource attempt.' }
$receipt=Get-Content -LiteralPath (Join-Path $ArchiveDirectory 'toolchain\setup-result.json') -Raw | ConvertFrom-Json
# Setup requires an actual Win64 VALID marker, not merely process exit zero.
if (!$receipt.sdk_validated) { throw 'Win64 VALID was not observed.' }
$uat=Join-Path $EngineRoot 'Engine\Build\BatchFiles\RunUAT.bat'
if (!(Test-Path -LiteralPath $uat)) { throw 'RunUAT.bat is missing.' }
$batch=Join-Path $ArchiveDirectory 'build.cmd'
$line='call "'+$uat+'" BuildCookRun "-project='+$ProjectFile+'" -noP4 -unattended -platform=Win64 -clientconfig='+$Configuration+' -build -cook -stage -pak -iostore -archive "-archivedirectory='+(Join-Path $ArchiveDirectory 'payload')+'"'
[IO.File]::WriteAllLines($batch,@('@echo off',$line,'exit /b %errorlevel%'),[Text.Encoding]::ASCII)
$cmd=Join-Path ([Environment]::GetFolderPath('System')) 'cmd.exe'
$out=Join-Path $ArchiveDirectory 'uat.stdout.log';$err=Join-Path $ArchiveDirectory 'uat.stderr.log';$started=[DateTime]::UtcNow.ToString('o')
$info=New-Object Diagnostics.ProcessStartInfo
 $info.FileName=$cmd;$info.Arguments='/d /s /c ""'+$batch+'""'
 $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
 $p=New-Object Diagnostics.Process;$p.StartInfo=$info
 $outStream=[IO.File]::Create($out);$errStream=[IO.File]::Create($err)
 try {
  [void]$p.Start()
  $copyOut=$p.StandardOutput.BaseStream.CopyToAsync($outStream);$copyErr=$p.StandardError.BaseStream.CopyToAsync($errStream)
  $p.WaitForExit();$copyOut.GetAwaiter().GetResult();$copyErr.GetAwaiter().GetResult()
 } finally { $outStream.Dispose();$errStream.Dispose() }
$files=@();$payload=Join-Path $ArchiveDirectory 'payload'
if (Test-Path -LiteralPath $payload) {
 $files=@(Get-ChildItem -LiteralPath $payload -File -Recurse | ForEach-Object {@{path=$_.FullName;bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}})
}
$success=($p.ExitCode -eq 0 -and @($files | Where-Object {$_.path -match '\.exe$'}).Count -gt 0 -and @($files | Where-Object {$_.path -match '\.(pak|utoc|ucas)$'}).Count -gt 0)
$report=[ordered]@{schema='biella.win64_build/v1';started_utc=$started;finished_utc=[DateTime]::UtcNow.ToString('o');platform='Win64';configuration=$Configuration;engine=$receipt.engine;project=$ProjectFile;project_sha256=(Get-FileHash -LiteralPath $ProjectFile -Algorithm SHA256).Hash.ToLowerInvariant();command=$line;exit_code=$p.ExitCode;package_created=$success;game_runtime_verified = $false;files=$files;stdout=$out;stderr=$err}
[IO.File]::WriteAllText((Join-Path $ArchiveDirectory 'build-result.json'),($report | ConvertTo-Json -Depth 10),(New-Object Text.UTF8Encoding($false)))
if (!$success) { throw 'Build/package failed; logs and build-result.json retain the failure.' }
Write-Output 'Windows package created; target install/play/update qualification is still required.'
