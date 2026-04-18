.text
  .org 0x0000
      jmp start

  .org 0x0010
  trap_handler:
      in 0
      pop_m char_tmp

      push_m char_tmp
      jz eof

      push_m char_tmp
      out 1

      iret

  eof:
      halt

  .data
  .org 0x0020
  char_tmp: .word 0

  .text
  .org 0x0100
  start:
      ei

  idle:
      jmp idle
