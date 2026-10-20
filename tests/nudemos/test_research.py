"""research, the desk: grading, scores, the runs' own evidence, the jobs' pure steps, the opening desk."""

from __future__ import annotations

import time

import pytest

from nudemos.research import PLANE, baked, cells, data, evals, job, views


def desk() -> dict:
    """The opening desk, keyed as the store keeps it."""
    return views.opening(time.time())


def run(model: str, style: str, context: str, right: int, key: str = "", at: float = 1.0) -> dict:
    """A finished run with ``right`` of the suite answered correctly."""
    answers = {
        q: {"correct": i < right, "got": 0, "seconds": 1.0, "cost": 0.0}
        for i, q in enumerate(evals.BY_ID)
    }
    return {
        "key": key or f"{model}{style}{context}{at}",
        "model": model,
        "style": style,
        "context": context,
        "status": "done",
        "at": at,
        "done_at": at,
        "answers": answers,
    }


# --- the suite and its grading ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("16", 16.0),
        ("Answer: 1,471", 1471.0),
        ("first 3 then 97.2", 97.2),
        ("none", None),
        ("-7.5", -7.5),
    ],
)
def test_last_number(text: str, want: float | None) -> None:
    assert evals.last_number(text) == want


def test_grade_reads_the_last_number_only() -> None:
    assert evals.grade("q01", "1248 + 612 = 1860, minus 389.\nAnswer: 1471")["correct"]
    assert not evals.grade("q01", "Answer: 1470")["correct"]


def test_noise_goes_before_the_question() -> None:
    q = evals.BY_ID["q01"]
    asked = evals.prompt("q01", "noisy")
    assert q["noise"] in asked
    assert asked.endswith("How many books does the library have now?")
    assert evals.prompt("q01", "clean") == q["text"]


def test_suite_has_two_tiers() -> None:
    tiers = [evals.tier(q) for q in evals.BY_ID]
    assert tiers.count("word") == 12
    assert tiers.count("hard") == 8


# --- scores ------------------------------------------------------------------------------------


def test_opening_desk_scores_every_claim() -> None:
    d = desk()
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"])
    assert set(sc) == {c["key"] for c in data.CLAIMS}
    for s in sc.values():
        assert -1 < s["score"] < 1
        assert s["status"] in {label for _, label, _ in views.STATUSES}


def test_evidence_against_moves_a_claim_down() -> None:
    d = desk()
    before = views.scores(d["claims"], d["evidence"], d["runs"])["emergence"]["score"]
    d["evidence"]["wei2022cot:emergence"] = {
        "key": "wei2022cot:emergence",
        "source": "wei2022cot",
        "claim": "emergence",
        "stance": "against",
        "weight": 2,
        "note": "",
        "at": time.time(),
    }
    after = views.scores(d["claims"], d["evidence"], d["runs"])["emergence"]
    assert after["score"] < before
    assert after["status"] == "Doubtful"


def test_steps_beating_direct_is_evidence_for_cot() -> None:
    runs = {
        r["key"]: r
        for r in (run("haiku", "steps", "clean", 20), run("haiku", "direct", "clean", 14))
    }
    (ev,) = [e for e in views.run_evidence(runs) if e["claim"] == "cot"]
    assert ev["stance"] == "for"
    assert ev["weight"] == 3


def test_no_gain_weighs_against_and_replication_adds_weight() -> None:
    once = {
        r["key"]: r
        for r in (run("haiku", "steps", "clean", 20), run("haiku", "direct", "clean", 20))
    }
    (ev,) = [e for e in views.run_evidence(once) if e["claim"] == "cot"]
    assert (ev["stance"], ev["weight"]) == ("against", 1)
    twice = {
        **once,
        **{
            r["key"]: r
            for r in (
                run("haiku", "steps", "clean", 20, at=2),
                run("haiku", "direct", "clean", 20, at=2),
            )
        },
    }
    (ev,) = [e for e in views.run_evidence(twice) if e["claim"] == "cot"]
    assert ev["weight"] == 2


def test_probe_bears_on_distract() -> None:
    probes = [
        {"context": "noisy" if i % 2 else "clean", "correct": not i % 2, "at": float(i)}
        for i in range(10)
    ]
    (ev,) = views.probe_evidence(probes)
    assert (ev["claim"], ev["stance"]) == ("distract", "for")


def test_history_ends_now_at_the_current_score() -> None:
    d = desk()
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"])
    hist = views.history(d["claims"], d["evidence"], d["runs"], d["models"])
    for key, pts in hist.items():
        assert pts[-1][1] == pytest.approx(sc[key]["score"], abs=1e-3)
        assert [p[0] for p in pts] == sorted(p[0] for p in pts)


def test_digest_and_notebook_read_the_desk() -> None:
    d = desk()
    assert "eval runs" in views.digest(d, "base")
    live = views.notebook(d)[0]
    assert live["live"]
    assert "{" not in live["text"]


# --- the jobs' steps ---------------------------------------------------------------------------


def test_a_run_carries_on_from_its_first_unanswered_question() -> None:
    r = {"key": "r", "answers": {}}
    r = job.answered(r, "q01", {"text": "1471", "total_cost_usd": 0.001}, 1.2)
    assert job.todo(r)[0] == "q02"
    assert r["answers"]["q01"]["correct"]
    assert job.finished(r)["status"] == "done"


def test_probe_asks_when_due_and_when_asked() -> None:
    now = time.time()
    assert job.due(None, 0, False, now)
    waiting = {"next_at": now + 60, "asked": 0, "day": time.strftime("%Y-%m-%d"), "today": 1}
    assert not job.due(waiting, 0, False, now)
    assert job.due(waiting, 1, False, now)
    assert not job.due({**waiting, "next_at": 0}, 0, True, now)
    assert not job.due({**waiting, "next_at": 0, "today": job.CAP}, 0, False, now)


def test_probe_takes_turns() -> None:
    asks = []
    p: dict = {}
    for _ in range(4):
        a = job.probe_next(p)
        asks.append((a["q"], a["context"]))
        p = job.probed(p, [], 0, a, {"text": "0"}, 1.0, time.time())["probe"]
    assert asks == [("q01", "clean"), ("q01", "noisy"), ("q02", "clean"), ("q02", "noisy")]


# --- the opening content and the cells ---------------------------------------------------------


def test_baked_runs_are_whole_and_graded_as_now() -> None:
    assert len(baked.RUNS) == 8
    for r in baked.RUNS:
        assert set(r["answers"]) == set(evals.BY_ID)
        for q, a in r["answers"].items():
            assert evals.grade(q, a["text"])["correct"] == a["correct"]


def test_every_evidence_names_a_source_and_a_claim() -> None:
    sources, claims = {s["key"] for s in data.SOURCES}, {c["key"] for c in data.CLAIMS}
    for e in data.EVIDENCE:
        assert e["source"] in sources
        assert e["claim"] in claims


def test_cell_sources_compile() -> None:
    assert PLANE.name == "research"
    for group in (
        cells.ROOT,
        cells.READING,
        cells.SOURCE,
        cells.CLAIMS,
        cells.CLAIM,
        cells.MODELS,
        cells.EVALS,
        cells.RUN,
        cells.WATCH,
        cells.NOTEBOOK,
    ):
        for name, source in group:
            compile(source, name, "exec")
    compile(
        job.job_source("b", {"key": "k", "model": "haiku", "style": "direct", "context": "clean"}),
        "run",
        "exec",
    )
    compile(job.probe_source("b"), "probe", "exec")
