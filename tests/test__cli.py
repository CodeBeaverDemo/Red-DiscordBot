import argparse
import asyncio
import sys
import pytest

from redbot.core._cli import (
    confirm,
    interactive_config,
    non_negative_int,
    message_cache_size_int,
    parse_cli_flags,
    ExitCodes,
)


def test_confirm_yes(monkeypatch):
    """Test confirm returns True for 'yes' input."""
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
    assert confirm("Test confirm") is True

def test_confirm_no(monkeypatch):
    """Test confirm returns False for 'no' input even with a default of True."""
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    assert confirm("Test confirm", default=True) is False

def test_confirm_default(monkeypatch):
    """Test confirm returns the default value when input is empty."""
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert confirm("Test confirm", default=True) is True

def test_confirm_invalid_then_valid(monkeypatch):
    """Test confirm loops on an invalid input then accepts a valid 'y'."""
    inputs = iter(["maybe", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    assert confirm("Test confirm") is True

def test_confirm_keyboard_interrupt(monkeypatch):
    """Test confirm handles KeyboardInterrupt by exiting with SHUTDOWN exit code."""
    def fake_input(prompt=""):
        raise KeyboardInterrupt
    monkeypatch.setattr("builtins.input", fake_input)
    with pytest.raises(SystemExit) as excinfo:
        confirm("Test confirm")
    assert excinfo.value.code == ExitCodes.SHUTDOWN

def test_confirm_eof(monkeypatch):
    """Test confirm handles EOFError by exiting with INVALID_CLI_USAGE exit code."""
    def fake_input(prompt=""):
        raise EOFError
    monkeypatch.setattr("builtins.input", fake_input)
    with pytest.raises(SystemExit) as excinfo:
        confirm("Test confirm")
    assert excinfo.value.code == ExitCodes.INVALID_CLI_USAGE

def test_non_negative_int_valid():
    """Test non_negative_int returns a valid positive integer."""
    assert non_negative_int("10") == 10

def test_non_negative_int_negative():
    """Test non_negative_int raises error on negative integer input."""
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int("-10")

def test_non_negative_int_non_numeric():
    """Test non_negative_int raises error on non-numeric input."""
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int("abc")

def test_message_cache_size_int_valid():
    """Test message_cache_size_int returns the valid integer input."""
    assert message_cache_size_int("1500") == 1500

def test_message_cache_size_int_too_low():
    """Test message_cache_size_int raises error when the number is less than 1000."""
    with pytest.raises(argparse.ArgumentTypeError):
        message_cache_size_int("500")

def test_parse_cli_flags_defaults():
    """Test parse_cli_flags returns expected default values with no arguments."""
    args = parse_cli_flags([])
    assert args.version is False
    # Check that logging_level is calculated (using cli_level_to_log_level logic internally)
    assert args.logging_level >= 0
    assert args.prefix == []

def test_parse_cli_flags_with_prefix_and_version():
    """Test parse_cli_flags correctly processes version and prefix arguments."""
    arg_list = ["--version", "-p", "!", "-p", "?"]
    args = parse_cli_flags(arg_list)
    assert args.version is True
    # The prefixes are sorted in reverse order so "?" precedes "!"
    assert args.prefix == ["?", "!"]

class FakeConfigItem:
    """Fake config item to simulate asynchronous setting of configuration values."""
    def __init__(self):
        self.value = None
    async def set(self, value):
        self.value = value

class FakeConfig:
    """Fake configuration container for token and prefix."""
    def __init__(self):
        self.token = FakeConfigItem()
        self.prefix = FakeConfigItem()

class FakeRed:
    """Fake Red object with a _config attribute used for testing interactive configuration."""
    def __init__(self):
        self._config = FakeConfig()

@pytest.mark.asyncio
async def test_interactive_config(monkeypatch):
    """Test interactive_config sets the token and prefix correctly during an interactive session."""
    token_str = "x" * 51  # valid token, length >= 50
    # Simulate inputs: token input, prefix input, then confirmation for the prefix choice
    inputs = iter([token_str, "!", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    red = FakeRed()
    result_token = await interactive_config(red, token_set=False, prefix_set=False, print_header=False)
    # Verify that the token is returned and set correctly
    assert result_token == token_str
    assert red._config.token.value == token_str
    # Verify that the prefix is set correctly (wrapped in a list)
    assert red._config.prefix.value == ["!"]

@pytest.mark.asyncio
async def test_interactive_config_with_existing_token_prefix(monkeypatch):
    """Test interactive_config does not prompt and modify settings when token and prefix are already set."""
    # When token_set and prefix_set are True, no input should be requested.
    monkeypatch.setattr("builtins.input", lambda prompt="": "should not be used")
    red = FakeRed()
    result_token = await interactive_config(red, token_set=True, prefix_set=True, print_header=False)
    # Since no prompting occurs, the token remains None
    assert result_token is None
    assert red._config.token.value is None
    assert red._config.prefix.value is None
def test_interactive_config_prefix_only(monkeypatch):
    """Test interactive_config prompts for and sets the prefix when token is already set."""
    # token_set True so token prompt is skipped; prefix_set False so prefix prompt is run.
    # Simulate: first input "LongPrefixName" (invalid due to length) then "n" for its confirmation,
    # then a valid input "!" with confirmation "y".
    responses = iter(["LongPrefixName", "n", "!", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    red = FakeRed()
    # Use asyncio.run to execute the asynchronous function
    token_result = __import__("asyncio").run(interactive_config(red, token_set=True, prefix_set=False, print_header=False))
    # token_result should be None because token was skipped.
    assert token_result is None
    assert red._config.prefix.value == ["!"]

@pytest.mark.asyncio
async def test_interactive_config_token_invalid_then_valid(monkeypatch):
    """Test interactive_config handles an invalid token input followed by a valid token input."""
    # token_set False so token prompt is active, prefix_set True so prefix prompt is skipped.
    token_invalid = "short"
    token_valid = "x" * 50  # exactly 50 characters: valid
    responses = iter([token_invalid, token_valid])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    red = FakeRed()
    result_token = await interactive_config(red, token_set=False, prefix_set=True, print_header=False)
    assert result_token == token_valid
    assert red._config.token.value == token_valid

def test_parse_cli_flags_all_args():
    """Test parse_cli_flags with almost every CLI flag to ensure all arguments are parsed correctly."""
    arg_list = [
        "--version",
        "--debuginfo",
        "--list-instances",
        "--edit",
        "--edit-instance-name", "NewInstance",
        "--overwrite-existing-instance",
        "--edit-data-path", "/new/path",
        "--copy-data",
        "--owner", "123456789",
        "--co-owner", "987654321", "1122334455",
        "-p", "!",
        "--no-prompt",
        "--no-cogs",
        "--load-cogs", "cog1", "cog2",
        "--unload-cogs", "cog3",
        "--cog-path", "/cogs/path1", "/cogs/path2",
        "--dry-run",
        "-v", "-v",
        "--dev",
        "--mentionable",
        "--rpc",
        "--rpc-port", "7000",
        "--token", "fake_token_value_that_is_long_enough_for_testing_purposes__________",
        "--no-instance",
        "TestInstance",
        "--team-members-are-owners",
        "--disable-intent", "guilds",
        "--force-rich-logging",
        "--rich-traceback-extra-lines", "5",
        "--rich-traceback-show-locals",
        "--message-cache-size", "2000",
        "--no-message-cache"
    ]
    args = parse_cli_flags(arg_list)
    assert args.version is True
    assert args.debuginfo is True
    assert args.list_instances is True
    assert args.edit is True
    assert args.edit_instance_name == "NewInstance"
    assert args.overwrite_existing_instance is True
    assert args.edit_data_path == "/new/path"
    assert args.copy_data is True
    assert args.owner == 123456789
    assert args.co_owner == [987654321, 1122334455]
    # The prefix should appear as a sorted list (with one element in this case).
    assert args.prefix == ["!"]
    assert args.no_prompt is True
    assert args.no_cogs is True
    assert args.load_cogs == ["cog1", "cog2"]
    assert args.unload_cogs == ["cog3"]
    assert args.cog_path == ["/cogs/path1", "/cogs/path2"]
    assert args.dry_run is True
    # logging_level should be increased due to two -v flags.
    assert args.logging_level > 0
    assert args.dev is True
    assert args.mentionable is True
    assert args.rpc is True
    assert args.rpc_port == 7000
    expected_token = "fake_token_value_that_is_long_enough_for_testing_purposes__________"
    assert args.token == expected_token
    assert args.no_instance is True
    assert args.instance_name == "TestInstance"
    assert args.use_team_features is True
    # --disable-intent should be parsed as a list.
    assert args.disable_intent == ["guilds"]
    # Check rich logging flags and traceback settings.
    assert args.rich_logging is True
    assert args.rich_traceback_extra_lines == 5
    assert args.rich_traceback_show_locals is True
    assert args.message_cache_size == 2000
    assert args.no_message_cache is True

def test_interactive_config_prefix_startswith_slash(monkeypatch):
    """Test that interactive_config reprompts when the user enters a prefix starting with '/'."""
    # Simulate inputs: prefix that starts with '/', then a valid prefix "!" and confirmation "y".
    responses = iter(["/hello", "!", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    from redbot.core._cli import interactive_config
    class FakeConfigItem:
        async def set(self, value):
            self.value = value
    class FakeConfig:
        def __init__(self):
            self.token = FakeConfigItem()
            self.prefix = FakeConfigItem()
    class FakeRed:
        def __init__(self):
            self._config = FakeConfig()
    red = FakeRed()
    # token_set True so token input is skipped, prefix_set False so prefix input is required.
    result = __import__("asyncio").run(interactive_config(red, token_set=True, prefix_set=False, print_header=False))
    assert result is None
    assert red._config.prefix.value == ["!"]

def test_parse_cli_flags_rich_logging_conflict():
    """Test that when both force rich logging and force disable rich logging flags are provided, the last one wins."""
    from redbot.core._cli import parse_cli_flags
    # Note: since argparse processes arguments in the order given, --force-disable-rich-logging overwrites the previous setting.
    args = parse_cli_flags(["--force-rich-logging", "--force-disable-rich-logging"])
    assert args.rich_logging is False

def test_message_cache_size_int_exact_boundary():
    """Test that message_cache_size_int accepts the boundary value 1000."""
    from redbot.core._cli import message_cache_size_int
    assert message_cache_size_int("1000") == 1000

def test_non_negative_int_maxsize_exceeded():
    """Test that non_negative_int raises an error when given a value greater than sys.maxsize."""
    from redbot.core._cli import non_negative_int
@pytest.mark.asyncio
async def test_interactive_config_prefix_keyboard_interrupt(monkeypatch):
    """Test interactive_config handles KeyboardInterrupt during the prefix confirmation process."""
    # Prepare an iterator that returns a valid prefix first, then raises KeyboardInterrupt on confirmation.
    responses = iter(["!", KeyboardInterrupt()])
    def fake_input(prompt=""):
        value = next(responses)
        if isinstance(value, BaseException):
            raise value
        return value
    monkeypatch.setattr("builtins.input", fake_input)
    from redbot.core._cli import interactive_config, ExitCodes
    # Create fake config objects and a fake Red as used in interactive_config.
    class FakeConfigItem:
        async def set(self, value):
            self.value = value
    class FakeConfig:
        def __init__(self):
            self.token = FakeConfigItem()
            self.prefix = FakeConfigItem()
    class FakeRed:
        def __init__(self):
            self._config = FakeConfig()
    fake_red = FakeRed()
    import asyncio
    with pytest.raises(SystemExit) as excinfo:
        await interactive_config(fake_red, token_set=True, prefix_set=False, print_header=False)
    assert excinfo.value.code == ExitCodes.SHUTDOWN

@pytest.mark.asyncio
async def test_interactive_config_print_header(capsys, monkeypatch):
    """Test that interactive_config prints the header when print_header is True."""
    responses = iter(["!", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    from redbot.core._cli import interactive_config
    class FakeConfigItem:
        async def set(self, value):
            self.value = value
    class FakeConfig:
        def __init__(self):
            self.token = FakeConfigItem()
            self.prefix = FakeConfigItem()
    class FakeRed:
        def __init__(self):
            self._config = FakeConfig()
    fake_red = FakeRed()
    import asyncio
    await interactive_config(fake_red, token_set=True, prefix_set=False, print_header=True)
    captured = capsys.readouterr().out
    # Verify header message is in the captured output.
    assert "Red - Discord Bot | Configuration process" in captured
    assert fake_red._config.prefix.value == ["!"]

def test_parse_cli_flags_instance_none():
    """Test that parse_cli_flags returns instance_name as None when not provided."""
    from redbot.core._cli import parse_cli_flags
    args = parse_cli_flags([])
    assert args.instance_name is None

def test_parse_cli_flags_invalid_co_owner():
    """Test that parse_cli_flags exits (via SystemExit) when an invalid co-owner value is provided."""
    from redbot.core._cli import parse_cli_flags
    with pytest.raises(SystemExit):
        parse_cli_flags(["--co-owner", "notanumber"])
    import sys
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int(str(sys.maxsize + 1))
# End of file.