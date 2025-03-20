import base64
from typing import Dict, Type

import bcrypt
from pydantic import BaseModel


class HasherError(Exception):
    """Generic error raised by Password Hashers"""


class DecryptionError(HasherError):
    """Raised when a Password Handler attempts to decrypt a password and cannot"""


class HasherNotFoundError(HasherError):
    """Raised when a Password Handler for a password type cannot be found"""


class Password(BaseModel):
    hash: str
    type: str


class PasswordHandler:
    encoding = "UTF-8"

    @classmethod
    def validate(cls, plaintext: str, hashed: str) -> bool:
        raise NotImplementedError()

    @classmethod
    def hash(cls, plaintext: str) -> Password:
        raise NotImplementedError()

    @classmethod
    def decrypt(cls, hashed: str) -> str:
        raise DecryptionError("Decrypting this type of password is not possible")


class PlaintextPasswordHandler(PasswordHandler):
    prefix = "__"
    suffix = "__"

    @classmethod
    def validate(cls, plaintext: str, hashed: str) -> bool:
        return f"{cls.prefix}{plaintext}{cls.suffix}" == hashed

    @classmethod
    def hash(cls, plaintext: str) -> Password:
        return Password(type="plaintext", hash=f"{cls.prefix}{plaintext}{cls.suffix}")

    @classmethod
    def decrypt(cls, hashed: str) -> str:
        start = len(cls.prefix)
        end = -len(cls.suffix)
        return hashed[start:end]


class Base64PasswordHandler(PasswordHandler):
    @classmethod
    def validate(cls, plaintext: str, hashed: str) -> bool:
        return plaintext == base64.b64decode(hashed).decode(cls.encoding)

    @classmethod
    def hash(cls, plaintext: str) -> Password:
        return Password(type="base64", hash=base64.b64encode(plaintext.encode(cls.encoding)).decode())

    @classmethod
    def decrypt(cls, hashed: str) -> str:
        return base64.b64decode(hashed).decode(cls.encoding)


class BcryptPasswordHandler(PasswordHandler):
    @classmethod
    def validate(cls, plaintext: str, hashed: str) -> bool:
        return bcrypt.checkpw(plaintext.encode(cls.encoding), hashed.encode())

    @classmethod
    def hash(cls, plaintext: str, salt: str = None, **kwargs) -> Password:
        salt = salt or bcrypt.gensalt(**kwargs)
        return Password(
            type="bcrypt",
            hash=bcrypt.hashpw(plaintext.encode(cls.encoding), salt).decode(),
        )


hasher_map: Dict[str, Type[PasswordHandler]] = {
    "plaintext": PlaintextPasswordHandler,
    "bcrypt": BcryptPasswordHandler,
    "base64": Base64PasswordHandler,
}
