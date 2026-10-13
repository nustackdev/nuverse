"""nuverse-demos agents: the plain Python that shapes what the cells draw, and the task board's books."""

from __future__ import annotations

import json
from pathlib import Path

from nuverse_demos.agents import flows, orchestrate, views
from nuverse_demos.agents.job import job_source


def _log(*events: dict) -> list[str]:
    return [views.dumped_of(e) for e in events]


def test_a_tool_call_and_its_result_share_one_entry():
    got = views.entries_of(
        _log(
            {"type": "user", "text": "hi"},
            {"type": "init", "session_id": "s"},
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls -la"}},
            {"type": "text", "text": "looking"},
            {"type": "tool_result", "id": "t1", "content": "a\nb", "is_error": False},
            {
                "type": "result",
                "num_turns": 2,
                "total_cost_usd": 0.1,
                "duration_ms": 1200,
                "usage": {},
            },
        ),
        {},
    )
    kinds = [(e["key"], e["kind"]) for e in got["entries"]]
    assert kinds == [("e0", "user"), ("t1", "tool"), ("e3", "text"), ("t1", "back"), ("e5", "note")]
    tool, back = got["entries"][1], got["entries"][3]
    assert (tool["title"], tool["code"], tool["lang"]) == ("Bash ls -la", "ls -la", "bash")
    assert back["title"] == "Bash ls -la  ·  done · 2 lines"
    assert got["entries"][4]["text"] == "Turn done · 2 steps · 1.2s · $0.100"
    assert got["seen"] == {"i": 6, "titles": {}}


def test_entries_pick_up_where_the_last_pass_left_off():
    first = views.entries_of(
        _log(
            {
                "type": "tool_use",
                "id": "t",
                "name": "Write",
                "input": {"file_path": "/x/a.py", "content": "x = 1"},
            }
        ),
        {},
    )
    assert first["entries"][0]["lang"] == "python"
    assert first["seen"] == {"i": 1, "titles": {"t": "Write a.py"}}
    later = views.entries_of(
        _log({"type": "tool_result", "id": "t", "content": "", "is_error": True}), first["seen"]
    )
    (back,) = later["entries"]
    assert back["title"] == "Write a.py  ·  failed"
    assert back["code"] == "(no output)"
    assert later["seen"]["i"] == 2


def test_long_tool_input_is_cut():
    (entry,) = views.entries_of(
        _log({"type": "tool_use", "id": "t", "name": "Other", "input": {"blob": "x" * 9000}}), {}
    )["entries"]
    assert entry["lang"] == "json"
    assert entry["code"].endswith("more characters")


def test_doing_and_tally_read_events():
    assert (
        views.doing_text(
            {"type": "tool_use", "name": "Write", "input": {"file_path": "/a/b/index.html"}}
        )
        == "Write index.html"
    )
    assert views.doing_text({"type": "text"}) == "writing"
    usage = {
        "input_tokens": 5,
        "cache_creation_input_tokens": 10,
        "cache_read_input_tokens": 85,
        "output_tokens": 7,
    }
    t = views.tally_of({"num_turns": 3, "usage": usage, "total_cost_usd": 0.5, "duration_ms": 2500})
    assert t == {"turns": 3, "in": 100, "out": 7, "cost": 0.5, "seconds": 2.5}


def test_a_spec_fills_its_blanks(tmp_path):
    spec = views.spec_from("", "", "", "", " do it ", 2)
    assert spec["name"] == "Agent 3"
    assert Path(spec["cwd"]).is_dir()
    assert (spec["model"], spec["mode"], spec["brief"]) == (
        views.MODELS[0],
        views.MODES[0],
        "do it",
    )
    assert views.spec_from("Ann", str(tmp_path), "opus", "plan", "", 0)["cwd"] == str(tmp_path)


def test_header_and_cards_read_a_view():
    v = {
        "status": "working",
        "spec": {"name": "Ann", "model": "m", "mode": "acceptEdits", "cwd": "/srv/x"},
        "doing": "Bash ls",
        "prompts": 2,
        "turns": 7,
        "calls": 3,
        "tokens_in": 12000,
        "tokens_out": 345,
        "cost": 0.123,
        "seconds": 9.4,
        "answer": "**Done**: wrote `index.html`\nmore",
        "error": "",
        "queued": 0,
    }
    h = views.head_of(v)
    assert (h["name"], h["tone"], h["doing"], h["tokens"], h["cost"], h["button"]) == (
        "Ann",
        "ok",
        "Bash ls",
        "12.3k",
        "$0.12",
        "Stop",
    )
    idle = views.head_of({**v, "status": "idle"})
    assert idle["doing"] == "waiting for you to say something"
    assert views.head_of({**v, "status": "stopped"})["button"] == "Resume"
    (card,) = views.cards_of([["p1", "j1", v]])
    assert card["key"] == "j1" and card["href"] == "/p1"
    assert card["doing"] == "Bash ls"
    assert card["stats"] == "2 prompts · 3 tool calls · 12.3k tokens · $0.12"
    assert (
        views.cards_of([["p1", "j1", {**v, "status": "idle"}]])[0]["doing"]
        == "Done: wrote index.html"
    )


def test_a_sketch_is_read_from_its_file(tmp_path):
    assert views.sketch_from(str(tmp_path), []) == []
    drawn = [{"type": "rect", "x": 0.1, "y": 0.1, "w": 0.3, "h": 0.2}]
    (tmp_path / "sketch.json").write_text(json.dumps(drawn))
    assert views.sketch_from(str(tmp_path), []) == drawn
    (tmp_path / "sketch.json").write_text("{nope")
    assert views.sketch_from(str(tmp_path), drawn) == drawn


def test_the_board_hands_out_tasks_and_closes_them():
    board = [{"task": t, "status": "open", "by": "", "mark": 0, "answer": ""} for t in ("a", "b")]
    took = flows.taken(board, "w1", 3)
    assert took["task"] == "a"
    assert flows.holds(took["tasks"], "w1")
    assert not flows.holds(took["tasks"], "w2")
    assert flows.closed(took["tasks"], "w1", 3, "x", True)["changed"] is False
    shut = flows.closed(took["tasks"], "w1", 4, "did a", True)
    assert shut["changed"]
    assert shut["tasks"][0] == {
        "task": "a",
        "status": "done",
        "by": "w1",
        "mark": 3,
        "answer": "did a",
    }
    tally = flows.tally_of(shut["tasks"])
    assert tally["phase"] == "1 of 2 done, 0 under way"
    assert "| a | w1 | done | did a |" in tally["outcome"]
    assert flows.taken(shut["tasks"], "w2", 0)["task"] == "b"
    assert flows.taken([{**board[0], "status": "done"}], "w2", 0)["task"] == ""


def test_flow_and_job_sources_bake_what_they_were_given():
    source = flows.flow_source(
        "chain", "root1", "/tmp/f", "Chain 1", {"brief": "b", "n": 1, "tasks": []}
    )
    assert "ROOT, DIR, NAME = 'root1', '/tmp/f', 'Chain 1'" in source
    assert "'brief': 'b'," in source
    job = job_source({"name": "a", "cwd": "/w", "model": "m", "mode": "plan", "brief": "x"}, idle=5)
    assert "'cwd': '/w'," in job and "IDLE = 5.0" in job
    assert orchestrate.lines_of("- one\n\n* two \n") == ["one", "two"]
