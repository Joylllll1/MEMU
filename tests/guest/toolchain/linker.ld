ENTRY(_start)

PHDRS {
  text PT_LOAD FLAGS(5);
  data PT_LOAD FLAGS(6);
}

SECTIONS {
  . = 0x80000000;

  .text : {
    *(.text.start)
    *(.text*)
  } :text

  .rodata : {
    *(.rodata*)
  } :text

  .data : {
    *(.sdata*)
    *(.data*)
  } :data

  .bss : {
    *(.sbss*)
    *(.bss*)
    *(COMMON)
  } :data

  . = ALIGN(16);
  _end = .;
}
