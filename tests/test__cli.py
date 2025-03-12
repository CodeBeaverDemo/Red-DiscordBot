import argparse
import asyncio
import sys
import pytest
import discord

from redbot.core._cli import (
    confirm,
    interactive_config,
    non_negative_int,
    message_cache_size_int,
    parse_cli_flags,
    ExitCodes,
)

class FakeConfigSub:
    """Fake sub-config with a set method."""
    def __init__(self):
        self.value = None

    async def set(self, value):
        self.value = value

class FakeConfig:
    """Fake configuration object holding token and prefix config."""
    def __init__(self):
        self.token = FakeConfigSub()
        self.prefix = FakeConfigSub()

class FakeRed:
    """Fake red object with _config attribute."""
    def __init__(self):
        self._config = FakeConfig()

def test_confirm_yes(monkeypatch):
    """Test confirm function returns True when user inputs yes."""
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    assert confirm("Proceed?") is True

def test_confirm_no(monkeypatch):
    """Test confirm function returns False when user inputs no."""
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    assert confirm("Proceed?") is False

def test_confirm_default(monkeypatch):
    """Test confirm function returns default when empty input is provided."""
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    # When default=True and input is empty, should return True.
    assert confirm("Proceed?", default=True) is True
    # When default=False and input is empty, should return False.
    assert confirm("Proceed?", default=False) is False

def test_non_negative_int_valid():
    """Test non_negative_int with valid numeric strings."""
    assert non_negative_int("0") == 0
    assert non_negative_int(str(sys.maxsize)) == sys.maxsize

def test_non_negative_int_invalid():
    """Test non_negative_int raises an error on negative input."""
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int("-1")

def test_message_cache_size_int_valid():
    """Test message_cache_size_int accepts valid input."""
    assert message_cache_size_int("1000") == 1000

def test_message_cache_size_int_invalid():
    """Test message_cache_size_int raises error when number is too small."""
    with pytest.raises(argparse.ArgumentTypeError):
        message_cache_size_int("999")

def test_parse_cli_flags_defaults():
    """Test parse_cli_flags returns default values when no arguments are given."""
    args = parse_cli_flags([])
    # instance_name should be None and no-cogs should be False
    assert args.instance_name is None
    assert args.no_cogs is False
    # logging_level should be an integer
    assert isinstance(args.logging_level, int)

def test_parse_cli_flags_prefix_sorting():
    """Test parse_cli_flags sorts the provided prefixes in reverse order."""
    args = parse_cli_flags(["--prefix", "!", "--prefix", "$"])
    # The prefixes should be sorted in reverse order.
    assert args.prefix == sorted(args.prefix, reverse=True)

def test_parse_cli_flags_verbose():
    """Test parse_cli_flags increases verbosity with multiple -v flags."""
    args = parse_cli_flags(["-v", "-v", "-v"])
    assert args.logging_level > 0

@pytest.mark.asyncio
async def test_interactive_config_both_prompts(monkeypatch):
    """Test interactive_config prompts for token and prefix when they are not preset."""
    # Prepare a sequence of inputs: token (must be at least 50 characters), prefix, and confirm prefix prompt.
    inputs = iter(["a" * 50, "!", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    fake_red = FakeRed()
    # token_set False and prefix_set False trigger input prompts.
    token = await interactive_config(fake_red, token_set=False, prefix_set=False, print_header=False)
    assert token == "a" * 50
    # Check that the token was saved in the config.
    assert fake_red._config.token.value == "a" * 50
    # The prefix is stored as a list.
    assert fake_red._config.prefix.value == ["!"]

@pytest.mark.asyncio
async def test_interactive_config_skip_prompts():
    """Test interactive_config skips prompting when configuration is preset."""
    fake_red = FakeRed()
    # When token_set and prefix_set are True, no inputs should be requested.
    token = await interactive_config(fake_red, token_set=True, prefix_set=True, print_header=False)
    # The function returns None when no configuration is needed.
    assert token is None

def test_confirm_keyboard_interrupt(monkeypatch):
    """Test confirm function exits with SHUTDOWN on KeyboardInterrupt."""
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(SystemExit) as e:
        confirm("Interrupt?")
    assert e.value.code == ExitCodes.SHUTDOWN

def test_confirm_eof_error(monkeypatch):
    """Test confirm function exits with INVALID_CLI_USAGE on EOFError."""
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(EOFError))
    with pytest.raises(SystemExit) as e:
        confirm("EOF?")
    assert e.value.code == ExitCodes.INVALID_CLI_USAGE

def test_confirm_invalid_input_then_valid(monkeypatch, capsys):
    """Test confirm function returns default when empty input follows an invalid input."""
    inputs = iter(["maybe", "", "yes"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    # When default is True, an empty string should return True
    result = confirm("Proceed?", default=True)
    captured = capsys.readouterr().out
    assert "Error: invalid input" in captured
    assert result is True

def test_parse_cli_flags_version():
    """Test parse_cli_flags sets the --version flag correctly."""
    args = parse_cli_flags(["--version"])
    assert args.version is True

def test_parse_cli_flags_extra_args():
    """Test parse_cli_flags with various extra arguments."""
    args = parse_cli_flags([
        "instance1",
        "--owner", "12345",
        "--co-owner", "23456", "34567",
        "--edit",
        "--edit-instance-name", "new_instance",
        "--edit-data-path", "/tmp/data",
        "--copy-data",
        "--no-instance"
    ])
    assert args.instance_name == "instance1"
    assert args.owner == 12345
    assert args.co_owner == [23456, 34567]
    assert args.edit is True
    assert args.edit_instance_name == "new_instance"
    assert args.edit_data_path == "/tmp/data"
    assert args.copy_data is True
    assert args.no_instance is True

def test_parse_cli_flags_disable_intent():
    """Test parse_cli_flags with --disable-intent flag using a valid intent."""
    # Use a valid intent flag from discord if available, else fallback to "guilds"
    valid_intents = list(discord.Intents.VALID_FLAGS)
    intent = valid_intents[0] if valid_intents else "guilds"
    args = parse_cli_flags(["--disable-intent", intent])
    assert args.disable_intent == [intent]

@pytest.mark.asyncio
async def test_interactive_config_keyboard_interrupt(monkeypatch):
    """Test interactive_config raises KeyboardInterrupt when token input is interrupted."""
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(KeyboardInterrupt))
    fake_red = FakeRed()
    with pytest.raises(KeyboardInterrupt):
        await interactive_config(fake_red, token_set=False, prefix_set=True, print_header=False)

@pytest.mark.asyncio
async def test_interactive_config_eof_error(monkeypatch):
    """Test interactive_config raises EOFError when token input receives EOF."""
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(EOFError))
    fake_red = FakeRed()
    with pytest.raises(EOFError):
        await interactive_config(fake_red, token_set=False, prefix_set=True, print_header=False)
# End of tests
@pytest.mark.asyncio
async def test_interactive_config_prefix_edge_case(monkeypatch):
    """Test interactive_config when the provided prefix is overly long or starts with forbidden '/' then recovers."""
    # Chain of inputs:
    # - Token: valid 50-char token.
    # - Prefix attempt1: overly long ("AAAAAAAAAAAA"), confirm "n" so it loops.
    # - Prefix attempt2: starts with "/" ("/hello") so it is rejected and does not trigger confirm.
    # - Prefix attempt3: valid "!" then confirmation prompt "y".
    inputs = iter([
        "a" * 50,          # valid token input
        "AAAAAAAAAAAA",    # too long prefix -> prompt confirmation below asks and gets "n"
        "n",               # decline overly long prefix prompt
        "/hello",          # prefix starting with '/' is rejected
        "!",               # valid prefix attempt
        "y"                # user confirms the chosen prefix
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    fake_red = FakeRed()
    token = await interactive_config(fake_red, token_set=False, prefix_set=False, print_header=False)
    assert token == "a" * 50
    assert fake_red._config.token.value == "a" * 50
    # The prefix should be stored as a list containing "!".
    assert fake_red._config.prefix.value == ["!"]

def test_confirm_invalid_default(monkeypatch):
    """Test that confirm raises a TypeError when an invalid default value is provided."""
    with pytest.raises(TypeError):
        confirm("Should fail?", default="invalid")

def test_non_negative_int_exceeds_maxsize():
    """Test non_negative_int raises an error when input exceeds sys.maxsize."""
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int(str(sys.maxsize + 1))

def test_parse_cli_flags_rich_logging_flags():
    """Test that rich logging flags are correctly parsed."""
    # Test --force-rich-logging
    args1 = parse_cli_flags(["--force-rich-logging"])
    assert args1.rich_logging is True

    # Test --force-disable-rich-logging
    args2 = parse_cli_flags(["--force-disable-rich-logging"])
    assert args2.rich_logging is False

def test_parse_cli_flags_rich_traceback_options():
    """Test that rich traceback options are correctly parsed."""
    args = parse_cli_flags(["--rich-traceback-extra-lines", "5", "--rich-traceback-show-locals"])
    assert args.rich_traceback_extra_lines == 5
    assert args.rich_traceback_show_locals is True

def test_parse_cli_flags_load_unload_and_cog_path():
    """Test parse_cli_flags when passing multiple load-cogs, unload-cogs, and cog-path values."""
    args = parse_cli_flags([
        "--load-cogs", "cog1", "cog2",
        "--unload-cogs", "cog3",
        "--cog-path", "/path1", "--cog-path", "/path2"
    ])
    # load-cogs and unload-cogs should be extended lists as provided.
    assert args.load_cogs == ["cog1", "cog2"]
    assert args.unload_cogs == ["cog3"]
    # cog-path should be a list of paths.
    assert args.cog_path == ["/path1", "/path2"]

def test_confirm_uppercase(monkeypatch):
    """Test confirm function handles uppercase 'YES' input as valid yes."""
    monkeypatch.setattr("builtins.input", lambda prompt: "YES")
    assert confirm("Proceed?") is True

def test_parse_cli_flags_misc_flags():
    """Test parse_cli_flags with various miscellaneous flags including debuginfo, mentionable, dry-run, no-prompt, dev, rpc, rpc-port and no-message-cache."""
    # Provide several miscellaneous flags and verify that they are set accordingly.
    args = parse_cli_flags([
        "--debuginfo",
        "--mentionable",
        "--dry-run",
        "--no-prompt",
        "--dev",
        "--rpc",
        "--rpc-port", "7000",
        "--no-message-cache"
    ])
    assert args.debuginfo is True
    assert args.mentionable is True
    assert args.dry_run is True
    assert args.no_prompt is True
    assert args.dev is True
    assert args.rpc is True
    assert args.rpc_port == 7000
    assert args.no_message_cache is True

@pytest.mark.asyncio
async def test_interactive_config_prefix_overly_long_accept(monkeypatch):
    """Test interactive_config accepts an overly long prefix when the user confirms it twice."""
    # Sequence:
    # 1. The user inputs a valid token (a 50-character string).
    # 2. When asked for a prefix, the user enters an overly long prefix ("AAAAAAAAAAAA").
    # 3. The overly long prefix is detected and the user confirms it is okay (input "y").
    # 4. The user is asked to confirm the final chosen prefix and confirms again (input "y").
    inputs = iter([
        "a" * 50,          # valid token input
        "AAAAAAAAAAAA",    # overly long prefix which exceeds 10 characters
        "y",               # confirmation for overly long prefix
        "y"                # final confirmation of the chosen prefix
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    fake_red = FakeRed()
    token = await interactive_config(fake_red, token_set=False, prefix_set=False, print_header=False)
    assert token == "a" * 50
    # Verify that the token is saved in the fake configuration.
    assert fake_red._config.token.value == "a" * 50
    # Verify that the confirmed prefix is saved as a list.
    assert fake_red._config.prefix.value == ["AAAAAAAAAAAA"]
@pytest.mark.asyncio
async def test_interactive_config_prefix_only(monkeypatch):
    """Test interactive_config prompts for prefix only when token_set is True and prefix_set is False."""
    # Only the prefix prompt should be shown since token_set is True.
    inputs = iter(["!", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    fake_red = FakeRed()
    token = await interactive_config(fake_red, token_set=True, prefix_set=False, print_header=False)
    # No token prompt, returns None
    assert token is None
    # The chosen prefix should be saved as a list
    assert fake_red._config.prefix.value == ["!"]

def test_parse_cli_flags_invalid_rich_traceback_extra_lines():
    """Test parse_cli_flags with an invalid value for rich traceback extra lines."""
    # non_negative_int should reject negative numbers like -1, causing argparse to exit.
    with pytest.raises(SystemExit):
            parse_cli_flags(["--rich-traceback-extra-lines", "-1"])

def test_parse_cli_flags_invalid_owner():
    """Test parse_cli_flags with an invalid owner argument (non-numeric)."""
    # Passing a non-numeric owner should fail as owner expects an int.
    with pytest.raises(SystemExit):
            parse_cli_flags(["--owner", "abc"])

@pytest.mark.asyncio
async def test_interactive_config_prints_header(monkeypatch, capsys):
    """Test that interactive_config prints the header when print_header is True."""
    # Supply a valid token of 50 characters, prefix and confirmation.
    inputs = iter(["a" * 50, "!", "y"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    fake_red = FakeRed()
    await interactive_config(fake_red, token_set=False, prefix_set=False, print_header=True)
    captured = capsys.readouterr().out
    # Check the header printed.
    assert "Red - Discord Bot | Configuration process" in captured
    # Also verify that the token was saved in the configuration.
    assert fake_red._config.token.value == "a" * 50