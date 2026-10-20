"""The design foundations, in the language's own words: what the system is for.

Embedded, not read from disk: the Principles page shows them as the nustack
design foundations put them (character, color, form, type, motion, and what
every surface inherits), trimmed of links to files a space can not reach.
"""

from __future__ import annotations


__all__ = ["DOCS"]


CHARACTER = """\
### Character

nustack builds a new foundation for computing. The brand should feel like that: a serious system from people at the frontier, that is still a pleasure to touch.

**What people should feel**

- **clarity**: they get it fast. one idea, said plainly
- **calm confidence**: no hype, no shouting. the work is the proof
- **precision**: everything deliberate. engineered, not decorated
- **aliveness**: things are live and connected
- **openness**: no magic, nothing hidden
- **craft**: modern and pleasant. somewhere you enjoy staying

**Who we are**

- **a system, not a showcase**: we feel like an instrument, not a brochure
- **small on purpose**: nothing without a reason
- **one idea everywhere**: connection, not ornament

**Not** hype, neon or glowing futurism. Not corporate gloss, not playful. Not cold or austere. Not busy.
"""

COLOR = """\
### Color

Few colors, each with one meaning. Color is identity, never decoration.

Our colors come from one sky. The sky is the ground, and it has two moments, one on each side of the night. Two lights live in it.

| Name | Role | In the sky |
| --- | --- | --- |
| **Dusk** | ground, dark | the sky after sunset |
| **Dawn** | ground, light | the first light before sunrise |
| **Afterglow Violet** | primary | the last light at the horizon |
| **Starlight Blue** | accent | the light of the stars |

The sky is the space. Afterglow is us acting in it. Starlight is the system answering.

- **Dusk and Dawn**: our grounds. Close to neutral with a faint blue lean, near black at dusk, near white at dawn. Calm and quiet, felt, not noticed.
- **Afterglow Violet**: intent, the spark, the human touch. Rare and decisive. If two things glow, one of them is wrong.
- **Starlight Blue**: clarity, information, light. The voice of the system. It shows, it never asks you to act.
- **Secondary**: Aurora good, Sunset careful, Ember wrong, Moonlight a note. Not brand colors: they serve function and stay quieter.
"""

FORM = """\
### Form

- **order**: everything sits on one rhythm. nothing is approximate
- **lines over boxes**: structure is drawn lightly
- **quiet depth**: things rest close to the ground. nothing floats far, nothing glows
- **soft geometry**: gentle, consistent, never sharp, never bubbly
- **density follows purpose**: tools are dense, reading breathes
"""

TYPE = """\
### Type

- **plain**: letters that get out of the way
- **two voices**: one for words, one for code
- **precise**: tight and even, never loose
- **quiet emphasis**: weight and color, never ornament
- **short**: say it once, plainly
"""

MOTION = """\
### Motion

- **calm**: felt, not seen. if you notice it, it is wrong
- **purposeful**: motion explains change, never performs
- **alive**: what is live moves because it is live
"""

INHERITANCE = """\
### Inheritance

Everything we make is nustack first, itself second.

- **fixed**: character, color meanings, form, voice, motion feel
- **tuned**: density, intensity, scale

A tool turns density up, a page turns it down, a small mark keeps only color. Each surface writes down what it tuned.
"""


#: ``(cell name, markdown)``, in the order the page shows them.
DOCS: tuple[tuple[str, str], ...] = (
    ("character", CHARACTER),
    ("color", COLOR),
    ("form", FORM),
    ("type", TYPE),
    ("motion", MOTION),
    ("inheritance", INHERITANCE),
)
