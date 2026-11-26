"""Logins, classes and practice records, stored in Supabase (free tier).

No username or password is written in the code: the admin creates the first accounts with
scripts/add_user.py, teachers add learners from the app or share a class code. Each account's
role is kept in its app_metadata, which only the server (secret key) can change.
"""

import os
import secrets
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

USERNAME_DOMAIN = "soma.local"   # learners log in with a username; Supabase needs an email form
TOKEN_CACHE_SECONDS = 300
CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O or 1/I, easy to read from a board
ROLES = ("learner", "teacher", "admin")
DEFAULT_SESSION_MINUTES = int(os.environ.get("SOMA_SESSION_MINUTES", "40"))
_token_cache = {}


class NotConfiguredError(RuntimeError):
    """Raised when the Supabase settings are missing from .env."""


class LoginError(RuntimeError):
    """Raised when a username or password is wrong, or a session has expired."""


class AccountError(RuntimeError):
    """Raised when an account or class cannot be created. The message is a short code
    (e.g. "username_taken", "bad_code") that the web page shows in the learner's language."""


def settings():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    public_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not (url and public_key and secret_key):
        raise NotConfiguredError("Login is not set up yet: add SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY "
                                 "and SUPABASE_SECRET_KEY to .env")
    return url, public_key, secret_key


def key_headers(key):
    # New sb_ keys go only in the apikey header; old JWT keys also go in Authorization
    headers = {"apikey": key}
    if not key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


# --- Database (server only, secret key) ---

def db(method, table, params=None, body=None, prefer=None):
    url, _, secret_key = settings()
    headers = key_headers(secret_key)
    if prefer:
        headers["Prefer"] = prefer
    response = httpx.request(method, f"{url}/rest/v1/{table}", headers=headers, params=params, json=body, timeout=20)
    response.raise_for_status()
    return response.json() if response.content else None


def select(table, **filters):
    """select("profiles", user_id="eq.123", select="name") -> list of rows."""
    return db("GET", table, params={"select": "*", **filters})


def insert(table, rows, upsert_on=None):
    params = {"on_conflict": upsert_on} if upsert_on else None
    prefer = "return=representation" + (",resolution=merge-duplicates" if upsert_on else "")
    return db("POST", table, params=params, body=rows, prefer=prefer)


def update(table, values, **filters):
    return db("PATCH", table, params=filters, body=values, prefer="return=representation")


# --- Logins ---

def as_email(username):
    username = username.strip().lower()
    return username if "@" in username else f"{username}@{USERNAME_DOMAIN}"


def describe(user):
    return {"id": user["id"],
            "role": (user.get("app_metadata") or {}).get("role", "learner"),
            "name": (user.get("user_metadata") or {}).get("name") or user.get("email", "").split("@")[0]}


def login(username, password):
    """Check a username and password; returns {"token", "id", "role", "name"}."""
    url, public_key, _ = settings()
    response = httpx.post(f"{url}/auth/v1/token?grant_type=password", headers={"apikey": public_key},
                          json={"email": as_email(username), "password": password}, timeout=15)
    if response.status_code != 200:
        raise LoginError("Wrong username or password.")
    data = response.json()
    user = describe(data["user"])
    _token_cache[data["access_token"]] = (time.time(), user)
    return {"token": data["access_token"], **user}


def user_from_token(token):
    """Who is calling? Checked with Supabase, then remembered for a few minutes."""
    cached = _token_cache.get(token)
    if cached and time.time() - cached[0] < TOKEN_CACHE_SECONDS:
        return cached[1]
    url, public_key, _ = settings()
    response = httpx.get(f"{url}/auth/v1/user",
                         headers={"apikey": public_key, "Authorization": f"Bearer {token}"}, timeout=15)
    if response.status_code != 200:
        _token_cache.pop(token, None)
        raise LoginError("Session expired. Please log in again.")
    user = describe(response.json())
    _token_cache[token] = (time.time(), user)
    return user


def create_user(username, password, role, name, class_id=None):
    """Create an account and its profile. Only the server can do this (secret key)."""
    if role not in ROLES:
        raise AccountError("unknown_role")
    if len(password) < 8:
        raise AccountError("short_password")
    url, _, secret_key = settings()
    response = httpx.post(f"{url}/auth/v1/admin/users", headers=key_headers(secret_key), timeout=15, json={
        "email": as_email(username), "password": password, "email_confirm": True,
        "app_metadata": {"role": role}, "user_metadata": {"name": name}})
    if response.status_code not in (200, 201):
        try:
            detail = response.json()
        except ValueError:
            detail = {}
        reason = str(detail.get("error_code") or detail.get("code") or "")
        if reason in ("email_exists", "user_already_exists") or "already been registered" in response.text:
            raise AccountError("username_taken")
        message = detail.get("msg") or detail.get("message") or response.text[:200]
        raise AccountError(f"create_failed: {response.status_code} {reason} {message}".strip())
    user = describe(response.json())
    insert("profiles", [{"user_id": user["id"], "role": role, "name": name, "class_id": class_id}],
           upsert_on="user_id")
    return user


# --- Profiles and classes ---

def profile(user_id):
    rows = select("profiles", user_id=f"eq.{user_id}")
    return rows[0] if rows else None


def level_state(user_id, language):
    """(difficulty, streak) in this language; difficulty is None before the placement check.
    streak > 0 counts greens in a row, streak < 0 counts yellows in a row."""
    rows = select("levels", user_id=f"eq.{user_id}", language=f"eq.{language}")
    return (rows[0]["difficulty"], rows[0].get("streak") or 0) if rows else (None, 0)


def difficulty(user_id, language):
    return level_state(user_id, language)[0]


def set_difficulty(user_id, language, value, streak=0):
    insert("levels", [{"user_id": user_id, "language": language, "difficulty": value, "streak": streak,
                       "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}],
           upsert_on="user_id,language")


def new_code():
    return "".join(secrets.choice(CODE_LETTERS) for _ in range(6))


def create_class(teacher_id, name, session_minutes=DEFAULT_SESSION_MINUTES):
    for _ in range(5):                       # a clash between random codes is very unlikely; retry if so
        try:
            return insert("classes", [{"teacher_id": teacher_id, "name": name, "code": new_code(),
                                       "session_minutes": session_minutes}])[0]
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 409:
                raise
    raise AccountError("code_failed")


def class_by_code(code):
    rows = select("classes", code=f"eq.{code.strip().upper()}")
    if not rows:
        raise AccountError("bad_code")
    return rows[0]


def classes_for(user):
    if user["role"] == "admin":
        return select("classes", order="created_at")
    return select("classes", teacher_id=f"eq.{user['id']}", order="created_at")


def own_class(user, class_id):
    """The class, if this teacher (or the admin) may manage it."""
    rows = select("classes", id=f"eq.{class_id}")
    if not rows or (user["role"] != "admin" and rows[0]["teacher_id"] != user["id"]):
        raise AccountError("not_allowed")
    return rows[0]


def set_session_minutes(class_id, minutes):
    return update("classes", {"session_minutes": minutes}, id=f"eq.{class_id}")[0]


def session_minutes_for(user_id):
    me = profile(user_id)
    if me and me.get("class_id"):
        rows = select("classes", id=f"eq.{me['class_id']}", select="session_minutes")
        if rows:
            return rows[0]["session_minutes"]
    return DEFAULT_SESSION_MINUTES


def join_class(code, username, password, name):
    """A learner joins with the class code: a new learner account in that class, then logged in."""
    room = class_by_code(code)
    create_user(username, password, "learner", name, class_id=room["id"])
    return login(username, password)


def assign_class(user, code):
    """A learner who has an account but no class joins one with the class code."""
    room = class_by_code(code)
    insert("profiles", [{"user_id": user["id"], "role": user["role"], "name": user["name"], "class_id": room["id"]}],
           upsert_on="user_id")
    return room


def class_learners(class_ids):
    if not class_ids:
        return []
    return select("profiles", role="eq.learner", class_id=f"in.({','.join(class_ids)})", order="name")


# --- Practice records (no answers or recordings, only numbers) ---

def log_event(user_id, kind, language, **values):
    me = profile(user_id) or {}
    insert("events", [{"user_id": user_id, "class_id": me.get("class_id"), "kind": kind,
                       "language": language, **values}])


def save_step(user_id, step):
    insert("progress", [{"user_id": user_id, "step": step}], upsert_on="user_id,step")


def steps_done(user_id):
    return select("progress", user_id=f"eq.{user_id}", select="step,passed_at")


def placement_passes(user_id, language):
    rows = select("events", user_id=f"eq.{user_id}", kind="eq.placement", language=f"eq.{language}",
                  order="created_at.desc", limit="3")
    return sum(1 for r in rows if r["passed"])
