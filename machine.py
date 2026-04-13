import sys
import ast
import logging
from isa import Opcode, read_code, decode_instruction

logging.basicConfig(level=logging.INFO, format="%(message)s")


class DataPath:
    """Тракт данных. Включает память, АЛУ, аппаратные стеки и порты ввода/вывода."""

    def __init__(
        self,
        memory_size: int,
        memory_init: list[int],
        io_schedule: list[tuple[int, str]],
    ):
        self.memory = memory_init + [0] * (memory_size - len(memory_init))
        self.data_stack: list[int] = []
        self.return_stack: list[int] = []

        # Теневой регистр
        self.shadow_data = 0
        self.shadow_addr = -1
        self.shadow_busy_ticks = 0
        self.shadow_pending = False

        self.schedule = io_schedule
        self.port_in_buffer: list[str] = []
        self.out_buffer = ""
        self.interrupt_pin = False

    def tick_background(self, current_tick: int) -> str:
        bg_log = ""
        if self.shadow_busy_ticks > 0:
            self.shadow_busy_ticks -= 1
            if self.shadow_busy_ticks == 0 and self.shadow_pending:
                self.memory[self.shadow_addr] = self.shadow_data
                self.shadow_pending = False
                bg_log = f" [MemWrite: {self.shadow_addr} <- {self.shadow_data}]"

        while self.schedule and current_tick >= self.schedule[0][0]:
            _, char = self.schedule.pop(0)
            self.port_in_buffer.append(char)
            self.interrupt_pin = True

        return bg_log

    def trigger_shadow_write(self, addr: int, data: int):
        self.shadow_data = data
        self.shadow_addr = addr
        self.shadow_busy_ticks = 2
        self.shadow_pending = True

    def is_shadow_match(self, addr: int) -> bool:
        return self.shadow_addr == addr

    def push(self, val: int):
        self.data_stack.append(val)

    def pop(self) -> int:
        return self.data_stack.pop() if self.data_stack else 0

    def alu_op(self, opcode: Opcode):
        if opcode == Opcode.ADD:
            self.push(self.pop() + self.pop())
        elif opcode == Opcode.SUB:
            b, a = self.pop(), self.pop()
            self.push(a - b)
        elif opcode == Opcode.MUL:
            self.push(self.pop() * self.pop())
        elif opcode == Opcode.DIV:
            b, a = self.pop(), self.pop()
            self.push(a // b if b != 0 else 0)
        elif opcode == Opcode.MOD:
            b, a = self.pop(), self.pop()
            self.push(a % b if b != 0 else 0)
        elif opcode == Opcode.CMP:
            self.push(1 if self.pop() == self.pop() else 0)
        elif opcode == Opcode.GT:
            b, a = self.pop(), self.pop()
            self.push(1 if a > b else 0)

    def io_read(self, port: int):
        if port == 0:
            val = ord(self.port_in_buffer.pop(0)) if self.port_in_buffer else 0
            self.push(val)

    def io_write(self, port: int):
        val = self.pop()
        if port == 1:
            self.out_buffer += chr(val % 256)
        else:
            self.out_buffer += str(val)


class ControlUnit:
    """Блок управления. Динамическое планирование, разрешение зависимостей и прерывания."""

    def __init__(self, data_path: DataPath, max_log_ticks: int = 1500):
        self.dp = data_path
        self.pc = 0
        self.tick = 0
        self.stall_ticks = 0
        self.ie = False
        self.halted = False
        self.bypass_log = ""
        self.max_log_ticks = max_log_ticks

    def log_state(self, msg: str):
        if self.tick <= self.max_log_ticks:
            logging.info(msg)
        elif self.tick == self.max_log_ticks + 1:
            logging.info(
                "\n[... Потактовый лог отключен после {self.max_log_ticks} ради производительности ...]"
            )
            logging.info("[...Процессор продолжает вычисления в фоновом режиме...]\n")

    def can_superscalar(self, op1: Opcode, op2: Opcode) -> bool:
        alu_ops = {
            Opcode.PUSH,
            Opcode.ADD,
            Opcode.SUB,
            Opcode.MUL,
            Opcode.DIV,
            Opcode.MOD,
            Opcode.CMP,
            Opcode.GT,
            Opcode.IN,
        }
        if op1 in alu_ops and op2 == Opcode.POP_M:
            if self.dp.shadow_busy_ticks > 0:
                return False
            return True
        if op1 in alu_ops and op2 in {Opcode.JMP, Opcode.JZ, Opcode.RET}:
            return True
        return False

    def execute_single(self, opcode: Opcode, arg: int):
        if opcode == Opcode.NOP:
            pass
        elif opcode == Opcode.HALT:
            self.halted = True
        elif opcode in {
            Opcode.ADD,
            Opcode.SUB,
            Opcode.MUL,
            Opcode.DIV,
            Opcode.MOD,
            Opcode.CMP,
            Opcode.GT,
        }:
            self.dp.alu_op(opcode)
        elif opcode == Opcode.PUSH:
            self.dp.push(arg)
        elif opcode == Opcode.PUSH_M:
            if self.dp.is_shadow_match(arg):
                self.dp.push(self.dp.shadow_data)
                self.stall_ticks = 0
                self.bypass_log = " [Reverse SWAP bypass]"
            else:
                self.dp.push(self.dp.memory[arg])
                self.stall_ticks = 1
        elif opcode == Opcode.POP_M:
            self.dp.trigger_shadow_write(arg, self.dp.pop())
        elif opcode == Opcode.IN:
            self.dp.io_read(arg)
        elif opcode == Opcode.OUT:
            self.dp.io_write(arg)
        elif opcode == Opcode.JMP:
            self.pc = arg
        elif opcode == Opcode.JZ:
            if self.dp.pop() == 0:
                self.pc = arg
        elif opcode == Opcode.CALL:
            self.dp.return_stack.append(self.pc)
            self.pc = arg
        elif opcode == Opcode.RET:
            self.pc = self.dp.return_stack.pop()
        elif opcode == Opcode.EI:
            self.ie = True
        elif opcode == Opcode.IRET:
            self.pc = self.dp.return_stack.pop()
            self.ie = True

    def process_next_tick(self):
        self.tick += 1
        self.bypass_log = ""
        bg_log = self.dp.tick_background(self.tick)

        if self.dp.interrupt_pin and self.ie:
            self.dp.interrupt_pin = False
            self.ie = False
            self.dp.return_stack.append(self.pc)
            self.pc = 0x0010
            self.log_state(f"Tick: {self.tick:04d} |INTERRUPT TRAP")
            return

        if self.stall_ticks > 0:
            self.stall_ticks -= 1
            self.log_state(
                f"Tick: {self.tick:04d} | PC: {self.pc:04X} | PIPELINE STALL (Wait for Mem){bg_log}"
            )
            return

        word1 = self.dp.memory[self.pc]
        word2 = self.dp.memory[self.pc + 1]
        op1, arg1 = decode_instruction(word1)
        op2, arg2 = decode_instruction(word2)

        if op1 in {Opcode.PUSH_M, Opcode.POP_M} and self.dp.shadow_busy_ticks > 0:
            if op1 == Opcode.PUSH_M and self.dp.is_shadow_match(arg1):
                pass
            else:
                self.stall_ticks = 1
                self.log_state(
                    f"Tick: {self.tick:04d} | PC: {self.pc:04X} | STRUCTURAL STALL (Shadow Busy){bg_log}"
                )
                return

        old_pc = self.pc
        if self.can_superscalar(op1, op2):
            self.pc += 2
            self.execute_single(op1, arg1)
            self.execute_single(op2, arg2)
            self.log_state(
                f"Tick: {self.tick:04d} | PC: {old_pc:04X} | Stk: {self.dp.data_stack} | "
                f"Exec: {op1.name} {arg1} || {op2.name} {arg2} (Superscalar){self.bypass_log}{bg_log}"
            )
        else:
            self.pc += 1
            self.execute_single(op1, arg1)
            self.log_state(
                f"Tick: {self.tick:04d} | PC: {old_pc:04X} | Stk: {self.dp.data_stack} | "
                f"Exec: {op1.name} {arg1}{self.bypass_log}{bg_log}"
            )

    def run(self):
        logging.info("--- Simulation Started ---")
        try:
            while not self.halted and self.tick < 50000000:
                self.process_next_tick()
        except IndexError:
            logging.error("Execution out of bounds / Stack underflow")

        if self.tick >= 50000000:
            logging.warning("Tick limit reached!")

        logging.info("--- Simulation Ended ---")
        logging.info(f"Total Ticks: {self.tick}")
        logging.info(f"Output Buffer: {self.dp.out_buffer}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python machine.py <code.bin> <schedule_file>")
        sys.exit(1)

    mem_init = read_code(sys.argv[1])
    schedule = []
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        content = f.read().strip()
        if content:
            schedule = ast.literal_eval(content)

    dp = DataPath(2048, mem_init, schedule)
    cpu = ControlUnit(dp)
    cpu.run()


if __name__ == "__main__":
    main()
