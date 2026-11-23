OUTPUT_ARCH(arm)
ENTRY(i30_ce_entry)

SECTIONS {
    . = 0x11000;
    .text : { *(.text .text.*) }
    . = ALIGN(0x1000);
    .rdata : { *(.rodata .rodata.*) }
    . = ALIGN(0x1000);
    .idata : { KEEP(*(.ce_import)) }
    . = ALIGN(0x1000);
    .data : { *(.data .data.*) }
    .bss (NOLOAD) : { *(.bss .bss.* COMMON) }
    /DISCARD/ : { *(.comment .note* .ARM.exidx* .ARM.extab*) }
}

ASSERT(SIZEOF(.bss) == 0, "The minimal probe cannot contain uninitialized globals")
