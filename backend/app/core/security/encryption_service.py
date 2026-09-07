import os
import json
import base64
from typing import Dict, Any, Tuple, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.security.key_manager import key_manager

class EncryptionService:
    """
    Centralized Encryption Service implementing Envelope Encryption with AES-256-GCM.
    - Master Key (protected via KeyManager / Windows DPAPI) wraps Data Encryption Key (DEK).
    - Per-asset DEKs encrypt asset payload.
    """
    def generate_dek(self) -> bytes:
        return AESGCM.generate_key(bit_length=256)

    def wrap_dek(self, dek: bytes, master_key: bytes) -> str:
        aesgcm = AESGCM(master_key)
        nonce = os.urandom(12)
        wrapped = aesgcm.encrypt(nonce, dek, None)
        # Store as base64 combined nonce + ciphertext
        return base64.b64encode(nonce + wrapped).decode('utf-8')

    def unwrap_dek(self, wrapped_dek_b64: str, master_key: bytes) -> bytes:
        raw = base64.b64decode(wrapped_dek_b64.encode('utf-8'))
        nonce = raw[:12]
        ciphertext = raw[12:]
        aesgcm = AESGCM(master_key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    def encrypt_bytes(self, plaintext: bytes, dek: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypts payload using AES-256-GCM.
        Returns:
            (ciphertext, dek, nonce)
        """
        if dek is None:
            dek = self.generate_dek()
        nonce = os.urandom(12)
        aesgcm = AESGCM(dek)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return ciphertext, dek, nonce

    def decrypt_bytes(self, ciphertext: bytes, dek: bytes, nonce: bytes) -> bytes:
        """
        Decrypts AES-256-GCM payload.
        Raises InvalidTag if tampered or invalid key.
        """
        aesgcm = AESGCM(dek)
        return aesgcm.decrypt(nonce, ciphertext, None)

    def encrypt_json(self, data: Dict[str, Any], dek: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
        payload = json.dumps(data).encode('utf-8')
        return self.encrypt_bytes(payload, dek)

    def decrypt_json(self, ciphertext: bytes, dek: bytes, nonce: bytes) -> Dict[str, Any]:
        plaintext = self.decrypt_bytes(ciphertext, dek, nonce)
        return json.loads(plaintext.decode('utf-8'))

encryption_service = EncryptionService()
