#include "ce_aa_usb.h"
#include "ce_aa_usb_session.h"
#include "ce_aa_projection.h"
#include "ce_startup_pref.h"

#define WIDE_STRING_(text) L##text
#define WIDE_STRING(text) WIDE_STRING_(text)

int DeleteFileW(const CE_WCHAR *);
CE_HANDLE GetModuleHandleW(const CE_WCHAR *);
CE_HANDLE GetDlgItem(CE_HANDLE, int);
int32_t SendMessageW(CE_HANDLE, uint32_t, uint32_t, int32_t);
int SetWindowPos(CE_HANDLE, CE_HANDLE, int, int, int, int, uint32_t);
int EndDialog(CE_HANDLE, int);
int SetDlgItemTextW(CE_HANDLE, int, const CE_WCHAR *);
int UpdateWindow(CE_HANDLE);
CE_HANDLE GetForegroundWindow(void);
int32_t GetWindowLongW(CE_HANDLE, int);
int32_t SetWindowLongW(CE_HANDLE, int, int32_t);
uintptr_t SetTimer(CE_HANDLE, uintptr_t, unsigned, void *);
const CE_WCHAR *GetCommandLineW(void);
int SetSystemTime(const uint16_t *time);
typedef int (*DialogProc)(CE_HANDLE, uint32_t, uint32_t, int32_t);
int DialogBoxIndirectParamW(CE_HANDLE, const void *, CE_HANDLE, DialogProc, int32_t);

enum { WIN_WAIT_TIMEOUT = 258 };
static const CE_WCHAR autostart[] = WIDE_STRING(I30_USB_STARTUP_PREF);

/* Standard CE dialog template. */
enum { USB_TEST = 1002, AUTO_CHECK = 1003, STATUS = 1004, SAVE = 1, CANCEL = 2 };
#define SETTINGS_TITLE L"AARE 설정"
#define STARTUP_LABEL L"부팅 후 AARE USB 감지"
#define STATUS_LABEL L"처음 한 번 휴대폰에서 USB 접근과 수신기 인증서를 승인하세요."
#define CONTROL_TEMPLATE(caption) struct __attribute__((packed, aligned(4))) { \
    uint32_t style, extended; uint16_t x, y, w, h, id, kind, class_id; \
    CE_WCHAR label[sizeof(caption) / sizeof(CE_WCHAR)]; uint16_t extra; \
}
static const struct __attribute__((packed, aligned(4))) {
    uint32_t style, extended;
    uint16_t count, x, y, w, h, menu, class_id;
    CE_WCHAR text[sizeof(SETTINGS_TITLE) / sizeof(CE_WCHAR)];
    CONTROL_TEMPLATE(STARTUP_LABEL) auto_checkbox __attribute__((aligned(4)));
    CONTROL_TEMPLATE(STATUS_LABEL) status;
    CONTROL_TEMPLATE(L"저장") save;
    CONTROL_TEMPLATE(L"닫기") cancel;
    CONTROL_TEMPLATE(L"USB 연결 시험") usb;
} settings = {
    0x80c80080, 0, 5, 0, 0, 212, 97, 0, 0, SETTINGS_TITLE,
    {0x50010003, 0, 12, 13, 189, 16, AUTO_CHECK, 0xffff, 0x80, STARTUP_LABEL, 0},
    {0x50000000, 0, 12, 35, 188, 33, STATUS, 0xffff, 0x82, STATUS_LABEL, 0},
    {0x50010001, 0, 12, 71, 42, 17, SAVE, 0xffff, 0x80, L"저장", 0},
    {0x50010000, 0, 60, 71, 42, 17, CANCEL, 0xffff, 0x80, L"닫기", 0},
    {0x50010000, 0, 115, 71, 85, 17, USB_TEST, 0xffff, 0x80, L"USB 연결 시험", 0},
};
#undef CONTROL_TEMPLATE
#undef SETTINGS_TITLE
#undef STARTUP_LABEL
#undef STATUS_LABEL

static int save_preference(const CE_WCHAR *path, int value)
{
    if (value) {
        CE_HANDLE file = CreateFileW(path, 0x40000000, 0, 0, 2, 0x80, 0);
        return file != (CE_HANDLE)-1 && CloseHandle(file);
    }
    if (DeleteFileW(path))
        return 1;
    uint32_t error = GetLastError();
    return error == 2 || error == 3;
}

static int save_settings(CE_HANDLE window)
{
    int boot = SendMessageW(GetDlgItem(window, AUTO_CHECK), 0xf0, 0, 0) == 1;
    if (boot != i30_usb_file_exists(autostart) && !save_preference(autostart, boot))
        return 0;
    OutputDebugStringW(boot ? L"i30 USB startup setting saved: on.\r\n" :
                             L"i30 USB startup setting saved: off.\r\n");
    return 1;
}

static const CE_WCHAR *test_usb(int automatic)
{
    const CE_WCHAR *result = i30_usb_file_exists(I30_AA_DRIVER_PATH) ?
        i30_usb_listen(automatic ? I30_USB_AUTOSTART : I30_USB_TEST, 0) : L"The USB client DLL is missing.";
    OutputDebugStringW(result);
    OutputDebugStringW(L"\r\n");
    return result;
}

typedef struct ProjectionDialog {
    CE_HANDLE cancel, worker;
    uint32_t open_tick;
} ProjectionDialog;

static uint32_t projection_usb(void *argument)
{
    ProjectionDialog *state = argument;
    OutputDebugStringW(i30_usb_listen(I30_USB_TEST, state->cancel));
    OutputDebugStringW(L"\r\n");
    return 0;
}

static int projection_window(CE_HANDLE window, uint32_t message, uint32_t parameter, int32_t detail)
{
    enum { USER_DATA = 8, INIT = 0x110, TIMER = 0x113, CLOSE = 0x10, KEY_DOWN = 0x100, ESCAPE = 27 };
    if (message == INIT) {
        ProjectionDialog *state = (ProjectionDialog *)(uintptr_t)(uint32_t)detail;
        SetWindowLongW(window, USER_DATA, detail);
        SetWindowPos(window, 0, 0, 0, 800, 480, 0x0044U);
        state->open_tick = GetTickCount();
        if (!SetTimer(window, 1, 100, 0))
            EndDialog(window, 1);
        return 1;
    }
    if (message != CLOSE && message != TIMER && (message != KEY_DOWN || parameter != ESCAPE))
        return 0;
    ProjectionDialog *state = (ProjectionDialog *)(uintptr_t)(uint32_t)GetWindowLongW(window, USER_DATA);
    if (state) {
        if (message != TIMER) {
            SetEvent(state->cancel);
            EndDialog(window, 0);
        } else if (state->worker) {
            if (WaitForSingleObject(state->worker, 0) != WIN_WAIT_TIMEOUT)
                EndDialog(window, 0);
        } else if (GetForegroundWindow() == window) {
            state->worker = CreateThread(0, 0, projection_usb, state, 0, 0);
            if (!state->worker)
                EndDialog(window, 1);
        } else if (GetTickCount() - state->open_tick >= 2000U) {
            OutputDebugStringW(L"i30 CE projection window did not receive foreground.\r\n");
            EndDialog(window, 1);
        }
    }
    return 1;
}

static void show_projection(CE_HANDLE owner)
{
    static const struct __attribute__((packed, aligned(4))) {
        uint32_t style, extended;
        uint16_t count, x, y, w, h, menu, window_class;
        CE_WCHAR title[sizeof(I30_PROJECTION_WINDOW_TITLE) / sizeof(CE_WCHAR)];
    } surface = {0x90000080U, 0, 0, 0, 0, 212, 97, 0, 0, I30_PROJECTION_WINDOW_TITLE};
    ProjectionDialog state = {CreateEventW(0, 1, 0, 0), 0, 0};
    if (!state.cancel)
        return;
    if (GetForegroundWindow() == owner)
        DialogBoxIndirectParamW(GetModuleHandleW(0), &surface, owner, projection_window, (int32_t)(uintptr_t)&state);
    SetEvent(state.cancel);
    if (state.worker) {
        WaitForSingleObject(state.worker, 0xffffffffU);
        CloseHandle(state.worker);
    }
    CloseHandle(state.cancel);
}

static int settings_dialog(CE_HANDLE window, uint32_t msg, uint32_t command, int32_t unused)
{
    (void)unused;
    if (msg == 0x110) { /* WM_INITDIALOG */
        SendMessageW(GetDlgItem(window, AUTO_CHECK), 0xf1, i30_usb_file_exists(autostart), 0);
        SetWindowPos(window, 0, 194, 116, 0, 0, 0x15);
        return 1;
    }
    if (msg == 0x111) { /* WM_COMMAND */
        unsigned id = command & 0xffffU;
        if (id == SAVE && !save_settings(window)) {
            SetDlgItemTextW(window, STATUS, L"설정을 저장할 수 없습니다.");
            return 1;
        }
        if (id == USB_TEST) {
            SetDlgItemTextW(window, STATUS, L"휴대폰에서 AARE를 열고 35초 안에 USB로 연결하세요.");
            UpdateWindow(window);
            SetDlgItemTextW(window, STATUS, test_usb(0));
            return 1;
        }
        if (id == SAVE || id == CANCEL) {
            EndDialog(window, id);
            return 1;
        }
    }
    return 0;
}

static int has_command(const CE_WCHAR *suffix, unsigned size)
{
    const CE_WCHAR *line = GetCommandLineW();
    unsigned length = 0;
    if (!line)
        return 0;
    while (line[length])
        ++length;
    if (length < size || (length > size && line[length - size - 1] != L' '))
        return 0;
    for (unsigned i = 0; i < size; ++i)
        if (line[length - size + i] != suffix[i])
            return 0;
    return 1;
}

static CE_HANDLE projection_owner(void)
{
    static const CE_WCHAR prefix[] = WIDE_STRING(I30_PROJECTION_COMMAND);
    const CE_WCHAR *line = GetCommandLineW();
    unsigned length = 0, count = sizeof(prefix) / sizeof(*prefix) - 1U;
    if (!line)
        return 0;
    while (line[length])
        ++length;
    if (length < count + 8U)
        return 0;
    unsigned start = length - count - 8U;
    if (start && line[start - 1] != L' ')
        return 0;
    for (unsigned i = 0; i < count; ++i) {
        if (line[start + i] != prefix[i])
            return 0;
    }
    uintptr_t value = 0;
    for (unsigned i = length - 8U; i < length; ++i) {
        unsigned digit = line[i];
        if (digit >= '0' && digit <= '9')
            digit -= '0';
        else if (digit >= 'a' && digit <= 'f')
            digit -= 'a' - 10U;
        else
            return 0;
        value = (value << 4U) | digit;
    }
    return (CE_HANDLE)value;
}

static void sync_emulator_clock(void)
{
    static const uint8_t expected[] = "I30UTC01";
    struct {
        uint8_t magic[8];
        uint16_t system_time[8];
    } clock;
    uint32_t length = 0;
    CE_HANDLE file = CreateFileW(WIDE_STRING(I30_EMULATOR_UTC_FILE), 0x80000000U, 1, 0, 3, 0x80, 0);
    if (file == (CE_HANDLE)-1)
        return;
    int ok = ReadFile(file, &clock, sizeof(clock), &length, 0);
    CloseHandle(file);
    if (!ok || length != sizeof(clock))
        return;
    for (unsigned i = 0; i < sizeof(clock.magic); ++i) {
        if (clock.magic[i] != expected[i])
            return;
    }
    OutputDebugStringW(SetSystemTime(clock.system_time) ? L"i30 CE clock set from emulator UTC.\r\n" :
                                                        L"i30 CE failed to set emulator UTC.\r\n");
}

void i30_ce_entry(void)
{
    static const CE_WCHAR start[] = WIDE_STRING(I30_STARTUP_COMMAND);
    static const CE_WCHAR launch[] = WIDE_STRING(I30_MANUAL_COMMAND);
    static const CE_WCHAR clock[] = WIDE_STRING(I30_EMULATOR_CLOCK_COMMAND);
    CE_HANDLE owner = projection_owner();
    if (has_command(clock, sizeof(clock) / sizeof(*clock) - 1)) {
        sync_emulator_clock();
    } else if (has_command(start, sizeof(start) / sizeof(*start) - 1)) {
        if (i30_usb_file_exists(autostart)) {
            OutputDebugStringW(L"i30 USB startup requested.\r\n");
            test_usb(1);
        }
    } else if (owner || has_command(launch, sizeof(launch) / sizeof(*launch) - 1)) {
        OutputDebugStringW(L"i30 Android Auto requested from stock navigation menu.\r\n");
        if (owner && i30_usb_file_exists(I30_AA_DRIVER_PATH) &&
            (i30_usb_file_exists(L"\\DiskA\\Application\\NAVI\\i30-ca.der") ||
             i30_usb_file_exists(L"\\DiskA\\Application\\NAVI\\i30-ca.pem")))
            show_projection(owner);
        else
            test_usb(0);
    } else {
        DialogBoxIndirectParamW(GetModuleHandleW(0), &settings, 0, settings_dialog, 0);
    }
    ExitThread(0);
}
