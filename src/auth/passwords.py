import bcrypt

DUMMY_PASSWORD_HASH = (
    "$2b$12$qtpS35Gv9EyuSF1JEydGVuIo8ZxSYbwEOfPS45fVmkuzPXkUQr8Ua"
)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False
