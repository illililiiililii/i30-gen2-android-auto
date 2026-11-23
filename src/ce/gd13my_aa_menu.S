#include "ce_startup_pref.h"

/* ARM trampoline before GD13MY Korean .061 CNaviMain dispatches touch.
 * fp is the active shot ID, sb is MSG, and r8 is the stock state base.
 * Swallow both edges in the added controls. Stock dispatch can otherwise open
 * a different view on the press before the Android Auto release is processed.
 */
.syntax unified
.arch armv4t
.arm
.text
.global _start
_start:
    ldr     r3, [sb, #4]              @ Displaced load of MSG.message
    sub     ip, r3, #512
    sub     ip, ip, #1
    cmp     ip, #1                   @ WM_LBUTTONDOWN or WM_LBUTTONUP
    bhi     resume
    cmp     fp, #101                 @ SHOT_NMN09, Navigation Settings > Other
    beq     settings_hit
    cmp     fp, #24                  @ SHOT_NMN01, Navigation Menu
    bne     resume
    ldrh    ip, [sb, #0xc]
    sub     ip, ip, #332
    sub     ip, ip, #3
    cmp     ip, #129
    bhs     resume
    ldrh    ip, [sb, #0xe]
    sub     ip, ip, #412
    cmp     ip, #53
    bhs     resume
    tst     r3, #1
    bne     consumed                @ Down: prevent the underlying stock hit
    b       manual_launch
settings_hit:
    ldrh    ip, [sb, #0xc]
    sub     ip, ip, #656
    sub     ip, ip, #2
    cmp     ip, #129
    bhs     resume
    ldrh    ip, [sb, #0xe]
    sub     ip, ip, #155
    cmp     ip, #53
    bhs     resume
    tst     r3, #1
    bne     consumed

    /* Preserve caller inputs and align SP for calls from the stock frame. */
    push    {r0-r3, r5, lr}
    mov     r5, sp
    bic     sp, sp, #7

    mov     r0, #0
    adr     r1, dialog_title
    bl      stock_find_window
    cmp     r0, #0
    beq     create_process
    bl      stock_foreground
    b       launch_done

manual_launch:
    push    {r0-r3, r5, lr}
    mov     r5, sp
    bic     sp, sp, #7

#ifdef I30_NATIVE_PROJECTION
    adrl    r0, native_module
    bl      stock_get_module
    cmp     r0, #0
    bne     resolve_native
    adrl    r0, native_path
    bl      stock_load_library
    cmp     r0, #0
    beq     launch_done
resolve_native:
    adrl    r1, native_entry
    adrl    ip, get_proc_delta
    ldr     r2, [ip]
    ldr     ip, [ip, r2]
    mov     lr, pc
    bx      ip
    cmp     r0, #0
    beq     launch_done
    mov     ip, r0
    ldr     r0, [sb]                  @ MSG.hwnd, in the original navigation UI thread
    mov     lr, pc
    bx      ip
    b       launch_done
#endif

    /* CreateProcessW takes ten arguments. PROCESS_INFORMATION is four words. */
create_process:
    sub     sp, sp, #80
    mov     r1, #0
    mov     r2, #0
    mov     r3, #0
    stmia   sp, {r1-r3}
    str     r1, [sp, #12]
    str     r1, [sp, #16]
    add     ip, sp, #24
    str     ip, [sp, #20]
    stmia   ip, {r1-r3}
    str     r1, [ip, #12]
#ifndef I30_NATIVE_PROJECTION
    cmp     fp, #24
    bne     launch
    adr     ip, manual_args
    ldmia   ip, {r0-r3}
    add     ip, sp, #40
    stmia   ip!, {r0-r3}
    ldr     r0, [sb]                  @ MSG.hwnd of the menu that received the tap
    mov     r1, #8
encode_owner:
    mov     r2, r0, lsr #28
    cmp     r2, #9
    addls   r2, r2, #48
    addhi   r2, r2, #87
    strh    r2, [ip], #2
    mov     r0, r0, lsl #4
    subs    r1, r1, #1
    bne     encode_owner
    mov     r2, #0
    strh    r2, [ip]
    add     r1, sp, #40
    mov     r2, #0
    mov     r3, #0
launch:
#endif
    adr     r0, app_path
    bl      stock_create_process
    cmp     r0, #0
    beq     launch_done
    ldr     r0, [sp, #28]
    cmp     r0, #0
    blne    stock_close_handle
    ldr     r0, [sp, #24]
    cmp     r0, #0
    blne    stock_close_handle
launch_done:
    mov     sp, r5
    pop     {r0-r3, r5, lr}
consumed:
    mvn     r7, #0                   @ Stock handled-message return
    b       stock_consumed
resume:
    b       stock_resume
dialog_title:
    .string16 "Android Auto"
app_path:
    .string16 "\\DiskA\\Application\\NAVI\\i30aa.exe"
#ifdef I30_NATIVE_PROJECTION
native_module:
    .string16 "i30nav.dll"
native_path:
    .string16 "\\DiskA\\Application\\NAVI\\i30nav.dll"
native_entry:
    .string16 "I30ToggleProjection"
    .balign 4
get_proc_delta:
    .word stock_get_proc_iat - get_proc_delta
#else
    .balign 4
manual_args:
    .string16 I30_PROJECTION_COMMAND
#endif
