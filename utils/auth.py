import re

from sqlalchemy import or_

from models import User

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")


def normalize_username(value: str) -> str:
    return value.strip().lower()


def normalize_mobile(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def is_valid_username(username: str) -> bool:
    return bool(USERNAME_RE.match(username))


def is_valid_mobile(mobile: str) -> bool:
    normalized = normalize_mobile(mobile)
    return len(normalized) == 10 and normalized[0] in "6789"


def find_user_by_login(login: str, role: str):
    login = (login or "").strip()
    if not login:
        return None

    email_try = login.lower()
    username_try = normalize_username(login)
    mobile_try = normalize_mobile(login)

    filters = [User.email == email_try, User.username == username_try]
    if mobile_try:
        filters.append(User.mobile == mobile_try)

    return User.query.filter(User.role == role, or_(*filters)).first()
