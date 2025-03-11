import pytest
from redbot.core import _i18n

class DummyTranslator:
    """Dummy translator used for testing reload translations."""
    def __init__(self):
        self.called = False

    def load_translations(self):
        self.called = True

@pytest.fixture(autouse=True)
def reset_globals():
    """Fixture to reset global state between tests."""
    # Clear translations and reset defaults
    _i18n.translators.clear()
    _i18n.current_locale_default = "en-US"
    _i18n.current_regional_format_default = None
    # Reset context variables by creating new instances
    _i18n.current_locale = _i18n.ContextVar("current_locale")
    _i18n.current_regional_format = _i18n.ContextVar("current_regional_format")

def test_get_standardized_locale_name_valid():
    """Test _get_standardized_locale_name with valid locale."""
    result = _i18n._get_standardized_locale_name("en-US")
    assert result == "en-US"

def test_get_standardized_locale_name_invalid_format():
    """Test _get_standardized_locale_name with invalid locale format (missing country code)."""
    with pytest.raises(ValueError, match="Invalid format - language code has to include country code"):
        _i18n._get_standardized_locale_name("en")

def test_set_global_locale():
    """Test setting global locale and verify that translations are reloaded."""
    dummy = DummyTranslator()
    _i18n.translators.append(dummy)
    result = _i18n.set_global_locale("fr-FR")
    assert result == "fr-FR"
    assert _i18n.current_locale_default == "fr-FR"
    assert dummy.called is True

def test_set_global_locale_invalid():
    """Test setting global locale with invalid locale should raise error."""
    with pytest.raises(ValueError, match="Invalid language code"):
        _i18n.set_global_locale("invalid")

def test_set_global_regional_format_valid():
    """Test setting global regional format with valid locale."""
    result = _i18n.set_global_regional_format("de-DE")
    assert result == "de-DE"
    assert _i18n.current_regional_format_default == "de-DE"

def test_set_global_regional_format_none():
    """Test setting global regional format with None."""
    result = _i18n.set_global_regional_format(None)
    assert result is None
    assert _i18n.current_regional_format_default is None

def test_set_contextual_locale_without_verification():
    """Test setting contextual locale without verification flag."""
    result = _i18n.set_contextual_locale("es", verify_language_code=False)
    # Since verification is False, the locale is not standardized; it should be exactly what was passed.
    assert result == "es"
    assert _i18n.current_locale.get("default") == "es"

def test_set_contextual_locale_with_verification_valid():
    """Test setting contextual locale with verification flag and valid locale."""
    result = _i18n.set_contextual_locale("it-IT", verify_language_code=True)
    assert result == "it-IT"
    assert _i18n.current_locale.get("default") == "it-IT"

def test_set_contextual_locale_with_verification_invalid():
    """Test setting contextual locale with verification flag and invalid locale raises error."""
    with pytest.raises(ValueError):
        _i18n.set_contextual_locale("it", verify_language_code=True)

def test_set_contextual_regional_format_without_verification():
    """Test setting contextual regional format without verification flag."""
    result = _i18n.set_contextual_regional_format("pt-BR", verify_language_code=False)
    assert result == "pt-BR"
    assert _i18n.current_regional_format.get("default") == "pt-BR"

def test_set_contextual_regional_format_with_verification_valid():
    """Test setting contextual regional format with verification flag and valid locale."""
    result = _i18n.set_contextual_regional_format("nl-NL", verify_language_code=True)
    assert result == "nl-NL"
    assert _i18n.current_regional_format.get("default") == "nl-NL"

def test_set_contextual_regional_format_with_verification_invalid():
    """Test setting contextual regional format with verification flag and invalid locale raises error."""
    with pytest.raises(ValueError):
        _i18n.set_contextual_regional_format("nl", verify_language_code=True)

def test_reload_on_contextual_locale():
    """Test that setting a contextual locale triggers _reload_locales on all translators."""
    translator1 = DummyTranslator()
    translator2 = DummyTranslator()
    _i18n.translators.extend([translator1, translator2])
    _i18n.set_contextual_locale("ja-JP", verify_language_code=True)
    assert translator1.called and translator2.called

def test_reload_on_global_locale():
    """Test that setting global locale triggers _reload_locales on all translators."""
    translator1 = DummyTranslator()
    translator2 = DummyTranslator()
    _i18n.translators.extend([translator1, translator2])
    _i18n.set_global_locale("ko-KR")
    assert translator1.called and translator2.called

def test_set_contextual_regional_format_with_none():
    """Test that passing None to set_contextual_regional_format behaves gracefully."""
    # While type hints expect str, this test ensures that None is handled without error.
    result = _i18n.set_contextual_regional_format(None)
    assert result is None
    assert _i18n.current_regional_format.get("default") is None
def test_get_standardized_locale_name_with_underscore_invalid():
    """Test _get_standardized_locale_name with a locale using underscore separator; should raise ValueError due to wrong formatting."""
    with pytest.raises(ValueError, match="Invalid language code. Use format: `en-US`"):
        _i18n._get_standardized_locale_name("en_US")

def test_set_global_regional_format_invalid():
    """Test setting global regional format with an invalid locale code should raise ValueError."""
    with pytest.raises(ValueError, match="Invalid language code"):
        _i18n.set_global_regional_format("invalid")

def test_set_contextual_regional_format_verify_none():
    """Test setting contextual regional format with verification on when passing None gracefully returns None."""
    result = _i18n.set_contextual_regional_format(None, verify_language_code=True)
    assert result is None
    assert _i18n.current_regional_format.get("default") is None
def test_get_standardized_locale_name_lowercase():
    """Test that _get_standardized_locale_name converts a lowercase region code to the correct format."""
    result = _i18n._get_standardized_locale_name("fr-fr")
    assert result == "fr-FR"

def test_context_var_default_value():
    """Test that the ContextVars return the provided fallback value when not set."""
    # Since these context variables were reset in the fixture and not set, they should return the fallback.
    default_locale = _i18n.current_locale.get("default")
    default_regional = _i18n.current_regional_format.get("default")
    assert default_locale == "default"
    assert default_regional == "default"

def test_set_global_locale_multiple_calls():
    """Test that multiple calls to set_global_locale update the global default and trigger reload on translators each time."""
    dummy = DummyTranslator()
    _i18n.translators.append(dummy)
    result1 = _i18n.set_global_locale("es-ES")
    assert result1 == "es-ES"
    assert _i18n.current_locale_default == "es-ES"
    # Reset dummy flag to test subsequent call
    dummy.called = False
    result2 = _i18n.set_global_locale("pt-PT")
    assert result2 == "pt-PT"
    assert _i18n.current_locale_default == "pt-PT"
    assert dummy.called is True

def test_set_contextual_locale_multiple_calls():
    """Test that multiple calls to set_contextual_locale update the ContextVar and trigger reload on translators each time."""
    dummy = DummyTranslator()
    _i18n.translators.append(dummy)
    result1 = _i18n.set_contextual_locale("ru-RU", verify_language_code=True)
    assert result1 == "ru-RU"
    assert _i18n.current_locale.get("default") == "ru-RU"
    # Reset dummy flag to test subsequent call
    dummy.called = False
    result2 = _i18n.set_contextual_locale("ar-SA", verify_language_code=True)
    assert result2 == "ar-SA"
    assert _i18n.current_locale.get("default") == "ar-SA"
    assert dummy.called is True
def test_get_standardized_locale_name_empty():
    """Test _get_standardized_locale_name with an empty string to ensure it raises a ValueError."""
    with pytest.raises(ValueError, match="Invalid language code"):
        _i18n._get_standardized_locale_name("")

class FailingTranslator:
    """Dummy translator that always raises an exception when load_translations is called."""
    def load_translations(self):
        raise RuntimeError("Translation failure")

def test_set_contextual_locale_propagate_exception():
    """Test that an exception in translator.load_translations propagates when setting a contextual locale."""
    failing = FailingTranslator()
    _i18n.translators.append(failing)
    with pytest.raises(RuntimeError, match="Translation failure"):
        _i18n.set_contextual_locale("ja-JP", verify_language_code=True)

def test_set_global_locale_propagate_exception():
    """Test that an exception in translator.load_translations propagates when setting a global locale."""
    failing = FailingTranslator()
    _i18n.translators.append(failing)
    with pytest.raises(RuntimeError, match="Translation failure"):
        _i18n.set_global_locale("ko-KR")