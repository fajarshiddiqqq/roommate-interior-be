from datetime import datetime
from flask import request, jsonify
from functools import wraps
from config import Config
import jwt


def require_token(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        if Config.SECRET_KEY is None:
            raise ValueError("JWT_SECRET is missing")

        token = request.headers.get("Authorization")
        if not token:
            return jsonify(meta="Token is missing", data=None, status=False), 401
        if not token.startswith("Bearer "):
            return jsonify(meta="Invalid token format", data=None, status=False), 403

        try:
            token = token.split("Bearer ")[1]
            auth = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify(meta="Token has expired", data=None, status=False), 401
        except jwt.InvalidTokenError:
            return jsonify(meta="Invalid token", data=None, status=False), 403

        return func(auth, *args, **kwargs)

    return decorated


def generate_token(expires_in, **kwargs):
    if Config.SECRET_KEY is None:
        raise ValueError("SECRET_KEY is missing")

    payload = {"exp": datetime.utcnow() + expires_in, **kwargs}
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")
