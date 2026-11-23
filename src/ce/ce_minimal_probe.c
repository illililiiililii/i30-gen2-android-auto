#include "aa_wire.h"
#include "ce_minimal.h"

#define INVALID_HANDLE ((CE_HANDLE)(uintptr_t)0xffffffffU)

#ifdef I30_AA_SETTINGS
int MessageBoxW(CE_HANDLE owner, const CE_WCHAR *text, const CE_WCHAR *title, uint32_t style);
static const CE_WCHAR settings_title[] = L"Android Auto";
#endif

static void log_ascii(const char *ascii)
{
    CE_WCHAR text[80];
    unsigned length = 0;
    for (; length < sizeof(text) / sizeof(text[0]) - 1U && ascii[length]; ++length)
        text[length] = (unsigned char)ascii[length];
    text[length] = 0;
    OutputDebugStringW(text);
}

static int check_file(void)
{
    CE_WCHAR path[260];
    uint8_t signature[2];
    uint32_t bytes = 0;
    uint32_t length = GetModuleFileNameW(0, path, sizeof(path) / sizeof(path[0]));
    CE_HANDLE file;
    int success, closed;
    if (!length || length >= sizeof(path) / sizeof(path[0]))
        return 0;
    file = CreateFileW(path, 0x80000000U, 1, 0, 3, 0x80, 0);
    if (file == INVALID_HANDLE)
        return 0;
    success = ReadFile(file, signature, sizeof(signature), &bytes, 0);
    closed = CloseHandle(file);
    return closed && success && bytes == sizeof(signature) && signature[0] == 'M' && signature[1] == 'Z';
}

static uint32_t probe_thread(void *parameter)
{
    volatile uint32_t *value = parameter;
    *value = 0x693330U;
    return 17;
}

static int check_heap_and_thread(void)
{
    CE_HANDLE heap = GetProcessHeap();
    volatile uint32_t *value;
    CE_HANDLE thread;
    uint32_t code = 0;
    int success = 0;
    if (!heap)
        return 0;
    value = HeapAlloc(heap, 0, sizeof(*value));
    if (!value)
        return 0;
    *value = 0;
    thread = CreateThread(0, 0, probe_thread, (void *)value, 0, 0);
    if (thread) {
        if (WaitForSingleObject(thread, 3000) != 0) {
            CloseHandle(thread);
            return 0;  /* The worker could still hold value. Process teardown reclaims it. */
        }
        success = GetExitCodeThread(thread, &code) && code == 17U && *value == 0x693330U;
        success = CloseHandle(thread) && success;
    }
    return HeapFree(heap, 0, (void *)value) && success;
}

typedef struct ProbeLink {
    unsigned offset;
    int sent;
} ProbeLink;

static int mock_write(void *context, const uint8_t *wire, unsigned size)
{
    static const uint8_t expected[] = {0, 3, 0, 6, 0, 1, 0, 1, 0, 6};
    ProbeLink *link = context;
    unsigned i;
    if (size != sizeof(expected))
        return -1;
    for (i = 0; i < size; ++i)
        if (wire[i] != expected[i])
            return -1;
    link->sent = 1;
    return (int)size;
}

static int mock_read(void *context, uint8_t *output, unsigned capacity)
{
    static const uint8_t response[] = {0, 3, 0, 8, 0, 2, 0, 1, 0, 7, 0, 0};
    ProbeLink *link = context;
    if (!link->sent || !capacity || link->offset >= sizeof(response))
        return 0;
    *output = response[link->offset++];
    return 1;
}

static int check_wire(void)
{
    ProbeLink context = {0, 0};
    I30Link link = {&context, mock_read, mock_write};
    uint16_t minor = 0;
    return i30_aa_negotiate_version(&link, &minor) == I30_WIRE_OK && minor == 7U;
}

void i30_ce_entry(void)
{
    uint32_t result = 0;
    uint32_t start;
#ifdef I30_AA_SETTINGS
    if (MessageBoxW(0, L"Run the Android Auto connection self-test?\r\n"
                       L"The test uses a simulated phone.", settings_title, 0x41) != 1) {
        log_ascii("i30 Android Auto settings cancelled\r\n");
        ExitThread(0);
    }
#endif
    start = GetTickCount();
    log_ascii("i30 CE bench probe start\r\n");
    if (!check_file())
        result |= 1U;
    if (!check_heap_and_thread())
        result |= 2U;
    if (!check_wire())
        result |= 4U;
    if (GetTickCount() - start > 4000U)
        result |= 8U;
    log_ascii(result ? "i30 CE bench probe failed\r\n" : "i30 CE bench probe passed\r\n");
#ifdef I30_AA_SETTINGS
    MessageBoxW(0, result ? L"Connection self-test failed." :
                         L"Self-test passed. Simulated peer negotiated Android Auto 1.7.",
                settings_title, result ? 0x10 : 0x40);
#endif
    ExitThread(result);
}
