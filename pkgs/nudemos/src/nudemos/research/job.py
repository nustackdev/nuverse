"""The desk's two jobs: an eval run, and the probe. Each a headless plane, its one cell a Nu loop over Claude.

Nu owns the loop, Claude Code owns the answer. Both jobs run in their own
process (the ``mp`` backend), under the supervisor, and write straight into
the desk's state, so every page that reads the desk follows them.

- :data:`RUN`: one arm of the eval. Every question of the suite not yet
  answered, one at a time: asked, graded on its last number, written into
  the run with what it took and cost. Restarted, it carries on from the
  first question without an answer. Done, it ends.
- :data:`PROBE`: one question every :data:`INTERVAL` seconds, the suite in
  turn, clean and distracted by turns, to the model the desk leans on. At
  most :data:`CAP` a day. "Probe now" asks at once; pause holds it.

The pure parts, what a run or the probe looks like after an answer, are
here as plain functions, so they are tested on their own.
"""

from __future__ import annotations

import time
from typing import Any

from . import evals


__all__ = [
    "CAP",
    "INTERVAL",
    "PROBE",
    "PROBE_MODEL",
    "RUN",
    "answered",
    "due",
    "finished",
    "job_source",
    "probe_next",
    "probe_source",
    "probed",
    "started",
    "todo",
]


#: Seconds between the probe's questions, and the most it asks in a day.
INTERVAL, CAP = 240.0, 100

#: The model the probe asks.
PROBE_MODEL = "claude-sonnet-5"


# --- a run, as plain data ---------------------------------------------------------------------


def todo(run: dict) -> list[str]:
    """The questions a run has no answer to yet, in suite order."""
    done = (run or {}).get("answers") or {}
    return [q for q in evals.BY_ID if q not in done]


def started(run: dict) -> dict:
    """``run`` marked running, with when it first started."""
    return {**run, "status": "running", "started_at": run.get("started_at") or time.time()}


def answered(run: dict, qid: str, reply: object, seconds: float) -> dict:
    """``run`` with ``qid`` answered: the reply graded, its time and cost kept."""
    reply = reply if isinstance(reply, dict) else {"text": str(reply)}
    text = str(reply.get("text") or reply.get("result") or "")
    graded = evals.grade(qid, text)
    answer = {
        "got": graded["got"],
        "correct": graded["correct"],
        "seconds": round(float(seconds), 2),
        "cost": float(reply.get("total_cost_usd") or 0.0),
        "text": text[:1200],
    }
    return {**run, "answers": {**(run.get("answers") or {}), qid: answer}, "status": "running"}


def failed(run: dict, qid: str, error: str) -> dict:
    """``run`` with ``qid`` marked as not answered: an error counts as wrong."""
    answer = {
        "got": None,
        "correct": False,
        "seconds": 0.0,
        "cost": 0.0,
        "text": f"Error: {error}"[:400],
    }
    return {**run, "answers": {**(run.get("answers") or {}), qid: answer}}


def finished(run: dict) -> dict:
    """``run`` marked done, now."""
    return {**run, "status": "done", "done_at": time.time()}


# --- the probe, as plain data -------------------------------------------------------------------


def _day(t: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t))


def due(probe: dict | None, asked: int | None, paused: bool | None, now: float) -> bool:
    """Whether the probe asks now: asked to, or its time came, not paused, under the day's cap."""
    p = probe or {}
    if (asked or 0) > p.get("asked", 0):
        return True
    if paused:
        return False
    today = p.get("today", 0) if p.get("day") == _day(now) else 0
    return today < CAP and now >= p.get("next_at", 0.0)


def probe_next(probe: dict | None) -> dict[str, str]:
    """The next question: the suite in turn, clean and distracted by turns."""
    n = (probe or {}).get("n", 0)
    ids = list(evals.BY_ID)
    return {"q": ids[(n // 2) % len(ids)], "context": "noisy" if n % 2 else "clean"}


def probed(
    probe: dict | None,
    probes: list | None,
    asked: int | None,
    ask: dict,
    reply: object,
    seconds: float,
    now: float,
) -> dict[str, Any]:
    """The probe and its list after one answer: ``{probe, probes}``. The list keeps the last 400."""
    p = probe or {}
    reply = reply if isinstance(reply, dict) else {"text": str(reply)}
    text = str(reply.get("text") or "")
    graded = (
        evals.grade(ask["q"], text)
        if not text.startswith("Error:")
        else {"got": None, "correct": False}
    )
    item = {
        "at": now,
        "q": ask["q"],
        "context": ask["context"],
        "got": graded["got"],
        "correct": graded["correct"],
        "seconds": round(float(seconds), 2),
        "cost": float(reply.get("total_cost_usd") or 0.0),
        "text": text[:300],
    }
    today = (p.get("today", 0) if p.get("day") == _day(now) else 0) + 1
    nxt = {
        **p,
        "n": p.get("n", 0) + 1,
        "asked": max(asked or 0, p.get("asked", 0)),
        "next_at": now + INTERVAL,
        "day": _day(now),
        "today": today,
        "status": "waiting",
    }
    return {"probe": nxt, "probes": [*(probes or []), item][-400:]}


def asking(probe: dict | None, ask: dict) -> dict:
    """The probe while it waits on ``ask``'s answer."""
    return {**(probe or {}), "status": "asking", "asking": ask}


# --- the cells ------------------------------------------------------------------------------------


RUN = """\
import nu
import nuspace
import nustd.cc
import nustd.time
from nudemos.research import evals, job
from nudemos.research.claude import Claude, options
from nudemos.research.kit import DESK

#: The run, baked in at launch. The desk is found by its key, the run's page in it.
RUN = {}

ME = DESK.runs[RUN["key"]]
todo, started, answered, failed, finished = (
    nu.host(job.todo), nu.host(job.started), nu.host(job.answered), nu.host(job.failed), nu.host(job.finished),
)
prompt = nu.host(evals.prompt)


def kept(update):
    # Read, changed, written back, in one commit: pages see each answer land.
    return nuspace.atomic(ME.set(update(ME)))


def one(qid):
    q = nu.Str(qid)

    def asked(t0):
        took = lambda r: kept(lambda run: answered(run, q, r, nustd.time.time() - nu.Float(t0)))
        return nu.TryCatch(nu.let(Claude.ask(prompt(q, RUN["context"])), took), catch=lambda e: kept(lambda run: failed(run, q, nu.Str(e))))

    return nu.let(nustd.time.time(), asked)


def icon(name):
    # The run's page wears a timer while it runs.
    return nuspace.atomic(nuspace.plane.set_icon(DESK.planes.runs[RUN["key"]], name))


def out(cell):
    done = nuspace.atomic(ME.fallback({})["status"] == "done")
    work = (
        kept(started) >> icon("lucide:timer") >> nu.ForEachDo(nuspace.atomic(todo(ME.fallback({}))), one)
        >> kept(finished) >> icon("lucide:chart-column")
    )
    asking = nu.With(nustd.cc.bind(Claude, **options(RUN["model"], evals.SYSTEM[RUN["style"]])), body=work)
    return nu.IfDo(done, nu.Noop(), asking)
"""


PROBE = """\
import nu
import nuspace
import nustd.cc
import nustd.time
from nudemos.research import evals, job
from nudemos.research.claude import Claude, options
from nudemos.research.kit import DESK

due, probe_next, probed, asking = nu.host(job.due), nu.host(job.probe_next), nu.host(job.probed), nu.host(job.asking)
prompt = nu.host(evals.prompt)


def wait():
    # Level wait: woken by Probe now, re-checked every few seconds for the clock and the pause.
    now = due(DESK.probe.fallback({}), DESK.asked.fallback(0), DESK.paused.fallback(False), nustd.time.time())
    return nu.WaitUntil(nuspace.atomic(DESK.asked.on_change()), nuspace.atomic(now), every=3.0)


def ask():
    def go(a, t0):
        ask = nu.Dict(a)
        mark = nuspace.atomic(DESK.probe.set(asking(DESK.probe.fallback({}), ask)))

        def landed(r):
            after = probed(
                DESK.probe.fallback({}), DESK.probes.extract(), DESK.asked.fallback(0), ask, r,
                nustd.time.time() - nu.Float(t0), nustd.time.time(),
            )
            write = lambda v: DESK.probe.set(nu.Dict(v)["probe"]) >> DESK.probes.set(nu.Dict(v)["probes"])
            return nuspace.atomic(nu.let(after, write))

        reply = nu.TryCatch(Claude.ask(prompt(ask["q"], ask["context"])), catch=lambda e: nu.Dict.of(text=nu.Str("Error: ") + nu.Str(e)))
        return mark >> nu.let(reply, landed)

    nxt = nuspace.atomic(probe_next(DESK.probe.fallback({})))
    return nu.let(nxt, lambda a: nu.let(nustd.time.time(), lambda t0: go(a, t0)))


def out(cell):
    bound = nustd.cc.bind(Claude, **options(job.PROBE_MODEL, evals.SYSTEM["direct"]))
    return nu.With(bound, body=nu.ForeverDo(wait() >> ask()))
"""


def job_source(run: dict[str, Any]) -> str:
    """:data:`RUN` with the run's arm baked in."""
    arm = {k: run[k] for k in ("key", "model", "style", "context")}
    return RUN.replace("RUN = {}", f"RUN = {arm!r}")


def probe_source() -> str:
    """:data:`PROBE`: it finds the desk by its key, so nothing is baked in."""
    return PROBE
