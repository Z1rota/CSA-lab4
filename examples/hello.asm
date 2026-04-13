%define PORT_IN 0
%define PORT_OUT 1
%define STRING_ADDR 200

.data
.org 0x00C8 ; 200 в десятичной
msg: .pstr "Hello" ; Данные лежат тут (200=длина, 201='H'...)
counter: .word 0

.text
.org 0x0000
    EI
main_loop:
    ; Бесконечный цикл, ждем пока не напечатаем 5 символов
    PUSH_M counter
    PUSH 5
    CMP
    JZ main_loop

end:
    HALT

.org 0x0010 ; Вектор прерываний
    ; Читаем порт
    IN PORT_IN
    ; Выводим обратно (эхо)
    OUT PORT_OUT

    ; Увеличиваем счетчик (чтобы выйти из программы)
    PUSH_M counter
    PUSH 1
    ADD
    POP_M counter
    IRET