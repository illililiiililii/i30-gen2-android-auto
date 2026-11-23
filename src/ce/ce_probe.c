#include "ce_wave.h"

/* Standalone query on a bench console/debugger. WAVE_FORMAT_QUERY acquires no stream. */
#ifdef _WIN32_WCE
int WINAPI WinMain(HINSTANCE instance, HINSTANCE previous, LPWSTR command, int show)
#else
int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, LPWSTR command, int show)
#endif
{
    MEMORYSTATUS ram;
    MMRESULT playback, capture;
    WCHAR message[240];

    UNREFERENCED_PARAMETER(instance);
    UNREFERENCED_PARAMETER(previous);
    UNREFERENCED_PARAMETER(command);
    UNREFERENCED_PARAMETER(show);
    ram.dwLength = sizeof(ram);
    GlobalMemoryStatus(&ram);
    playback = i30_playback_query(WAVE_MAPPER);
    capture = i30_capture_query(WAVE_MAPPER);
    wsprintfW(message, L"i30 CE: screen=%dx%d RAM=%lu free=%lu waveOut48k=%u waveIn16k=%u out=%u in=%u\r\n",
        GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN), (DWORD)ram.dwTotalPhys, (DWORD)ram.dwAvailPhys,
        playback, capture, waveOutGetNumDevs(), waveInGetNumDevs());
    OutputDebugStringW(message);
    return playback == MMSYSERR_NOERROR && capture == MMSYSERR_NOERROR ? 0 : 1;
}
