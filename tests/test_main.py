import pytest
from datetime import timedelta
# Assuming your main bot script is main.py and these can be imported
# If main.py is not structured to allow direct import of these,
# you might need to copy these functions here or refactor main.py
# For this exercise, we assume they can be imported or are copied/adapted.

# --- Functions from main.py (or adapted for testing) ---

# Define roles (copied from main.py for test context)
ADMIN = "ADMIN"
MODERATOR = "MODERATOR"
USER = "USER"
BOT_OWNER_ID = 123456789 # Example ID, ensure consistency if used in tests

# In-memory stores (copied for test context)
user_roles_global = {} # Simulates global user_roles from main.py
forbidden_keywords_global = ["keyword1", "spamlink.com", "another_bad_word"] # From main.py

def parse_duration(duration_str: str) -> timedelta | None:
    if not duration_str or len(duration_str) < 2:
        return None
    value_str = duration_str[:-1]
    unit = duration_str[-1].lower()
    if not value_str.isdigit():
        return None
    value = int(value_str)
    
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    return None

def get_user_role(chat_id: int, user_id: int, roles_dict: dict) -> str:
    """Returns the role of the user. Defaults to USER."""
    return roles_dict.get(chat_id, {}).get(user_id, USER)

def is_admin(chat_id: int, user_id: int, roles_dict: dict) -> bool:
    """Returns True if the user is an ADMIN."""
    return get_user_role(chat_id, user_id, roles_dict) == ADMIN

def is_moderator(chat_id: int, user_id: int, roles_dict: dict) -> bool:
    """Returns True if the user is a MODERATOR or ADMIN."""
    return get_user_role(chat_id, user_id, roles_dict) in [ADMIN, MODERATOR]

def contains_forbidden_keyword(text: str, keywords: list[str]) -> bool:
    """Simulates the forbidden keyword check logic."""
    if not text: # Added check for empty text
        return False
    return any(keyword.lower() in text.lower() for keyword in keywords)

# --- Unit Tests ---

# Tests for parse_duration
@pytest.mark.parametrize("duration_str, expected_timedelta", [
    ("1h", timedelta(hours=1)),
    ("30m", timedelta(minutes=30)),
    ("2d", timedelta(days=2)),
    ("10h", timedelta(hours=10)),
    ("5m", timedelta(minutes=5)),
    ("0m", timedelta(minutes=0)), # Test zero duration
    ("0h", timedelta(hours=0)),
    ("0d", timedelta(days=0)),
])
def test_parse_duration_valid(duration_str, expected_timedelta):
    assert parse_duration(duration_str) == expected_timedelta

@pytest.mark.parametrize("duration_str", [
    "1z",      # Invalid unit
    "abc",     # Non-numeric value
    "",        # Empty string
    "h",       # No value
    "1",       # No unit
    "1hm",     # Mixed unit (unsupported)
    "1h30m",   # Combined (unsupported by current simple parser)
    "-1h",     # Negative value (not handled by isdigit)
    "1.5h",    # Float value (not handled by isdigit)
])
def test_parse_duration_invalid(duration_str):
    assert parse_duration(duration_str) is None

# Tests for Role Management
@pytest.fixture
def sample_roles():
    # Fixture to provide a sample user_roles dictionary for tests
    return {
        100: { # chat_id 100
            1: ADMIN,
            2: MODERATOR,
            3: USER,
            BOT_OWNER_ID: ADMIN # Ensure bot owner is admin in this chat
        },
        200: { # chat_id 200
            4: MODERATOR,
            5: USER
        }
    }

def test_get_user_role_admin(sample_roles):
    assert get_user_role(100, 1, sample_roles) == ADMIN

def test_get_user_role_moderator(sample_roles):
    assert get_user_role(100, 2, sample_roles) == MODERATOR

def test_get_user_role_user(sample_roles):
    assert get_user_role(100, 3, sample_roles) == USER

def test_get_user_role_default_user(sample_roles):
    # User not in dict for chat 100
    assert get_user_role(100, 99, sample_roles) == USER
    # User in dict for chat 200, but not chat 100
    assert get_user_role(100, 4, sample_roles) == USER

def test_get_user_role_chat_not_found(sample_roles):
    assert get_user_role(999, 1, sample_roles) == USER # Chat 999 not in roles

def test_is_admin_true(sample_roles):
    assert is_admin(100, 1, sample_roles) is True

def test_is_admin_false_moderator(sample_roles):
    assert is_admin(100, 2, sample_roles) is False

def test_is_admin_false_user(sample_roles):
    assert is_admin(100, 3, sample_roles) is False

def test_is_admin_false_default_user(sample_roles):
    assert is_admin(100, 99, sample_roles) is False

def test_is_moderator_true_admin(sample_roles):
    # Admins are also moderators
    assert is_moderator(100, 1, sample_roles) is True

def test_is_moderator_true_moderator(sample_roles):
    assert is_moderator(100, 2, sample_roles) is True

def test_is_moderator_false_user(sample_roles):
    assert is_moderator(100, 3, sample_roles) is False

def test_is_moderator_false_default_user(sample_roles):
    assert is_moderator(100, 99, sample_roles) is False

# Tests for Forbidden Keyword Detection
def test_contains_forbidden_keyword_true():
    assert contains_forbidden_keyword("This message has keyword1", forbidden_keywords_global) is True
    assert contains_forbidden_keyword("Check out spamlink.com", forbidden_keywords_global) is True
    assert contains_forbidden_keyword("another_bad_word here", forbidden_keywords_global) is True
    assert contains_forbidden_keyword("Message with KEYWORD1 in caps", forbidden_keywords_global) is True # Case-insensitivity

def test_contains_forbidden_keyword_false():
    assert contains_forbidden_keyword("This is a clean message", forbidden_keywords_global) is False
    assert contains_forbidden_keyword("No forbidden words here", forbidden_keywords_global) is False
    assert contains_forbidden_keyword("", forbidden_keywords_global) is False # Empty string

def test_contains_forbidden_keyword_partial_match_not_forbidden():
    # Ensure "key" is not forbidden if "keyword1" is.
    assert contains_forbidden_keyword("This message has key word", forbidden_keywords_global) is False


# How to run tests:
# Ensure pytest is installed (pip install -r requirements.txt)
# From the project root directory, run: python -m pytest
# Or simply: pytest
# (Assuming this file is in a 'tests' subdirectory and main.py is in the root or discoverable by Python's import system)
#
# For the functions copied/adapted here, this test file can be run directly if main.py is not importable.
# If main.py can be imported (e.g., by adding an __init__.py to the root and tests directory,
# and ensuring the root is in PYTHONPATH), you could replace the copied functions with imports like:
# from ..main import parse_duration, get_user_role, ADMIN, MODERATOR, USER, BOT_OWNER_ID
# (and adjust function signatures for roles_dict if using the global `user_roles` from main.py directly)
#
# Note: Testing async functions that interact with Telegram's API (like command handlers)
# is more complex and would require an async test runner (like pytest-asyncio) and extensive mocking.
# The tests here focus on synchronous, pure-logic utility functions.
