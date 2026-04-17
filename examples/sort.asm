.data
; Массив: первое слово - длина (5), далее сами элементы
arr_addr: .word 5
          .word 42
          .word 12
          .word 88
          .word 5
          .word 19

n:     .word 0
i:     .word 0
j:     .word 0
addr1: .word 0
addr2: .word 0
val1:  .word 0
val2:  .word 0

.text
.org 0x0100
_start:
    push 0
    load
    pop_m n

    push 0
    pop_m i
loop_i:

    push_m i
    push_m n
    push 2
    sub
    gt
    jz start_j
    jmp print_arr
start_j:
    push 0
    pop_m j
loop_j:

    push_m j
    push_m n
    push_m i
    sub
    push 2
    sub
    gt
    jz do_compare
    jmp end_j

do_compare:

    push 0
    push 1
    add
    push_m j
    add
    pop_m addr1

    push_m addr1
    push 1
    add
    pop_m addr2


    push_m addr1
    load
    pop_m val1

    push_m addr2
    load
    pop_m val2

    push_m val1
    push_m val2
    gt
    jz next_j

    push_m addr1
    push_m val2
    store

    push_m addr2
    push_m val1
    store

next_j:
    push_m j
    push 1
    add
    pop_m j
    jmp loop_j

end_j:
    push_m i
    push 1
    add
    pop_m i
    jmp loop_i

print_arr:
    push 0
    pop_m i
print_loop:
    push_m i
    push_m n
    push 1
    sub
    gt
    jz do_print
    halt
do_print:
    push 0
    push 1
    add
    push_m i
    add
    load
    out 2

    push 32
    out 1

    push_m i
    push 1
    add
    pop_m i
    jmp print_loop