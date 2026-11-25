#include "ce_aa_native_win.h"

extern "C" {
#include "ce_aa_usb.h"
#include "ce_aa_video.h"
}
#include "ce_aa_usb_session.h"

namespace {

using WindowProc = int32_t (*)(CE_HANDLE, uint32_t, uint32_t, int32_t);
struct WindowClass {
    uint32_t style;
    WindowProc proc;
    int class_extra, window_extra;
    CE_HANDLE instance, icon, cursor, background;
    const CE_WCHAR *menu, *name;
};

struct CeFont {
    int32_t height, width, escapement, orientation, weight;
    uint8_t italic, underline, strikeout, charset, output, clip, quality, pitch;
    CE_WCHAR face[32];
};

extern "C" {
uint16_t RegisterClassW(const WindowClass *);
int GetClassInfoW(CE_HANDLE, const CE_WCHAR *, WindowClass *);
CE_HANDLE CreateWindowExW(uint32_t, const CE_WCHAR *, const CE_WCHAR *, uint32_t,
                         int, int, int, int, CE_HANDLE, CE_HANDLE, CE_HANDLE, void *);
int32_t DefWindowProcW(CE_HANDLE, uint32_t, uint32_t, int32_t);
int DestroyWindow(CE_HANDLE);
int32_t SendMessageW(CE_HANDLE, uint32_t, uint32_t, int32_t);
CE_HANDLE GetStockObject(int);
uintptr_t SetTimer(CE_HANDLE, uintptr_t, unsigned, void *);
int KillTimer(CE_HANDLE, uintptr_t);
int32_t InterlockedIncrement(volatile int32_t *);
int32_t InterlockedDecrement(volatile int32_t *);
int32_t InterlockedExchange(volatile int32_t *, int32_t);
int32_t InterlockedCompareExchange(volatile int32_t *, int32_t, int32_t);
int InvalidateRect(CE_HANDLE, const CeRect *, int);
int ValidateRect(CE_HANDLE, const CeRect *);
CE_HANDLE GetDCEx(CE_HANDLE, CE_HANDLE, uint32_t);
int ReleaseDC(CE_HANDLE, CE_HANDLE);
CE_HANDLE CreateFontIndirectW(const CeFont *);
CE_HANDLE SelectObject(CE_HANDLE, CE_HANDLE);
int DeleteObject(CE_HANDLE);
int FillRect(CE_HANDLE, const CeRect *, CE_HANDLE);
int DrawTextW(CE_HANDLE, const CE_WCHAR *, int, CeRect *, uint32_t);
int SetBkMode(CE_HANDLE, int);
uint32_t SetTextColor(CE_HANDLE, uint32_t);
int ScreenToClient(CE_HANDLE, CePoint *);
CE_HANDLE WindowFromPoint(CePoint);
}

constexpr uint32_t ws_child = 0x40000000, ws_popup = 0x80000000;
constexpr uint32_t ws_clip_siblings = 0x04000000;
constexpr uint32_t swp_nosize = 1, swp_nomove = 2, swp_nozorder = 4, swp_noactivate = 0x10;
constexpr uint32_t swp_show = 0x40, swp_hide = 0x80, swp_noownerzorder = 0x200;
constexpr uint32_t visibility_flags = swp_nosize | swp_nomove | swp_nozorder | swp_noactivate;
constexpr uint32_t wm_destroy = 2, wm_close = 0x10, wm_keydown = 0x100;
constexpr uint32_t wm_timer = 0x113, wm_mouseactivate = 0x21;
constexpr uint32_t wm_paint = 0xf, wm_erasebkgnd = 0x14, wm_lbuttondown = 0x201, wm_lbuttonup = 0x202;
constexpr uint32_t wm_mousemove = 0x200, wm_cancelmode = 0x1f, wm_capturechanged = 0x215;
constexpr uint32_t wm_stock_display_changed = 0x8001;
constexpr uintptr_t display_timer = 1;
constexpr int black_brush = 4, dark_gray_brush = 3;
constexpr CeRect map_button{300, 324, 500, 370};

struct Projection {
    CE_HANDLE map, cancel, worker, video, heading, body;
    volatile int32_t references, status;
    int32_t displayed, painted;
    bool closing, back_pressed;
    bool touch_enabled, touch_pressed, touch_reset;
    unsigned touch_head, touch_count;
    uint32_t touch_position;
    uint32_t touches[32];
};

CE_HANDLE module = reinterpret_cast<CE_HANDLE>(-1);

Projection *state_for(CE_HANDLE window)
{
    return reinterpret_cast<Projection *>(static_cast<uint32_t>(GetWindowLongW(window, CE_GWL_USERDATA)));
}

void release(Projection *state)
{
    if (InterlockedDecrement(&state->references) == 0) {
        if (state->video)
            CloseHandle(state->video);
        if (state->heading)
            DeleteObject(state->heading);
        if (state->body)
            DeleteObject(state->body);
        CloseHandle(state->cancel);
        HeapFree(GetProcessHeap(), 0, state);
    }
}

void report_status(void *argument, I30UsbProjectionStatus status)
{
    auto *state = static_cast<Projection *>(argument);
    InterlockedExchange(&state->status, status);
}

uint32_t run_usb(void *argument)
{
    auto *state = static_cast<Projection *>(argument);
    OutputDebugStringW(i30_usb_project(state->cancel, report_status, state));
    OutputDebugStringW(L"\r\n");
    if (WaitForSingleObject(state->cancel, 0) != CE_WAIT_OBJECT_0)
        report_status(state, I30_USB_UNAVAILABLE);
    release(state);
    return 0;
}

bool hide(CE_HANDLE window)
{
    return !IsWindowVisible(window) ||
           SetWindowPos(window, nullptr, 0, 0, 0, 0, visibility_flags | swp_hide);
}

const CE_WCHAR *status_text(int32_t status)
{
    switch (status) {
    case I30_USB_WAITING: return L"휴대폰 연결 대기 중";
    case I30_USB_CONNECTING: return L"휴대폰 USB 연결 중";
    case I30_USB_AUTHENTICATING: return L"휴대폰 연결됨 · 인증 확인 중";
    case I30_USB_AUTH_REQUIRED: return L"휴대폰 연결됨 · 헤드유닛 인증 설정 필요";
    case I30_USB_RECONNECT: return L"연결이 끝났습니다. USB를 다시 연결해 주세요.";
    case I30_USB_UNAVAILABLE: return L"USB 대기를 시작할 수 없습니다.";
    default: return L"휴대폰 USB 연결 준비 중";
    }
}

int draw_text(CE_HANDLE dc, CE_HANDLE font, const CE_WCHAR *text, CeRect rect)
{
    constexpr uint32_t center_single_line = 1U | 4U | 0x20U;
    CE_HANDLE previous = font ? SelectObject(dc, font) : nullptr;
    int height = DrawTextW(dc, text, -1, &rect, center_single_line);
    if (previous)
        SelectObject(dc, previous);
    return height;
}

bool video_active(const Projection *state)
{
    return state->video && WaitForSingleObject(state->video, 0) == CE_WAIT_OBJECT_0;
}

void reset_touch(Projection *state)
{
    state->touch_head = state->touch_count = 0;
    state->touch_pressed = false;
    state->touch_reset = true;
}

bool touch_visible(CE_HANDLE window, const Projection *state)
{
    return !state->closing && IsWindowVisible(window) && video_active(state) &&
           i30_projection_above_map(window, state->map) && i30_stock_display_safe();
}

uint32_t read_touch(CE_HANDLE window, Projection *state, uint32_t request)
{
    constexpr unsigned capacity = sizeof(state->touches) / sizeof(state->touches[0]);
    if (request != I30_TOUCH_READ) {
        state->touch_enabled = request == I30_TOUCH_ENABLE;
        reset_touch(state);
        return 1;
    }
    if (!state->touch_enabled || !touch_visible(window, state))
        reset_touch(state);
    if (state->touch_reset) {
        state->touch_reset = false;
        return I30_TOUCH_RESET;
    }
    if (!state->touch_count)
        return I30_TOUCH_EMPTY;
    uint32_t sample = state->touches[state->touch_head];
    state->touch_head = (state->touch_head + 1) % capacity;
    --state->touch_count;
    return sample;
}

void queue_touch(Projection *state, uint32_t message, int32_t detail)
{
    constexpr unsigned capacity = sizeof(state->touches) / sizeof(state->touches[0]);
    int x = static_cast<int16_t>(detail);
    int y = static_cast<int16_t>(static_cast<uint32_t>(detail) >> 16);
    bool inside = x >= 0 && x < I30_VIDEO_WIDTH && y >= 0 && y < I30_VIDEO_HEIGHT;
    unsigned action = message == wm_lbuttondown ? I30_TOUCH_DOWN :
                      message == wm_lbuttonup ? I30_TOUCH_UP : I30_TOUCH_MOVE;
    if (action == I30_TOUCH_DOWN ? state->touch_pressed || !inside : !state->touch_pressed)
        return;
    if (!inside) {
        x = x < 0 ? 0 : x >= I30_VIDEO_WIDTH ? I30_VIDEO_WIDTH - 1 : x;
        y = y < 0 ? 0 : y >= I30_VIDEO_HEIGHT ? I30_VIDEO_HEIGHT - 1 : y;
    }
    uint32_t position = (static_cast<unsigned>(y) << 10) | static_cast<unsigned>(x);
    if (action == I30_TOUCH_MOVE && position == state->touch_position)
        return;
    state->touch_position = position;
    uint32_t sample = (action << 19) | position;
    unsigned tail = (state->touch_head + state->touch_count) % capacity;
    unsigned previous = (tail + capacity - 1) % capacity;
    if (action == I30_TOUCH_MOVE && state->touch_count && I30_TOUCH_ACTION(state->touches[previous]) == action) {
        state->touches[previous] = sample;
    } else if (state->touch_count == capacity) {
        reset_touch(state);
    } else {
        state->touches[tail] = sample;
        ++state->touch_count;
        state->touch_pressed = action != I30_TOUCH_UP;
    }
}

void paint_status(CE_HANDLE window, Projection *state)
{
    if (state->closing || video_active(state) || !i30_stock_display_safe() ||
        !i30_projection_above_map(window, state->map))
        return;
    constexpr uint32_t cached_clipped_dc = 2U | 0x10U;
    CE_HANDLE dc = GetDCEx(window, nullptr, cached_clipped_dc);
    if (!dc)
        return;
    if (!video_active(state) && i30_stock_display_safe()) {
        const CeRect screen{0, 0, I30_VIDEO_WIDTH, I30_VIDEO_HEIGHT};
        FillRect(dc, &screen, GetStockObject(black_brush));
        SetBkMode(dc, 1); // TRANSPARENT
        SetTextColor(dc, 0x00ffffff);
        draw_text(dc, state->heading, L"Android Auto", {30, 130, 770, 198});
        int painted = draw_text(dc, state->body, status_text(state->displayed), {30, 207, 770, 269});
        FillRect(dc, &map_button, GetStockObject(dark_gray_brush));
        draw_text(dc, state->body, L"지도 돌아가기", map_button);
        if (painted && state->painted != state->displayed) {
            state->painted = state->displayed;
            if (state->painted == I30_USB_WAITING)
                OutputDebugStringW(L"i30 native USB waiting screen painted.\r\n");
            else if (state->painted == I30_USB_AUTH_REQUIRED)
                OutputDebugStringW(L"i30 native USB authentication screen painted.\r\n");
        }
    }
    ReleaseDC(window, dc);
}

bool inside_map_button(int32_t point)
{
    auto x = static_cast<int16_t>(point);
    auto y = static_cast<int16_t>(static_cast<uint32_t>(point) >> 16);
    return x >= map_button.left && x < map_button.right && y >= map_button.top && y < map_button.bottom;
}

bool panel_origin(CE_HANDLE map, CePoint &origin)
{
    CeRect rect;
    origin = {0, 0};
    return map && IsWindowVisible(map) && !(GetWindowLongW(map, CE_GWL_EXSTYLE) & CE_WS_TOPMOST) &&
           GetClientRect(map, &rect) &&
           rect.right - rect.left == I30_VIDEO_WIDTH && rect.bottom - rect.top == I30_VIDEO_HEIGHT &&
           ClientToScreen(map, &origin);
}

bool place(CE_HANDLE window, CE_HANDLE map)
{
    CePoint origin, current{0, 0};
    if (!panel_origin(map, origin) || (GetWindowLongW(window, CE_GWL_EXSTYLE) & CE_WS_TOPMOST))
        return false;
    if (i30_projection_above_map(window, map)) {
        if (!ClientToScreen(window, &current))
            return false;
        if (current.x == origin.x && current.y == origin.y)
            return true;
        return SetWindowPos(window, nullptr, origin.x, origin.y, I30_VIDEO_WIDTH, I30_VIDEO_HEIGHT,
                            swp_nozorder | swp_noactivate | swp_noownerzorder) &&
               i30_projection_above_map(window, map);
    }
    CE_HANDLE above = GetWindow(map, CE_GW_PREV);
    // Never insert at HWND_TOP across a topmost boundary. GW_OWNER may
    // already have placed the popup in the correct normal-band slot.
    if (above && (GetWindowLongW(above, CE_GWL_EXSTYLE) & CE_WS_TOPMOST))
        return false;
    return SetWindowPos(window, above, origin.x, origin.y, I30_VIDEO_WIDTH, I30_VIDEO_HEIGHT,
                        swp_noactivate | swp_noownerzorder) && i30_projection_above_map(window, map);
}

void close_projection(CE_HANDLE window, Projection *state)
{
    state->closing = true;
    reset_touch(state);
    hide(window);
    SetEvent(state->cancel);
    if (!state->worker || WaitForSingleObject(state->worker, 0) == CE_WAIT_OBJECT_0)
        DestroyWindow(window);
}

void refresh(CE_HANDLE window, Projection *state)
{
    if (state->closing || !IsWindow(state->map)) {
        close_projection(window, state);
        return;
    }
    if (!i30_stock_display_safe()) {
        reset_touch(state);
        hide(window);
        return;
    }
    if (!i30_projection_above_map(window, state->map) && !hide(window))
        return;
    if (!place(window, state->map)) {
        hide(window);
        return;
    }
    const bool showing = !IsWindowVisible(window);
    if (showing &&
        (!SetWindowPos(window, nullptr, 0, 0, 0, 0, visibility_flags | swp_show) ||
         !i30_projection_above_map(window, state->map))) {
        hide(window);
        return;
    }
    if (!state->worker) {
        InterlockedIncrement(&state->references);
        state->worker = CreateThread(nullptr, 0, run_usb, state, 0, nullptr);
        if (!state->worker) {
            release(state);
            close_projection(window, state);
        } else {
            OutputDebugStringW(L"i30 native projection placed immediately above the stock map.\r\n");
        }
    }
    int32_t status = InterlockedCompareExchange(&state->status, 0, 0);
    if (showing || status != state->displayed) {
        state->displayed = status;
        InvalidateRect(window, nullptr, 0);
    }
}

void handle_touch(CE_HANDLE window, Projection *state, uint32_t message, int32_t detail)
{
    if (video_active(state)) {
        state->back_pressed = false;
        if (state->touch_enabled && touch_visible(window, state))
            queue_touch(state, message, detail);
        else
            reset_touch(state);
    } else if (message == wm_lbuttondown) {
        state->back_pressed = inside_map_button(detail);
    } else if (message == wm_lbuttonup) {
        bool go_back = state->back_pressed && inside_map_button(detail);
        state->back_pressed = false;
        if (go_back)
            close_projection(window, state);
    }
}

int32_t window_proc(CE_HANDLE window, uint32_t message, uint32_t param, int32_t detail)
{
    Projection *state = state_for(window);
    if (state) {
        if (message == I30_TOUCH_MESSAGE)
            return read_touch(window, state, param);
        if (message == wm_cancelmode || message == wm_capturechanged)
            reset_touch(state);
        if (message == wm_paint) {
            ValidateRect(window, nullptr);
            paint_status(window, state);
            return 0;
        }
        if (message == wm_erasebkgnd)
            return 1;
        if (message == wm_lbuttondown || message == wm_lbuttonup || message == wm_mousemove) {
            handle_touch(window, state, message, detail);
            return 0;
        }
        if ((message == wm_timer && param == display_timer) || message == wm_stock_display_changed) {
            refresh(window, state);
            return 0;
        }
        if (message == wm_close || (message == wm_keydown && param == 27)) {
            close_projection(window, state);
            return 0;
        }
        if (message == wm_destroy) {
            SetWindowLongW(window, CE_GWL_USERDATA, 0);
            KillTimer(window, display_timer);
            SetEvent(state->cancel);
            if (state->worker)
                CloseHandle(state->worker);
            release(state);
        }
    }
    if (message == wm_mouseactivate)
        return 3; // MA_NOACTIVATE.
    return DefWindowProcW(window, message, param, detail);
}

} // namespace

extern "C" int I30RouteProjectionTouch(CE_HANDLE source, uint32_t message, int32_t detail)
{
    CE_HANDLE window = FindWindowW(I30_NAVIGATION_PROJECTION_CLASS, nullptr);
    if (!source || !window || message < wm_mousemove || message > wm_lbuttonup)
        return 0;
    auto *state = state_for(window);
    if (!state || state->closing || !IsWindowVisible(window) || !i30_stock_display_safe() ||
        !i30_projection_above_map(window, state->map))
        return 0;
    if (source != window) {
        CE_HANDLE root = source;
        while (root && (GetWindowLongW(root, CE_GWL_STYLE) & ws_child))
            root = GetParent(root);
        if (root != state->map)
            return 0;
        CePoint point{static_cast<int16_t>(detail), static_cast<int16_t>(static_cast<uint32_t>(detail) >> 16)};
        if (!ClientToScreen(source, &point))
            return 0;
        CE_HANDLE hit = WindowFromPoint(point);
        if ((hit != window && hit != source && hit != state->map) || !ScreenToClient(window, &point)) {
            reset_touch(state);
            return 0;
        }
        detail = static_cast<int32_t>((static_cast<uint32_t>(point.y) << 16) | (static_cast<uint32_t>(point.x) & 0xffffU));
    }
    handle_touch(window, state, message, detail);
    return 1;
}

extern "C" int i30_ce_entry(CE_HANDLE instance, uint32_t reason, void *)
{
    if (reason == 1) // DLL_PROCESS_ATTACH
        module = instance;
    return 1;
}

extern "C" int I30ToggleProjection(CE_HANDLE menu)
{
    CE_HANDLE map = menu;
    while (map && (GetWindowLongW(map, CE_GWL_STYLE) & ws_child))
        map = GetParent(map);
    CePoint origin;
    if (!panel_origin(map, origin)) {
        OutputDebugStringW(L"i30 native projection found no visible 800x480 stock map owner.\r\n");
        return 0;
    }
    if (!i30_usb_file_exists(I30_AA_DRIVER_PATH)) {
        OutputDebugStringW(L"i30 native projection could not find the CE USB module.\r\n");
        return 0;
    }
    if (CE_HANDLE existing = FindWindowW(I30_NAVIGATION_PROJECTION_CLASS, nullptr)) {
        Projection *state = state_for(existing);
        if (!state || state->map != map)
            return 0;
        close_projection(existing, state);
        return 1;
    }
    WindowClass klass = {0, window_proc, 0, 0, module, nullptr, nullptr, GetStockObject(black_brush),
                         nullptr, I30_NAVIGATION_PROJECTION_CLASS};
    WindowClass installed;
    if (!RegisterClassW(&klass) &&
        (!GetClassInfoW(module, klass.name, &installed) || installed.proc != window_proc))
        return 0;
    auto *state = static_cast<Projection *>(HeapAlloc(GetProcessHeap(), 0, sizeof(Projection)));
    if (!state)
        return 0;
    *state = {};
    state->map = map;
    state->cancel = CreateEventW(nullptr, 1, 0, nullptr);
    state->references = 1;
    state->status = state->displayed = I30_USB_STARTING;
    state->painted = -1;
    if (!state->cancel) {
        HeapFree(GetProcessHeap(), 0, state);
        return 0;
    }
    state->video = CreateEventW(nullptr, 1, 0, I30_AA_VIDEO_ACTIVE);
    if (!state->video) {
        release(state);
        return 0;
    }
    CeFont font{};
    font.charset = 129; // HANGEUL_CHARSET
    font.height = -36;
    font.weight = 700;
    state->heading = CreateFontIndirectW(&font);
    font.height = -25;
    font.weight = 400;
    state->body = CreateFontIndirectW(&font);
    CE_HANDLE window = CreateWindowExW(0, klass.name, L"Android Auto · i30", ws_popup | ws_clip_siblings,
                                      origin.x, origin.y, I30_VIDEO_WIDTH, I30_VIDEO_HEIGHT,
                                      map, nullptr, module, nullptr);
    uint32_t map_process = 0, window_process = 0;
    uint32_t map_thread = GetWindowThreadProcessId(map, &map_process);
    if (!window || !map_thread || GetWindowThreadProcessId(window, &window_process) != map_thread ||
        map_process != window_process) {
        if (window)
            DestroyWindow(window);
        release(state);
        return 0;
    }
    SetWindowLongW(window, CE_GWL_USERDATA, static_cast<int32_t>(reinterpret_cast<uintptr_t>(state)));
    if (state_for(window) != state) {
        DestroyWindow(window);
        release(state);
        return 0;
    }
    if (!SetTimer(window, display_timer, 50, nullptr)) {
        DestroyWindow(window);
        return 0;
    }
    if (!i30_stock_display_safe())
        OutputDebugStringW(L"i30 native projection waiting for stock display permission.\r\n");
    refresh(window, state);
    return 1;
}

extern "C" void I30StockDisplayChanged(void)
{
    if (CE_HANDLE window = FindWindowW(I30_NAVIGATION_PROJECTION_CLASS, nullptr))
        SendMessageW(window, wm_stock_display_changed, 0, 0);
}
