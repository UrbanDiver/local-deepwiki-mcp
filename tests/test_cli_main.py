"""Tests for the unified CLI dispatcher (cli/main.py)."""

import sys
from unittest.mock import MagicMock, patch

from local_deepwiki.cli.main import SUBCOMMANDS, main, show_help


class TestSubcommandTable:
    """Tests for the SUBCOMMANDS configuration."""

    def test_all_expected_commands_present(self):
        expected = {
            "mcp",
            "serve",
            "watch",
            "export",
            "export-pdf",
            "config",
            "search",
            "cache",
        }
        assert set(SUBCOMMANDS.keys()) == expected

    def test_each_entry_has_three_fields(self):
        for name, entry in SUBCOMMANDS.items():
            assert len(entry) == 3, f"{name} should have (module, func, description)"

    def test_descriptions_are_nonempty(self):
        for name, (_, _, desc) in SUBCOMMANDS.items():
            assert desc, f"{name} should have a description"

    def test_function_names_are_main(self):
        for name, (_, func_name, _) in SUBCOMMANDS.items():
            assert func_name == "main", f"{name} function should be 'main'"


class TestShowHelp:
    """Tests for the help display."""

    def test_show_help_does_not_raise(self, capsys):
        show_help()
        captured = capsys.readouterr()
        assert "deepwiki" in captured.out

    def test_show_help_lists_all_commands(self, capsys):
        show_help()
        captured = capsys.readouterr()
        for name in SUBCOMMANDS:
            assert name in captured.out


class TestMainDispatch:
    """Tests for the main() dispatcher."""

    def test_no_args_shows_help(self, capsys):
        with patch.object(sys, "argv", ["deepwiki"]):
            result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "deepwiki" in captured.out

    def test_help_flag_shows_help(self, capsys):
        with patch.object(sys, "argv", ["deepwiki", "--help"]):
            result = main()
        assert result == 0

    def test_h_flag_shows_help(self, capsys):
        with patch.object(sys, "argv", ["deepwiki", "-h"]):
            result = main()
        assert result == 0

    def test_unknown_command_returns_1(self, capsys):
        with patch.object(sys, "argv", ["deepwiki", "nonexistent"]):
            result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "Unknown command" in captured.err

    def test_dispatches_to_subcommand(self):
        mock_main = MagicMock(return_value=0)
        mock_module = MagicMock()
        mock_module.main = mock_main

        with patch.object(sys, "argv", ["deepwiki", "config", "show"]):
            with patch(
                "importlib.import_module", return_value=mock_module
            ) as mock_import:
                result = main()

        mock_import.assert_called_once_with("local_deepwiki.cli.config_cli")
        mock_main.assert_called_once()
        assert result == 0

    def test_argv_rewritten_for_subcommand(self):
        captured_argv = []

        def capture_main():
            captured_argv.extend(sys.argv)
            return 0

        mock_module = MagicMock()
        mock_module.main = capture_main

        with patch.object(sys, "argv", ["deepwiki", "serve", "--port", "8080"]):
            with patch("importlib.import_module", return_value=mock_module):
                main()

        assert captured_argv == ["deepwiki serve", "--port", "8080"]

    def test_none_return_treated_as_success(self):
        mock_module = MagicMock()
        mock_module.main = MagicMock(return_value=None)

        with patch.object(sys, "argv", ["deepwiki", "config"]):
            with patch("importlib.import_module", return_value=mock_module):
                result = main()

        assert result == 0

    def test_nonzero_return_propagated(self):
        mock_module = MagicMock()
        mock_module.main = MagicMock(return_value=2)

        with patch.object(sys, "argv", ["deepwiki", "config"]):
            with patch("importlib.import_module", return_value=mock_module):
                result = main()

        assert result == 2

    def test_each_command_imports_correct_module(self):
        """Verify each subcommand routes to the right module."""
        for cmd_name, (module_path, func_name, _) in SUBCOMMANDS.items():
            mock_func = MagicMock(return_value=0)
            mock_module = MagicMock()
            setattr(mock_module, func_name, mock_func)

            with patch.object(sys, "argv", ["deepwiki", cmd_name]):
                with patch(
                    "importlib.import_module", return_value=mock_module
                ) as mock_import:
                    main()

            mock_import.assert_called_once_with(module_path)
