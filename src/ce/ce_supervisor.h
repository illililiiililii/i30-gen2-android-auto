#ifndef I30_CE_SUPERVISOR_H
#define I30_CE_SUPERVISOR_H

#include <windows.h>

enum {
    I30_STOCK_REAR_VIEW = 0x01,
    I30_STOCK_PARKING_VIEW = 0x02,
    I30_STOCK_WARNING = 0x04,
    I30_STOCK_BLUETOOTH_MEDIA = 0x01,
    I30_STOCK_CALL = 0x02,
    I30_STOCK_PRIORITY_SOUND = 0x04
};

typedef struct I30HostState {
    BOOL phone_attached;
    BOOL projection_selected;
    BOOL stock_permits_projection;
    BOOL resource_budget_ok;
    DWORD heartbeat_pid;  /* The OEM host validates peer identity and timestamps the heartbeat. */
    DWORD heartbeat_tick;
    DWORD stock_surface_priority; /* Active OEM reverse, parking and warning surfaces. */
    DWORD stock_audio_priority;   /* Active OEM media, call and warning audio routes. */
} I30HostState;

typedef struct I30Supervisor {
    LPCWSTR executable;   /* Approved absolute path, retained by the caller. */
    LPWSTR arguments;     /* Writable command line for CreateProcess. */
    HANDLE stop_event;    /* Manual-reset event supplied to the child via its argument contract. */
    HANDLE worker;
    DWORD worker_pid;
    DWORD started;
    DWORD stop_started;
    DWORD exited;
    UINT failures;
    BOOL visible;
    BOOL stopping;
    BOOL force_sent;
    BOOL waiting_retry;
    BOOL projected_audio;
    void *context;
    BOOL (*surface)(void *context, BOOL projected);
    BOOL (*audio)(void *context, BOOL projected);
    void (*log)(void *context, LPCWSTR message, DWORD detail);
} I30Supervisor;

/* Zero-initialize, then set executable, arguments, stop_event and surface before use.
 * Keep OEM surfaces available independently of the child and poll on the OEM host thread.
 * The optional audio callback changes the projection route without switching the OEM source.
 * Populate the priority fields from the OEM coordinators before allowing a surface.
 * At shutdown, continue with phone_attached=FALSE until worker is NULL. */
void i30_supervisor_step(I30Supervisor *host, const I30HostState *state, DWORD now);

#endif
