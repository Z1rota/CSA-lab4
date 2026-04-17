import sys
import ast
import argparse
import logging
from isa import Opcode, read_code, decode_instruction

logging.basicConfig(level=logging.INFO, format="%(message)s")


class DataPath:
    """Тракт данных. Включает память, АЛУ, Аппаратные стеки и порты ввода/вывода."""

    def __init__(self, memory_size: int, memory_init: list[int], io_schedule: list[tuple[int, str]]):
        self.memory = memory_init + [0] * (memory_size - len(memory_init))

        # Аппаратные стеки (изолированы от ОЗУ)
        self.data_stack: list[int] = []
        self.return_stack: list[int] = []
        self.MAX_STACK = 256

        # Теневой регистр  (Superscalar/Pipelining)
        self.shadow_data = 0
        self.shadow_addr = -1
        self.shadow_busy_ticks = 0
        self.shadow_pending = False

        # Прерывания, порты и тд (Interrupts, ports, etc)
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
        return self.shadow_pending and self.shadow_addr == addr

    def push(self, val: int):
        if len(self.data_stack) >= self.MAX_STACK:
            raise OverflowError("Data Stack Overflow")
        self.data_stack.append(val)

    def pop(self) -> int:
        if not self.data_stack:
            raise IndexError("Data Stack Underflow")
        return self.data_stack.pop()

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
    """Блок управления. Реализует многотактовое выполнение и суперскалярность."""

    def __init__(self, data_path: DataPath, superscalar_enabled: bool = True, max_log_ticks: int = 1500):
        self.dp = data_path
        self.pc = 0
        self.tick = 0
        self.stall_ticks = 0
        self.ie = False
        self.halted = False
        self.bypass_log = ""
        self.max_log_ticks = max_log_ticks
        self.superscalar_enabled = superscalar_enabled
        self.instructions_executed = 0

    def log_state(self, msg: str):
        if self.tick <= self.max_log_ticks:
            logging.debug(msg)

    def get_instruction_cost(self, opcode: Opcode) -> int:
        """Возвращает базовое количество тактов на фазу Execute."""
        if opcode in {Opcode.PUSH_M, Opcode.POP_M}:
            return 2
        return 1

    def can_superscalar(self, op1: Opcode, op2: Opcode) -> bool:
        if not self.superscalar_enabled:
            return False
        alu_ops = {Opcode.PUSH, Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV, Opcode.MOD, Opcode.CMP, Opcode.GT,
                   Opcode.IN}
        if op1 in alu_ops and op2 == Opcode.POP_M:
            if self.dp.shadow_busy_ticks > 0:
                return False
            return True
        if op1 in alu_ops and op2 in {Opcode.JMP, Opcode.JZ, Opcode.RET}:
            return True
        return False

    def execute_single(self, opcode: Opcode, arg: int):
        self.instructions_executed += 1
        if opcode == Opcode.NOP:
            pass
        elif opcode == Opcode.HALT:
            self.halted = True
        elif opcode in {Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV, Opcode.MOD, Opcode.CMP, Opcode.GT}:
            self.dp.alu_op(opcode)
        elif opcode == Opcode.PUSH:
            self.dp.push(arg)
        elif opcode == Opcode.PUSH_M:
            if self.dp.is_shadow_match(arg):
                self.dp.push(self.dp.shadow_data)
                self.bypass_log = " [Bypass from Shadow]"
            else:
                self.dp.push(self.dp.memory[arg])
        elif opcode == Opcode.POP_M:
            self.dp.trigger_shadow_write(arg, self.dp.pop())
        elif opcode == Opcode.IN:
            self.dp.io_read(arg)
        elif opcode == Opcode.OUT:
            self.dp.io_write(arg)
        elif opcode == Opcode.JMP:
            self.pc = arg
        elif opcode == Opcode.JZ:
            if self.dp.pop() == 0: self.pc = arg
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
        elif opcode == Opcode.LOAD:
            addr = self.dp.pop()
            # Проверка bypass
            if self.dp.is_shadow_match(addr):
                self.dp.push(self.dp.shadow_data)
            else:
                self.dp.push(self.dp.memory[addr])
        elif opcode == Opcode.STORE:
            val = self.dp.pop()
            addr = self.dp.pop()
            self.dp.trigger_shadow_write(addr, val)

    def process_next_tick(self):
        self.tick += 1
        self.bypass_log = ""
        bg_log = self.dp.tick_background(self.tick)

        if self.dp.interrupt_pin and self.ie:
            self.dp.interrupt_pin = False
            self.ie = False
            self.dp.return_stack.append(self.pc)
            self.pc = 0x0010
            self.log_state(f"Tick: {self.tick:04d} | INTERRUPT TRAP")
            return

        if self.stall_ticks > 0:
            self.stall_ticks -= 1
            if self.stall_ticks == 0:
                self.log_state(f"Tick: {self.tick:04d} | Pipeline Active{bg_log}")
            else:
                self.log_state(f"Tick: {self.tick:04d} | PIPELINE STALL{bg_log}")
            return

        # Fetch stage
        word1 = self.dp.memory[self.pc]
        op1, arg1 = decode_instruction(word1)

        word2 = self.dp.memory[self.pc + 1] if self.pc + 1 < len(self.dp.memory) else 0
        op2, arg2 = decode_instruction(word2)

        old_pc = self.pc


        if op1 == Opcode.PUSH_M and self.dp.shadow_busy_ticks > 0 and not self.dp.is_shadow_match(arg1):
            self.stall_ticks = 1
            self.log_state(f"Tick: {self.tick:04d} | PC: {self.pc:04X} | STALL (Shadow Memory Busy){bg_log}")
            return

        # Execute stage
        fetch_cost = 1
        if self.can_superscalar(op1, op2):
            self.pc += 2
            self.execute_single(op1, arg1)
            self.execute_single(op2, arg2)
            exec_cost = max(self.get_instruction_cost(op1), self.get_instruction_cost(op2))
            self.stall_ticks = fetch_cost + exec_cost - 1
            self.log_state(
                f"Tick: {self.tick:04d} | PC: {old_pc:04X} | Stk: {self.dp.data_stack} | "
                f"Exec: {op1.name} {arg1} || {op2.name} {arg2} (Superscalar){self.bypass_log}{bg_log}"
            )
        else:
            self.pc += 1
            self.execute_single(op1, arg1)
            exec_cost = self.get_instruction_cost(op1)
            self.stall_ticks = fetch_cost + exec_cost - 1
            self.log_state(
                f"Tick: {self.tick:04d} | PC: {old_pc:04X} | Stk: {self.dp.data_stack} | "
                f"Exec: {op1.name} {arg1}{self.bypass_log}{bg_log}"
            )

    def run(self):
        try:
            while not self.halted and self.tick < 5000000:
                self.process_next_tick()
        except Exception as e:
            logging.error(f"Execution fault: {e}")

        logging.info(f"Total Ticks: {self.tick}")
        logging.info(f"Instructions Executed: {self.instructions_executed}")
        logging.info(f"Output: {self.dp.out_buffer}")


def main(code_file: str, schedule_file: str, no_superscalar: bool):
    mem_init, entry_point = read_code(code_file)
    schedule = []
    if schedule_file:
        try:
            with open(schedule_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    schedule = ast.literal_eval(content)
        except FileNotFoundError:
            pass

    dp = DataPath(2048, mem_init, schedule)
    cpu = ControlUnit(dp, superscalar_enabled=not no_superscalar)
    cpu.pc = entry_point
    cpu.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("code", help="binary file")
    parser.add_argument("schedule", nargs='?', default="", help="IO schedule txt")
    parser.add_argument("--no-superscalar", action="store_true", help="Disable superscalar execution")
    args = parser.parse_args()
    main(args.code, args.schedule, args.no_superscalar)