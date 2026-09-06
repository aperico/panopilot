from pathlib import Path

import panopilot.explore as explore_module
from panopilot.cli import build_parser


def _subcommand_names(parser):
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            return set(choices)
    return set()


def test_explore_module_imports_path_used_by_result_payload():
    # Regression for 0.13.0:
    # explore_osv() returned Path(project_path).exists() after the Qt window
    # closed but Path had not been imported.
    assert explore_module.Path is Path


def test_013_cli_commands_are_registered():
    commands = _subcommand_names(build_parser())

    assert "camera-at" in commands
    assert "reframe-path" in commands
