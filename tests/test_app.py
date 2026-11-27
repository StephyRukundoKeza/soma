import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: E402

client = TestClient(app.app)
LEARNER = {"id": "u1", "role": "learner", "name": "Aline"}
TEACHER = {"id": "t1", "role": "teacher", "name": "Mrs U"}
ADMIN = {"id": "a1", "role": "admin", "name": "Stephy"}
AUTH = {"Authorization": "Bearer token"}
ROOM = {"id": "c1", "teacher_id": "t1", "name": "S4 A", "code": "K7RW2Q", "session_minutes": 4}


SAMPLE_BOOKS = json.loads((Path(__file__).parent / "sample_chunks.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def sample_books(monkeypatch):
    """A tiny sample book, so these tests pass on any computer, with or without the real index."""
    monkeypatch.setattr(app.curriculum, "load_chunks", lambda: SAMPLE_BOOKS)
    for cached in (app.curriculum.units, app.curriculum.running_header):
        cached.cache_clear()
    yield
    for cached in (app.curriculum.units, app.curriculum.running_header):
        cached.cache_clear()


@pytest.fixture
def as_user(monkeypatch):
    def log_in(user):
        monkeypatch.setattr(app.accounts, "user_from_token", lambda token: user)
    return log_in


@pytest.fixture
def events(monkeypatch):
    logged = []
    monkeypatch.setattr(app.accounts, "log_event", lambda user_id, kind, language, **v: logged.append((kind, v)))
    return logged


def test_home_page_shows_the_login_screen():
    response = client.get("/")
    assert response.status_code == 200 and 'id="loginForm"' in response.text and 'id="joinForm"' in response.text


def test_pages_need_a_login():
    assert client.post("/api/ask", json={"question": "Hi"}).status_code == 401
    assert client.get("/api/units").status_code == 401


def test_wrong_password_is_refused(monkeypatch):
    def wrong(username, password):
        raise app.accounts.LoginError("x")
    monkeypatch.setattr(app.accounts, "login", wrong)
    response = client.post("/api/login", json={"username": "a", "password": "b"})
    assert response.status_code == 401 and response.json()["error"] == "wrong_login"


def test_a_learner_cannot_use_the_teacher_login_but_an_admin_can(monkeypatch):
    monkeypatch.setattr(app.accounts, "login", lambda u, p: {"token": "x", **(ADMIN if u == "admin" else LEARNER)})
    assert client.post("/api/login", json={"username": "aline", "password": "pw", "role": "teacher"}).status_code == 403
    assert client.post("/api/login", json={"username": "admin", "password": "pw", "role": "teacher"}).status_code == 200


def test_learners_join_with_a_class_code(monkeypatch):
    seen = {}

    def join(code, username, password, name):
        seen.update(code=code, username=username, name=name)
        return {"token": "x", **LEARNER}
    monkeypatch.setattr(app.accounts, "join_class", join)
    response = client.post("/api/join", json={"code": "K7RW2Q", "name": "Aline", "username": "aline", "password": "longpassword"})
    assert response.status_code == 200 and seen == {"code": "K7RW2Q", "username": "aline", "name": "Aline"}


def test_a_wrong_class_code_gives_a_code_the_page_can_translate(monkeypatch):
    def bad(code):
        raise app.accounts.AccountError("bad_code")
    monkeypatch.setattr(app.accounts, "class_by_code", bad)
    response = client.get("/api/join/AAAAAA")
    assert response.status_code == 400 and response.json()["error"] == "bad_code"


def test_the_table_of_contents_lists_the_units(as_user):
    as_user(LEARNER)
    data = client.get("/api/units?language=rw", headers=AUTH).json()
    assert data["grade"] == "S4" and [u["title"] for u in data["units"]] == ["Umuco nyarwanda", "Ikiganiro mpaka"]


def test_a_unit_can_be_read(as_user):
    as_user(LEARNER)
    data = client.get("/api/units/en-1?language=en", headers=AUTH).json()
    assert data["title"] == "Friendship" and len(data["pages"]) == 2
    assert all("hidden from learners" not in page["text"] for page in data["pages"])   # teacher's guide stays out


def test_placement_sets_the_starting_level(as_user, monkeypatch, events):
    saved = {}
    as_user(LEARNER)
    monkeypatch.setattr(app.accounts, "placement_passes", lambda user_id, language: 2)
    monkeypatch.setattr(app.accounts, "set_difficulty", lambda user_id, language, value: saved.update(lang=language, d=value))
    data = client.post("/api/placement/finish", json={"language": "rw"}, headers=AUTH).json()
    assert data == {"difficulty": 5, "level": 2} and saved == {"lang": "rw", "d": 5}


def test_a_second_green_in_a_row_makes_the_next_task_harder(as_user, monkeypatch, events):
    saved = {}
    as_user(LEARNER)
    monkeypatch.setattr(app.accounts, "level_state", lambda user_id, language: (3, 1))   # one green already
    monkeypatch.setattr(app.accounts, "set_difficulty", lambda user_id, language, value, streak=0: saved.update(d=value, s=streak))
    monkeypatch.setattr(app.practice, "assess", lambda *a, **k: {"reply": "Ni byiza!", "passed": True, "finished": True})
    spoken = {"seconds": 12, "wpm": 80, "pauses_per_min": 3.0, "fillers_per_100": 2.0, "phrases": ["ndumva"]}
    data = client.post("/api/task/answer", headers=AUTH, json={
        "language": "rw", "unit": "rw-1", "scenario": "debate", "task": "Vuga...", "answer": "Ndumva...",
        "tries": 1, "spoken": spoken}).json()
    assert data["change"] == "up" and data["level"] == 2 and data["colour"] == "green" and saved == {"d": 4, "s": 0}
    assert [kind for kind, _ in events] == ["task", "level"]
    task_event = events[0][1]
    assert task_event["scenario"] == "debate" and task_event["pauses_per_min"] == 3.0 and "phrases" not in task_event


def test_no_answer_text_is_saved_in_events(as_user, monkeypatch, events):
    as_user(LEARNER)
    monkeypatch.setattr(app.accounts, "level_state", lambda user_id, language: (3, 0))
    monkeypatch.setattr(app.practice, "assess", lambda *a, **k: {"reply": "ok", "passed": False, "finished": True})
    monkeypatch.setattr(app.accounts, "set_difficulty", lambda *a: None)
    client.post("/api/task/answer", headers=AUTH, json={
        "language": "rw", "unit": "rw-1", "task": "T", "answer": "my secret answer", "tries": 3})
    assert all("my secret answer" not in str(values) for _, values in events)


def test_sessions_use_the_class_length_and_send_results(as_user, monkeypatch, events):
    ran = []
    as_user(LEARNER)
    monkeypatch.setattr(app.accounts, "session_minutes_for", lambda user_id: 4)
    monkeypatch.setattr(app, "run_etl_quietly", lambda: ran.append(True))
    assert client.post("/api/session/start", json={"language": "rw"}, headers=AUTH).json() == {"minutes": 4}
    client.post("/api/session/end", json={"language": "rw", "seconds": 240}, headers=AUTH)
    assert [kind for kind, _ in events] == ["session_start", "session_end"] and events[1][1]["seconds"] == 240


def test_only_teachers_see_classes_and_add_learners(as_user, monkeypatch):
    created = {}
    monkeypatch.setattr(app.accounts, "classes_for", lambda user: [ROOM])
    monkeypatch.setattr(app.accounts, "class_learners", lambda ids: [{"user_id": "u1", "name": "Aline", "class_id": "c1"}])
    monkeypatch.setattr(app.etl, "learner_summaries", lambda learners: [{"name": l["name"]} for l in learners])
    monkeypatch.setattr(app.accounts, "own_class", lambda user, class_id: ROOM)
    monkeypatch.setattr(app.accounts, "create_user", lambda u, p, role, name, class_id=None: created.update(role=role, class_id=class_id) or LEARNER)
    as_user(LEARNER)
    assert client.get("/api/teacher/classes", headers=AUTH).status_code == 403
    as_user(TEACHER)
    data = client.get("/api/teacher/classes", headers=AUTH).json()
    assert data["classes"][0]["code"] == "K7RW2Q" and data["classes"][0]["learners"] == [{"name": "Aline"}]
    client.post("/api/teacher/classes/c1/students", headers=AUTH, json={"name": "Joshua", "username": "joshua", "password": "longpassword"})
    assert created == {"role": "learner", "class_id": "c1"}


def test_only_the_admin_adds_teachers(as_user, monkeypatch):
    monkeypatch.setattr(app.accounts, "create_user", lambda u, p, role, name, class_id=None: {"id": "t2", "role": role, "name": name})
    body = {"name": "Mr K", "username": "mrk", "password": "longpassword"}
    as_user(TEACHER)
    assert client.post("/api/admin/teachers", json=body, headers=AUTH).status_code == 403
    as_user(ADMIN)
    assert client.post("/api/admin/teachers", json=body, headers=AUTH).json()["role"] == "teacher"


def test_ask_returns_answer_and_sources_without_the_learners_name(as_user, monkeypatch):
    seen = {}

    def answer(question, language, names=()):
        seen["names"] = names
        return {"answer": "Noise (GSCS S4, p. 48)", "grounded": True, "sources": [{"citation": "GSCS S4, p. 48"}]}
    monkeypatch.setattr(app.rag, "answer", answer)
    as_user(LEARNER)
    data = client.post("/api/ask", json={"question": "What are barriers?"}, headers=AUTH).json()
    assert data["sources"] == ["GSCS S4, p. 48"] and seen["names"] == ["Aline"]


def test_busy_models_give_a_friendly_message_in_the_learners_language(as_user, monkeypatch):
    def busy(*args, **kwargs):
        raise app.rag.ModelsBusyError("503")
    monkeypatch.setattr(app.rag, "answer", busy)
    as_user(LEARNER)
    response = client.post("/api/ask", json={"question": "Ni iki?", "language": "rw"}, headers=AUTH)
    assert response.status_code == 503 and "Ongera ugerageze" in response.json()["error"]


def test_a_recording_becomes_text_in_the_learners_language(as_user, monkeypatch):
    seen = {}

    def transcribe(audio, language, context=""):
        seen.update(audio=audio, language=language, context=context)
        return " Ndumva ufite ukuri ", "digital-umuganda-whisper"
    monkeypatch.setattr(app.speech, "transcribe", transcribe)
    as_user(LEARNER)
    audio = base64.b64encode(b"RIFF....WAVEfmt ").decode()
    data = client.post("/api/transcribe", json={"audio": audio, "language": "rw", "context": "Vuga..."}, headers=AUTH).json()
    assert data["text"] == "Ndumva ufite ukuri" and seen["language"] == "rw" and seen["context"] == "Vuga..."
    assert data["fluency"]["phrases"] == ["ndumva"]


def test_recordings_need_a_login_and_must_be_readable(as_user):
    assert client.post("/api/transcribe", json={"audio": "AAAA"}).status_code == 401
    as_user(LEARNER)
    assert client.post("/api/transcribe", json={"audio": "not base64!"}, headers=AUTH).status_code == 400


def test_a_learner_without_a_class_joins_one_with_the_code(as_user, monkeypatch):
    joined = {}
    as_user(LEARNER)
    monkeypatch.setattr(app.accounts, "profile", lambda user_id: {"user_id": user_id, "class_id": None})
    monkeypatch.setattr(app.accounts, "assign_class", lambda user, code: joined.update(code=code) or ROOM)
    data = client.post("/api/me/class", json={"code": "K7RW2Q"}, headers=AUTH).json()
    assert data == {"class": "S4 A", "session_minutes": 4} and joined == {"code": "K7RW2Q"}


def test_a_learner_already_in_a_class_cannot_switch_alone(as_user, monkeypatch):
    as_user(LEARNER)
    monkeypatch.setattr(app.accounts, "profile", lambda user_id: {"user_id": user_id, "class_id": "c1"})
    response = client.post("/api/me/class", json={"code": "K7RW2Q"}, headers=AUTH)
    assert response.status_code == 400 and response.json()["error"] == "already_in_class"


def test_learners_see_their_own_progress(as_user, monkeypatch):
    as_user(LEARNER)
    monkeypatch.setattr(app.etl, "learner_progress", lambda user_id, language: {"user": user_id, "level": 2, "start_level": 1})
    monkeypatch.setattr(app.accounts, "steps_done", lambda user_id: [{"step": 0}, {"step": 1}])
    data = client.get("/api/progress/me?language=rw", headers=AUTH).json()
    assert data == {"user": "u1", "level": 2, "start_level": 1, "guided_done": 2}


def test_only_the_learners_own_teacher_sees_their_progress(as_user, monkeypatch):
    monkeypatch.setattr(app.accounts, "profile", lambda user_id: {"user_id": user_id, "role": "learner", "name": "Aline", "class_id": "c1"})
    monkeypatch.setattr(app.etl, "learner_progress", lambda user_id, language: {"level": 2})
    monkeypatch.setattr(app.accounts, "steps_done", lambda user_id: [])

    def own_class(user, class_id):
        if user["id"] != "t1":
            raise app.accounts.AccountError("not_allowed")
        return ROOM
    monkeypatch.setattr(app.accounts, "own_class", own_class)
    as_user(LEARNER)
    assert client.get("/api/teacher/learners/u1", headers=AUTH).status_code == 403
    as_user({"id": "t9", "role": "teacher", "name": "Other"})
    assert client.get("/api/teacher/learners/u1", headers=AUTH).status_code == 400
    as_user(TEACHER)
    assert client.get("/api/teacher/learners/u1?language=rw", headers=AUTH).json()["name"] == "Aline"
