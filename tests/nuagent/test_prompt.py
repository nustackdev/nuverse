"""The opening prompt: section order, the task last, pieces in and out, the generated parts."""

from __future__ import annotations

import pytest

import nu
import nuskills
import nustd.kv
from nuagent import prompt
from nuagent.core import Run
from nuagent.prompt import NU, NUSPACE, TASK, Section, inserted, opening, replaced, sections
from nuagent.protocol import LABELS
from nuagent.protocol import prompt as protocol_text


TASK_TEXT = "Set `Notes.title` to 'hi', then end the run."


class Movie(nu.Shape):
    """A film on the shelf."""

    title = nu.StrRef.slot()


class Library(nu.Shape):
    """Everything the task is about."""

    nums = nu.ListRef.slot(int)
    shelf = nu.DictRef.slot(Movie)
    featured = nu.ShapeRef.slot(Movie)
    visits = nustd.kv.IntRef.slot()


def names(parts: tuple[Section, ...]) -> list[str]:
    return [s.name for s in parts]


# --- order -------------------------------------------------------------------


def test_the_default_is_protocol_then_the_nu_skill_then_the_catalogue():
    assert names(sections()) == ["protocol", *NU, "catalogue"]


def test_the_nu_pieces_are_the_ones_the_nu_skill_loads_up_front():
    assert NU == ("nu/thesis", "nu/crashcourse", "nu/composition", "nu/pitfalls", "nu/inspect")


def test_the_task_is_last_and_every_section_is_in_order():
    text = opening(TASK_TEXT)
    assert text.endswith(TASK + TASK_TEXT + "\n")
    at = [text.index(s.render()) for s in sections()]
    assert at == sorted(at)
    assert at[-1] < text.index(TASK + TASK_TEXT)


def test_the_protocol_is_there_whole_with_its_labels():
    text = opening(TASK_TEXT)
    assert protocol_text().strip() in text
    for label in LABELS.values():
        assert label in text


def test_each_piece_is_its_nuskills_text():
    text = opening(TASK_TEXT)
    for piece_id in NU:
        assert nuskills.read(piece_id).strip() in text


# --- pieces in and out --------------------------------------------------------


def test_add_appends_pieces_and_keeps_a_repeat_once():
    parts = sections(add=NUSPACE)
    assert "nu/crashcourse" in NUSPACE
    assert names(parts).count("nu/crashcourse") == 1
    assert names(parts) == ["protocol", *NU, "nuspace/model", "nuspace/brackets", "catalogue"]


def test_drop_leaves_a_piece_out():
    assert "nu/pitfalls" not in names(sections(drop=["nu/pitfalls"]))


def test_pieces_replaces_the_default_set():
    assert names(sections(["nu/crashcourse"])) == ["protocol", "nu/crashcourse", "catalogue"]


def test_an_unknown_piece_fails_where_the_prompt_is_put_together():
    with pytest.raises(KeyError):
        sections(add=["nu/nope"])


def test_sections_edit_by_name():
    parts = sections()
    note = Section("note", lambda: "A note.")
    assert names(inserted(parts, note, before="catalogue"))[-2:] == ["note", "catalogue"]
    assert names(inserted(parts, note, after="protocol"))[:2] == ["protocol", "note"]
    assert names(inserted(parts, note))[-1] == "note"
    swapped = replaced(parts, Section("protocol", lambda: "Reply in Nu."))
    assert opening("t", swapped).startswith("Reply in Nu.\n\n")
    assert names(prompt.without(parts, "catalogue", "nu/thesis")) == ["protocol", *NU[1:]]
    with pytest.raises(KeyError):
        inserted(parts, note, before="nope")


# --- catalogue ---------------------------------------------------------------


def test_the_catalogue_lists_the_flat_kernel_live():
    text = prompt.catalogue().render()
    lines = text.splitlines()
    assert lines[0] == "# Catalogue"
    listed = {line.split()[0] for line in lines if line.startswith("  ")}
    assert {"nu.ForEachDo", "nu.WhileDo", "nu.IntRef", "nu.Str", "nu.If", "nu.let"} <= listed
    assert len(listed) > 100


def test_the_catalogue_leaves_host_names_out():
    listed = {
        line.split()[0] for line in prompt.catalogue().render().splitlines() if line[:2] == "  "
    }
    assert not {"nu.run", "nu.arun", "nu.Command", "nu.ScalarQuery", "nu.Arg"} & listed


def test_the_catalogue_takes_a_fabric_the_run_binds():
    text = prompt.catalogue("nu", "nustd.kv").render()
    assert "## nustd.kv" in text
    assert "  nustd.kv.Snapshot " in text
    assert "## nustd.kv" in opening("t", sections(modules=["nu", "nustd.kv"]))
    assert "catalogue" not in names(sections(modules=()))


# --- surface -----------------------------------------------------------------


def test_the_surface_renders_each_shape_as_its_declaration():
    text = prompt.surface(Library, Movie, run=Run).render()
    assert text.startswith("# Your world")
    assert "## shape Library" in text
    assert "Everything the task is about." in text
    assert (
        "```python\n"
        "class Library(nu.Shape):\n"
        "    nums: nu.ListRef[int]\n"
        "    shelf: nu.DictRef[str, Movie]\n"
        "    featured: nu.ShapeRef[Movie]\n"
        "    visits: nustd.kv.IntRef\n"
        "```"
    ) in text
    assert "class Movie(nu.Shape):\n    title: nu.StrRef\n" in text
    assert text.rstrip().endswith("class Run(nu.Shape):\n    done: nu.BoolRef\n```")


def test_a_copied_declaration_builds_and_reaches_the_world():
    text = prompt.surface(Movie, Library).render()
    declared = "\n\n".join(b.removeprefix("python\n") for b in text.split("```")[1::2])
    source = (
        "import nu\nimport nustd.kv\n\n"
        + declared.replace("    visits: nustd.kv.IntRef\n", "")
        + "\n\ndef out():\n"
        "    return Library.nums.append(3) >> Library.featured.title.set('Dune')\n"
    )
    world = {"nums": [1]}
    term = nu.run(nu.LoadNu(source))[0]
    nu.run(term, nu.Context().bind(dict, world))
    assert world == {"nums": [1, 3], "featured": {"title": "Dune"}}


def test_the_surface_comes_after_the_catalogue_and_before_the_task():
    parts = sections(app=[Library])
    assert names(parts)[-2:] == ["catalogue", "surface"]
    text = opening(TASK_TEXT, parts)
    assert text.index("# Catalogue") < text.index("# Your world") < text.index(TASK)
    assert "## shape Run" in text


def test_the_surface_takes_a_module_and_lists_each_class_once():
    import sys

    here = sys.modules[__name__]
    text = prompt.surface(here, Movie).render()
    assert text.count("## shape Movie") == 1
    assert "## shape Library" in text


def test_the_surface_refuses_what_is_not_a_shape_or_service():
    with pytest.raises(TypeError):
        prompt.surface(42)
