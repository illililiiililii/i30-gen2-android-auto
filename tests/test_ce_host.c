/* Desktop Win32 process test for the native CE adapter's shared supervisor logic. */
#include <assert.h>
#include <stdio.h>
#include <wchar.h>
#include "ce_supervisor.h"
#include "ce_wave.h"

typedef struct {
    BOOL screen;
    BOOL audio;
} ProjectionOwnership;

static BOOL screen(void *context, BOOL projected)
{
    ProjectionOwnership *ownership = (ProjectionOwnership *)context;
    ownership->screen = projected;
    return TRUE;
}

static BOOL audio(void *context, BOOL projected)
{
    ProjectionOwnership *ownership = (ProjectionOwnership *)context;
    ownership->audio = projected;
    return TRUE;
}

static void log_event(void *context, LPCWSTR message, DWORD detail)
{
    UNREFERENCED_PARAMETER(context);
    wprintf(L"%ls %lu\n", message, detail);
}

int wmain(int argc, wchar_t **argv)
{
    I30Supervisor host = {0};
    I30HostState state = {0};
    I30Playback player = {0};
    I30Capture microphone = {0};
    WCHAR executable[MAX_PATH], args[MAX_PATH], event_name[80];
    HANDLE event;
    DWORD now = 100, length;
    ProjectionOwnership ownership = {0};

    if (argc == 3 && wcscmp(argv[1], L"--child") == 0) {
        event = OpenEventW(SYNCHRONIZE, FALSE, argv[2]);
        if (!event)
            return 3;
        assert(WaitForSingleObject(event, 10000) == WAIT_OBJECT_0);
        CloseHandle(event);
        return 0;
    }
    if (argc == 2 && wcscmp(argv[1], L"--hang") == 0) {
        Sleep(10000);
        return 4;
    }
    length = GetModuleFileNameW(NULL, executable, _countof(executable));
    assert(length > 0 && length < _countof(executable));
    assert(swprintf_s(event_name, _countof(event_name), L"Local\\i30-ce-test-%lu", GetCurrentProcessId()) > 0);
    event = CreateEventW(NULL, TRUE, FALSE, event_name);
    assert(event && GetLastError() != ERROR_ALREADY_EXISTS);
    assert(swprintf_s(args, _countof(args), L"i30-ce-test --child %ls", event_name) > 0);
    host.executable = executable;
    host.arguments = args;
    host.stop_event = event;
    host.surface = screen;
    host.audio = audio;
    host.log = log_event;
    host.context = &ownership;

    state.phone_attached = state.projection_selected = state.resource_budget_ok = TRUE;
    i30_supervisor_step(&host, &state, now);
    assert(!host.worker && !ownership.screen && !ownership.audio);
    state.stock_permits_projection = TRUE;
    i30_supervisor_step(&host, &state, ++now);
    assert(host.worker && !ownership.screen && !ownership.audio);
    state.heartbeat_pid = host.worker_pid + 1;
    state.heartbeat_tick = ++now;
    i30_supervisor_step(&host, &state, now);
    assert(!ownership.screen && !ownership.audio);
    state.heartbeat_pid = host.worker_pid;
    i30_supervisor_step(&host, &state, ++now);
    assert(ownership.screen && ownership.audio);

    state.stock_audio_priority = I30_STOCK_BLUETOOTH_MEDIA;
    i30_supervisor_step(&host, &state, ++now);
    assert(ownership.screen && !ownership.audio && !host.stopping);
    state.stock_surface_priority = I30_STOCK_REAR_VIEW;
    i30_supervisor_step(&host, &state, ++now);
    assert(!ownership.screen && !ownership.audio && host.worker && !host.stopping);
    state.stock_surface_priority = 0;
    i30_supervisor_step(&host, &state, ++now);
    assert(ownership.screen && !ownership.audio && !host.stopping);
    state.stock_audio_priority = I30_STOCK_CALL | I30_STOCK_PRIORITY_SOUND;
    i30_supervisor_step(&host, &state, ++now);
    assert(ownership.screen && !ownership.audio);
    state.stock_audio_priority = 0;
    i30_supervisor_step(&host, &state, ++now);
    assert(ownership.screen && ownership.audio);

    state.stock_permits_projection = FALSE;
    i30_supervisor_step(&host, &state, ++now);
    assert(!ownership.screen && !ownership.audio && host.stopping);
    assert(WaitForSingleObject(host.worker, 2000) == WAIT_OBJECT_0);
    i30_supervisor_step(&host, &state, ++now);
    assert(!host.worker && !host.failures);

    state.stock_permits_projection = TRUE;
    i30_supervisor_step(&host, &state, ++now);
    assert(host.worker && !ownership.screen && !ownership.audio);
    state.heartbeat_pid = host.worker_pid;
    state.heartbeat_tick = ++now;
    i30_supervisor_step(&host, &state, now);
    assert(ownership.screen && ownership.audio);
    assert(TerminateProcess(host.worker, 42));
    assert(WaitForSingleObject(host.worker, 2000) == WAIT_OBJECT_0);
    i30_supervisor_step(&host, &state, ++now);
    assert(!host.worker && !ownership.screen && !ownership.audio && host.failures == 1);
    i30_supervisor_step(&host, &state, now + 499);
    assert(!host.worker);
    assert(swprintf_s(args, _countof(args), L"i30-ce-test --hang") > 0);
    now += 500;
    i30_supervisor_step(&host, &state, now);
    assert(host.worker && !ownership.screen && !ownership.audio);
    state.heartbeat_pid = host.worker_pid;
    state.heartbeat_tick = ++now;
    i30_supervisor_step(&host, &state, now);
    assert(ownership.screen && ownership.audio);
    now += 2001;
    i30_supervisor_step(&host, &state, now);
    assert(!ownership.screen && !ownership.audio && host.stopping && host.failures == 2);
    now += 1000;
    i30_supervisor_step(&host, &state, now);
    assert(WaitForSingleObject(host.worker, 2000) == WAIT_OBJECT_0);
    i30_supervisor_step(&host, &state, ++now);
    assert(!host.worker && !ownership.screen && !ownership.audio);
    state.phone_attached = FALSE;
    i30_supervisor_step(&host, &state, ++now);
    assert(!host.failures);
    CloseHandle(event);

    assert(i30_playback_open(&player, WAVE_MAPPER, FALSE) == MMSYSERR_ALLOCATED);
    assert(i30_capture_open(&microphone, WAVE_MAPPER, FALSE) == MMSYSERR_ALLOCATED);
    assert(!player.handle && !microphone.handle);
    wprintf(L"Wave format query playback=%u capture=%u\n", i30_playback_query(WAVE_MAPPER), i30_capture_query(WAVE_MAPPER));
    return 0;
}
