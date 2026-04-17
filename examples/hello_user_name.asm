.data
prompt_str: .pstr "What is your name?\n"
hello_str:  .pstr "Hello, "
excl_str:   .pstr "!\n"

name_buf: .word 0
          .org 0x0100

char: .word 0
pstr_ptr: .word 0
pstr_len: .word 0
pstr_idx: .word 0

.text
.org 0x0200
_start:
    push prompt_str
    call print_pstr

    push name_buf
    push 0
    store

read_loop:
    in 0
    pop_m char

    push_m char
    jz print_hello

    push_m char
    push 10
    sub
    jz print_hello

    push name_buf
    push name_buf
    load
    add
    push 1
    add
    push_m char
    store

    push name_buf
    push name_buf
    load
    push 1
    add
    store

    jmp read_loop

print_hello:
    push hello_str
    call print_pstr

    push name_buf
    call print_pstr

    push excl_str
    call print_pstr
    halt

print_pstr:
    pop_m pstr_ptr
    push_m pstr_ptr
    load
    pop_m pstr_len

    push 1
    pop_m pstr_idx
print_loop:
    push_m pstr_idx
    push_m pstr_len
    gt
    jz print_char
    ret
print_char:
    push_m pstr_ptr
    push_m pstr_idx
    add
    load
    out 1

    push_m pstr_idx
    push 1
    add
    pop_m pstr_idx
    jmp print_loop