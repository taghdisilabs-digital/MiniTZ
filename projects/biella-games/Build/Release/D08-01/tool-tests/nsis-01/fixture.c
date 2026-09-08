// D08 installer-tool fixture only. No Unreal or game code.
typedef unsigned long DWORD;
__declspec(dllimport) void* __stdcall GetStdHandle(DWORD);
__declspec(dllimport) int __stdcall WriteFile(void*, const void*, DWORD, DWORD*, void*);
__declspec(dllimport) __declspec(noreturn) void __stdcall ExitProcess(unsigned);
void mainCRTStartup(void) {
    const char message[] = "BIELLA_D08_INSTALLER_TEST_FIXTURE_NOT_GAME\r\n";
    DWORD written = 0;
    int ok = WriteFile(GetStdHandle((DWORD)-11), message, sizeof(message)-1, &written, (void*)0);
    ExitProcess(ok && written == sizeof(message)-1 ? 0 : 1);
}
