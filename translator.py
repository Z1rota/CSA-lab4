import sys
from isa import Opcode, encode_instruction, write_code


def translate(source: str) -> tuple[list[int], list[str], int]:
    lines = source.split("\n")
    macros: dict[str, int] = {}
    labels: dict[str, int] = {}

    memory = [0] * 1024
    pc = 0

    section = ".text"
    # Pass 1: delete&refact
    parsed_lines = []
    for line in lines:
        line = line.split(";")[0].strip()
        if not line:
            continue

        if line.startswith("%define"):
            parts = line.split()
            macros[parts[1]] = int(parts[2])
            continue

        if line in (".data", ".text"):
            section = line
            continue

        if line.startswith(".org"):
            pc = int(line.split()[1], 0)
            continue

        if ":" in line:
            label, rest = line.split(":", 1)
            labels[label.strip()] = pc
            line = rest.strip()
            if not line:
                continue

        if section == ".data":
            parts = line.split(maxsplit=1)
            directive = parts[0]
            val_str = parts[1]

            if directive == ".word":
                memory[pc] = int(val_str, 0)
                pc += 1
            elif directive == ".pstr":
                val_str = val_str.strip('"')
                memory[pc] = len(val_str)
                pc += 1
                for char in val_str:
                    memory[pc] = ord(char)
                    pc += 1
            continue

        parsed_lines.append((pc, line))
        pc += 1

    # Pass 2: Code generation
    debug_log = []
    for addr, line in parsed_lines:
        parts = line.split()
        mnemonica = parts[0].upper()
        arg_str = parts[1] if len(parts) > 1 else "0"

        if arg_str in macros:
            arg = macros[arg_str]
        elif arg_str in labels:
            arg = labels[arg_str]
        else:
            try:
                arg = int(arg_str, 0)
            except ValueError:
                arg = 0

        opcode = Opcode[mnemonica]
        machine_word = encode_instruction(opcode, arg)
        memory[addr] = machine_word

        hex_code = f"{machine_word & 0xFFFFFFFF:08X}"
        debug_log.append(f"{addr:04X} - {hex_code} - {mnemonica} {arg_str}")

        entry_point = labels.get("_start", 0)
    return memory, debug_log, entry_point


def main(source_file: str, target_file: str):
    with open(source_file, "r", encoding="utf-8") as f:
        source_code = f.read()
    mem, dbg, entry_point = translate(source_code)
    write_code(target_file, mem, entry_point)
    with open(target_file + ".log", "w", encoding="utf-8") as f:
        f.write("\n".join(dbg))


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python translator.py <source.asm> <output.bin>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
