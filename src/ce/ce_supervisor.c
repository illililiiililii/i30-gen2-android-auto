#include "ce_supervisor.h"

#define I30_START_LIMIT 8000U
#define I30_HEARTBEAT_LIMIT 2000U
#define I30_STOP_LIMIT 1000U
#define I30_RETRY_DELAY 500U
#define I30_MAX_FAILURES 2U

static void report(I30Supervisor *host, LPCWSTR message, DWORD detail)
{
    if (host->log)
        host->log(host->context, message, detail);
}

static void stock(I30Supervisor *host)
{
    if (host->visible) {
        if (host->surface(host->context, FALSE))
            host->visible = FALSE;
        else
            report(host, L"stock_surface_restore_failed", 0);
    }
}

static void audio(I30Supervisor *host, BOOL projected)
{
    if (host->audio && host->projected_audio != projected) {
        if (host->audio(host->context, projected))
            host->projected_audio = projected;
        else
            report(host, L"projection_audio_ownership_failed", (DWORD)projected);
    }
}

static void failed(I30Supervisor *host, DWORD now)
{
    if (host->failures < I30_MAX_FAILURES)
        ++host->failures;
    host->exited = now;
    host->waiting_retry = TRUE;
}

static void stop(I30Supervisor *host, DWORD now)
{
    if (host->stopping)
        return;
    host->stopping = TRUE;
    host->stop_started = now;
    if (!SetEvent(host->stop_event))
        report(host, L"stop_event_failed", GetLastError());
}

static void start(I30Supervisor *host, DWORD now)
{
    PROCESS_INFORMATION child;
#ifndef _WIN32_WCE
    STARTUPINFOW desktop_start;
    ZeroMemory(&desktop_start, sizeof(desktop_start));
    desktop_start.cb = sizeof(desktop_start);
#endif

    if (!ResetEvent(host->stop_event) || !CreateProcessW(host->executable, host->arguments,
            NULL, NULL, FALSE, 0, NULL, NULL,
#ifdef _WIN32_WCE
            NULL,
#else
            &desktop_start,
#endif
            &child)) {
        report(host, L"worker_start_failed", GetLastError());
        failed(host, now);
        return;
    }
    CloseHandle(child.hThread);
    host->worker = child.hProcess;
    host->worker_pid = child.dwProcessId;
    host->started = now;
    host->waiting_retry = FALSE;
    report(host, L"worker_started", host->worker_pid);
}

void i30_supervisor_step(I30Supervisor *host, const I30HostState *state, DWORD now)
{
    BOOL admitted = state->phone_attached && state->projection_selected &&
                    state->stock_permits_projection && state->resource_budget_ok;
    BOOL allow_surface = admitted && state->stock_surface_priority == 0;
    DWORD wait_result, exit_code;
    BOOL heartbeat;

    if (!allow_surface)
        stock(host);
    if (!allow_surface || state->stock_audio_priority)
        audio(host, FALSE);
    if (host->worker) {
        wait_result = WaitForSingleObject(host->worker, 0);
        if (wait_result == WAIT_OBJECT_0) {
            stock(host);
            audio(host, FALSE);
            if (GetExitCodeProcess(host->worker, &exit_code))
                report(host, L"worker_exited", exit_code);
            else
                report(host, L"worker_exit_code_failed", GetLastError());
            CloseHandle(host->worker);
            host->worker = NULL;
            host->worker_pid = 0;
            if (!host->stopping && admitted)
                failed(host, now);
            host->stopping = host->force_sent = FALSE;
        } else if (wait_result != WAIT_TIMEOUT) {
            report(host, L"worker_wait_failed", GetLastError());
            stock(host);
            audio(host, FALSE);
            stop(host, now);
        }
    }
    if (!state->phone_attached) {
        host->failures = 0;
        host->waiting_retry = FALSE;
    }
    if (!host->worker) {
        if (allow_surface && !host->visible && host->failures < I30_MAX_FAILURES &&
                (!host->waiting_retry || now - host->exited >= I30_RETRY_DELAY))
            start(host, now);
        return;
    }
    if (!admitted)
        stop(host, now);
    if (host->stopping) {
        if (!host->force_sent && now - host->stop_started >= I30_STOP_LIMIT) {
            host->force_sent = TRUE;
            if (TerminateProcess(host->worker, ERROR_TIMEOUT))
                report(host, L"worker_stop_timeout", host->worker_pid);
            else
                report(host, L"worker_terminate_failed", GetLastError());
        }
        return;
    }

    heartbeat = state->heartbeat_pid == host->worker_pid &&
                now - state->heartbeat_tick <= I30_HEARTBEAT_LIMIT &&
                state->heartbeat_tick - host->started <= now - host->started;
    if (heartbeat) {
        if (allow_surface && !host->visible)
            host->visible = host->surface(host->context, TRUE);
        if (allow_surface && host->visible && !state->stock_audio_priority)
            audio(host, TRUE);
    } else if (host->visible || now - host->started >= I30_START_LIMIT) {
        stock(host);
        audio(host, FALSE);
        failed(host, now);
        stop(host, now);
        report(host, L"worker_heartbeat_timeout", host->worker_pid);
    }
}
