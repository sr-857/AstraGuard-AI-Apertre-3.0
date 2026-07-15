"""Tests for Data Encryption (#647)"""

import pytest
import os
from src.security.encryption import DataEncryption, encrypt_field, decrypt_field


class TestDataEncryption:
    @pytest.fixture
    def encryption(self):
        return DataEncryption(master_key="test-master-key-32-bytes-long!")
    
    def test_encrypt_decrypt_string(self, encryption):
        plaintext = "sensitive data 123"
        ciphertext = encryption.encrypt(plaintext)
        
        assert ciphertext != plaintext
        assert len(ciphertext) > 0
        
        decrypted = encryption.decrypt(ciphertext)
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_bytes(self, encryption):
        plaintext = b"binary data"
        ciphertext = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(ciphertext)
        
        assert decrypted == plaintext.decode('utf-8')
    
    def test_different_ciphertexts(self, encryption):
        plaintext = "same data"
        ciphertext1 = encryption.encrypt(plaintext)
        ciphertext2 = encryption.encrypt(plaintext)
        
        # Should be different due to random nonce
        assert ciphertext1 != ciphertext2
        
        # But both should decrypt to same plaintext
        assert encryption.decrypt(ciphertext1) == plaintext
        assert encryption.decrypt(ciphertext2) == plaintext
    
    def test_invalid_ciphertext(self, encryption):
        with pytest.raises(ValueError, match="Decryption failed"):
            encryption.decrypt("invalid-ciphertext")
    
    def test_encrypt_dict(self, encryption):
        data = {
            "username": "john_doe",
            "password": "secret123",
            "email": "john@example.com"
        }
        
        encrypted = encryption.encrypt_dict(data, ["password", "email"])
        
        assert encrypted["username"] == "john_doe"  # Not encrypted
        assert encrypted["password"] != "secret123"  # Encrypted
        assert encrypted["email"] != "john@example.com"  # Encrypted
    
    def test_decrypt_dict(self, encryption):
        data = {
            "username": "john_doe",
            "password": "secret123",
            "email": "john@example.com"
        }
        
        encrypted = encryption.encrypt_dict(data, ["password", "email"])
        decrypted = encryption.decrypt_dict(encrypted, ["password", "email"])
        
        assert decrypted == data
    
    def test_convenience_functions(self):
        # Set environment variable for testing
        os.environ["ENCRYPTION_MASTER_KEY"] = "test-key-for-convenience"
        
        plaintext = "test data"
        ciphertext = encrypt_field(plaintext)
        decrypted = decrypt_field(ciphertext)
        
        assert decrypted == plaintext
