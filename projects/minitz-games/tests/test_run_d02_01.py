from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from run_d02_01 import runtime_has_task_error


KNOWN_STARTUP_ERROR = (
    "StructProperty FDataflowToolNodeSnapshot::Date is not initialized properly "
    "even though its struct probably has a custom default constructor. "
    "Non deterministic fields should use UPROPERTY(Meta = (IgnoreForMemberInitializationTest)) "
    "to avoid errors from this test. Module:DataflowNodes File:Public/Dataflow/DataflowToolNode.h"
)


def test_exact_known_pre_scenario_engine_diagnostic_does_not_fail_streaming_run():
    log = "\n".join([
        "LogClass: Error: " + KNOWN_STARTUP_ERROR,
        "LogAutomationTest: Error: LogClass: " + KNOWN_STARTUP_ERROR,
        "D02_STREAM WORLD_READY source=authored_world_partition",
        "D02_01_TEST event=relocate phase=1",
        "LogAutomationController: Test Completed. Result={Success} Name={WorldStreaming}",
    ])
    assert runtime_has_task_error(log) is False


def test_unknown_startup_error_is_rejected():
    assert runtime_has_task_error(
        "LogTemp: Error: missing vehicle asset\nD02_STREAM WORLD_READY") is True


def test_known_error_in_task_window_or_without_marker_is_rejected():
    error = "LogClass: Error: " + KNOWN_STARTUP_ERROR
    assert runtime_has_task_error("D02_STREAM WORLD_READY\n" + error) is True
    assert runtime_has_task_error(error) is True


def test_task_window_generic_error_is_rejected():
    log = "\n".join([
        "D02_STREAM WORLD_READY source=authored_world_partition",
        "D02_01_TEST event=relocate phase=1",
        "LogTemp: Error: streaming traversal failed",
    ])
    assert runtime_has_task_error(log) is True


def test_global_fatal_assert_ensure_or_test_fail_is_rejected_even_before_marker():
    for bad in ("Fatal error:", "Assertion failed:", "Ensure condition failed:", "Result={Fail}"):
        assert runtime_has_task_error(bad + "\nD02_STREAM WORLD_READY source=authored_world_partition") is True
