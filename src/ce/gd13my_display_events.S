#include "ce_aa_display_events.h"

.syntax unified
.arch armv4t
.arm
.text

#ifdef I30_SYSTEM_DISPLAY
.global stock_before_rear
stock_before_rear:
    /* r4 is the decoded rear bit, r9 is the live LibSystem object. */
    cmp     r4, #0
    beq     rear_decode
    push    {r0-r3, r5, ip, lr}
    mov     r5, sp
    bic     sp, sp, #7
    mov     r0, #2                   @ EVENT_RESET before stock camera activation
    bl      change_event
    mov     sp, r5
    pop     {r0-r3, r5, ip, lr}
rear_decode:
    ldr     r3, [r9, #0x30]           @ Displaced instruction
    b       stock_decode_resume

.global stock_after_rear
stock_after_rear:
    /* Preserve stock rear teardown and use its committed state. */
    push    {r0-r3, r5, ip, lr}
    ldr     r0, [r9, #0x30]
    ldr     r1, [r9, #0x3c]
    orrs    r0, r0, r1
    bne     status_done
    mov     r5, sp
    bic     sp, sp, #7
    mov     r0, #3                   @ EVENT_SET after a confirmed neutral sample
    bl      change_event
    mov     sp, r5
status_done:
    pop     {r0-r3, r5, ip, lr}
    push    {ip}
    adr     ip, after_literal_delta
    ldr     r3, [ip]
    ldr     r3, [ip, r3]             @ Reload the original relocated literal
    pop     {ip}
    b       stock_after_resume
.balign 4
after_literal_delta:
    .word stock_after_literal - after_literal_delta
#else
.global stock_camera_request
stock_camera_request:
    /* At this export r0 is the requested rear-view visibility. */
    push    {r4, r5, r6, lr}
    mov     r4, r0
    cmp     r4, #0
    movne   r0, #3                   @ EVENT_SET before opening the stock rear view
    blne    change_event
    mov     r0, r4
    bl      stock_camera_body
    mov     r5, r0
    orrs    r0, r4, r5
    moveq   r0, #2                   @ EVENT_RESET after stock accepts rear-view off
    bleq    change_event
    mov     r0, r5
    pop     {r4, r5, r6, pc}
stock_camera_body:
    mov     r1, r0                   @ Displaced export instruction
    b       stock_camera_resume
#endif

/* Module-local slot retains the named CE event for the lifetime of its publisher. */
change_event:
    push    {r4, r5, r6, lr}
    mov     r5, r0
    adr     r4, handle_delta
    ldr     r0, [r4]
    add     r4, r4, r0
    ldr     r0, [r4]
    cmp     r0, #0
    bne     modify_event
    mov     r0, #0
    mov     r1, #1
    mov     r2, #0
    adr     r3, event_name
#ifdef I30_SYSTEM_DISPLAY
    bl      call_create
#else
    bl      stock_create_event
#endif
    cmp     r0, #0
    beq     event_done
    str     r0, [r4]
    /* Write this once so guest logs distinguish a stock publisher from a test peer. */
    mov     r6, r0
    adr     r0, started
    bl      stock_debug
    mov     r0, r6
modify_event:
    mov     r1, r5
#ifdef I30_SYSTEM_DISPLAY
    bl      call_modify
#else
    bl      stock_modify_event
#endif
event_done:
    pop     {r4, r5, r6, pc}

#ifdef I30_SYSTEM_DISPLAY
call_create:
    adr     ip, create_delta
    ldr     r2, [ip]
    ldr     ip, [ip, r2]
    mov     r2, #0
    bx      ip
call_modify:
    adr     ip, modify_delta
    ldr     r2, [ip]
    ldr     ip, [ip, r2]
    bx      ip
.balign 4
create_delta:
    .word stock_create_iat - create_delta
modify_delta:
    .word stock_modify_iat - modify_delta
#endif
handle_delta:
    .word stock_event_handle - handle_delta
event_name:
#ifdef I30_SYSTEM_DISPLAY
    .string16 I30_STOCK_DISPLAY_SAFE_NAME
started:
    .string16 "i30 OEM MICOM display publisher ready.\r\n"
#else
    .string16 I30_STOCK_CAMERA_ACTIVE_NAME
started:
    .string16 "i30 OEM rear-view publisher ready.\r\n"
#endif
