from app.core.crypto import decrypt_str, encrypt_str


def test_roundtrip():
    assert decrypt_str(encrypt_str("00559293976")) == "00559293976"
