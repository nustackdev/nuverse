"""Reading the desk: scores, the runs' own evidence, the leaderboard, the week. Plain Python.

Everything a cell shows is worked out here from the store's plain dicts, so
the cells stay short and this is tested on its own.

**Scores.** A claim's evidence is what the papers give (weighted 1 to 3, for
or against) and what our own runs give, worked out fresh from the finished
runs every time (:func:`run_evidence`): step by step against direct answers
bears on ``cot``, clean against distracted on ``distract``, a small model
thinking against a large one answering on ``testtime``. The score is
``(for - against) / (for + against + 2)``: between -1 and 1, and slow to
move on thin evidence.
"""

from __future__ import annotations

import re
import statistics
import time
from typing import Any

from . import baked, data, evals, job


__all__ = [
    "LABELS",
    "STATUSES",
    "accuracy",
    "activity",
    "ago",
    "digest",
    "history",
    "latest",
    "leaderboard",
    "model_evidence",
    "notebook",
    "opening",
    "pools",
    "probe_evidence",
    "probe_split",
    "run_evidence",
    "scores",
    "short",
    "status_of",
    "title_of_run",
]


DAY = 86_400.0

#: A claim's short name, for its page and the board.
LABELS = {
    "cot": "Step by step helps",
    "distract": "Irrelevant details hurt",
    "testtime": "Thinking can stand in for size",
    "chinchilla": "About 20 tokens per parameter",
    "overtrain": "Open models overtrain",
    "emergence": "Emergence is a mirage",
    "feedback": "Feedback beats size",
    "middle": "Lost in the middle",
    "reversal": "The reversal curse",
    "contamination": "Benchmarks are contaminated",
}

#: A score's status, from the top: (lowest score, label, tone).
STATUSES = (
    (0.45, "Supported", "ok"),
    (0.15, "Leaning yes", "info"),
    (-0.15, "Contested", "warn"),
    (-2.0, "Doubtful", "danger"),
)


def short(text: str, n: int = 40) -> str:
    """A claim's text cut to a short name at a word."""
    text = text.strip().rstrip(".")
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0] + "..."


def ago(t: float, now: float | None = None) -> str:
    """``just now``, ``12 min ago``, ``3 h ago``, ``2 days ago``."""
    s = max(0.0, (now or time.time()) - (t or 0.0))
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{int(s // 60)} min ago"
    if s < DAY:
        return f"{int(s // 3600)} h ago"
    d = int(s // DAY)
    return "yesterday" if d == 1 else f"{d} days ago"


# --- the opening desk ------------------------------------------------------------------------


def opening(now: float) -> dict[str, Any]:
    """The desk's first state, keyed as the store keeps it, its days-ago made into times against ``now``."""

    def at(days: float, salt: int = 0) -> float:
        # A working hour on the day, not midnight: 9:00 plus a little per item.
        return now - days * DAY - ((salt * 2_351) % 21_600)

    sources = [
        {**s, "at": at(s.pop("ago"), i)} for i, s in enumerate(dict(s) for s in data.SOURCES)
    ]
    claims = [
        {
            **c,
            "label": LABELS.get(c["key"], short(c["text"])),
            "at": at(c.pop("ago"), i),
            "by": _by_claim(c["key"]),
        }
        for i, c in enumerate(dict(c) for c in data.CLAIMS)
    ]
    evidence = {}
    for i, e in enumerate(data.EVIDENCE):
        e = dict(e)
        key = f"{e['source']}:{e['claim']}"
        evidence[key] = {**e, "key": key, "at": at(e.pop("ago"), i), "by": _by_source(e["source"])}
    models = {m["key"]: dict(m) for m in data.MODELS}
    runs = []
    for r in baked.RUNS:
        days = r["ago"]
        runs.append(
            {
                **{k: v for k, v in r.items() if k != "ago"},
                "at": at(days, len(runs)),
                "done_at": at(days, len(runs)) + r["seconds"],
                "status": "done",
            }
        )
    notes = [
        {**n, "at": at(n["ago"], i), **({"live": True} if n.get("live") else {})}
        for i, n in enumerate(data.NOTEBOOK)
    ]
    for n in notes:
        n.pop("ago", None)
    # The probe's answers, at its own pace, the last a few minutes ago; its next question soon after opening.
    gap = job.INTERVAL
    probes = [
        {**p, "at": now - 180 - (len(baked.PROBES) - 1 - i) * gap}
        for i, p in enumerate(baked.PROBES)
    ]
    day = time.strftime("%Y-%m-%d", time.localtime(now))
    probe = {
        "n": len(probes),
        "asked": 0,
        "next_at": now + 45,
        "day": day,
        "today": sum(
            1 for p in probes if time.strftime("%Y-%m-%d", time.localtime(p["at"])) == day
        ),
        "status": "waiting",
    }
    return {
        "sources": {s["key"]: s for s in sources},
        "claims": {c["key"]: c for c in claims},
        "evidence": evidence,
        "models": models,
        "runs": {r["key"]: r for r in runs},
        "notebook": notes,
        "probes": probes,
        "probe": probe,
    }


def _by_claim(key: str) -> str:
    """Who put a claim up: whoever added its first source."""
    first = min(
        (e for e in data.EVIDENCE if e["claim"] == key), key=lambda e: -e["ago"], default=None
    )
    return _by_source(first["source"]) if first else data.TEAM[0]


def _by_source(key: str) -> str:
    return next((s["by"] for s in data.SOURCES if s["key"] == key), data.TEAM[0])


# --- runs ------------------------------------------------------------------------------------


def accuracy(run: dict, tier: str = "") -> tuple[int, int]:
    """``(right, asked)`` over a run's answers so far, on one tier (``word``, ``hard``) or all."""
    answers = [
        a for q, a in (run.get("answers") or {}).items() if not tier or evals.tier(q) == tier
    ]
    return sum(1 for a in answers if a.get("correct")), len(answers)


def pct(right: int, n: int) -> str:
    return f"{100 * right / n:.0f}%" if n else "-"


def title_of_run(run: dict) -> str:
    """``Haiku · Direct · Clean``."""
    return evals.arm_label(run["model"], run["style"], run["context"])


def latest(runs: dict) -> dict[tuple[str, str, str], dict]:
    """The latest finished run per arm."""
    best: dict[tuple[str, str, str], dict] = {}
    for r in runs.values():
        if r.get("status") != "done":
            continue
        arm = (r["model"], r["style"], r["context"])
        if arm not in best or r.get("done_at", 0) > best[arm].get("done_at", 0):
            best[arm] = r
    return best


def _rate(run: dict) -> float:
    right, n = accuracy(run)
    return right / n if n else 0.0


def pools(runs: dict) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Every finished run pooled per arm: ``{right, n, runs, latest, at}``. More runs, more weight."""
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in runs.values():
        if r.get("status") != "done":
            continue
        p = out.setdefault(
            (r["model"], r["style"], r["context"]), {"right": 0, "n": 0, "runs": 0, "latest": r}
        )
        right, n = accuracy(r)
        p["right"], p["n"], p["runs"] = p["right"] + right, p["n"] + n, p["runs"] + 1
        if r.get("done_at", 0) >= p["latest"].get("done_at", 0):
            p["latest"] = r
    for p in out.values():
        p["rate"] = p["right"] / p["n"] if p["n"] else 0.0
        p["at"] = p["latest"].get("done_at", 0)
    return out


def _runs(p: dict) -> str:
    return f"{p['right']}/{p['n']}" + (f" over {p['runs']} runs" if p["runs"] > 1 else "")


def _compared(claim: str, a: dict, b: dict, said: str, nothing: str, key: str) -> dict[str, Any]:
    """Evidence from two pooled arms: how much ``a`` beats ``b``, positive bearing for.

    No effect weighs 1, an effect 2, a big one (20 points) 3; replicated (both
    arms run twice or more) adds 1, up to 3.
    """
    gap = a["rate"] - b["rate"]
    if gap >= 0.05:
        stance, weight, note = "for", 3 if gap >= 0.2 else 2, said.format(gap=f"{100 * gap:.0f}")
    elif gap <= -0.05:
        stance, weight, note = "against", 2, f"Reversed: {100 * -gap:.0f} points the other way."
    else:
        stance, weight, note = "against", 1, nothing
    if min(a["runs"], b["runs"]) >= 2:
        weight = min(3, weight + 1)
    return {
        "key": f"run:{claim}:{key}",
        "kind": "run",
        "source": a["latest"]["key"],
        "other": b["latest"]["key"],
        "claim": claim,
        "stance": stance,
        "weight": weight,
        "note": f"{note} ({_runs(a)} against {_runs(b)})",
        "at": max(a["at"], b["at"]),
        "by": "eval",
    }


def run_evidence(runs: dict, probes: list | None = None) -> list[dict[str, Any]]:
    """What our finished runs, and the probe, say about the claims they bear on, worked out fresh."""
    arms = pools(runs)
    out = []
    for model, name in evals.MODELS.items():
        for context, cname in evals.CONTEXTS.items():
            s, d = arms.get((model, "steps", context)), arms.get((model, "direct", context))
            if s and d:
                who = f"{name}, {cname.lower()}"
                out.append(
                    _compared(
                        "cot",
                        s,
                        d,
                        f"{who}: step by step is {{gap}} points over direct.",
                        f"{who}: no gain.",
                        f"{model}:{context}",
                    )
                )
        for style, sname in evals.STYLES.items():
            c, n = arms.get((model, style, "clean")), arms.get((model, style, "noisy"))
            if c and n:
                who = f"{name}, {sname.lower()}"
                out.append(
                    _compared(
                        "distract",
                        c,
                        n,
                        f"{who}: the distractor costs {{gap}} points.",
                        f"{who}: no drop.",
                        f"{model}:{style}",
                    )
                )
    small, large = list(evals.MODELS)[1], next(iter(evals.MODELS))
    for context, cname in evals.CONTEXTS.items():
        h, s = arms.get((small, "steps", context)), arms.get((large, "direct", context))
        if h and s:
            keeps = h["rate"] - s["rate"] >= -0.05
            out.append(
                {
                    "key": f"run:testtime:{context}",
                    "kind": "run",
                    "source": h["latest"]["key"],
                    "other": s["latest"]["key"],
                    "claim": "testtime",
                    "stance": "for" if keeps else "against",
                    "weight": 3 if keeps and min(h["runs"], s["runs"]) >= 2 else 2,
                    "note": f"{cname}: Haiku thinking {_runs(h)}, Sonnet answering {_runs(s)}.",
                    "at": max(h["at"], s["at"]),
                    "by": "eval",
                }
            )
    out += probe_evidence(probes or [])
    return out


def probe_evidence(probes: list) -> list[dict[str, Any]]:
    """The probe's clean against distracted record on ``distract``: weight 1, 2 past 40 answers."""
    if len(probes) < 4:
        return []
    clean = [p for p in probes if p.get("context") != "noisy"]
    noisy = [p for p in probes if p.get("context") == "noisy"]

    def rate(ps: list) -> float:
        return sum(1 for p in ps if p.get("correct")) / len(ps) if ps else 0.0

    def right(ps: list) -> str:
        return f"{sum(1 for p in ps if p.get('correct'))}/{len(ps)}"

    stance = "for" if rate(clean) - rate(noisy) >= 0.05 else "against"
    return [
        {
            "key": "probe:distract",
            "kind": "probe",
            "source": "probe",
            "claim": "distract",
            "stance": stance,
            "weight": 2 if len(probes) >= 40 else 1,
            "note": f"Sonnet answering directly: clean {right(clean)}, distracted {right(noisy)}.",
            "at": probes[-1].get("at") or 0,
            "by": "probe",
        }
    ]


def _score(items: list[dict]) -> tuple[int, int, float]:
    f = sum(e["weight"] for e in items if e["stance"] == "for")
    a = sum(e["weight"] for e in items if e["stance"] == "against")
    return f, a, (f - a) / (f + a + 2)


def status_of(score: float) -> tuple[str, str]:
    """``(label, tone)`` for a score."""
    for lo, label, tone in STATUSES:
        if score >= lo:
            return label, tone
    return STATUSES[-1][1], STATUSES[-1][2]


def model_evidence(models: dict) -> list[dict[str, Any]]:
    """What the model table says about ``overtrain``: open models since 2023, past twice the ~20 rule or not."""
    recent = [
        m
        for m in models.values()
        if m.get("open") and (m.get("year") or 0) >= 2023 and m.get("tokens") and m.get("params")
    ]
    if not recent:
        return []
    over = [m for m in recent if m["tokens"] * 1000 / m["params"] > 40]
    share = len(over) / len(recent)
    names = ", ".join(m["name"] for m in over[:3]) or "none"
    return [
        {
            "key": "models:overtrain",
            "kind": "models",
            "source": "models",
            "claim": "overtrain",
            "stance": "for" if share >= 0.5 else "against",
            "weight": 3 if share >= 0.75 else 2 if share >= 0.5 else 1,
            "note": f"{len(over)} of {len(recent)} open models since 2023 train past 40 tokens per parameter ({names}).",
            "at": max((m.get("at") or 0) for m in recent) or time.time() - 19 * DAY,
            "by": "models",
        }
    ]


def scores(
    claims: dict, evidence: dict, runs: dict, models: dict | None = None, probes: list | None = None
) -> dict[str, dict[str, Any]]:
    """Per claim: ``{for, against, score, status, tone, papers, ours, items}``, items newest first."""
    ours = run_evidence(runs, probes) + model_evidence(models or {})
    out = {}
    for key in claims:
        items = [e for e in evidence.values() if e.get("claim") == key]
        items += [e for e in ours if e["claim"] == key]
        f, a, s = _score(items)
        label, tone = status_of(s)
        out[key] = {
            "for": f,
            "against": a,
            "score": round(s, 3),
            "status": label,
            "tone": tone,
            "papers": sum(1 for e in items if not e.get("kind")),
            "ours": sum(1 for e in items if e.get("kind")),
            "items": sorted(items, key=lambda e: -(e.get("at") or 0)),
        }
    return out


def history(
    claims: dict, evidence: dict, runs: dict, models: dict | None = None, probes: list | None = None
) -> dict[str, list[list[float]]]:
    """Per claim, its score after each piece of evidence landed: ``[[ms, score], ...]``, now last."""
    items = list(evidence.values()) + run_evidence(runs, probes) + model_evidence(models or {})
    out = {}
    for key, c in claims.items():
        mine = sorted((e for e in items if e.get("claim") == key), key=lambda e: e.get("at") or 0)
        start = min([c.get("at") or 0] + [e.get("at") or 0 for e in mine])
        pts = [[start * 1000 - 3_600_000, 0.0]]
        for i in range(len(mine)):
            pts.append([(mine[i].get("at") or 0) * 1000, round(_score(mine[: i + 1])[2], 3)])
        pts.append([time.time() * 1000, pts[-1][1]])
        out[key] = pts
    return out


def leaderboard(runs: dict) -> list[dict[str, Any]]:
    """Every run, best first: arm, overall and per tier accuracy, pace and cost."""
    rows = []
    for r in runs.values():
        right, n = accuracy(r)
        hr, hn = accuracy(r, "hard")
        secs = [a.get("seconds") or 0 for a in (r.get("answers") or {}).values()]
        cost = sum(a.get("cost") or 0 for a in (r.get("answers") or {}).values())
        rows.append(
            {
                "key": r["key"],
                "arm": title_of_run(r),
                "acc": round(100 * right / n, 1) if n else None,
                "word": pct(*accuracy(r, "word")),
                "hard": pct(hr, hn),
                "done": f"{n}/{len(evals.BY_ID)}",
                "median": f"{statistics.median(secs):.1f} s" if secs else "-",
                "cost": f"${cost:.3f}",
                "status": r.get("status", ""),
                "when": ago(r.get("done_at") or r.get("at") or 0),
                "_sort": (r.get("status") == "done", -(right / n if n else 0), -(r.get("at") or 0)),
            }
        )
    rows.sort(key=lambda x: x.pop("_sort"))
    return rows


# --- the week, and the notebook --------------------------------------------------------------


def digest(desk: dict, base: str = "", now: float | None = None) -> str:
    """What changed on the desk in the last seven days, as markdown, from the whole store."""
    now = now or time.time()
    week = now - 7 * DAY
    sources, claims, runs = desk["sources"], desk["claims"], desk["runs"]
    evidence = desk["evidence"]
    added = [s for s in sources.values() if (s.get("at") or 0) >= week]
    reading = [s for s in sources.values() if s.get("status") == "reading"]
    fresh = [r for r in runs.values() if (r.get("done_at") or r.get("at") or 0) >= week]
    live = [r for r in runs.values() if r.get("status") in ("queued", "running")]
    models = desk.get("models") or {}
    probes = desk.get("probes") or []
    now_scores = scores(claims, evidence, runs, models, probes)
    then_ev = {k: e for k, e in evidence.items() if (e.get("at") or 0) < week}
    then_runs = {k: r for k, r in runs.items() if (r.get("done_at") or 0) < week}
    then = scores(
        claims, then_ev, then_runs, models, [p for p in probes if (p.get("at") or 0) < week]
    )
    moved = sorted(
        ((k, now_scores[k]["score"] - then[k]["score"]) for k in claims),
        key=lambda kv: -abs(kv[1]),
    )
    lines = []
    if added:
        names = ", ".join(
            s["title"].split(":")[0] for s in sorted(added, key=lambda s: -s["at"])[:3]
        )
        lines.append(
            f"- **{len(added)} sources** came in: {names}{'...' if len(added) > 3 else ''}"
        )
    if reading:
        lines.append(
            f"- **{len(reading)} in reading** now, {sum(1 for s in sources.values() if s.get('status') == 'queued')} queued"
        )
    if fresh or live:
        done = [r for r in fresh if r.get("status") == "done"]
        best = max(done, key=_rate, default=None)
        bit = f", the best {title_of_run(best)} at {pct(*accuracy(best))}" if best else ""
        lines.append(
            f"- **{len(done)} eval runs** finished{bit}"
            + (f", {len(live)} running now" if live else "")
        )
    for key, d in moved[:3]:
        if abs(d) < 0.01:
            continue
        s = now_scores[key]
        way = "up" if d > 0 else "down"
        name = f"[{claims[key]['label']}](/{base}.claim.{key})" if base else claims[key]["label"]
        lines.append(
            f"- {name} moved **{way} {abs(d):.2f}** to {s['score']:+.2f}, {s['status'].lower()}"
        )
    probes = desk.get("probes") or []
    recent = [p for p in probes if (p.get("at") or 0) >= now - DAY]
    if recent:
        right = sum(1 for p in recent if p.get("correct"))
        lines.append(
            f"- The probe asked **{len(recent)}** question{'s' if len(recent) != 1 else ''} today, {right} right"
        )
    return "\n".join(lines) or "A quiet week: nothing new on the desk."


def activity(desk: dict, base: str, n: int = 10) -> str:
    """The desk's latest doings, newest first, as markdown: who added, linked, ran, wrote; what the probe missed."""
    sources, claims, runs = desk["sources"], desk["claims"], desk["runs"]
    ev: list[tuple[float, str]] = []
    for s in sources.values():
        ev.append(
            (
                s.get("at") or 0,
                f"{s.get('by', 'Someone')} added [{_short_title(s)}](/{base}.src.{s['key']})",
            )
        )
    for e in desk["evidence"].values():
        s, c = sources.get(e["source"]), claims.get(e["claim"])
        if s and c:
            ev.append(
                (
                    e.get("at") or 0,
                    f"{e.get('by') or s.get('by', 'Someone')} weighed [{_short_title(s)}](/{base}.src.{s['key']}) "
                    f"{'for' if e['stance'] == 'for' else 'against'} [{c['label']}](/{base}.claim.{c['key']})",
                )
            )
    for r in runs.values():
        right, asked = accuracy(r)
        if r.get("status") == "done":
            ev.append(
                (
                    r.get("done_at") or 0,
                    f"[{title_of_run(r)}](/{base}.run.{r['key']}) finished, {right}/{asked}, run by {r.get('by', 'the desk')}",
                )
            )
        else:
            ev.append(
                (
                    r.get("at") or 0,
                    f"[{title_of_run(r)}](/{base}.run.{r['key']}) is running, {asked}/{len(evals.BY_ID)} answered",
                )
            )
    for p in desk.get("probes") or []:
        if not p.get("correct"):
            q = evals.BY_ID.get(p["q"], {}).get("label", p["q"])
            ev.append(
                (
                    p.get("at") or 0,
                    f"[The probe](/{base}.watch) missed *{q}*, {'distracted' if p.get('context') == 'noisy' else 'clean'}: said {p.get('got'):g}"
                    if isinstance(p.get("got"), (int, float))
                    else f"[The probe](/{base}.watch) got no answer to *{q}*",
                )
            )
    for note in desk.get("notebook") or []:
        if not note.get("live"):
            ev.append(
                (
                    note.get("at") or 0,
                    f"{note.get('by', 'Someone')} wrote [{note['title']}](/{base}.notebook) in the notebook",
                )
            )
    for c in claims.values():
        ev.append(
            (
                c.get("at") or 0,
                f"{c.get('by', 'Someone')} put [{c['label']}](/{base}.claim.{c['key']}) on the board",
            )
        )
    ev.sort(key=lambda x: -x[0])
    return "\n".join(f"- {line}  ·  *{ago(t)}*" for t, line in ev[:n])


def _short_title(s: dict) -> str:
    """A source by its first author and year: ``Shi et al. 2023``."""
    return f"{s.get('authors', '').split(',')[0]} {s.get('year') or ''}".strip()


def filled(text: str, known: dict[str, str]) -> str:
    """``text`` with every ``{name}`` it knows written in; the rest left as typed."""
    return re.sub(r"\{(\w+)\}", lambda m: known.get(m.group(1), m.group(0)), text)


def notebook(desk: dict, now: float | None = None) -> list[dict[str, Any]]:
    """The notebook's entries, newest first, live ones filled from the desk as it is now."""
    now = now or time.time()
    out = []
    for n in desk.get("notebook") or []:
        text = n["text"]
        if n.get("live"):
            text = filled(text, _numbers(desk, now))
        out.append(
            {
                **n,
                "text": text,
                "when": time.strftime("%a %d %b", time.localtime(n.get("at") or now)),
            }
        )
    return sorted(out, key=lambda n: -(n.get("at") or 0))


def _numbers(desk: dict, now: float) -> dict[str, str]:
    runs = desk["runs"]
    arms = latest(runs)
    done = [r for r in runs.values() if r.get("status") == "done"]
    best = max(done, key=_rate, default=None)

    def gap(a: str, b: str, axis: int) -> str:
        diffs = []
        for arm, r in arms.items():
            if arm[axis] != a:
                continue
            other = list(arm)
            other[axis] = b
            o = arms.get(tuple(other))
            if o:
                diffs.append(_rate(r) - _rate(o))
        if not diffs:
            return "not run yet"
        m = statistics.mean(diffs)
        return f"{100 * m:+.0f} points on average" if abs(m) >= 0.005 else "no difference"

    sc = scores(desk["claims"], desk["evidence"], runs, desk.get("models"), desk.get("probes"))
    probes = list(desk.get("probes") or [])
    secs = [p.get("seconds") or 0 for p in probes]
    return {
        "now": time.strftime("%H:%M", time.localtime(now)),
        "runs": str(len(done)),
        "best": title_of_run(best) if best else "none yet",
        "best_acc": pct(*accuracy(best)) if best else "-",
        "cot_gap": gap("steps", "direct", 1),
        "noise_gap": gap("clean", "noisy", 2),
        "hard_direct": _tier_rate(arms, "direct", "hard"),
        "hard_steps": _tier_rate(arms, "steps", "hard"),
        "probes": f"{len(probes)} question{'s' if len(probes) != 1 else ''}",
        "probe_acc": pct(sum(1 for p in probes if p.get("correct")), len(probes)),
        "probe_lat": f"{statistics.median(secs):.1f} s" if secs else "-",
        "probe_split": probe_split(probes),
        "cot_score": f"{sc['cot']['score']:+.2f}" if "cot" in sc else "-",
        "cot_status": sc.get("cot", {}).get("status", "").lower(),
        "distract_score": f"{sc['distract']['score']:+.2f}" if "distract" in sc else "-",
        "distract_status": sc.get("distract", {}).get("status", "").lower(),
    }


def probe_split(probes: list) -> str:
    """``24/24 against 22/24``: the probe's clean answers right, then its distracted ones."""
    clean = [p for p in probes if p.get("context") != "noisy"]
    noisy = [p for p in probes if p.get("context") == "noisy"]
    right = lambda ps: f"{sum(1 for p in ps if p.get('correct'))}/{len(ps)}"  # noqa: E731
    return f"{right(clean)} against {right(noisy)}" if probes else "nothing asked yet"


def _tier_rate(arms: dict, style: str, tier: str) -> str:
    right = n = 0
    for arm, r in arms.items():
        if arm[1] == style:
            a, b = accuracy(r, tier)
            right, n = right + a, n + b
    return pct(right, n)
