#include "ce_minimal.h"

typedef int32_t (*WindowProc)(CE_HANDLE, uint32_t, uintptr_t, intptr_t);

typedef struct WindowClass {
    unsigned style;
    WindowProc callback;
    int class_extra, window_extra;
    CE_HANDLE module, icon, cursor, background;
    const CE_WCHAR *menu, *name;
} WindowClass;

typedef struct ChildProcess {
    CE_HANDLE process, thread;
    uint32_t process_id, thread_id;
} ChildProcess;

CE_HANDLE GetModuleHandleW(const CE_WCHAR *);
uint16_t RegisterClassW(const WindowClass *);
CE_HANDLE CreateWindowExW(uint32_t, const CE_WCHAR *, const CE_WCHAR *, uint32_t, int, int, int, int,
                          CE_HANDLE, CE_HANDLE, CE_HANDLE, void *);
int32_t DefWindowProcW(CE_HANDLE, uint32_t, uintptr_t, intptr_t);
int SetForegroundWindow(CE_HANDLE);
CE_HANDLE GetForegroundWindow(void);
int ShowWindow(CE_HANDLE, int);
void Sleep(uint32_t);
int SetWindowPos(CE_HANDLE, CE_HANDLE, int, int, int, int, uint32_t);
int GetMessageW(void *, CE_HANDLE, unsigned, unsigned);
int DispatchMessageW(void *);
int CreateProcessW(const CE_WCHAR *, CE_WCHAR *, void *, void *, int, uint32_t, void *,
                   const CE_WCHAR *, void *, ChildProcess *);

#ifdef I30_TEST_WAVE_QUERY
typedef struct WaveFormat {
    uint16_t tag, channels;
    uint32_t rate, bytes_per_second;
    uint16_t block_align, bits, extra;
} WaveFormat;

uint32_t waveOutOpen(void *, unsigned, const WaveFormat *, uintptr_t, uintptr_t, unsigned);
uint32_t waveInOpen(void *, unsigned, const WaveFormat *, uintptr_t, uintptr_t, unsigned);
unsigned waveOutGetNumDevs(void);
unsigned waveInGetNumDevs(void);
uint32_t waveOutGetDevCaps(unsigned, void *, unsigned);
uint32_t waveInGetDevCaps(unsigned, void *, unsigned);

static void report_wave_result(const CE_WCHAR *label, uint32_t result)
{
    static const char digits[] = "0123456789abcdef";
    CE_WCHAR line[64];
    unsigned offset = 0;
    while (*label && offset < sizeof(line) / sizeof(line[0]) - 11U)
        line[offset++] = *label++;
    for (unsigned i = 0; i < 8; ++i) {
        line[offset + 7 - i] = digits[result & 15U];
        result >>= 4;
    }
    line[offset + 8] = '\r';
    line[offset + 9] = '\n';
    line[offset + 10] = 0;
    OutputDebugStringW(line);
}

static void report_wave_caps(const CE_WCHAR *label, const uint8_t *bytes, unsigned size)
{
    static const char digits[] = "0123456789abcdef";
    CE_WCHAR line[220];
    unsigned offset = 0;
    while (*label)
        line[offset++] = *label++;
    for (unsigned i = 0; i < size && offset < sizeof(line) / sizeof(line[0]) - 4U; ++i) {
        line[offset++] = digits[bytes[i] >> 4];
        line[offset++] = digits[bytes[i] & 15U];
    }
    line[offset++] = '\r';
    line[offset++] = '\n';
    line[offset] = 0;
    OutputDebugStringW(line);
}

static void probe_wave_formats(void)
{
    /* Same PCM formats as ce_wave.c. WAVE_FORMAT_QUERY does not open a stream. */
    const WaveFormat playback = {1, 2, 48000, 192000, 4, 16, 0};
    const WaveFormat capture = {1, 1, 16000, 32000, 2, 16, 0};
    uint32_t output[24] = {0}, input[24] = {0};
    report_wave_result(L"i30 WAVE devices OUT: ", waveOutGetNumDevs());
    report_wave_result(L"i30 WAVE devices IN: ", waveInGetNumDevs());
    uint32_t status = waveOutGetDevCaps(0, output, sizeof(output));
    report_wave_result(L"i30 WAVE caps OUT: ", status);
    if (!status)
        report_wave_caps(L"i30 WAVE data OUT: ", (const uint8_t *)output, sizeof(output));
    status = waveInGetDevCaps(0, input, sizeof(input));
    report_wave_result(L"i30 WAVE caps IN: ", status);
    if (!status)
        report_wave_caps(L"i30 WAVE data IN: ", (const uint8_t *)input, sizeof(input));
    report_wave_result(L"i30 WAVE query OUT: ", waveOutOpen(0, (unsigned)-1, &playback, 0, 0, 1));
    report_wave_result(L"i30 WAVE query IN: ", waveInOpen(0, (unsigned)-1, &capture, 0, 0, 1));
}
#endif

static int start_settings(CE_WCHAR *arguments, int wait)
{
    ChildProcess child;
    if (!CreateProcessW(L"\\DiskA\\Application\\NAVI\\i30aa.exe", arguments, 0, 0, 0, 0, 0, 0, 0, &child))
        return 0;
    CloseHandle(child.thread);
    int ready = !wait || WaitForSingleObject(child.process, 5000) == 0;
    CloseHandle(child.process);
    return ready;
}

void i30_ce_entry(void)
{
    CE_WCHAR clock[] = L"-i30clock";
#if defined(I30_TEST_OWNED_WINDOW)
    CE_WCHAR run[] = L"-i30run:00000000";
#else
    CE_WCHAR run[] = L"-i30run";
#endif
    OutputDebugStringW(L"i30 virtual phone probe started.\r\n");
    if (!start_settings(clock, 1)) {
        OutputDebugStringW(L"i30 virtual phone probe clock setup failed.\r\n");
        ExitThread(1);
    }
#ifdef I30_TEST_WAVE_QUERY
    probe_wave_formats();
#endif
#if defined(I30_TEST_OWNED_WINDOW)
    uintptr_t owner = (uintptr_t)GetForegroundWindow();
    if (!owner) {
        OutputDebugStringW(L"i30 virtual phone probe found no stock foreground owner.\r\n");
        ExitThread(5);
    }
    for (unsigned i = 0; i < 8; ++i) {
        unsigned digit = owner >> 28U;
        run[8 + i] = (CE_WCHAR)(digit < 10 ? '0' + digit : 'a' + digit - 10);
        owner <<= 4U;
    }
    if (!start_settings(run, 0)) {
        OutputDebugStringW(L"i30 virtual phone probe could not start the USB client.\r\n");
        ExitThread(4);
    }
#elif defined(I30_VIRTUAL_LCD_BENCH)
    if (!start_settings(run, 0)) {
        OutputDebugStringW(L"i30 virtual phone probe could not start the USB client.\r\n");
        ExitThread(4);
    }
#else
    static const CE_WCHAR name[] = L"I30.GD13MY.VideoSurface.1";
#ifdef I30_WAIT_FOR_CALIBRATION
    Sleep(20000);
#endif
    CE_HANDLE module = GetModuleHandleW(0);
    WindowClass window_class = { .callback = DefWindowProcW, .module = module, .name = name };
    if (!RegisterClassW(&window_class)) {
        OutputDebugStringW(L"i30 virtual phone probe window registration failed.\r\n");
        ExitThread(2);
    }
    CE_HANDLE window = CreateWindowExW(0, name, L"Android Auto USB test", 0x90000000U, 0, 0, 800, 480,
                                       0, 0, module, 0);
    if (!window) {
        OutputDebugStringW(L"i30 virtual phone probe window creation failed.\r\n");
        ExitThread(3);
    }
    ShowWindow(window, 5);
    SetWindowPos(window, (CE_HANDLE)-1, 0, 0, 800, 480, 0x0040U);
    SetForegroundWindow((CE_HANDLE)((uintptr_t)window | 1U));
    OutputDebugStringW(L"i30 virtual phone probe created the test window.\r\n");
    if (GetForegroundWindow() == window)
        OutputDebugStringW(L"i30 virtual phone probe acquired foreground.\r\n");
    if (!start_settings(run, 0)) {
        OutputDebugStringW(L"i30 virtual phone probe could not start the USB client.\r\n");
        ExitThread(4);
    }
    uint32_t message[10];
    while (GetMessageW(message, 0, 0, 0) > 0)
        DispatchMessageW(message);
#endif
    ExitThread(0);
}
