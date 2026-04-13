%define PORT_CHAR_OUT 1
%define PORT_INT_OUT 2
%define MAX_NUM 999
%define MIN_NUM 99

.data
.org 0x0100
max_pal:  .word 0
a:        .word 0
b:        .word 0
product:  .word 0
temp:     .word 0
reversed: .word 0
rem:      .word 0

.text
.org 0x0000
start:
    PUSH MAX_NUM
    POP_M a

loop_a:
    ; if a == 9 -> print_result
    PUSH_M a
    PUSH MIN_NUM
    CMP
    PUSH 0     ; инверсия для JZ
    CMP
    JZ print_result

    ; b = a (начинаем внутренний цикл от a, чтобы не проверять дубликаты)
    PUSH_M a
    POP_M b

loop_b:
    ; if b == 9 -> next_a
    PUSH_M b
    PUSH MIN_NUM
    CMP
    PUSH 0     ; инверсия
    CMP
    JZ next_a

    ; product = a * b
    PUSH_M a
    PUSH_M b
    MUL
    POP_M product

    ; if max_pal > product -> next_a
    ; (т.к. b уменьшается, дальше произведения будут только меньше, смело берем следующее a)
    PUSH_M max_pal
    PUSH_M product
    GT
    PUSH 0     ; инверсия
    CMP
    JZ next_a

    ; --- Проверка на палиндром ---
    PUSH_M product
    POP_M temp

    PUSH 0
    POP_M reversed

reverse_loop:
    ; if temp == 0 -> check_pal
    PUSH_M temp
    PUSH 0
    CMP
    PUSH 0     ; инверсия
    CMP
    JZ check_pal

    ; rem = temp % 10
    PUSH_M temp
    PUSH 10
    MOD
    POP_M rem

    ; reversed = reversed * 10 + rem
    PUSH_M reversed
    PUSH 10
    MUL
    PUSH_M rem
    ADD
    POP_M reversed

    ; temp = temp / 10
    PUSH_M temp
    PUSH 10
    DIV
    POP_M temp

    JMP reverse_loop

check_pal:
    ; if product == reversed -> update_max
    PUSH_M product
    PUSH_M reversed
    CMP
    PUSH 0     ; инверсия
    CMP
    JZ update_max
    JMP next_b

update_max:
    PUSH_M product
    POP_M max_pal

next_b:
    ; b = b - 1
    PUSH_M b
    PUSH 1
    SUB
    POP_M b
    JMP loop_b

next_a:
    ; a = a - 1
    PUSH_M a
    PUSH 1
    SUB
    POP_M a
    JMP loop_a

print_result:
    ; Выводим ответ через числовой порт
    PUSH_M max_pal
    OUT PORT_INT_OUT
    HALT