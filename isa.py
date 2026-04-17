import struct
from enum import Enum


class Opcode(int, Enum):
    NOP = 0x00
    PUSH = 0x01
    PUSH_M = 0x02
    POP_M = 0x03
    ADD = 0x04
    SUB = 0x05
    MOD = 0x06
    CMP = 0x07
    JMP = 0x08
    JZ = 0x09
    CALL = 0x0A
    RET = 0x0B
    IN = 0x0C
    OUT = 0x0D
    IRET = 0x0E
    HALT = 0x0F
    EI = 0x10
    MUL = 0x11
    GT = 0x13
    DIV = 0x12
    LOAD = 0x14
    STORE = 0x15


def encode_instruction(opcode: Opcode, operand: int = 0) -> int:
    op = int(opcode) & 0xFF
    arg = int(operand) & 0xFFFFFF
    return (op << 24) | arg


def decode_instruction(word: int) -> tuple[Opcode, int]:
    op = (word >> 24) & 0xFF
    arg = word & 0xFFFFFF
    if arg & 0x800000:
        arg -= 0x1000000
    return Opcode(op), arg


def write_code(filepath: str, memory: list[int], entry_point: int = 0) -> None:
    with open(filepath, "wb") as f:
        f.write(struct.pack(">i", entry_point))
        for word in memory:
            f.write(struct.pack(">i", word))

def read_code(filepath: str) -> tuple[list[int], int]:
    memory = []
    entry_point = 0
    with open(filepath, "rb") as f:
        chunk = f.read(4)
        if chunk and len(chunk) == 4:
            entry_point = struct.unpack(">i", chunk)[0]
        while chunk := f.read(4):
            if len(chunk) == 4:
                memory.append(struct.unpack(">i", chunk)[0])
    return memory, entry_point