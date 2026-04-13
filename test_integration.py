import contextlib
import io
import os
import ast
import pytest
import logging


from translator import translate
from machine import DataPath, ControlUnit

TEST_DIR = "examples"


@pytest.mark.parametrize(
    "source_file, schedule_file, golden_file",
    [
        ("hello.asm", "text.txt", "hello_golden.txt"),
        ("prob1.asm", "empty.txt", "prob1_golden.txt"),
    ],
)
def test_algorithms(source_file, schedule_file, golden_file):
    source_path = os.path.join(TEST_DIR, source_file)
    schedule_path = os.path.join(TEST_DIR, schedule_file)
    golden_path = os.path.join(TEST_DIR, golden_file)

    with open(source_path, "r", encoding="utf-8") as f:
        source_code = f.read()

    memory, debug_log = translate(source_code)

    schedule = []
    if os.path.exists(schedule_path):
        with open(schedule_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                schedule = ast.literal_eval(content)

    output_stream = io.StringIO()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(output_stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    with contextlib.redirect_stdout(output_stream):
        dp = DataPath(2048, memory, schedule)
        cpu = ControlUnit(dp)
        cpu.run()

    logger.removeHandler(handler)
    execution_log = output_stream.getvalue()
    actual_result = (
        "=== SOURCE CODE ===\n" + source_code + "\n\n"
        "=== MACHINE CODE LOG ===\n" + "\n".join(debug_log) + "\n\n"
        "=== EXECUTION LOG ===\n" + execution_log
    )

    if not os.path.exists(golden_path):
        with open(golden_path, "w", encoding="utf-8") as f:
            f.write(actual_result)
        pytest.skip(f"Golden file {golden_file} was generated. Run tests again")

    else:
        with open(golden_path, "r", encoding="utf-8") as f:
            expected_result = f.read()

        assert actual_result == expected_result, (
            f"Test failed for {source_file}. Output doesn't match golden file\n"
            f"If you changed the code intentionally, delete {golden_file} and run pytest again."
        )
