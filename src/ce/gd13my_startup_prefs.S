#include "ce_startup_pref.h"

.syntax unified
.arm
.text
.global startup_prefs
.type startup_prefs, %function
startup_prefs:
    push {r0-r3, r5-r7, lr}
    ldrb r0, [r10, #3]            @ ACK source app, before stock normalizes it
    cmp r0, #2
    bne finish
    ldr r0, [r9, #0x4f4]         @ Stock current app
    cmp r0, #2
    bne finish
    ldrb r0, [r9, #0x7c2]        @ No pending mode switch in NAVI MAIN ACK
    cmp r0, #0
    bne finish
    adrl r0, auto_path
    bl selected
    cmp r0, #0
    beq finish

    mov r0, #0
    mov r1, #1
    mov r2, #0
    adrl r3, gate_name
    bl stock_create_event
    movs r7, r0
    beq finish
    bl stock_last_error
    cmp r0, #183                   @ ERROR_ALREADY_EXISTS
    bne first_time
    mov r0, r7
    bl stock_close
    b finish

first_time:
    @ Keep the first event handle for the lifetime of the system manager.
    @ The event serializes subsequent NAVI-ready notifications this boot.
    adrl r0, startup_args
    bl spawn_settings
finish:
    pop {r0-r3, r5-r7, lr}
    mov r5, #1                     @ Displaced stock instruction
    b stock_resume

.global clock_entry
.type clock_entry, %function
clock_entry:
    push {r0-r3, r5-r7, lr}
    adrl r0, emulator_clock_path
    bl selected
    cmp r0, #0
    beq clock_done
    adrl r0, clock_args
    bl spawn_settings
clock_done:
    pop {r0-r3, r5-r7, lr}
    b stock_entry

spawn_settings:
    push {r4, lr}
    @ The startup argument is a writable buffer for CreateProcessW.
    mov r4, r0
    sub sp, sp, #64
    mov r0, #0
    mov r1, #0
    mov r2, #0
    mov r3, #0
    stmia sp, {r0-r3}
    str r0, [sp, #16]
    add r1, sp, #24               @ PROCESS_INFORMATION
    str r1, [sp, #20]
    add r2, sp, #40
    ldmia r4, {r0, r3, r5-r7}
    stmia r2, {r0, r3, r5-r7}
    adrl r0, launcher
    mov r1, r2
    mov r2, #0
    mov r3, #0
    bl stock_create_process
    cmp r0, #0
    beq spawn_done
    ldr r0, [sp, #24]
    bl stock_close
    ldr r0, [sp, #28]
    bl stock_close
spawn_done:
    add sp, sp, #64
    pop {r4, pc}

selected:
    push {r4, lr}
    bl stock_attributes
    cmn r0, #1
    @ A missing path and a directory both use the unchecked default.
    beq not_selected
    tst r0, #16
    moveq r0, #1
    movne r0, #0
    pop {r4, pc}
not_selected:
    mov r0, #0
    pop {r4, pc}

.balign 4
startup_args:
    .string16 I30_STARTUP_COMMAND
    .balign 4
clock_args:
    .string16 I30_EMULATOR_CLOCK_COMMAND
    .balign 4
auto_path:
    .string16 I30_USB_STARTUP_PREF
emulator_clock_path:
    .string16 I30_EMULATOR_UTC_FILE
gate_name:
    .string16 "I30.GD13MY.Startup.1"
launcher:
    .string16 "\\DiskA\\Application\\NAVI\\i30aa.exe"
