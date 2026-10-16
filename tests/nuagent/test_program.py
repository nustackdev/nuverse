"""Extract and attempt: what the program is, and how it went."""

from __future__ import annotations

import pytest
from _support.scripted import HEAD, Mem, block

import nu
from nuagent.core import attempt, extract
from nuagent.presets.store.mem import MemSession
from nuagent.protocol import CONSTRUCT, NO_CODE, OK, RUNTIME


def extracted(reply: str) -> str:
    return nu.run(extract(reply))[0]


# --- extract -----------------------------------------------------------------


@pytest.mark.parametrize("tag", ["python", "py", ""])
def test_extract_takes_the_block_and_drops_its_tag(tag):
    assert extracted(f"Doing it.\n```{tag}\nx = 1\n```\nDone.") == "x = 1"


def test_extract_keeps_a_multi_line_module_whole():
    module = "import nu\n\n\ndef out():\n    return nu.Int(1)"
    assert extracted(block(module)) == module


def test_extract_takes_the_first_block():
    reply = "```python\nfirst = 1\n```\nor rather\n```python\nsecond = 2\n```"
    assert extracted(reply) == "first = 1"


def test_extract_uses_a_fenceless_reply_whole():
    assert extracted("  import nu\ndef out(): ...  \n") == "import nu\ndef out(): ..."


def test_extract_falls_back_on_an_unclosed_fence():
    assert extracted("```python\nx = 1") == "```python\nx = 1"


def test_extract_leaves_empty_empty():
    assert extracted("") == ""


def test_extract_composes_over_a_ref():
    term = nu.Frame(MemSession, extract(MemSession.reply), reply=block("y = 2"))
    assert nu.run(term)[0] == "y = 2"


# --- attempt -----------------------------------------------------------------


def attempted(reply: str, mem: Mem | None = None) -> dict:
    mem = mem or Mem()
    return mem.run(attempt(extract(reply), reply=reply))


def test_a_query_comes_back_as_its_repr():
    assert attempted(block(HEAD + "def out():\n    return nu.Str('hi') + '!'")) == {
        "kind": OK,
        "value": "'hi!'",
    }


def test_a_command_yields_none_and_the_world_is_the_evidence():
    mem = Mem()
    outcome = attempted(block(HEAD + "def out():\n    return World.log.set(['a'])"), mem)
    assert outcome == {"kind": OK, "value": "None"}
    assert mem.world == {"log": ["a"]}


def test_the_program_runs_exactly_once():
    mem = Mem(world={"log": []})
    attempted(block(HEAD + "def out():\n    return World.log.append('x')"), mem)
    assert mem.world["log"] == ["x"]


def test_the_yield_is_never_cut_short():
    outcome = attempted(block(HEAD + "def out():\n    return nu.Str('x' * 50000)"))
    assert outcome["value"] == repr("x" * 50000)


def test_a_parse_failure_is_construct_with_its_line():
    outcome = attempted(block("import nu\n\ndef out(:\n    return nu.Int(1)"))
    assert outcome["kind"] == CONSTRUCT
    assert outcome["line"] == 3
    assert "does not parse" in outcome["message"]


def test_a_raising_entry_point_is_construct_with_its_line():
    outcome = attempted(block("import nu\n\ndef out():\n    return nu.Nope()"))
    assert outcome["kind"] == CONSTRUCT
    assert outcome["line"] == 4
    assert "Nope" in outcome["message"]


def test_a_failure_with_no_position_has_no_line():
    outcome = attempted(block("import nu\n\ndef out():\n    return 5"))
    assert outcome == {
        "kind": CONSTRUCT,
        "message": "entry point 'out' returned int, expected a Nu term",
        "line": None,
    }


def test_built_then_raised_is_runtime_with_its_type():
    outcome = attempted(block("import nu\n\ndef out():\n    return nu.Div(1, 0)"))
    assert outcome == {"kind": RUNTIME, "message": "ZeroDivisionError: division by zero"}


def test_prose_is_no_code_not_a_syntax_error():
    assert attempted("I think the answer is 4 \u2014 surely.") == {"kind": NO_CODE}


def test_an_unclosed_fence_of_prose_is_no_code():
    assert attempted("```python\nLet me think about this first") == {"kind": NO_CODE}


def test_fenced_garbage_still_gets_its_diagnostic():
    assert attempted("```python\nthis is not python\n```")["kind"] == CONSTRUCT


def test_without_the_reply_a_fenceless_failure_is_construct():
    mem = Mem()
    assert mem.run(attempt("plain words here"))["kind"] == CONSTRUCT
