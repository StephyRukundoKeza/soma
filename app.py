"""SOMA website: run `python app.py`, then open http://127.0.0.1:8000"""

import base64
import binascii
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src" / "soma"))
os.chdir(ROOT)  # the index files are found relative to the project folder

from contextlib import asynccontextmanager  # noqa: E402

from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import accounts  # noqa: E402
import curriculum  # noqa: E402
import etl  # noqa: E402
import fluency  # noqa: E402
import practice  # noqa: E402
import rag  # noqa: E402
import speech  # noqa: E402
import tutor  # noqa: E402

LANGUAGES = {"en", "rw", "sw", "fr"}
MAX_AUDIO_BYTES = 3_000_000   # about 90 seconds of 16 kHz speech
ETL_EVERY_SECONDS = int(os.environ.get("SOMA_ETL_EVERY_SECONDS", "600"))
BUSY = {
    "en": "SOMA is very busy right now. Please try again in a minute.",
    "rw": "SOMA ifite akazi kenshi ubu. Ongera ugerageze mu munota umwe.",
    "sw": "SOMA ina kazi nyingi sasa hivi. Tafadhali jaribu tena baada ya dakika moja.",
    "fr": "SOMA est très occupé en ce moment. Réessaie dans une minute.",
}

def warm_up_search():
    """Load the search model and index in the background, so the first learner does not wait."""
    try:
        import index

        index.load_index(index.DEFAULT_MODEL)
        index.get_model(index.DEFAULT_MODEL)
        print("[search] index and model ready")
    except Exception as error:
        print(f"[search] not loaded yet: {str(error)[:120]}")


@asynccontextmanager
async def lifespan(app):
    # The dashboard ETL also runs on a schedule while the server is up
    if ETL_EVERY_SECONDS > 0 and os.environ.get("SUPABASE_URL"):
        threading.Thread(target=etl_loop, daemon=True).start()
    threading.Thread(target=speech.warm_up, daemon=True).start()
    threading.Thread(target=warm_up_search, daemon=True).start()
    yield


app = FastAPI(title="SOMA", lifespan=lifespan)


# --- Request bodies ---

class Login(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)
    role: str = "learner"


class Join(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    name: str = Field(min_length=1, max_length=40)
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=200)


class ClassCode(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class NewAccount(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=200)


class NewClass(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    minutes: int = Field(default=40, ge=1, le=120)


class Minutes(BaseModel):
    minutes: int = Field(ge=1, le=120)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    language: str = "en"


class Turn(BaseModel):
    role: str
    text: str = Field(max_length=1500)


class Spoken(BaseModel):
    """Fluency measures from /api/transcribe, sent back with the spoken answer."""
    seconds: float = Field(gt=0, le=120)
    wpm: int = Field(ge=0, le=400)
    target_wpm: list[int] = [100, 160]
    speaking_ratio: float = Field(default=1.0, ge=0, le=1)
    pauses: int = Field(default=0, ge=0, le=200)
    long_pauses: int = Field(default=0, ge=0, le=200)
    pauses_per_min: float = Field(default=0, ge=0, le=200)
    fillers: int = Field(default=0, ge=0, le=500)
    fillers_per_100: float = Field(default=0, ge=0, le=100)
    repeats: int = Field(default=0, ge=0, le=500)
    phrases: list[str] = Field(default=[], max_length=20)


class Practice(BaseModel):
    step: int = Field(ge=0, lt=len(tutor.LEARNING_SEQUENCE))
    message: str = Field(default="", max_length=1000)
    history: list[Turn] = []
    language: str = "en"
    spoken: Spoken | None = None


class TaskRequest(BaseModel):
    language: str = "en"
    unit: str = Field(max_length=20)
    recent: list[str] = Field(default=[], max_length=10)


class TaskAnswer(BaseModel):
    language: str = "en"
    unit: str = Field(max_length=20)
    scenario: str = Field(default="", max_length=20)
    task: str = Field(max_length=1500)
    answer: str = Field(min_length=1, max_length=1500)
    tries: int = Field(ge=1, le=practice.MAX_TRIES)
    history: list[Turn] = []
    spoken: Spoken | None = None


class PlacementTask(BaseModel):
    language: str = "en"
    n: int = Field(ge=0, lt=len(practice.PLACEMENT_DIFFICULTIES))


class PlacementAnswer(PlacementTask):
    task: str = Field(max_length=1500)
    answer: str = Field(min_length=1, max_length=1500)
    spoken: Spoken | None = None


class LanguageOnly(BaseModel):
    language: str = "en"


class SessionEnd(BaseModel):
    language: str = "en"
    seconds: float = Field(ge=0, le=3 * 60 * 60)


class Recording(BaseModel):
    audio: str = Field(max_length=MAX_AUDIO_BYTES * 4 // 3 + 8)   # base64 WAV
    language: str = "en"
    context: str = Field(default="", max_length=1500)              # the task being answered


# --- Helpers ---

def language_of(code):
    return code if code in LANGUAGES else "en"


def current_user(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "login")
    try:
        return accounts.user_from_token(token)
    except accounts.LoginError:
        raise HTTPException(401, "expired")
    except accounts.NotConfiguredError as error:
        raise HTTPException(503, str(error))


def staff_only(user=Depends(current_user)):
    if user["role"] not in ("teacher", "admin"):
        raise HTTPException(403, "not_allowed")
    return user


def admin_only(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "not_allowed")
    return user


def model_call(language, function, *args, **kwargs):
    start = time.time()
    try:
        return function(*args, **kwargs)
    except rag.ModelsBusyError:
        raise HTTPException(503, BUSY[language])
    finally:
        print(f"[time] {function.__module__}.{function.__name__}: {time.time() - start:.1f} s "
              f"(model: {rag.last_model_used})")


def speech_numbers(spoken):
    """The few fluency numbers kept for the dashboard; never the words themselves."""
    if not spoken:
        return {}
    return {"wpm": spoken["wpm"], "seconds": spoken["seconds"], "pauses_per_min": spoken["pauses_per_min"],
            "fillers_per_100": spoken["fillers_per_100"]}


def run_etl_quietly():
    try:
        etl.run()
    except Exception as error:   # the dashboard refreshes again on the next run
        print(f"ETL run failed: {error}")


@app.exception_handler(HTTPException)
def error_as_json(request, error):
    return JSONResponse({"error": error.detail}, status_code=error.status_code)


@app.exception_handler(accounts.AccountError)
def account_error(request, error):
    return JSONResponse({"error": str(error)}, status_code=400)


@app.exception_handler(accounts.NotConfiguredError)
def not_configured(request, error):
    return JSONResponse({"error": str(error)}, status_code=503)


# --- Pages ---

@app.get("/")
def home():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/logo-mark.png")
def logo():
    return FileResponse(ROOT / "web" / "logo-mark.png")


# --- Accounts ---

@app.post("/api/login")
def login(body: Login):
    try:
        user = accounts.login(body.username, body.password)
    except accounts.LoginError:
        raise HTTPException(401, "wrong_login")
    allowed = ("teacher", "admin") if body.role == "teacher" else ("learner",)
    if user["role"] not in allowed:
        raise HTTPException(403, "wrong_role")
    return user


@app.get("/api/join/{code}")
def join_info(code: str):
    room = accounts.class_by_code(code)
    return {"class": room["name"]}


@app.post("/api/join")
def join(body: Join):
    return accounts.join_class(body.code, body.username, body.password, body.name)


@app.get("/api/me")
def me(user=Depends(current_user)):
    profile = accounts.profile(user["id"]) or {}
    room = None
    if profile.get("class_id"):
        rows = accounts.select("classes", id=f"eq.{profile['class_id']}", select="name,session_minutes")
        room = rows[0] if rows else None
    return {**user, "class": room["name"] if room else None,
            "session_minutes": room["session_minutes"] if room else accounts.DEFAULT_SESSION_MINUTES}


@app.post("/api/me/class")
def join_with_code(body: ClassCode, user=Depends(current_user)):
    if user["role"] != "learner":
        raise HTTPException(403, "not_allowed")
    profile = accounts.profile(user["id"]) or {}
    if profile.get("class_id"):
        raise HTTPException(400, "already_in_class")
    room = accounts.assign_class(user, body.code)
    return {"class": room["name"], "session_minutes": room["session_minutes"]}


# --- Ask SOMA and the guided sequence ---

@app.post("/api/ask")
def ask(body: Question, user=Depends(current_user)):
    language = language_of(body.language)
    result = model_call(language, rag.answer, body.question, language, names=[user["name"]])
    return {"answer": result["answer"], "grounded": result["grounded"],
            "sources": [s["citation"] for s in result["sources"]]}


@app.get("/api/sequence")
def sequence(user=Depends(current_user)):
    return {"skill": tutor.SKILL, "steps": len(tutor.LEARNING_SEQUENCE)}


@app.get("/api/progress")
def my_progress(user=Depends(current_user)):
    return {"done": sorted({row["step"] for row in accounts.steps_done(user["id"])})}


@app.post("/api/practice")
def guided_practice(body: Practice, user=Depends(current_user)):
    language = language_of(body.language)
    result = model_call(language, tutor.coach, body.step, body.message, [t.model_dump() for t in body.history],
                        language, names=[user["name"]], spoken=body.spoken.model_dump() if body.spoken else None)
    if result["passed"] and user["role"] == "learner":
        accounts.save_step(user["id"], body.step)
    return result


# --- Table of contents and reading ---

@app.get("/api/units")
def unit_list(language: str = "en", user=Depends(current_user)):
    language = language_of(language)
    return {"grade": curriculum.GRADE,
            "units": [{"id": u["id"], "number": u["number"], "title": u["title"]} for u in curriculum.units(language)]}


@app.get("/api/units/{unit_id}")
def unit_reading(unit_id: str, language: str = "en", user=Depends(current_user)):
    language = language_of(language)
    try:
        unit = curriculum.find_unit(language, unit_id)
    except KeyError:
        raise HTTPException(404, "not_found")
    return {"id": unit["id"], "title": unit["title"], "pages": curriculum.unit_pages(language, unit_id)}


# --- Placement check ---

@app.get("/api/placement")
def placement_status(language: str = "en", user=Depends(current_user)):
    difficulty = accounts.difficulty(user["id"], language_of(language))
    return {"needed": difficulty is None, "difficulty": difficulty,
            "level": practice.level_of(difficulty) if difficulty else None}


@app.post("/api/placement/task")
def placement_task(body: PlacementTask, user=Depends(current_user)):
    language = language_of(body.language)
    unit = practice.placement_unit(language, body.n)
    difficulty = practice.PLACEMENT_DIFFICULTIES[body.n]
    scenario = practice.SCENARIOS[body.n % len(practice.SCENARIOS)]
    task, scenario = model_call(language, practice.new_task, language, unit, difficulty, names=[user["name"]],
                                scenario=scenario)
    return {"task": task, "unit": unit, "scenario": scenario, "n": body.n, "total": len(practice.PLACEMENT_DIFFICULTIES)}


@app.post("/api/placement/answer")
def placement_answer(body: PlacementAnswer, user=Depends(current_user)):
    language = language_of(body.language)
    difficulty = practice.PLACEMENT_DIFFICULTIES[body.n]
    spoken = body.spoken.model_dump() if body.spoken else None
    result = model_call(language, practice.assess, language, difficulty, body.task, body.answer,
                        practice.MAX_TRIES, spoken=spoken, names=[user["name"]])
    accounts.log_event(user["id"], "placement", language, difficulty=difficulty, passed=result["passed"],
                       **speech_numbers(spoken))
    return {"reply": result["reply"], "passed": result["passed"]}


@app.post("/api/placement/finish")
def placement_finish(body: LanguageOnly, user=Depends(current_user)):
    language = language_of(body.language)
    difficulty = practice.start_difficulty(accounts.placement_passes(user["id"], language))
    accounts.set_difficulty(user["id"], language, difficulty)
    accounts.log_event(user["id"], "level", language, difficulty=difficulty)
    return {"difficulty": difficulty, "level": practice.level_of(difficulty)}


# --- Adaptive practice ---

@app.post("/api/task/new")
def task_new(body: TaskRequest, user=Depends(current_user)):
    language = language_of(body.language)
    try:
        curriculum.find_unit(language, body.unit)
    except KeyError:
        raise HTTPException(404, "not_found")
    difficulty = accounts.difficulty(user["id"], language) or 1
    task, scenario = model_call(language, practice.new_task, language, body.unit, difficulty, body.recent,
                                names=[user["name"]])
    return {"task": task, "scenario": scenario, "difficulty": difficulty, "level": practice.level_of(difficulty)}


@app.post("/api/task/answer")
def task_answer(body: TaskAnswer, user=Depends(current_user)):
    language = language_of(body.language)
    difficulty, streak = accounts.level_state(user["id"], language)
    difficulty = difficulty or 1
    spoken = body.spoken.model_dump() if body.spoken else None
    result = model_call(language, practice.assess, language, difficulty, body.task, body.answer, body.tries,
                        [t.model_dump() for t in body.history], spoken, names=[user["name"]])
    new, colour = difficulty, None
    if result["finished"]:
        colour = "green" if practice.is_green(result["passed"], body.tries) else "yellow"
        new, streak = practice.next_step(difficulty, streak, result["passed"], body.tries)
        accounts.log_event(user["id"], "task", language, unit=body.unit, difficulty=difficulty,
                           passed=result["passed"], scenario=body.scenario or None, **speech_numbers(spoken))
        accounts.set_difficulty(user["id"], language, new, streak)
        if new != difficulty:
            accounts.log_event(user["id"], "level", language, difficulty=new)
    change = "up" if new > difficulty else "down" if new < difficulty else "same"
    return {**result, "colour": colour, "streak": streak, "difficulty": new, "level": practice.level_of(new),
            "change": change}


# --- Timed sessions ---

@app.post("/api/session/start")
def session_start(body: LanguageOnly, user=Depends(current_user)):
    accounts.log_event(user["id"], "session_start", language_of(body.language))
    return {"minutes": accounts.session_minutes_for(user["id"])}


@app.post("/api/session/end")
def session_end(body: SessionEnd, user=Depends(current_user)):
    accounts.log_event(user["id"], "session_end", language_of(body.language), seconds=round(body.seconds, 1))
    threading.Thread(target=run_etl_quietly, daemon=True).start()   # results reach the teacher right away
    return {"saved": True}


# --- Progress dashboards ---

@app.get("/api/progress/me")
def progress_me(language: str = "en", user=Depends(current_user)):
    data = etl.learner_progress(user["id"], language_of(language))
    data["guided_done"] = len({row["step"] for row in accounts.steps_done(user["id"])})
    return data


@app.get("/api/teacher/learners/{learner_id}")
def progress_of_learner(learner_id: str, language: str = "en", user=Depends(staff_only)):
    learner = accounts.profile(learner_id)
    if not learner or learner["role"] != "learner" or not learner.get("class_id"):
        raise HTTPException(404, "not_found")
    accounts.own_class(user, learner["class_id"])          # only this learner's teacher (or the admin)
    data = etl.learner_progress(learner_id, language_of(language))
    data["name"] = learner["name"]
    data["guided_done"] = len({row["step"] for row in accounts.steps_done(learner_id)})
    return data


# --- Teacher and admin ---

@app.get("/api/teacher/classes")
def teacher_classes(user=Depends(staff_only)):
    rooms = accounts.classes_for(user)
    learners = accounts.class_learners([r["id"] for r in rooms])
    return {"classes": [{**room, "learners": etl.learner_summaries([l for l in learners if l["class_id"] == room["id"]])}
                        for room in rooms]}


@app.post("/api/teacher/classes")
def teacher_new_class(body: NewClass, user=Depends(staff_only)):
    return accounts.create_class(user["id"], body.name, body.minutes)


@app.post("/api/teacher/classes/{class_id}/minutes")
def teacher_minutes(class_id: str, body: Minutes, user=Depends(staff_only)):
    accounts.own_class(user, class_id)
    return accounts.set_session_minutes(class_id, body.minutes)


@app.post("/api/teacher/classes/{class_id}/students")
def teacher_add_student(class_id: str, body: NewAccount, user=Depends(staff_only)):
    accounts.own_class(user, class_id)
    return accounts.create_user(body.username, body.password, "learner", body.name, class_id=class_id)


@app.post("/api/teacher/refresh")
def teacher_refresh(user=Depends(staff_only)):
    return {"loaded": etl.run()}


@app.post("/api/admin/teachers")
def admin_add_teacher(body: NewAccount, user=Depends(admin_only)):
    return accounts.create_user(body.username, body.password, "teacher", body.name)


# --- Voice ---

@app.post("/api/transcribe")
def transcribe(body: Recording, user=Depends(current_user)):
    """Turn a learner's recording into text; the audio is not kept."""
    language = language_of(body.language)
    try:
        audio = base64.b64decode(body.audio, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "bad_audio")
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "too_long")
    text, engine = model_call(language, speech.transcribe, audio, language, body.context)
    text = (text or "").strip()
    samples, rate = speech.wav_samples(audio)
    return {"text": text, "engine": engine, "fluency": fluency.measure(samples, rate, text, language) if text else None}


# --- Scheduled ETL while the server runs ---

def etl_loop():
    while True:
        time.sleep(ETL_EVERY_SECONDS)
        run_etl_quietly()


if __name__ == "__main__":
    import uvicorn

    # 0.0.0.0 lets a phone on the same Wi-Fi open the site with the laptop's address
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
