import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import pytest  # noqa: E402

import accounts  # noqa: E402


def test_no_login_details_are_written_in_the_code(monkeypatch):
    for name in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(accounts.NotConfiguredError):
        accounts.login("aline", "password")


def test_usernames_become_supabase_emails():
    assert accounts.as_email(" Aline ") == "aline@soma.local"
    assert accounts.as_email("teacher@school.rw") == "teacher@school.rw"


def test_new_secret_keys_stay_out_of_the_authorization_header():
    assert accounts.key_headers("sb_secret_abc") == {"apikey": "sb_secret_abc"}
    assert accounts.key_headers("eyJold")["Authorization"] == "Bearer eyJold"


def test_role_comes_from_app_metadata_which_only_the_admin_can_set():
    user = {"id": "1", "email": "a@soma.local", "app_metadata": {"role": "teacher"},
            "user_metadata": {"role": "learner", "name": "A"}}
    assert accounts.describe(user)["role"] == "teacher"


def test_class_codes_are_easy_to_read_from_a_board():
    code = accounts.new_code()
    assert len(code) == 6 and not set(code) & set("01IO")


def test_new_accounts_need_a_known_role_and_a_long_password(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_x")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    with pytest.raises(accounts.AccountError, match="unknown_role"):
        accounts.create_user("a", "longpassword", "boss", "A")
    with pytest.raises(accounts.AccountError, match="short_password"):
        accounts.create_user("a", "short", "learner", "A")
