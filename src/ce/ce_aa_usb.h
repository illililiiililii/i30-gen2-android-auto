#ifndef I30_CE_AA_USB_H
#define I30_CE_AA_USB_H

#include "ce_minimal.h"

#define I30_AA_DRIVER_PATH L"\\DiskA\\Application\\NAVI\\i30usb.dll"
#define I30_AA_DRIVER_ID L"I30AA_GD13MY_061_USB_1"
#define I30_AA_GATE L"I30AA.GD13MY.061.USB.Gate"
#define I30_AA_SWITCH L"I30AA.GD13MY.061.USB.Switch"
#define I30_AA_READY L"I30AA.GD13MY.061.USB.Ready"
#define I30_AA_FAILURE L"I30AA.GD13MY.061.USB.Failure"
#define I30_AA_VERSION L"I30AA.GD13MY.061.USB.Version"
#define I30_AA_AUTH_REQUIRED L"I30AA.GD13MY.061.USB.AuthRequired"
#define I30_AA_VIDEO_ACTIVE L"I30AA.GD13MY.061.USB.VideoActive"

#define I30_SAMSUNG 0x04e8U
#define I30_SAMSUNG_MTP 0x6860U
#define I30_GOOGLE 0x18d1U
#define I30_AOA_DATA 0x2d00U
#define I30_AOA_ADB_DATA 0x2d01U
typedef struct CeUsbDriverSettings CeUsbDriverSettings;

CE_HANDLE CreateEventW(void *, int, int, const CE_WCHAR *);
uint32_t GetLastError(void);
int EventModify(CE_HANDLE, uint32_t);
#define SetEvent(event) EventModify((event), 3U)
void Sleep(uint32_t);
int MessageBoxW(CE_HANDLE, const CE_WCHAR *, const CE_WCHAR *, uint32_t);

#endif
