import jwt
from passlib.context import CryptContext
import datetime
from derms_schemas import TokenResponse
import os

JWT_SECRET_KEY      = os.getenv("JWT_SECRET_KEY", "my-super-secret-key-never-put-this-in-code")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

def create_token(username: str) -> TokenResponse:
    payload = {
        "sub": username,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30),
        "iat": datetime.datetime.now(datetime.timezone.utc)
    }
    token = jwt.encode(key=JWT_SECRET_KEY, algorithm=ALGORITHM, payload=payload)
    response = TokenResponse(access_token=token, token_type="bearer")
    return response

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

if __name__ == "__main__":
    h = hash_password("secret123")
    print(h)                                    # long bcrypt string starting with $2b$
    print(verify_password("secret123", h))      # True
    print(verify_password("wrong", h))          # False