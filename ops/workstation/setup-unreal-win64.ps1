[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$RequiredEngineVersion,
 [string]$EngineRoot, [string]$EngineInstaller, [string]$BuildToolsInstaller,
 [switch]$InstallMissing,
 [string]$WorkRoot=(Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'Biella\Win64Build')
)
$ErrorActionPreference='Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Execute on Windows, not Linux.' }
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$WorkRoot=(Resolve-Path -LiteralPath $WorkRoot).Path
$report=[ordered]@{schema='biella.win64_build_setup/v1';observed_utc=[DateTime]::UtcNow.ToString('o');machine=[Environment]::MachineName;required_engine_version=$RequiredEngineVersion;work_root=$WorkRoot;status='INCOMPLETE';game_runtime_verified = $false;compiler_probe=@{status='NOT_RUN';scope='TOOLCHAIN_PROBE_NOT_GAME'};engine=$null;sdk_validated=$false;actions=@();missing=@();errors=@();script_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()}
function Invoke-Batch([string]$Name,[string[]]$Lines) {
 $batch=Join-Path $WorkRoot ($Name+'.cmd')
 [IO.File]::WriteAllLines($batch,@('@echo off')+$Lines,[Text.Encoding]::ASCII)
 $out=Join-Path $WorkRoot ($Name+'.stdout.log');$err=Join-Path $WorkRoot ($Name+'.stderr.log')
 $cmd=Join-Path ([Environment]::GetFolderPath('System')) 'cmd.exe'
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
 return @{exit_code=$p.ExitCode;stdout=$out;stderr=$err;text=([IO.File]::ReadAllText($out)+[IO.File]::ReadAllText($err))}
}
function Get-CppInstall {
 $path=Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Microsoft Visual Studio\Installer\vswhere.exe'
 if (!(Test-Path -LiteralPath $path)) { return $null }
 $raw=& $path -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json
 if ($LASTEXITCODE -ne 0) { throw 'vswhere query failed.' }
 return @($raw | ConvertFrom-Json) | Select-Object -First 1
}
try {
 $report.volumes=@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace)
 $report.graphics=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion)
 $vs=Get-CppInstall
 if (!$vs -and $InstallMissing -and $BuildToolsInstaller) {
  $installer=(Resolve-Path -LiteralPath $BuildToolsInstaller).Path
  $p=Start-Process -FilePath $installer -ArgumentList '--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended' -Wait -PassThru
  $report.actions+=@{operation='install_missing_cpp_tools';exit_code=$p.ExitCode;installer=$installer}
  if ($p.ExitCode -notin @(0,3010)) { throw "C++ installer returned $($p.ExitCode)." }
  $vs=Get-CppInstall
 }
 if (!$vs) { $report.missing+='CPP_TOOLCHAIN_NOT_FOUND' }
 else {
  $report.visual_studio=@{path=$vs.installationPath;version=$vs.installationVersion}
  $devcmd=Join-Path $vs.installationPath 'Common7\Tools\VsDevCmd.bat'
  $cpp=Join-Path $WorkRoot 'compiler-probe.cpp';$exe=Join-Path $WorkRoot 'compiler-probe.exe';$obj=Join-Path $WorkRoot 'compiler-probe.obj'
  [IO.File]::WriteAllText($cpp,(@('#include <windows.h>','#include <stdio.h>','int main(){printf("BIELLA_WIN64_TOOLCHAIN_OK %lu\n", (unsigned long)GetCurrentProcessId());return 0;}') -join "`r`n"))
  $run=Invoke-Batch 'compiler-probe' @(('call "'+$devcmd+'" -no_logo -arch=amd64 -host_arch=amd64'),'if errorlevel 1 exit /b %errorlevel%',('cl.exe /nologo /O1 /MT "'+$cpp+'" /Fe:"'+$exe+'" /Fo:"'+$obj+'"'),'if errorlevel 1 exit /b %errorlevel%',('"'+$exe+'"'),'exit /b %errorlevel%')
  $report.compiler_probe=@{status='FAIL';scope='TOOLCHAIN_PROBE_NOT_GAME';exit_code=$run.exit_code;stdout=$run.stdout;stderr=$run.stderr}
  if ($run.exit_code -eq 0 -and $run.text -match 'BIELLA_WIN64_TOOLCHAIN_OK' -and (Test-Path -LiteralPath $exe)) {
   $report.compiler_probe.status='PASS';$report.compiler_probe.sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
  } else { $report.missing+='CPP_COMPILE_LINK_EXECUTION_FAILED' }
 }
 if (!$EngineRoot) {
  $candidates=@()
  foreach ($base in @([Environment]::GetFolderPath('ProgramFiles'),[Environment]::GetFolderPath('ProgramFilesX86'))) {
   $epic=Join-Path $base 'Epic Games'
   if (Test-Path -LiteralPath $epic) { $candidates+=@(Get-ChildItem -LiteralPath $epic -Directory | Select-Object -ExpandProperty FullName) }
  }
  $key='HKCU:\Software\Epic Games\Unreal Engine\Builds'
  if (Test-Path $key) { $candidates+=@((Get-ItemProperty $key).PSObject.Properties | Where-Object {$_.Name -notmatch '^PS'} | ForEach-Object {$_.Value}) }
  foreach ($candidate in $candidates) {
   $vfile=Join-Path $candidate 'Engine\Build\Build.version'
   if (Test-Path -LiteralPath $vfile) {
    $v=Get-Content -LiteralPath $vfile -Raw | ConvertFrom-Json
    if ("$($v.MajorVersion).$($v.MinorVersion).$($v.PatchVersion)" -eq $RequiredEngineVersion) { $EngineRoot=$candidate;break }
   }
  }
  $report.engine_discovery_scope='ProgramFiles Epic Games directories and current-user Unreal build registrations; other custom locations remain unknown.'
 }
 if ($InstallMissing -and $EngineInstaller -and (!$EngineRoot -or !(Test-Path -LiteralPath (Join-Path $EngineRoot 'Engine\Build\Build.version')))) {
  if (!$EngineRoot) { throw 'EngineRoot is required with an authorized Unreal MSI; no install path is invented.' }
  $msi=(Resolve-Path -LiteralPath $EngineInstaller).Path
  if ([IO.Path]::GetExtension($msi) -ne '.msi') { throw 'EngineInstaller must be an authorized Unreal MSI, not Linux binaries or a launcher.' }
  $msiexec=Join-Path ([Environment]::GetFolderPath('System')) 'msiexec.exe';$log=Join-Path $WorkRoot 'engine-install.log'
  $arg='/i "'+$msi+'" /qn /norestart /L*v "'+$log+'" INSTALLLOCATION="'+$EngineRoot+'" INSTALL_CREATE_SHORTCUT=0 ENGINE_STARTER_CHECKED=0 ENGINE_TEMPLATES_CHECKED=0'
  $p=Start-Process -FilePath $msiexec -ArgumentList $arg -Wait -PassThru
  $report.actions+=@{operation='install_missing_unreal';installer=$msi;exit_code=$p.ExitCode;log=$log}
  if ($p.ExitCode -notin @(0,3010)) { throw "Unreal MSI returned $($p.ExitCode)." }
 }
 if (!$EngineRoot -or !(Test-Path -LiteralPath (Join-Path $EngineRoot 'Engine\Build\Build.version'))) { $report.missing+='UNREAL_NOT_FOUND' }
 else {
  $EngineRoot=(Resolve-Path -LiteralPath $EngineRoot).Path;$versionPath=Join-Path $EngineRoot 'Engine\Build\Build.version'
  $v=Get-Content -LiteralPath $versionPath -Raw | ConvertFrom-Json;$version="$($v.MajorVersion).$($v.MinorVersion).$($v.PatchVersion)"
  $report.engine=@{root=$EngineRoot;version=$version;version_sha256=(Get-FileHash -LiteralPath $versionPath -Algorithm SHA256).Hash.ToLowerInvariant()}
  if ($version -ne $RequiredEngineVersion) { $report.missing+='ENGINE_VERSION_MISMATCH' }
  else {
   $build=Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
   if (!(Test-Path -LiteralPath $build) -or !(Test-Path -LiteralPath (Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'))) { $report.missing+='UNREAL_WINDOWS_BINARIES_MISSING' }
   else {
    $run=Invoke-Batch 'unreal-sdk-validation' @(('call "'+$build+'" -Mode=ValidatePlatforms -Platforms=Win64 -OutputSDKs'),'exit /b %errorlevel%')
    $report.sdk=@{exit_code=$run.exit_code;stdout=$run.stdout;stderr=$run.stderr}
    # UBT may return zero while declaring the platform INVALID.
    $report.sdk_validated=($run.exit_code -eq 0 -and $run.text -match '##PlatformValidate:\s*Win64 VALID\b' -and $run.text -notmatch '##PlatformValidate:\s*Win64 INVALID\b')
    if (!$report.sdk_validated) { $report.missing+='UNREAL_WIN64_SDK_NOT_VALIDATED' }
   }
  }
 }
 if ($report.compiler_probe.status -eq 'PASS' -and $report.sdk_validated -and $report.missing.Count -eq 0) { $report.status='TOOLCHAIN_VALIDATED_NOT_GAME_QUALIFIED' }
} catch { $report.errors+=@($_.Exception.Message) }
[IO.File]::WriteAllText((Join-Path $WorkRoot 'setup-result.json'),($report | ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($false)))
$report | ConvertTo-Json -Depth 12
if ($report.status -ne 'TOOLCHAIN_VALIDATED_NOT_GAME_QUALIFIED') { exit 2 }
