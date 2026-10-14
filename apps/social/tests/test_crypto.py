import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ImproperlyConfigured

from apps.social.crypto import decrypt, encrypt


def test_encrypt_roundtrip_and_ciphertext_differs():
    token = encrypt("ya29.secret-access-token")

    assert token != "ya29.secret-access-token"
    assert "secret-access-token" not in token
    assert decrypt(token) == "ya29.secret-access-token"


def test_same_plaintext_encrypts_differently_each_time():
    assert encrypt("same") != encrypt("same")


def test_decrypt_with_wrong_key_raises(settings):
    token = encrypt("secret")
    settings.OAUTH_ENCRYPTION_KEY = Fernet.generate_key().decode()

    with pytest.raises(InvalidToken):
        decrypt(token)


def test_tampered_ciphertext_raises():
    token = encrypt("secret")

    with pytest.raises(InvalidToken):
        decrypt(token[:-4] + "AAAA")


@pytest.mark.parametrize("bad_key", ["", "not-a-fernet-key"])
def test_missing_or_malformed_key_is_a_configuration_error(settings, bad_key):
    settings.OAUTH_ENCRYPTION_KEY = bad_key

    with pytest.raises(ImproperlyConfigured):
        encrypt("secret")
