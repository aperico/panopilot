import inspect

import panopilot.cli as cli


def test_cli_imports_sys_for_interactive_project_rebuild():
    source = inspect.getsource(
        cli
    )

    assert "import sys" in source
    assert "sys.stdin.isatty()" in source
