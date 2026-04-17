.data
char_tmp: .word 0

.text
_start:
loop:
    in 0                ; Читаем символ в стек
    pop_m char_tmp      ; Сохраняем в память
    push_m char_tmp     ; Возвращаем в стек для проверки
    jz end              ; Если 0 (EOF) - выходим

    push_m char_tmp     ; Возвращаем в стек для вывода
    out 1               ; Выводим символ
    jmp loop
end:
    halt