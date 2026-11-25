#include "aa_wire.h"
#include "ce_aa_usb.h"
#ifdef I30_NATIVE_TLS
#include "ce_aa_tls.h"
#endif
#include <stddef.h>

/* Layout checked against GD13MY .061 usbd.dll and the stock usbmsc client. */
typedef struct UsbEndpoint {
    uint32_t size;
    uint8_t descriptor[7];
    const void *extension;
    uint32_t extension_size;
} UsbEndpoint;

typedef struct UsbInterface {
    uint32_t size;
    uint8_t descriptor[9];
    uint32_t extension_size;
    const UsbEndpoint *endpoints;
    const void *extension;
} UsbInterface;

typedef struct UsbConfig {
    uint32_t size;
    uint8_t descriptor[9];
    const void *extension;
    uint32_t interface_count;
    const UsbInterface *interfaces;
    uint32_t extension_size;
} UsbConfig;

typedef struct UsbDevice {
    uint32_t size;
    uint8_t descriptor[18];
    const UsbConfig *configurations;
    const UsbConfig *active;
} UsbDevice;

typedef struct UsbRequest {
    uint8_t request_type, request;
    uint16_t value, index, length;
} UsbRequest;

typedef uint32_t (*UsbNotify)(void *);

typedef struct UsbFunctions {
    uint32_t size;
    void (*unused1[12])(void);
    const UsbDevice *(*device_info)(CE_HANDLE);
    CE_HANDLE (*vendor_transfer)(CE_HANDLE, UsbNotify, void *, uint32_t, const UsbRequest *, void *, uint32_t);
    void (*unused2[8])(void);
    CE_HANDLE (*open_pipe)(CE_HANDLE, const uint8_t *);
    void (*unused3[2])(void);
    int (*close_pipe)(CE_HANDLE);
    void (*unused4[2])(void);
    CE_HANDLE (*bulk_transfer)(CE_HANDLE, UsbNotify, void *, uint32_t, uint32_t, void *, uint32_t);
    void (*unused5[2])(void);
    int (*complete)(CE_HANDLE);
    int (*status)(CE_HANDLE, uint32_t *, uint32_t *);
    void (*unused6[2])(void);
    int (*close_transfer)(CE_HANDLE);
} UsbFunctions;

#if defined(__arm__)
_Static_assert(offsetof(UsbDevice, active) == 0x1c, "CE USB device layout");
_Static_assert(offsetof(UsbConfig, interfaces) == 0x18, "CE USB configuration layout");
_Static_assert(sizeof(UsbInterface) == 0x1c && offsetof(UsbInterface, endpoints) == 0x14, "CE USB interface layout");
_Static_assert(sizeof(UsbEndpoint) == 0x14, "CE USB endpoint stride");
_Static_assert(offsetof(UsbFunctions, vendor_transfer) == 0x38, "CE USB vendor function offset");
_Static_assert(offsetof(UsbFunctions, open_pipe) == 0x5c, "CE USB pipe function offset");
_Static_assert(offsetof(UsbFunctions, bulk_transfer) == 0x74, "CE USB bulk function offset");
_Static_assert(offsetof(UsbFunctions, close_transfer) == 0x90, "CE USB transfer cleanup offset");
_Static_assert(sizeof(UsbRequest) == 8, "USB setup packet size");
#endif

enum { USB_IN = 0x80, USB_NO_WAIT = 0x100, USB_SHORT_TRANSFER_OK = 0x200, USB_BULK = 2, USB_MASS_STORAGE = 8 };
enum { AA_VERSION_FRAME = 12, EVENT_ALREADY_EXISTS = 183, WAIT_TIMEOUT = 258 };
enum { USB_VERSION_MS = 3000, USB_TLS_MS = 8000, USB_VIDEO_MS = 20000 };

typedef struct UsbLink {
    const UsbFunctions *api;
    CE_HANDLE stop, input, output, video;
    uint32_t start;
    unsigned offset, used, read_size, timeout;
    uint8_t staged[512];
} UsbLink;

int i30_ce_entry(CE_HANDLE module, uint32_t reason, void *reserved)
{
    (void)module;
    (void)reason;
    (void)reserved;
    return 1;
}

static unsigned le16(const uint8_t *p)
{
    return p[0] | (unsigned)p[1] << 8;
}

static int running(CE_HANDLE stop)
{
    return WaitForSingleObject(stop, 0) == WAIT_TIMEOUT;
}

static int transfer_allowed(const UsbLink *link)
{
    return running(link->stop) && GetTickCount() - link->start < link->timeout;
}

static CE_HANDLE session_event(const CE_WCHAR *name)
{
    /* Match the menu's named manual-reset events using the CE object API. */
    CE_HANDLE event = CreateEventW(0, 1, 0, name);
    if (event && GetLastError() != EVENT_ALREADY_EXISTS) {
        CloseHandle(event);
        return 0;
    }
    return event;
}

static void signal_status(const CE_WCHAR *name)
{
    CE_HANDLE event = session_event(name);
    if (event) {
        SetEvent(event);
        CloseHandle(event);
    }
}

static void transfer_error(uint32_t code)
{
    static const char hex[] = "0123456789abcdef";
    static const CE_WCHAR message[] = L"i30 CE USB transfer error: 0x00000000\r\n";
    CE_WCHAR line[sizeof(message) / sizeof(message[0])];
    for (unsigned i = 0; i < sizeof(line) / sizeof(line[0]); ++i)
        line[i] = message[i];
    for (unsigned i = 0; i < 8; ++i)
        line[sizeof(line) / sizeof(line[0]) - 4U - i] = hex[(code >> (4U * i)) & 15U];
    OutputDebugStringW(line);
}

static int finish(UsbLink *link, CE_HANDLE transfer, unsigned capacity)
{
    uint32_t length = 0, error = 1;
    int result = -1, completed = 0;
    if (!transfer) {
        OutputDebugStringW(L"i30 CE USB transfer submission failed.\r\n");
        return -1;
    }
    while (transfer_allowed(link)) {
        if (link->api->complete(transfer)) {
            completed = 1;
            if (!link->api->status(transfer, &length, &error))
                OutputDebugStringW(L"i30 CE USB transfer status unavailable.\r\n");
            else if (error)
                transfer_error(error);
            else if (length > capacity)
                OutputDebugStringW(L"i30 CE USB transfer length exceeds request.\r\n");
            else
                result = (int)length;
            break;
        }
        Sleep(10);
    }
    /* Stock CloseTransfer aborts unfinished transfers before releasing the handle. */
    if (!link->api->close_transfer(transfer)) {
        OutputDebugStringW(L"i30 CE USB transfer cleanup failed.\r\n");
        result = -1;
    }
    if (!completed)
        OutputDebugStringW(running(link->stop) ? L"i30 CE USB transfer timed out.\r\n" :
                           L"i30 CE USB transfer cancelled.\r\n");
    return result;
}

static int control(UsbLink *link, CE_HANDLE device, uint8_t code, uint16_t index, void *data, uint16_t size)
{
    UsbRequest request = {code == 51 ? 0xc0 : 0x40, code, 0, index, size};
    CE_HANDLE transfer;
    if (!transfer_allowed(link))
        return 0;
    transfer = link->api->vendor_transfer(device, 0, 0,
               USB_NO_WAIT | (code == 51 ? USB_IN : 0U), &request, data, 0);
    return finish(link, transfer, size) == (int)size;
}

static int start_accessory(UsbLink *link, CE_HANDLE device)
{
    static const char identity[4][36] = {"i30 Research", "Android Auto", "i30 GD13MY USB test", "1.0"};
    uint8_t protocol[2];
    unsigned index, length;
    char payload[sizeof(identity[0])];
    int issued;
    if (!control(link, device, 51, 0, protocol, sizeof(protocol)) ||
        (le16(protocol) != 1U && le16(protocol) != 2U))
        return 0;
    for (index = 0; index < 4; ++index) {
        for (length = 0; identity[index][length]; ++length)
            payload[length] = identity[index][length];
        payload[length] = 0;
        if (!control(link, device, 52, (uint16_t)index, payload, (uint16_t)(length + 1U)))
            return 0;
    }
    /* Tell the menu before issuing START: the phone can disconnect during the transfer. */
    signal_status(I30_AA_SWITCH);
    issued = control(link, device, 53, 0, 0, 0);
    return issued;
}

static int write_link(void *opaque, const uint8_t *data, unsigned size)
{
    UsbLink *link = opaque;
    uint8_t request[16];
    unsigned i;
    if (!transfer_allowed(link) || size > sizeof(request))
        return -1;
    for (i = 0; i < size; ++i)
        request[i] = data[i];
    return finish(link, link->api->bulk_transfer(link->output, 0, 0, USB_NO_WAIT,
                  size, request, 0), size);
}

static int read_link(void *opaque, uint8_t *data, unsigned capacity)
{
    UsbLink *link = opaque;
    unsigned count, i;
    int length;
    if (!capacity)
        return -1;
    if (!transfer_allowed(link)) {
        OutputDebugStringW(running(link->stop) ? L"i30 CE USB read deadline reached.\r\n" :
                           L"i30 CE USB read cancelled.\r\n");
        return -1;
    }
    if (link->offset == link->used) {
        unsigned flags = USB_IN | USB_NO_WAIT;
        if (link->read_size != AA_VERSION_FRAME)
            flags |= USB_SHORT_TRANSFER_OK;
        length = finish(link, link->api->bulk_transfer(link->input, 0, 0, flags, link->read_size,
                                                      link->staged, 0), link->read_size);
        if (length <= 0)
            return -1;
        link->offset = 0;
        link->used = (unsigned)length;
    }
    count = link->used - link->offset;
    if (count > capacity)
        count = capacity;
    for (i = 0; i < count; ++i)
        data[i] = link->staged[link->offset + i];
    link->offset += count;
    return (int)count;
}

#ifdef I30_NATIVE_TLS
static void start_video(void *opaque)
{
    UsbLink *link = opaque;
    link->video = session_event(I30_AA_VIDEO_ACTIVE);
    if (link->video)
        SetEvent(link->video);
    /* Keep this attach-based driver within the manual launcher's 35-second wait. */
    link->start = GetTickCount();
    link->timeout = USB_VIDEO_MS;
}

static int write_tls(void *opaque, const uint8_t *data, unsigned size)
{
    UsbLink *link = opaque;
    uint8_t packet[512];
    unsigned sent = 0;
    while (sent < size && transfer_allowed(link)) {
        unsigned count = size - sent;
        if (count > sizeof(packet))
            count = sizeof(packet);
        for (unsigned i = 0; i < count; ++i)
            packet[i] = data[sent + i];
        if (finish(link, link->api->bulk_transfer(link->output, 0, 0, USB_NO_WAIT,
                                                 count, packet, 0), count) != (int)count)
            return -1;
        sent += count;
    }
    if (sent < size)
        OutputDebugStringW(running(link->stop) ? L"i30 CE USB write deadline reached.\r\n" :
                           L"i30 CE USB write cancelled.\r\n");
    return (int)sent;
}
#endif

static int negotiate(UsbLink *link, CE_HANDLE device, const UsbInterface *interface)
{
    const uint8_t *input = 0, *output = 0;
    unsigned i;
    uint16_t minor = 0;
    int success = 0;
    I30Link wire = {link, read_link, write_link};
    if (!interface || interface->size != sizeof(*interface) || interface->descriptor[0] != 9U ||
        interface->descriptor[1] != 4U || interface->descriptor[2] != 0U ||
        interface->descriptor[3] != 0U || interface->descriptor[4] != 2U ||
        interface->descriptor[5] != 0xffU || !interface->endpoints)
        return 0;
    for (i = 0; i < 2; ++i) {
        const UsbEndpoint *endpoint = &interface->endpoints[i];
        const uint8_t *desc = endpoint->descriptor;
        if (endpoint->size != sizeof(*endpoint) || desc[0] != 7U || desc[1] != 5U ||
            (desc[3] & 3U) != USB_BULK || !(desc[2] & 15U) || !le16(desc + 4))
            return 0;
        if (desc[2] & USB_IN)
            input = desc;
        else
            output = desc;
    }
    if (!input || !output)
        return 0;
    link->input = link->api->open_pipe(device, input);
    if (link->input) {
        link->output = link->api->open_pipe(device, output);
        if (link->output) {
            success = i30_aa_negotiate_version(&wire, &minor) == I30_WIRE_OK && minor >= 6U;
#ifdef I30_NATIVE_TLS
            if (success) {
                signal_status(I30_AA_VERSION);
                link->start = GetTickCount();
                link->timeout = USB_TLS_MS;
                link->read_size = sizeof(link->staged);
                link->video = 0;
                wire.write = write_tls;
                if (i30_ce_authenticate(&wire, start_video))
                    signal_status(I30_AA_AUTH_REQUIRED);
                if (link->video) {
                    EventModify(link->video, 2U); /* EVENT_RESET */
                    CloseHandle(link->video);
                }
            }
#endif
            success = link->api->close_pipe(link->output) && success;
        }
        success = link->api->close_pipe(link->input) && success;
    }
    return success;
}

static int no_storage(const UsbDevice *info)
{
    const UsbConfig *config = info->active;
    unsigned i;
    if (info->descriptor[4] == USB_MASS_STORAGE || !config ||
        config->size != sizeof(*config) || !config->interfaces ||
        !config->interface_count || config->interface_count > 32U)
        return 0;
    for (i = 0; i < config->interface_count; ++i)
        if (config->interfaces[i].size != sizeof(UsbInterface) ||
            config->interfaces[i].descriptor[5] == USB_MASS_STORAGE)
            return 0;
    return 1;
}

int USBDeviceAttach(CE_HANDLE device, const UsbFunctions *api, const UsbInterface *interface,
                    const CE_WCHAR *driver, int *accepted, const CeUsbDriverSettings *settings, uint32_t unused)
{
    const UsbDevice *info;
    uint32_t vendor, product;
    UsbLink link;
    int success = 0;
    (void)driver;
    (void)settings;
    (void)unused;
    if (!accepted)
        return 0;
    *accepted = 0;
    if (!device || !api || api->size != 0xacU || !api->device_info || !api->vendor_transfer ||
        !api->open_pipe || !api->close_pipe || !api->bulk_transfer || !api->complete ||
        !api->status || !api->close_transfer)
        return 0;
    info = api->device_info(device);
    if (!info || info->size != sizeof(*info) || info->descriptor[0] != 18U || info->descriptor[1] != 1U)
        return 0;
    vendor = le16(info->descriptor + 8);
    product = le16(info->descriptor + 10);
    link.stop = session_event(I30_AA_GATE);
    if (!link.stop)
        return 0;
    link.api = api;
    link.start = GetTickCount();
    link.timeout = USB_VERSION_MS;
    link.read_size = AA_VERSION_FRAME;
    link.offset = link.used = 0;
    if (running(link.stop) && vendor == I30_SAMSUNG && product == I30_SAMSUNG_MTP &&
        !interface && no_storage(info)) {
        success = start_accessory(&link, device);
    } else if (running(link.stop) && vendor == I30_GOOGLE &&
               (product == I30_AOA_DATA || product == I30_AOA_ADB_DATA) &&
               interface && interface->descriptor[2] == 0U) {
        success = negotiate(&link, device, interface);
        signal_status(success ? I30_AA_READY : I30_AA_FAILURE);
    }
    CloseHandle(link.stop);
    *accepted = success;
    return success;
}
