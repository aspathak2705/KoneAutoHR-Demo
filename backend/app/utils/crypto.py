import base64

def encrypt_token(token: str, key: str = "autohr_secret_crypto_key") -> str:
    if not token:
        return ""
    key_len = len(key)
    xor_bytes = bytes([ord(c) ^ ord(key[i % key_len]) for i, c in enumerate(token)])
    return base64.urlsafe_b64encode(xor_bytes).decode("utf-8")

def decrypt_token(cipher_text: str, key: str = "autohr_secret_crypto_key") -> str:
    if not cipher_text:
        return ""
    try:
        xor_bytes = base64.urlsafe_b64decode(cipher_text.encode("utf-8"))
        key_len = len(key)
        return "".join([chr(b ^ ord(key[i % key_len])) for i, b in enumerate(xor_bytes)])
    except Exception:
        return ""
