"""
Message Encryption Service
End-to-end encryption for chat messages using AES-256
"""
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import base64
import os


def generate_rsa_keypair():
    """
    Generate RSA key pair for a user.
    Returns (public_key_pem, private_key_pem) as strings.
    """
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Get public key
    public_key = private_key.public_key()
    
    # Serialize to PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    return public_pem, private_pem


def encrypt_message(message: str, recipient_public_key_pem: str) -> str:
    """
    Encrypt a message using AES-256, then encrypt the AES key with recipient's RSA public key.
    Returns: base64-encoded string containing encrypted_key + encrypted_message
    """
    if not message:
        return ""
    
    # Generate random AES key (256-bit)
    aes_key = os.urandom(32)
    
    # Generate random IV
    iv = os.urandom(16)
    
    # Encrypt message with AES
    cipher = Cipher(
        algorithms.AES(aes_key),
        modes.CFB(iv),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    encrypted_message = encryptor.update(message.encode('utf-8')) + encryptor.finalize()
    
    # Load recipient's public key
    public_key = serialization.load_pem_public_key(
        recipient_public_key_pem.encode('utf-8'),
        backend=default_backend()
    )
    
    # Encrypt AES key with RSA
    encrypted_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    # Combine: encrypted_key_length (4 bytes) + encrypted_key + iv + encrypted_message
    combined = len(encrypted_key).to_bytes(4, 'big') + encrypted_key + iv + encrypted_message
    
    # Base64 encode for storage
    return base64.b64encode(combined).decode('utf-8')


def decrypt_message(encrypted_data: str, recipient_private_key_pem: str) -> str:
    """
    Decrypt a message using recipient's RSA private key to get AES key, then decrypt message.
    Returns: decrypted message string
    """
    if not encrypted_data:
        return ""
    
    try:
        # Base64 decode
        combined = base64.b64decode(encrypted_data.encode('utf-8'))
        
        # Extract encrypted_key_length
        key_length = int.from_bytes(combined[:4], 'big')
        
        # Extract encrypted key, IV, and encrypted message
        encrypted_key = combined[4:4+key_length]
        iv = combined[4+key_length:4+key_length+16]
        encrypted_message = combined[4+key_length+16:]
        
        # Load private key
        private_key = serialization.load_pem_private_key(
            recipient_private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        
        # Decrypt AES key with RSA
        aes_key = private_key.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Decrypt message with AES
        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.CFB(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        decrypted_message = decryptor.update(encrypted_message) + decryptor.finalize()
        
        return decrypted_message.decode('utf-8')
        
    except Exception as e:
        print(f"Decryption error: {e}")
        return "[Unable to decrypt message]"


def encrypt_private_key(private_key_pem: str, password: str) -> str:
    """
    Encrypt a private key with a password for secure storage.
    Uses AES-256 with password-derived key.
    """
    # Simple password-based encryption (in production, use better KDF like PBKDF2)
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = kdf.derive(password.encode('utf-8'))
    
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(private_key_pem.encode('utf-8')) + encryptor.finalize()
    
    # Combine salt + iv + encrypted_data
    combined = salt + iv + encrypted
    return base64.b64encode(combined).decode('utf-8')


def decrypt_private_key(encrypted_private_key: str, password: str) -> str:
    """
    Decrypt a private key using password.
    """
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    
    try:
        combined = base64.b64decode(encrypted_private_key.encode('utf-8'))
        salt = combined[:16]
        iv = combined[16:32]
        encrypted_data = combined[32:]
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(password.encode('utf-8'))
        
        cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
        
        return decrypted.decode('utf-8')
    except Exception as e:
        print(f"Private key decryption error: {e}")
        return None
