"""The protocol prose and the renderer say the same thing."""

from __future__ import annotations

import re

import pytest

import nu
from nuagent.core import FENCE
from nuagent.presets.store.mem import MemOutcome, MemSession
from nuagent.protocol import (
    CONSTRUCT,
    KINDS,
    LABELS,
    NO_CODE,
    NO_CODE_TEXT,
    OK,
    RUNTIME,
    observation,
    prompt,
    render,
)


PROSE = prompt()


def rendered(outcome: dict) -> str:
    return nu.run(render(nu.Dict(outcome)))[0]


def test_every_failure_kind_has_a_label_and_ok_has_none():
    assert set(LABELS) == set(KINDS) - {OK}


def test_every_label_is_in_the_prose():
    for label in LABELS.values():
        assert f"`{label}" in PROSE


def test_the_prose_names_no_label_the_renderer_lacks():
    quoted = set(re.findall(r"^- `([A-Z][A-Z ]+):", PROSE, re.M))
    assert quoted == set(LABELS.values())


@pytest.mark.parametrize(
    ("outcome", "text"),
    [
        ({"kind": NO_CODE}, NO_CODE_TEXT),
        (
            {
                "kind": CONSTRUCT,
                "message": "source does not parse: '(' was never closed",
                "line": 5,
            },
            "CONSTRUCTION FAILED: source does not parse: '(' was never closed (line 5)",
        ),
        (
            {"kind": RUNTIME, "message": "ZeroDivisionError: division by zero"},
            "RUNTIME FAILED: ZeroDivisionError: division by zero",
        ),
    ],
)
def test_each_failure_example_in_the_prose_is_what_the_renderer_writes(outcome, text):
    assert rendered(outcome) == text
    assert f"`{text}`" in PROSE


def test_ok_renders_the_value_as_is():
    assert rendered({"kind": OK, "value": "'a\\nb'"}) == "'a\\nb'"


def test_a_construct_failure_without_a_line_has_no_line():
    assert rendered({"kind": CONSTRUCT, "message": "m", "line": None}) == "CONSTRUCTION FAILED: m"


def test_the_observation_format_is_the_one_the_prose_shows():
    assert "    outcome: <what happened>\n    state: <the world after the run>" in PROSE
    with_state = observation(nu.Dict({"kind": OK, "value": "None"}), nu.List.of(1, 2))
    without = observation(nu.Dict({"kind": OK, "value": "None"}))
    assert nu.run(with_state)[0] == "outcome: None\nstate: [1, 2]"
    assert nu.run(without)[0] == "outcome: None"


def test_every_python_block_in_the_prose_builds():
    blocks = PROSE.split(FENCE)[1::2]
    sources = [b.removeprefix("python") for b in blocks if b.startswith("python")]
    assert len(sources) == 2
    for source in sources:
        assert isinstance(nu.run(nu.LoadNu(source))[0], nu.Nu)


def test_the_outcome_shape_carries_every_payload_field():
    assert list(MemOutcome._slots) == ["kind", "value", "message", "line"]
    assert list(MemSession._slots) == ["messages", "reply", "program", "outcome"]
