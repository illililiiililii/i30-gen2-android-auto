#include "ce_aa_usb.h"
#include "ce_aa_usb_session.h"
#include "ce_startup_pref.h"

#define WIDE_STRING_(text) L##text
#define WIDE_STRING(text) WIDE_STRING_(text)

int32_t RegCreateKeyExW(CE_HANDLE, const CE_WCHAR *, uint32_t, CE_WCHAR *, uint32_t,
                       uint32_t, void *, CE_HANDLE *, uint32_t *);
int32_t RegSetValueExW(CE_HANDLE, const CE_WCHAR *, uint32_t, uint32_t, const void *, uint32_t);
int32_t RegCloseKey(CE_HANDLE);
int32_t RegDeleteKeyW(CE_HANDLE, const CE_WCHAR *);
uint32_t GetLastError(void);
uint32_t GetFileAttributesW(const CE_WCHAR *);
uint32_t WaitForMultipleObjects(uint32_t, const CE_HANDLE *, int, uint32_t);

enum { WIN_ALREADY_EXISTS = 183, WIN_WAIT_TIMEOUT = 258, REG_CREATED_NEW_KEY = 1, REG_SZ = 1 };
#define HKLM ((CE_HANDLE)0x80000002U)

static const CE_WCHAR autostart[] = WIDE_STRING(I30_USB_STARTUP_PREF);
int i30_usb_file_exists(const CE_WCHAR *path)
{
    uint32_t attrs = GetFileAttributesW(path);
    return attrs != 0xffffffffU && !(attrs & 0x10U);
}
/* GD13MY .061 USB host groups are decimal VID_PID, device class, interface class. */
#define LOAD_CLIENTS L"Drivers\\USB\\LoadClients\\"
static const CE_WCHAR *const client_keys[] = {
    L"Drivers\\USB\\ClientDrivers\\" I30_AA_DRIVER_ID,
    LOAD_CLIENTS L"6353_11520\\Default\\255\\" I30_AA_DRIVER_ID,
    LOAD_CLIENTS L"6353_11521\\Default\\255\\" I30_AA_DRIVER_ID,
    LOAD_CLIENTS L"1256_26720\\Default\\Default\\" I30_AA_DRIVER_ID,
};

static CE_HANDLE new_event(const CE_WCHAR *name)
{
    CE_HANDLE event = CreateEventW(0, 1, 0, name);
    if (event && GetLastError() == WIN_ALREADY_EXISTS) {
        CloseHandle(event);
        return 0;
    }
    return event;
}

static int register_clients(unsigned *installed)
{
    for (unsigned i = 0; i < sizeof(client_keys) / sizeof(client_keys[0]); ++i) {
        CE_HANDLE key;
        uint32_t disposition;
        int status = RegCreateKeyExW(HKLM, client_keys[i], 0, 0, 0, 0, 0, &key, &disposition);
        if (status)
            return 0;
        if (disposition == REG_CREATED_NEW_KEY) {
            ++*installed;
            if (i)
                status = RegSetValueExW(key, L"DLL", 0, REG_SZ, I30_AA_DRIVER_PATH, sizeof(I30_AA_DRIVER_PATH));
        }
        RegCloseKey(key);
        if (disposition != REG_CREATED_NEW_KEY || status)
            return 0;
    }
    return 1;
}

enum { PROJECTION_CANCEL, PROJECTION_SWITCH, PROJECTION_VERSION, PROJECTION_AUTH,
       PROJECTION_FAILURE, PROJECTION_READY, PROJECTION_SIGNAL_COUNT };

static void wait_for_projection(const CE_HANDLE *events, I30UsbStatus report, void *context)
{
    static const enum I30UsbProjectionStatus states[] = {
        I30_USB_UNAVAILABLE, I30_USB_CONNECTING, I30_USB_AUTHENTICATING,
        I30_USB_AUTH_REQUIRED, I30_USB_RECONNECT, I30_USB_RECONNECT
    };
    enum I30UsbProjectionStatus status = I30_USB_WAITING;
    report(context, status);
    for (;;) {
        unsigned result = WaitForMultipleObjects(PROJECTION_SIGNAL_COUNT, events, 0, 0xffffffffU);
        if (result == PROJECTION_CANCEL)
            return;
        if (result >= PROJECTION_SIGNAL_COUNT || !EventModify(events[result], 2U)) { /* EVENT_RESET */
            report(context, I30_USB_UNAVAILABLE);
            return;
        }
        /* READY also follows a successful version exchange without credentials. */
        if (result == PROJECTION_READY && status == I30_USB_AUTH_REQUIRED)
            continue;
        status = states[result];
        report(context, status);
    }
}

static const CE_WCHAR *listen(enum I30UsbListenMode mode, CE_HANDLE cancel,
                             I30UsbStatus report, void *context)
{
    CE_HANDLE gate, switching, signals[3], version = 0, auth = 0;
    const CE_WCHAR *message = L"Could not create the USB test session.";
    const int automatic = mode == I30_USB_AUTOSTART;
    const uint32_t wait_ms = automatic ? 1000 : 35000;
    unsigned installed = 0;
    int clean = 1;
    gate = new_event(I30_AA_GATE);
    if (!gate)
        return L"A USB connection test is already running.";
    switching = new_event(I30_AA_SWITCH);
    signals[0] = new_event(I30_AA_READY);
    signals[1] = new_event(I30_AA_FAILURE);
    signals[2] = cancel;
    if (report) {
        version = new_event(I30_AA_VERSION);
        auth = new_event(I30_AA_AUTH_REQUIRED);
    }
    if (switching && signals[0] && signals[1] && (!report || (cancel && version && auth))) {
        message = L"Could not register the USB test driver.";
        if (register_clients(&installed)) {
            OutputDebugStringW(L"i30 USB attach ready. Connect Samsung phone.\r\n");
            if (report) {
                const CE_HANDLE events[] = {cancel, switching, version, auth, signals[1], signals[0]};
                wait_for_projection(events, report, context);
                message = L"Android Auto projection listener stopped.";
            } else do {
                uint32_t result = WaitForMultipleObjects(cancel ? 3 : 2, signals, 0, wait_ms);
                if (cancel && result == 2) {
                    message = L"Android Auto projection closed.";
                    break;
                }
                if (result <= 1U) {
                    message = result == 0U ?
                        L"Phone answered the Android Auto version request.\r\nProjection setup is pending." :
                        L"USB accessory found, but the version request failed.";
                    if (automatic) {
                        if (!EventModify(signals[result], 2U)) { /* EVENT_RESET */
                            message = L"The Android Auto USB status event could not be reset.";
                            break;
                        }
                        OutputDebugStringW(message);
                        OutputDebugStringW(L"\r\n");
                    }
                } else if (result != WIN_WAIT_TIMEOUT) {
                    message = L"The USB connection test could not wait for the phone.";
                    break;
                } else if (!automatic) {
                    message = WaitForSingleObject(switching, 0) == 0U ?
                        L"The phone did not reappear in USB accessory mode." :
                        L"No supported phone attached. Unplug and connect after starting the test.";
                }
            } while (automatic && i30_usb_file_exists(autostart));
            if (automatic && !i30_usb_file_exists(autostart))
                message = L"Android Auto auto-connect stopped.";
        }
    }
    SetEvent(gate);
    while (installed)
        clean = (RegDeleteKeyW(HKLM, client_keys[--installed]) == 0) && clean;
    if (!clean)
        message = L"USB test ended, but the temporary driver registration could not be removed.";
    if (auth)
        CloseHandle(auth);
    if (version)
        CloseHandle(version);
    if (signals[1])
        CloseHandle(signals[1]);
    if (signals[0])
        CloseHandle(signals[0]);
    if (switching)
        CloseHandle(switching);
    CloseHandle(gate);
    return message;
}

const CE_WCHAR *i30_usb_listen(enum I30UsbListenMode mode, CE_HANDLE cancel)
{
    return listen(mode, cancel, 0, 0);
}

const CE_WCHAR *i30_usb_project(CE_HANDLE cancel, I30UsbStatus report, void *context)
{
    return listen(I30_USB_PROJECTION, cancel, report, context);
}

