#ifndef I30_CE_MINIMAL_H
#define I30_CE_MINIMAL_H

#include <stdint.h>

/* Narrow CE user-mode ABI used by the freestanding probe. All scalar arguments,
 * handles and UTF-16 pointers are 32-bit ARM ABI values. */
#ifdef __cplusplus
typedef wchar_t CE_WCHAR;
extern "C" {
#else
typedef uint16_t CE_WCHAR;
#endif
typedef void *CE_HANDLE;
typedef uint32_t (*CE_THREAD)(void *context);

void OutputDebugStringW(const CE_WCHAR *text);
CE_HANDLE CreateFileW(const CE_WCHAR *path, uint32_t access, uint32_t share, void *security,
                     uint32_t creation, uint32_t flags, CE_HANDLE template_file);
int ReadFile(CE_HANDLE file, void *buffer, uint32_t size, uint32_t *read, void *overlapped);
int CloseHandle(CE_HANDLE handle);
CE_HANDLE GetProcessHeap(void);
void *HeapAlloc(CE_HANDLE heap, uint32_t flags, uint32_t size);
int HeapFree(CE_HANDLE heap, uint32_t flags, void *memory);
CE_HANDLE CreateThread(void *security, uint32_t stack, CE_THREAD routine, void *context,
                      uint32_t flags, uint32_t *thread_id);
uint32_t WaitForSingleObject(CE_HANDLE object, uint32_t milliseconds);
int GetExitCodeThread(CE_HANDLE thread, uint32_t *code);
uint32_t GetModuleFileNameW(CE_HANDLE module, CE_WCHAR *name, uint32_t capacity);
uint32_t GetTickCount(void);
void ExitThread(uint32_t code) __attribute__((noreturn));

#ifdef __cplusplus
}
#endif
#endif
