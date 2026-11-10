import pytest

from wabot.config import Settings

BASE = {
    "WA_VERIFY_TOKEN": "v",
    "WA_APP_SECRET": "s",
    "WA_ACCESS_TOKEN": "t",
    "WA_PHONE_NUMBER_ID": "p",
}


def set_env(monkeypatch, **extra):
    monkeypatch.setattr("wabot.config.load_dotenv", lambda: None)
    for k in ("OWNER_PHONE_NUMBER", "WABOT_DB_PATH"):
        monkeypatch.delenv(k, raising=False)
    for k, v in {**BASE, **extra}.items():
        monkeypatch.setenv(k, v)


def test_owner_number_is_read_from_env(monkeypatch):
    set_env(monkeypatch, OWNER_PHONE_NUMBER="5491112345678")
    assert Settings.from_env().owner_phone_number == "5491112345678"


def test_owner_number_is_required(monkeypatch):
    set_env(monkeypatch)
    with pytest.raises(RuntimeError, match="OWNER_PHONE_NUMBER"):
        Settings.from_env()


def test_owner_number_must_be_digits(monkeypatch):
    set_env(monkeypatch, OWNER_PHONE_NUMBER="+54 9 11 1234-5678")
    with pytest.raises(RuntimeError, match="digits"):
        Settings.from_env()
