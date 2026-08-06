import hashlib, hmac, json, time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, unquote
import jwt
from .config import settings

class AuthError(Exception):
    pass

def validate_init_data(init_data: str, max_age: int = 3600) -> dict:
    try:
        data = dict(parse_qsl(init_data))
        received_hash = data.pop("hash", "")
        if not received_hash or "user" not in data:
            raise AuthError("no hash or user")
        check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        secret = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
        computed = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed, received_hash):
            raise AuthError("bad signature")
        if time.time() - int(data.get("auth_date", "0")) > max_age:
            raise AuthError("initData expired")
        return json.loads(unquote(data["user"]))
    except AuthError:
        raise
    except Exception:
        raise AuthError("malformed initData")

def issue_jwt(tg_id: int) -> str:
    payload = {"sub": str(tg_id),
               "iat": datetime.now(timezone.utc),
               "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

def decode_jwt(token: str) -> int:
    try:
        return int(jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])["sub"])
    except Exception:
        raise AuthError("bad token")
