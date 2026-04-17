.data
max_pal: .word 0
i:       .word 999
j:       .word 999
prod:    .word 0


temp:    .word 0
rev:     .word 0

.text
_start:
loop_i:
    push_m i
    push 99
    gt
    jz print_res

    push_m i
    pop_m j


loop_j:
    push_m j
    push 99
    gt
    jz next_i


    push_m i
    push_m j
    mul
    pop_m prod


    push_m prod
    push_m max_pal
    gt
    jz next_i

    call check_pal
    jz next_j

    push_m prod
    pop_m max_pal

next_j:
    ; j = j - 1
    push_m j
    push 1
    sub
    pop_m j
    jmp loop_j

next_i:
    ; i = i - 1
    push_m i
    push 1
    sub
    pop_m i
    jmp loop_i

print_res:
    push_m max_pal
    out 2
    push 10
    out 1
    halt



check_pal:
    ; rev = 0
    push 0
    pop_m rev
    ; temp = prod
    push_m prod
    pop_m temp

pal_loop:
    push_m temp
    push 0
    gt
    jz pal_end

    ; rev = rev * 10
    push_m rev
    push 10
    mul

    ; digit = temp % 10
    push_m temp
    push 10
    mod

    ; rev = rev + digit
    add
    pop_m rev

    ; temp = temp / 10
    push_m temp
    push 10
    div
    pop_m temp

    jmp pal_loop

pal_end:

    push_m prod
    push_m rev
    cmp
    ret