#ifndef I30_CE_AA_USB_SESSION_H
#define I30_CE_AA_USB_SESSION_H

#include "ce_minimal.h"

#ifdef __cplusplus
extern "C" {
#endif

enum I30UsbListenMode { I30_USB_TEST, I30_USB_AUTOSTART, I30_USB_PROJECTION };
enum I30UsbProjectionStatus {
    I30_USB_STARTING, I30_USB_WAITING, I30_USB_CONNECTING, I30_USB_AUTHENTICATING,
    I30_USB_AUTH_REQUIRED, I30_USB_APPROVAL, I30_USB_AUTH_FAILED, I30_USB_MEDIA,
    I30_USB_MEDIA_FAILED, I30_USB_VERSION_FAILED, I30_USB_RECONNECT, I30_USB_UNAVAILABLE
};
typedef void (*I30UsbStatus)(void *context, enum I30UsbProjectionStatus status);

int i30_usb_file_exists(const CE_WCHAR *path);
const CE_WCHAR *i30_usb_listen(enum I30UsbListenMode mode, CE_HANDLE cancel);
const CE_WCHAR *i30_usb_project(CE_HANDLE cancel, I30UsbStatus report, void *context);

#ifdef __cplusplus
}
#endif
#endif
