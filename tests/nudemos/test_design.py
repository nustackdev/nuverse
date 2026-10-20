"""The design demo's plain logic: the spec, its knobs, the checks, the history, the export's files."""

from __future__ import annotations

import io
import json

import pytest

from nudemos.design import checks, color, job, kit, logo, studio
from nudemos.design import spec as specs


def test_defaults_round_trip_through_oklch():
    for key, value in specs.DEFAULTS.items():
        if value.startswith("#"):
            assert color.hexof(*color.oklch(value)) == value, key


def test_the_language_passes_its_own_checks():
    s = checks.summary(specs.merged({}))
    assert s["fail"] == 0
    assert s["pass"] + s["under"] == s["total"]


def test_a_knob_turns_hue_and_keeps_lightness():
    writes = specs.apply_knob({}, "knob.afterglow", 320)
    assert writes["knob.afterglow"] == "320"
    before = color.oklch(specs.DEFAULTS["dusk:afterglow"])
    after = color.oklch(writes["dusk:afterglow"])
    assert after[0] == pytest.approx(before[0], abs=0.01)
    assert after[2] == pytest.approx(320, abs=2)
    assert "mark.from" in writes and "dawn:ink-1" not in writes


def test_tint_zero_makes_the_sky_neutral():
    writes = specs.apply_knob({}, "knob.tint", 0)
    assert color.oklch(writes["dusk:ground"])[1] < 0.003


def test_a_bright_afterglow_fails_white_labels():
    proposal = studio.POOL[0][3]
    assert studio.verdict(specs.merged({}), proposal).endswith("fails")
    rows = {r["key"]: r for r in checks.run({**specs.merged({}), **proposal})["pairs"]}
    assert rows["on-afterglow on afterglow"]["verdict"] == "fail"


def test_a_five_pixel_grid_breaks_the_rule():
    rules = {
        r["key"]: r["ok"] for r in checks.run({**specs.merged({}), "space.unit": "5"})["rules"]
    }
    assert rules["grid is 4px"] is False


def test_edits_drop_defaults_and_refuse_bad_hex():
    stored = kit._applied({}, {"radius.md": "8", "dusk:ground": "not a color"})
    assert stored == {"radius.md": "8"}
    assert kit._applied(stored, {"radius.md": "6"}) == {}


def test_history_merges_a_drag_into_one_line():
    log = kit._logged([], {}, {"radius.md": "7"}, "you", "Rounded", 100.0)
    log = kit._logged(log, {"radius.md": "7"}, {"radius.md": "9"}, "you", "Rounded", 102.0)
    assert len(log) == 1
    assert log[0]["changes"]["radius.md"] == ["6", "9"]
    log = kit._logged(log, {"radius.md": "9"}, {"radius.md": "10"}, "you", "Rounded", 200.0)
    assert len(log) == 2


def test_ago_reads_like_a_person():
    assert kit.ago(1000.0, 1005.0) == "just now"
    assert kit.ago(0.0, 3 * 86400.0) == "3 days ago"


def test_variants_are_six_and_differ():
    vs = logo.variants(specs.merged({}))
    assert len(vs) == 6
    assert all(v["mark.from"] != specs.DEFAULTS["mark.from"] for v in vs[:4])


def test_a_release_plans_every_file_once():
    names = [f["name"] for f in job.plan(specs.merged({}))]
    assert len(names) == len(set(names))
    assert {"tokens.css", "tokens.json", "favicon.ico", "nu-square-1024.png"} <= set(names)


def test_release_files_are_what_they_say():
    from PIL import Image

    sp = specs.merged({"radius.md": "8"})
    plan = {f["name"]: f for f in job.plan(sp)}
    tokens = json.loads(job.make(sp, plan["tokens.json"]))
    assert tokens["dusk"]["afterglow"] == "#8946db" and tokens["radius"]["md"] == "8"
    assert b"--r-md:8px" in job.make(sp, plan["tokens.css"])
    assert job.make(sp, plan["nu-square.svg"]).startswith(b"<svg")
    png = Image.open(io.BytesIO(job.make(sp, plan["nu-square-32.png"])))
    assert png.size == (32, 32) and png.mode == "RGBA"
    assert b"radius.md" in job.make(sp, plan["CHANGES.md"])
