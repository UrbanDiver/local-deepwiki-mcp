"""Tests for configuration profile management."""

import argparse
from unittest.mock import patch

import pytest

from local_deepwiki.config.loader import (
    activate_profile,
    delete_profile,
    get_active_profile_name,
    list_profiles,
    save_profile,
)
from local_deepwiki.cli.profile_cli import (
    cmd_profile_delete,
    cmd_profile_list,
    cmd_profile_save,
    cmd_profile_use,
    dispatch_profile,
    register_profile_subparser,
)


@pytest.fixture
def profiles_dir(tmp_path):
    """Set up temporary profile directories."""
    config_dir = tmp_path / ".config" / "local-deepwiki"
    profiles = config_dir / "profiles"
    profiles.mkdir(parents=True)
    active_file = config_dir / "active_profile"

    with (
        patch.object(
            __import__("local_deepwiki.config.loader", fromlist=["CONFIG_DIR"]),
            "CONFIG_DIR",
            config_dir,
        ),
        patch.object(
            __import__("local_deepwiki.config.loader", fromlist=["PROFILES_DIR"]),
            "PROFILES_DIR",
            profiles,
        ),
        patch.object(
            __import__(
                "local_deepwiki.config.loader", fromlist=["ACTIVE_PROFILE_FILE"]
            ),
            "ACTIVE_PROFILE_FILE",
            active_file,
        ),
    ):
        yield profiles, active_file, config_dir


# Use a simpler approach - patch module-level vars directly
import local_deepwiki.config.loader as loader_module


@pytest.fixture
def temp_profiles(tmp_path):
    """Temporarily redirect profile directories to tmp_path."""
    config_dir = tmp_path / ".config" / "local-deepwiki"
    profiles = config_dir / "profiles"
    profiles.mkdir(parents=True)
    active_file = config_dir / "active_profile"
    config_yaml = config_dir / "config.yaml"

    original_config_dir = loader_module.CONFIG_DIR
    original_profiles_dir = loader_module.PROFILES_DIR
    original_active_file = loader_module.ACTIVE_PROFILE_FILE

    loader_module.CONFIG_DIR = config_dir
    loader_module.PROFILES_DIR = profiles
    loader_module.ACTIVE_PROFILE_FILE = active_file

    yield {
        "config_dir": config_dir,
        "profiles_dir": profiles,
        "active_file": active_file,
        "config_yaml": config_yaml,
        "tmp_path": tmp_path,
    }

    loader_module.CONFIG_DIR = original_config_dir
    loader_module.PROFILES_DIR = original_profiles_dir
    loader_module.ACTIVE_PROFILE_FILE = original_active_file


class TestListProfiles:
    def test_empty_when_no_profiles(self, temp_profiles):
        # Remove profiles dir to test non-existent case
        import shutil

        shutil.rmtree(temp_profiles["profiles_dir"])
        assert list_profiles() == []

    def test_lists_yaml_files(self, temp_profiles):
        (temp_profiles["profiles_dir"] / "dev.yaml").write_text(
            "llm:\n  provider: ollama\n"
        )
        (temp_profiles["profiles_dir"] / "prod.yaml").write_text(
            "llm:\n  provider: anthropic\n"
        )
        assert list_profiles() == ["dev", "prod"]

    def test_ignores_non_yaml(self, temp_profiles):
        (temp_profiles["profiles_dir"] / "dev.yaml").write_text(
            "llm:\n  provider: ollama\n"
        )
        (temp_profiles["profiles_dir"] / "notes.txt").write_text("not a profile")
        assert list_profiles() == ["dev"]

    def test_sorted_alphabetically(self, temp_profiles):
        (temp_profiles["profiles_dir"] / "zebra.yaml").write_text("")
        (temp_profiles["profiles_dir"] / "alpha.yaml").write_text("")
        assert list_profiles() == ["alpha", "zebra"]


class TestGetActiveProfileName:
    def test_none_when_no_file(self, temp_profiles):
        assert get_active_profile_name() is None

    def test_none_when_empty_file(self, temp_profiles):
        temp_profiles["active_file"].write_text("")
        assert get_active_profile_name() is None

    def test_returns_name_when_profile_exists(self, temp_profiles):
        (temp_profiles["profiles_dir"] / "dev.yaml").write_text("")
        temp_profiles["active_file"].write_text("dev")
        assert get_active_profile_name() == "dev"

    def test_none_when_profile_deleted(self, temp_profiles):
        temp_profiles["active_file"].write_text("deleted-profile")
        assert get_active_profile_name() is None


class TestSaveProfile:
    def test_saves_config_file(self, temp_profiles):
        # Create a config file to snapshot
        config_file = temp_profiles["tmp_path"] / "config.yaml"
        config_file.write_text("llm:\n  provider: ollama\n")

        path = save_profile("test", config_path=config_file)
        assert path.exists()
        assert path.read_text() == "llm:\n  provider: ollama\n"

    def test_saves_defaults_when_no_config(self, temp_profiles):
        # No config file anywhere - should save defaults
        with patch(
            "local_deepwiki.config.loader.Path.cwd",
            return_value=temp_profiles["tmp_path"],
        ):
            path = save_profile("defaults")
        assert path.exists()
        assert path.suffix == ".yaml"

    def test_rejects_invalid_name(self, temp_profiles):
        with pytest.raises(ValueError, match="Invalid profile name"):
            save_profile("bad name!")

    def test_rejects_path_traversal(self, temp_profiles):
        with pytest.raises(ValueError, match="Invalid profile name"):
            save_profile("../evil")

    def test_overwrites_existing_profile(self, temp_profiles):
        config1 = temp_profiles["tmp_path"] / "c1.yaml"
        config1.write_text("version: 1\n")
        save_profile("test", config_path=config1)

        config2 = temp_profiles["tmp_path"] / "c2.yaml"
        config2.write_text("version: 2\n")
        save_profile("test", config_path=config2)

        saved = (temp_profiles["profiles_dir"] / "test.yaml").read_text()
        assert "version: 2" in saved


class TestActivateProfile:
    def test_copies_profile_to_config(self, temp_profiles):
        (temp_profiles["profiles_dir"] / "dev.yaml").write_text(
            "llm:\n  provider: ollama\n"
        )

        with patch("local_deepwiki.config.loader.reset_config"):
            activate_profile("dev")

        config_yaml = temp_profiles["config_dir"] / "config.yaml"
        assert config_yaml.exists()
        assert "ollama" in config_yaml.read_text()

    def test_records_active_name(self, temp_profiles):
        (temp_profiles["profiles_dir"] / "prod.yaml").write_text(
            "llm:\n  provider: anthropic\n"
        )

        with patch("local_deepwiki.config.loader.reset_config"):
            activate_profile("prod")

        assert temp_profiles["active_file"].read_text() == "prod"

    def test_raises_for_missing_profile(self, temp_profiles):
        with pytest.raises(FileNotFoundError, match="not found"):
            activate_profile("nonexistent")

    def test_resets_cached_config(self, temp_profiles):
        (temp_profiles["profiles_dir"] / "dev.yaml").write_text("")

        with patch("local_deepwiki.config.loader.reset_config") as mock_reset:
            activate_profile("dev")

        mock_reset.assert_called_once()


class TestDeleteProfile:
    def test_deletes_existing(self, temp_profiles):
        (temp_profiles["profiles_dir"] / "old.yaml").write_text("")
        assert delete_profile("old") is True
        assert not (temp_profiles["profiles_dir"] / "old.yaml").exists()

    def test_returns_false_for_missing(self, temp_profiles):
        assert delete_profile("nonexistent") is False

    def test_clears_active_if_deleted(self, temp_profiles):
        (temp_profiles["profiles_dir"] / "dev.yaml").write_text("")
        temp_profiles["active_file"].write_text("dev")

        delete_profile("dev")
        assert not temp_profiles["active_file"].exists()

    def test_keeps_active_for_other_profile(self, temp_profiles):
        (temp_profiles["profiles_dir"] / "dev.yaml").write_text("")
        (temp_profiles["profiles_dir"] / "prod.yaml").write_text("")
        temp_profiles["active_file"].write_text("prod")

        delete_profile("dev")
        assert temp_profiles["active_file"].read_text() == "prod"


class TestProfileCLICommands:
    """Tests for the CLI command functions."""

    def test_cmd_save_success(self, temp_profiles, capsys):
        config_file = temp_profiles["tmp_path"] / "config.yaml"
        config_file.write_text("llm:\n  provider: ollama\n")

        args = argparse.Namespace(name="test")
        with patch("local_deepwiki.config.loader.save_profile", wraps=save_profile):
            with patch(
                "local_deepwiki.cli.profile_cli.save_profile",
                side_effect=lambda name, **kw: save_profile(
                    name, config_path=config_file
                ),
            ):
                result = cmd_profile_save(args)

        assert result == 0

    def test_cmd_save_invalid_name(self, capsys):
        args = argparse.Namespace(name="bad name!")
        with patch(
            "local_deepwiki.cli.profile_cli.save_profile",
            side_effect=ValueError("Invalid profile name 'bad name!'"),
        ):
            result = cmd_profile_save(args)
        assert result == 1

    def test_cmd_use_success(self, temp_profiles, capsys):
        (temp_profiles["profiles_dir"] / "dev.yaml").write_text("")

        args = argparse.Namespace(name="dev")
        with patch("local_deepwiki.cli.profile_cli.activate_profile") as mock_activate:
            result = cmd_profile_use(args)

        assert result == 0
        mock_activate.assert_called_once_with("dev")

    def test_cmd_use_missing(self, capsys):
        args = argparse.Namespace(name="missing")
        with patch(
            "local_deepwiki.cli.profile_cli.activate_profile",
            side_effect=FileNotFoundError("Profile 'missing' not found"),
        ):
            result = cmd_profile_use(args)
        assert result == 1

    def test_cmd_list_empty(self, temp_profiles, capsys):
        # Remove all profiles
        import shutil

        shutil.rmtree(temp_profiles["profiles_dir"])

        args = argparse.Namespace()
        result = cmd_profile_list(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "No profiles" in captured.out

    def test_cmd_list_shows_profiles(self, temp_profiles, capsys):
        (temp_profiles["profiles_dir"] / "dev.yaml").write_text("")
        (temp_profiles["profiles_dir"] / "prod.yaml").write_text("")

        args = argparse.Namespace()
        result = cmd_profile_list(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "dev" in captured.out
        assert "prod" in captured.out

    def test_cmd_delete_success(self, capsys):
        args = argparse.Namespace(name="old")
        with patch("local_deepwiki.cli.profile_cli.delete_profile", return_value=True):
            result = cmd_profile_delete(args)
        assert result == 0

    def test_cmd_delete_missing(self, capsys):
        args = argparse.Namespace(name="missing")
        with patch("local_deepwiki.cli.profile_cli.delete_profile", return_value=False):
            result = cmd_profile_delete(args)
        assert result == 1


class TestRegisterProfileSubparser:
    def test_registers_subcommands(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register_profile_subparser(subparsers)

        # Verify profile subcommand exists
        args = parser.parse_args(["profile", "list"])
        assert args.command == "profile"
        assert args.profile_command == "list"

    def test_save_requires_name(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register_profile_subparser(subparsers)

        with pytest.raises(SystemExit):
            parser.parse_args(["profile", "save"])


class TestDispatchProfile:
    def test_no_subcommand_shows_usage(self, capsys):
        args = argparse.Namespace(profile_command=None)
        result = dispatch_profile(args)
        assert result == 1

    def test_dispatches_to_func(self):
        mock_func = lambda args: 0
        args = argparse.Namespace(profile_command="list", func=mock_func)
        result = dispatch_profile(args)
        assert result == 0
