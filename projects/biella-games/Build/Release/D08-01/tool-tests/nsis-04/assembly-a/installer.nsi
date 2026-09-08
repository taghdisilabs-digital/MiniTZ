Unicode true
RequestExecutionLevel user
CRCCheck force
SetCompressor /SOLID lzma
Name "Biella Games D08-TEST_FIXTURE"
OutFile "/root/biella/artifacts/games/D08-01/BiellaGames-D08-TEST_FIXTURE-9b4631d636f9-setup.exe"
ShowInstDetails show
ShowUninstDetails show
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles
Var Mutex
Function .onInit
  System::Call 'kernel32::CreateMutexW(p 0, i 0, w "Local\BiellaD08-9b4631d636f9da90e8d2f8db5128e5d66509536dc2c29d49d1e5a9e0703c4c5a") p .r1 ?e'
  Pop $0
  StrCpy $Mutex $1
  StrCmp $0 183 mutex_failed
  StrCmp $Mutex 0 mutex_failed mutex_ready
mutex_failed:
  SetErrorLevel 2
  Quit
mutex_ready:
  StrCpy $INSTDIR "$LOCALAPPDATA\BiellaGames-D08-InstallerFixture\9b4631d636f9da90e8d2f8db5128e5d66509536dc2c29d49d1e5a9e0703c4c5a"
FunctionEnd
Section "Install"
  IfFileExists "$INSTDIR" exists fresh
exists:
  DetailPrint "Existing version retained; uninstall it explicitly before reinstalling."
  SetErrorLevel 2
  Quit
fresh:
  SetOverwrite off
  SetOutPath "$INSTDIR\payload"
  IfErrors failed
  File "/oname=fixture.exe" "/root/biella/repos/biella-engine/projects/biella-games/Build/Release/D08-01/tool-tests/nsis-04/fixture-a/payload/fixture.exe"
  IfErrors failed
  SetOutPath "$INSTDIR\payload\nested $$ test"
  IfErrors failed
  File "/oname=résumé $$.txt" "/root/biella/repos/biella-engine/projects/biella-games/Build/Release/D08-01/tool-tests/nsis-04/fixture-a/payload/nested $ test/résumé $.txt"
  IfErrors failed
  SetOutPath "$INSTDIR"
  File /oname=manifest.json "/root/biella/repos/biella-engine/projects/biella-games/Build/Release/D08-01/tool-tests/nsis-04/fixture-a/manifest.json"
  IfErrors failed
  WriteUninstaller "$INSTDIR\uninstall.exe"
  IfErrors failed
  SetErrorLevel 0
  Goto done
failed:
  DetailPrint "Installation incomplete; this version is not ready to launch."
  SetErrorLevel 1
done:
SectionEnd
Section "Uninstall"
  Delete "$INSTDIR\payload\fixture.exe"
  Delete "$INSTDIR\payload\nested $$ test\résumé $$.txt"
  RMDir "$INSTDIR\payload\nested $$ test"
  RMDir "$INSTDIR\payload"
  Delete "$INSTDIR\manifest.json"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
  SetErrorLevel 0
SectionEnd
