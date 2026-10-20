"""The html documents design cells draw, each built from the spec. Plain Python, no Nu.

Every document is whole: its own fonts (embedded, a frame reaches nothing
outside it), its tokens as CSS variables, then its body. Nothing in a body
names a hex: it reaches for ``var(--afterglow)``, ``var(--r-md)``,
``var(--dur-fast)``, so one edit to the spec moves every drawing that uses
the token, the way the kit's components do.

``mode`` picks the theme a document is drawn in: ``dusk``, ``dawn``, or
``auto``, which follows the viewer's system (a frame cannot see the shell's
own theme switch). Some documents draw both themes side by side whatever
the mode.
"""

from __future__ import annotations

from html import escape

from . import checks, color, fonts, logo
from .spec import COLORS, SCALARS, THEMES, num, theme


__all__ = [
    "app",
    "board",
    "contrast_sheet",
    "elevation",
    "gallery",
    "glance",
    "hero",
    "motion",
    "page",
    "palette",
    "proposal",
    "readme",
    "social",
    "space",
    "specimen",
    "tile",
]


FACES = (
    "@font-face{font-family:Inter;src:url(data:font/woff2;base64,"
    + fonts.INTER
    + ") format('woff2');font-weight:400 600}"
    "@font-face{font-family:'JetBrains Mono';src:url(data:font/woff2;base64,"
    + fonts.MONO
    + ") format('woff2')}"
)


def _vars(spec: dict[str, str], name: str) -> str:
    """One theme's colors and every scalar token, as CSS variables."""
    th = theme(spec, name)
    out = [f"--{k}:{v}" for k, v in th.items()]
    out.append(f"--scheme:{'dark' if name == 'dusk' else 'light'}")
    shadows = {
        "dusk": (
            "inset 0 1px 0 rgba(255,255,255,.03),0 1px 2px rgba(0,0,0,.3)",
            "inset 0 1px 0 rgba(255,255,255,.05),0 2px 4px rgba(0,0,0,.24),0 8px 20px rgba(0,0,0,.3)",
            "inset 0 1px 0 rgba(255,255,255,.05),0 8px 16px rgba(0,0,0,.26),0 24px 56px rgba(0,0,0,.34)",
        ),
        "dawn": (
            "0 1px 1px rgba(26,29,36,.04),0 1px 3px rgba(26,29,36,.06)",
            "0 2px 4px rgba(26,29,36,.05),0 6px 16px rgba(26,29,36,.08)",
            "0 4px 8px rgba(26,29,36,.05),0 20px 48px rgba(26,29,36,.12)",
        ),
    }[name]
    out += [f"--sh-raised:{shadows[0]}", f"--sh-floating:{shadows[1]}", f"--sh-modal:{shadows[2]}"]
    return ";".join(out)


def _scalars(spec: dict[str, str]) -> str:
    out = [
        f"--font-sans:'{spec['type.sans']}',Inter,ui-sans-serif,system-ui,sans-serif",
        f"--font-mono:'{spec['type.mono']}','JetBrains Mono',ui-monospace,monospace",
    ]
    for step in ("xs", "sm", "base", "lg", "xl", "2xl", "3xl", "display", "hero"):
        out.append(f"--fs-{step}:{num(spec, f'type.{step}'):g}px")
    out.append(f"--fw-title:{num(spec, 'type.title-weight'):g}")
    out.append(f"--tr-display:{num(spec, 'type.tracking'):g}em")
    u = num(spec, "space.unit")
    out.append(f"--u:{u:g}px")
    for k in (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24):
        out.append(f"--s{k}:{u * k:g}px")
    out.append(f"--control:{num(spec, 'space.control'):g}px")
    for r in ("sm", "md", "lg", "xl"):
        out.append(f"--r-{r}:{num(spec, f'radius.{r}'):g}px")
    for m in ("fast", "base", "slow"):
        out.append(f"--dur-{m}:{num(spec, f'motion.{m}'):g}ms")
    for e in ("ease-out", "ease-in", "ease-in-out"):
        out.append(f"--{e}:cubic-bezier({spec[f'motion.{e}']})")
    return ";".join(out)


def tokens_css(spec: dict[str, str], mode: str) -> str:
    """The spec as CSS custom properties: scalars on ``:root``, colors per ``mode``."""
    scal = f":root{{{_scalars(spec)}}}"
    if mode in THEMES:
        return scal + f":root{{{_vars(spec, mode)}}}"
    return (
        scal
        + f":root{{{_vars(spec, 'dawn')}}}@media (prefers-color-scheme: dark){{:root{{{_vars(spec, 'dusk')}}}}}"
    )


BASE = """
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--ground);color:var(--ink-1);font-family:var(--font-sans);font-size:var(--fs-base);line-height:1.5;
  -webkit-font-smoothing:antialiased;color-scheme:var(--scheme)}
code,.mono{font-family:var(--font-mono);font-variant-ligatures:none}
.k{font-size:var(--fs-xs);font-weight:500;letter-spacing:.04em;text-transform:uppercase;color:var(--ink-3)}
.muted{color:var(--ink-2)}.quiet{color:var(--ink-3)}
.t-dusk{background:var(--ground)}
"""


def page(
    spec: dict[str, str],
    body: str,
    *,
    mode: str = "auto",
    css: str = "",
    pad: int = 20,
    glyph: bool = False,
) -> str:
    """A whole document around ``body``, the spec's tokens as variables, in ``mode``."""
    defs = logo.glyph_defs() if glyph else ""
    return (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        + FACES
        + tokens_css(spec, mode)
        + BASE
        + f"body{{padding:{pad}px}}"
        + css
        + f"</style></head><body>{defs}{body}</body></html>"
    )


def scoped(spec: dict[str, str], name: str, inner: str, cls: str = "") -> str:
    """``inner`` drawn in one theme whatever the document's mode."""
    return f'<div class="themed {cls}" style="{_vars(spec, name)};background:var(--ground);color:var(--ink-1)">{inner}</div>'


def _img(
    spec: dict[str, str], name: str, size: int, *, small: bool = False, css: str = "", uid: str = ""
) -> str:
    """One mark inline, pointing at the document's one glyph (``page(glyph=True)``)."""
    svg = logo.asset(spec, name, small=small, shared=True, uid=uid)
    attrs = f'width="{size}" height="{size}" role="img" aria-label="Nu {name}" style="display:block;flex:none;{css}"'
    return svg.replace("<svg ", f"<svg {attrs} ", 1)


def _lockup(spec: dict[str, str], height: int, uid: str = "lk") -> str:
    svg = logo.lockup(spec, "var(--ink-1)", shared=True, uid=uid)
    return svg.replace(
        "<svg ", f'<svg height="{height}" width="{height * 300 / 64:.0f}" style="display:block" ', 1
    )


# --- the kit, drawn from tokens --------------------------------------------------------------


KIT = """
.btn{display:inline-flex;align-items:center;gap:var(--s2);height:var(--control);padding:0 var(--s3);border-radius:var(--r-md);
  font:500 var(--fs-lg)/1 var(--font-sans);border:1px solid transparent;cursor:pointer;white-space:nowrap;
  transition:background var(--dur-fast) var(--ease-out),box-shadow var(--dur-fast) var(--ease-out),transform var(--dur-fast) var(--ease-out)}
.btn.primary{background:var(--afterglow);color:var(--on-afterglow);border-color:var(--afterglow-ring,var(--afterglow-pressed))}
.btn.primary:hover,.btn.primary.hov{background:var(--afterglow-hover)}.btn.primary:active,.btn.primary.prs{background:var(--afterglow-pressed)}
.btn.secondary{background:var(--ground-overlay);color:var(--ink-1);border-color:var(--line);box-shadow:var(--sh-raised)}
.btn.secondary:hover,.btn.secondary.hov{background:var(--ground-hover)}
.btn.ghost{background:transparent;color:var(--ink-1)}.btn.ghost:hover,.btn.ghost.hov{background:var(--hover)}
.btn.danger{background:var(--ember-solid);color:#fff}
.btn.sm{height:calc(var(--control) - 8px);font-size:var(--fs-sm);padding:0 var(--s2)}
.btn.icon{width:var(--control);padding:0;justify-content:center}
.btn:focus-visible,.btn.foc{outline:2px solid var(--afterglow-focus);outline-offset:2px}
.btn.off{opacity:.45;cursor:default}
.input{white-space:nowrap;overflow:hidden;height:var(--control);border-radius:var(--r-md);border:1px solid var(--line-strong);background:var(--ground-overlay);
  color:var(--ink-1);padding:0 var(--s3);font:400 var(--fs-lg)/1 var(--font-sans);display:flex;align-items:center;min-width:0;
  transition:box-shadow var(--dur-fast) var(--ease-out),border-color var(--dur-fast) var(--ease-out)}
.input.ph{color:var(--ink-4)}.input.foc{border-color:var(--afterglow-focus);box-shadow:0 0 0 3px color-mix(in srgb,var(--afterglow-focus) 30%,transparent)}
.input.bad{border-color:var(--ember)}.err{color:var(--ember);font-size:var(--fs-sm);margin-top:var(--s1)}
.lab{font-size:var(--fs-sm);font-weight:500;color:var(--ink-2);margin-bottom:var(--s1)}
.sw{width:34px;height:20px;border-radius:999px;background:var(--line-strong);position:relative;flex:none;transition:background var(--dur-fast) var(--ease-out)}
.sw::after{content:"";position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:#fff;
  box-shadow:0 1px 2px rgba(0,0,0,.25);transition:transform var(--dur-fast) var(--ease-out)}
.sw.on{background:var(--afterglow)}.sw.on::after{transform:translateX(14px)}
.cb{width:16px;height:16px;border-radius:var(--r-sm);border:1px solid var(--line-strong);background:var(--ground-overlay);flex:none;
  display:grid;place-items:center;color:#fff;font-size:11px;line-height:1}
.cb.on{background:var(--afterglow);border-color:var(--afterglow)}.rd{border-radius:50%}.rd.on{background:var(--ground-overlay);box-shadow:inset 0 0 0 4px var(--afterglow);border-color:var(--afterglow)}
.slider{position:relative;height:16px;display:flex;align-items:center}.slider .tr{height:4px;border-radius:2px;background:var(--line);width:100%}
.slider .fl{position:absolute;left:0;height:4px;border-radius:2px;background:var(--afterglow)}
.slider .th{position:absolute;width:16px;height:16px;border-radius:50%;background:#fff;border:1px solid var(--line-strong);box-shadow:var(--sh-raised);margin-left:-8px}
.seg{display:inline-flex;padding:2px;border-radius:var(--r-md);background:var(--ground-deep);border:1px solid var(--line-subtle)}
.seg span{padding:4px var(--s3);border-radius:var(--r-sm);font-size:var(--fs-sm);font-weight:500;color:var(--ink-2)}
.seg span.on{background:var(--ground-overlay);color:var(--ink-1);box-shadow:var(--sh-raised)}
.tabs{display:flex;gap:var(--s4);border-bottom:1px solid var(--line-subtle)}.tabs span{padding:var(--s2) 0;font-weight:500;color:var(--ink-3);font-size:var(--fs-lg)}
.tabs span.on{color:var(--ink-1);box-shadow:inset 0 -2px 0 var(--afterglow-line)}
.badge{display:inline-flex;align-items:center;gap:4px;height:20px;padding:0 var(--s2);border-radius:var(--r-sm);font-size:var(--fs-xs);font-weight:500;
  background:var(--afterglow-soft);color:var(--afterglow-text)}
.badge.info{background:var(--starlight-soft);color:var(--starlight)}.badge.ok{background:var(--aurora-soft);color:var(--aurora)}
.badge.warn{background:var(--sunset-soft);color:var(--sunset)}.badge.bad{background:var(--ember-soft);color:var(--ember)}
.badge.note{background:var(--moonlight-soft);color:var(--moonlight)}.badge.plain{background:var(--hover);color:var(--ink-2)}
.dot{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block}
.call{border-radius:var(--r-lg);padding:var(--s3) var(--s4);font-size:var(--fs-base);border:1px solid}
.call b{font-weight:600;margin-right:6px}
.call.ok{background:var(--aurora-soft);color:var(--aurora);border-color:color-mix(in srgb,var(--aurora) 35%,transparent)}
.call.warn{background:var(--sunset-soft);color:var(--sunset);border-color:color-mix(in srgb,var(--sunset) 35%,transparent)}
.call.bad{background:var(--ember-soft);color:var(--ember);border-color:color-mix(in srgb,var(--ember) 35%,transparent)}
.call.note{background:var(--moonlight-soft);color:var(--moonlight);border-color:color-mix(in srgb,var(--moonlight) 35%,transparent)}
.card{background:var(--ground-card);border:1px solid var(--line);border-radius:var(--r-lg)}
.raised{background:var(--ground-overlay);border:1px solid var(--line);border-radius:var(--r-lg);box-shadow:var(--sh-raised)}
.floating{background:var(--ground-overlay);border:1px solid var(--line);border-radius:var(--r-md);box-shadow:var(--sh-floating)}
.modal{background:var(--ground-overlay);border:1px solid var(--line);border-radius:var(--r-lg);box-shadow:var(--sh-modal)}
.menu{padding:4px;min-width:180px}.menu div{padding:6px var(--s2);border-radius:var(--r-sm);display:flex;justify-content:space-between;font-size:var(--fs-base)}
.menu div.on{background:var(--hover)}.menu kbd{font-family:var(--font-mono);font-size:var(--fs-xs);color:var(--ink-3)}
.menu hr{border:0;border-top:1px solid var(--line-subtle);margin:4px 0}.menu .bad{color:var(--ember)}
.tip{display:inline-block;background:var(--ink-1);color:var(--ground);font-size:var(--fs-sm);padding:4px var(--s2);border-radius:var(--r-sm)}
.prog{height:6px;border-radius:3px;background:var(--hover);overflow:hidden}.prog i{display:block;height:100%;background:var(--starlight);border-radius:3px}
.tbl{width:100%;border-collapse:collapse;font-size:var(--fs-base)}.tbl th{text-align:left;font-weight:500;color:var(--ink-3);font-size:var(--fs-sm);padding:6px var(--s3);border-bottom:1px solid var(--line)}
.tbl td{padding:7px var(--s3);border-bottom:1px solid var(--line-subtle)}.tbl tr.sel td{background:var(--press)}.tbl tr:hover td{background:var(--hover)}
.tbl .num{font-family:var(--font-mono);text-align:right}
.stat .v{font-size:var(--fs-3xl);font-weight:var(--fw-title);letter-spacing:-.01em}.stat .d{font-size:var(--fs-sm)}
.up{color:var(--aurora)}.down{color:var(--ember)}
.ring{outline:2px solid var(--afterglow-focus);outline-offset:2px}
.live{display:inline-flex;align-items:center;gap:6px;color:var(--starlight);font-size:var(--fs-sm);font-weight:500}
.live .dot{animation:pulse 1.6s var(--ease-in-out) infinite}
@keyframes pulse{50%{opacity:.35}}
"""


def _bars(vals: list[float], slots: list[str], w: int = 260, h: int = 120) -> str:
    n = len(vals)
    bw = w / n * 0.62
    top = max(vals)
    bars = "".join(
        f'<rect x="{i * w / n + (w / n - bw) / 2:.1f}" y="{h - v / top * (h - 8):.1f}" width="{bw:.1f}" '
        f'height="{v / top * (h - 8):.1f}" rx="2" fill="var(--{slots[i % len(slots)]})"/>'
        for i, v in enumerate(vals)
    )
    grid = "".join(
        f'<line x1="0" x2="{w}" y1="{y}" y2="{y}" stroke="var(--line-subtle)"/>'
        for y in (h * 0.25, h * 0.5, h * 0.75)
    )
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none">{grid}{bars}<line x1="0" x2="{w}" y1="{h}" y2="{h}" stroke="var(--line)"/></svg>'


def _lines(series: list[list[float]], slots: list[str], w: int = 260, h: int = 120) -> str:
    top = max(max(s) for s in series)
    low = min(min(s) for s in series)
    out = []
    for s, slot in zip(series, slots, strict=False):
        pts = " ".join(
            f"{i * w / (len(s) - 1):.1f},{h - 6 - (v - low) / (top - low) * (h - 14):.1f}"
            for i, v in enumerate(s)
        )
        out.append(
            f'<polyline points="{pts}" fill="none" stroke="var(--{slot})" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        )
    grid = "".join(
        f'<line x1="0" x2="{w}" y1="{y}" y2="{y}" stroke="var(--line-subtle)"/>'
        for y in (h * 0.25, h * 0.5, h * 0.75)
    )
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none">{grid}{"".join(out)}</svg>'


#: Families of the gallery, in order.
FAMILIES = ("actions", "inputs", "navigation", "feedback", "data", "surfaces")


def _family(name: str, spec: dict[str, str]) -> str:
    if name == "actions":
        return """
<div class="row"><button class="btn primary">Run cell</button><button class="btn secondary">Duplicate</button>
<button class="btn ghost">Cancel</button><button class="btn danger">Delete plane</button></div>
<div class="row"><button class="btn primary hov">Hover</button><button class="btn primary prs">Pressed</button>
<button class="btn primary foc">Focused</button><button class="btn primary off">Disabled</button></div>
<div class="row"><button class="btn secondary sm">Small</button><button class="btn ghost sm">&#8943; More</button>
<button class="btn secondary icon" aria-label="add">+</button><button class="btn ghost icon" aria-label="close">&#215;</button></div>"""
    if name == "inputs":
        return """
<div class="cols">
 <div><div class="lab">Plane name</div><div class="input">Quarterly review</div></div>
 <div><div class="lab">Search</div><div class="input ph">Find a cell, a plane, a token</div></div>
 <div><div class="lab">Endpoint</div><div class="input foc">api.helio-labs.dev/v2</div></div>
 <div><div class="lab">Batch size</div><div class="input bad">-12</div><div class="err">Must be 1 or more.</div></div>
</div>
<div class="row" style="gap:28px">
 <label class="row tight"><span class="sw on"></span>Live sync</label><label class="row tight"><span class="sw"></span>Compact</label>
 <label class="row tight"><span class="cb on">&#10003;</span>Pinned</label><label class="row tight"><span class="cb"></span>Archived</label>
 <label class="row tight"><span class="cb rd on"></span>Dusk</label><label class="row tight"><span class="cb rd"></span>Dawn</label>
</div>
<div class="row" style="gap:28px"><div style="flex:1"><div class="lab">Learning rate</div><div class="slider"><div class="tr"></div>
<div class="fl" style="width:38%"></div><div class="th" style="left:38%"></div></div></div>
<div><div class="lab">View</div><div class="seg"><span>List</span><span class="on">Board</span><span>Timeline</span></div></div></div>"""
    if name == "navigation":
        return """
<div class="tabs"><span class="on">Overview</span><span>Runs</span><span>Checkpoints</span><span>Settings</span></div>
<div class="cols" style="grid-template-columns:200px 1fr;gap:20px">
 <div class="side"><div class="si on">&#9670; Design</div><div class="si">&#9671; Tokens</div><div class="si sub">Color</div><div class="si sub">Type</div><div class="si">&#9671; Components</div><div class="si">&#9671; Mocks</div></div>
 <div><div class="crumbs">Design <span>/</span> Tokens <span>/</span> <b>Color</b></div>
 <div class="row" style="margin-top:16px"><span class="pg">&#8249;</span><span class="pg on">1</span><span class="pg">2</span><span class="pg">3</span><span class="pg">&#8250;</span></div>
 <div class="row" style="margin-top:14px"><span class="kbdl">Search</span><kbd class="kb">Ctrl</kbd><kbd class="kb">K</kbd></div></div>
</div>"""
    if name == "feedback":
        return """
<div class="row"><span class="badge">Draft</span><span class="badge info">Live</span><span class="badge ok"><i class="dot"></i>Passing</span>
<span class="badge warn">Under target</span><span class="badge bad">Failing</span><span class="badge note">Note</span><span class="badge plain">v1.4.0</span></div>
<div class="stack">
<div class="call ok"><b>Release cut.</b>Thirty files written, every check passing.</div>
<div class="call warn"><b>Careful.</b>ink-3 on ground-deep sits at 4.6, just over the bar.</div>
<div class="call bad"><b>Fails.</b>White on the new Afterglow reads 3.9, under 4.5.</div>
<div class="call note"><b>Note.</b>Chart slots are their own set: a blue in a chart is not Starlight.</div></div>
<div class="row" style="gap:20px;align-items:center"><div style="flex:1"><div class="lab">Exporting assets</div><div class="prog"><i style="width:64%"></i></div></div>
<span class="tip">Copied to clipboard</span><span class="live"><i class="dot"></i>Syncing</span></div>"""
    if name == "data":
        from .job import plan

        summ = checks.summary(spec)
        ratios = sorted(float(r[t]) for r in checks.run(spec)["pairs"] for t in THEMES)
        files = len(plan(spec))
        rows = (
            ("tokens", "78", "+4", "up"),
            ("contrast pairs", "52", "0", ""),
            ("components", "31", "+2", "up"),
            ("open proposals", "3", "-1", "down"),
        )
        body = "".join(
            f'<tr{" class=sel" if i == 1 else ""}><td>{a}</td><td class="num">{b}</td><td class="num {c3}">{c}</td></tr>'
            for i, (a, b, c, c3) in enumerate(rows)
        )
        return f"""
<div class="cols" style="grid-template-columns:repeat(3,1fr)">
 <div class="card stat" style="padding:14px 16px"><div class="k">Checks passing</div><div class="v">{summ["pass"] + summ["under"]} / {summ["total"]}</div><div class="d {"down" if summ["fail"] else "up"}">{summ["fail"]} failing</div></div>
 <div class="card stat" style="padding:14px 16px"><div class="k">Median contrast</div><div class="v">{ratios[len(ratios) // 2]:.1f}</div><div class="d quiet">dusk and dawn</div></div>
 <div class="card stat" style="padding:14px 16px"><div class="k">Assets per release</div><div class="v">{files}</div><div class="d quiet">svg, png, ico, css</div></div>
</div>
<div class="cols" style="grid-template-columns:1.1fr 1fr 1fr">
 <div class="card" style="padding:4px 0"><table class="tbl"><tr><th>what</th><th class="num">count</th><th class="num">change</th></tr>{body}</table></div>
 <div class="card" style="padding:14px"><div class="k" style="margin-bottom:8px">Cells run per day</div>{_bars([12, 18, 15, 24, 31, 27, 36], ["chart-1"])}</div>
 <div class="card" style="padding:14px"><div class="k" style="margin-bottom:8px">Three series, in slot order</div>
 {_lines([[3, 4, 3.6, 5, 5.4, 6.2, 7], [2, 2.6, 3.1, 2.8, 3.6, 4.1, 4.6], [1, 1.4, 1.2, 2.2, 2.0, 2.6, 3.4]], ["chart-1", "chart-2", "chart-3"])}</div>
</div>"""
    return """
<div class="cols" style="grid-template-columns:repeat(4,1fr);align-items:start">
 <div class="card" style="padding:14px"><div class="k">0 flat</div><div class="muted" style="margin-top:6px">Cards and panels in a document.</div></div>
 <div class="raised" style="padding:14px"><div class="k">1 raised</div><div class="muted" style="margin-top:6px">Elevated cards, a thumb.</div></div>
 <div class="floating menu"><div class="on">Open beside <kbd>Ctrl Enter</kbd></div><div>Rename <kbd>F2</kbd></div><div>Duplicate</div><hr><div class="bad">Delete</div></div>
 <div class="scrimbox"><div class="modal" style="padding:16px"><div style="font-weight:var(--fw-title)">Delete this plane?</div>
 <div class="muted" style="margin:6px 0 14px;font-size:var(--fs-sm)">Its cells and their state go with it.</div>
 <div class="row" style="justify-content:flex-end"><button class="btn ghost sm">Cancel</button><button class="btn danger sm">Delete</button></div></div></div>
</div>"""


GALLERY = """
.fam{display:grid;grid-template-columns:120px 1fr;gap:20px;padding:18px 0;border-top:1px solid var(--line-subtle)}
.fam:first-child{border-top:0;padding-top:4px}.fam h3{margin:6px 0 0;font-size:var(--fs-sm);font-weight:600;color:var(--ink-2);text-transform:capitalize}
.body{display:flex;flex-direction:column;gap:14px;min-width:0}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.row.tight{gap:8px;flex-wrap:nowrap;font-size:var(--fs-base)}
.cols{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.stack{display:flex;flex-direction:column;gap:8px}
.side{background:var(--ground-deep);border-radius:var(--r-lg);padding:6px;border:1px solid var(--line-subtle)}
.si{padding:5px 8px;border-radius:var(--r-sm);color:var(--ink-2);font-size:var(--fs-base)}.si.on{background:var(--press);color:var(--ink-1);font-weight:500}.si.sub{padding-left:26px;color:var(--ink-3)}
.crumbs{color:var(--ink-3);font-size:var(--fs-base)}.crumbs span{margin:0 6px;color:var(--ink-4)}.crumbs b{color:var(--ink-1);font-weight:500}
.pg{min-width:28px;height:28px;border-radius:var(--r-md);display:grid;place-items:center;color:var(--ink-2);font-size:var(--fs-sm)}.pg.on{background:var(--press);color:var(--ink-1);font-weight:500}
.kb{font-family:var(--font-mono);font-size:var(--fs-xs);border:1px solid var(--line);border-bottom-width:2px;border-radius:var(--r-sm);padding:1px 6px;color:var(--ink-2);background:var(--ground-card)}
.kbdl{color:var(--ink-3);font-size:var(--fs-sm);margin-right:2px}
.scrimbox{background:color-mix(in srgb,var(--ground-deep) 70%,transparent);border-radius:var(--r-lg);padding:14px;border:1px dashed var(--line)}
"""


def gallery(
    spec: dict[str, str], families: tuple[str, ...] = FAMILIES, *, mode: str = "auto"
) -> str:
    """The kit's controls in families, drawn from the spec's tokens."""
    body = "".join(
        f'<section class="fam"><h3>{f}</h3><div class="body">{_family(f, spec)}</div></section>'
        for f in families
    )
    return page(spec, body, mode=mode, css=KIT + GALLERY, pad=22)


# --- the palette -----------------------------------------------------------------------------


PALETTE = """
.two{display:grid;grid-template-columns:1fr 1fr;gap:0}.themed{padding:20px 22px}
.grp{margin-bottom:18px}.grp:last-child{margin-bottom:0}.grp .k{margin-bottom:8px}
.chips{display:grid;grid-template-columns:repeat(auto-fill,minmax(92px,1fr));gap:8px}
.chip .s{height:44px;border-radius:var(--r-md);border:1px solid var(--line-subtle);display:flex;align-items:flex-end;padding:4px 6px;font-size:10px;font-weight:600}
.chip .n{font-size:11px;font-weight:500;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chip .h{font-size:10.5px;color:var(--ink-3);font-family:var(--font-mono)}
.chip.ch .s{outline:2px solid var(--afterglow-focus);outline-offset:1px}
.head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:14px}
.head b{font-size:var(--fs-xl);font-weight:var(--fw-title)}
"""


def _chips(spec: dict[str, str], name: str, groups: tuple[str, ...], changed: set[str]) -> str:
    th = theme(spec, name)
    out = []
    for g in groups:
        chips = []
        for grp, tok, *_ in COLORS:
            if grp != g:
                continue
            ratio = color.contrast(th["ink-1"], th[tok])
            label = "Aa" if ratio >= 4.5 else ""
            ink = th["ink-1"] if ratio >= 4.5 else "#ffffff"
            cls = "chip ch" if f"{name}:{tok}" in changed else "chip"
            chips.append(
                f'<div class="{cls}"><div class="s" style="background:{th[tok]};color:{ink}">{label}</div>'
                f'<div class="n">{tok}</div><div class="h">{th[tok]}</div></div>'
            )
        out.append(
            f'<div class="grp"><div class="k">{g}</div><div class="chips">{"".join(chips)}</div></div>'
        )
    return "".join(out)


def palette(
    spec: dict[str, str],
    changed: set[str],
    groups: tuple[str, ...] = ("ground", "line", "ink", "afterglow", "starlight", "state", "chart"),
) -> str:
    """Every color, Dusk beside Dawn. Tokens changed from the language get a ring."""
    sides = "".join(
        scoped(
            spec,
            t,
            f'<div class="head"><b>{t.title()}</b><span class="quiet">{"dark" if t == "dusk" else "light"}</span></div>'
            + _chips(spec, t, groups, changed),
        )
        for t in THEMES
    )
    return page(spec, f'<div class="two">{sides}</div>', css=PALETTE, pad=0)


# --- type, space, motion -----------------------------------------------------------------------


SPEC_CSS = """
.two{display:grid;grid-template-columns:1fr 1fr}.themed{padding:22px 26px}
.step{display:grid;grid-template-columns:86px 1fr;gap:16px;align-items:baseline;padding:10px 0;border-bottom:1px solid var(--line-subtle)}
.step:last-child{border-bottom:0}.step .m{font-family:var(--font-mono);font-size:11px;color:var(--ink-3);line-height:1.4}
.step .m b{color:var(--ink-2);font-weight:500;display:block;font-family:var(--font-sans);font-size:12px}
.sample{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.voices{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}
.voice{border:1px solid var(--line);border-radius:var(--r-lg);padding:14px 16px;background:var(--ground-card)}
.voice .big{font-size:40px;letter-spacing:-.02em;line-height:1.1;margin:6px 0}
pre{margin:8px 0 0;font-family:var(--font-mono);font-size:12.5px;line-height:1.6;color:var(--ink-2)}
.kw{color:var(--afterglow-text)}.st{color:var(--aurora)}.fn{color:var(--starlight)}.cm{color:var(--ink-3)}.ty{color:var(--sunset)}
"""

_TYPE = (
    ("hero", "Computational space", 600),
    ("display", "Everything is connected", 600),
    ("3xl", "One spec, every surface", 600),
    ("2xl", "Afterglow is us acting in the sky", 600),
    ("xl", "Reading breathes. Tools are dense, pages are not.", 400),
    ("lg", "Run cell  ·  Open beside  ·  Duplicate", 500),
    ("base", "Default app text sits at thirteen pixels, neutral tracking.", 400),
    ("sm", "Secondary text, dense table cells, metadata", 400),
    ("xs", "MICRO LABEL  ·  BADGE  ·  11PX FLOOR", 500),
)


def specimen(spec: dict[str, str], *, mode: str = "auto") -> str:
    """The type ladder, each step set at its size, then the two voices."""
    steps = []
    for step, text, weight in _TYPE:
        px = num(spec, f"type.{step}")
        w = num(spec, "type.title-weight") if weight == 600 else weight
        tr = num(spec, "type.tracking") if px >= 32 else (0.01 if px <= 12 else 0)
        steps.append(
            f'<div class="step"><div class="m"><b>{step}</b>{px:g}px · {w:g}</div>'
            f'<div class="sample" style="font-size:{px:g}px;font-weight:{w:g};letter-spacing:{tr:g}em;line-height:1.15">{escape(text)}</div></div>'
        )
    code = (
        '<span class="kw">def</span> <span class="fn">out</span>(plane):\n'
        '    <span class="cm"># the spec, read live, drawn in Afterglow</span>\n'
        '    <span class="kw">return</span> on_system(plane, <span class="kw">lambda</span> base: '
        'swatch.set(<span class="st">"afterglow"</span>))'
    )
    voices = (
        f'<div class="voices"><div class="voice"><div class="k">words · {escape(spec["type.sans"])}</div>'
        f'<div class="big" style="font-weight:var(--fw-title)">Aa Gg Rr 0123</div><div class="muted">Plain letters that get out of the way. 400 to read, 500 for controls, 600 for titles.</div></div>'
        f'<div class="voice"><div class="k">code · {escape(spec["type.mono"])}</div><pre>{code}</pre></div></div>'
    )
    return page(spec, "".join(steps) + voices, mode=mode, css=SPEC_CSS, pad=22)


SPACE_CSS = """
.ladder{display:flex;flex-direction:column;gap:6px}.lad{display:grid;grid-template-columns:40px 1fr 60px;gap:12px;align-items:center;font-size:12px}
.lad i{display:block;height:12px;background:var(--starlight-soft);border:1px solid color-mix(in srgb,var(--starlight) 45%,transparent);border-radius:2px}
.lad .m{font-family:var(--font-mono);color:var(--ink-3);text-align:right}.lad.bad i{background:var(--ember-soft);border-color:var(--ember)}
.radii{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-top:6px}
.rad{height:84px;border:1.5px solid var(--line-strong);background:var(--ground-card);display:flex;align-items:flex-end;padding:8px;font-size:12px;color:var(--ink-2)}
.cols2{display:grid;grid-template-columns:1fr 1.25fr;gap:32px}h4{margin:0 0 12px;font-size:12px;font-weight:600;color:var(--ink-2)}
.grid4{background-image:linear-gradient(var(--line-subtle) 1px,transparent 1px),linear-gradient(90deg,var(--line-subtle) 1px,transparent 1px);
  background-size:var(--u) var(--u);border-radius:var(--r-lg);border:1px solid var(--line);padding:calc(var(--u)*4);margin-top:18px}
.grid4 .card{padding:calc(var(--u)*3) calc(var(--u)*4);display:flex;gap:calc(var(--u)*3);align-items:center}
"""


def space(spec: dict[str, str], *, mode: str = "auto") -> str:
    """The spacing ladder on the grid, the radii, a card laid on the grid."""
    unit = num(spec, "space.unit")
    steps = checks.grid(spec)
    top = max(steps)
    ladder = "".join(
        f'<div class="lad{" bad" if s % 4 else ""}"><span class="quiet">{k}</span><i style="width:{s / top * 100:.1f}%"></i><span class="m">{s}px</span></div>'
        for k, s in zip((1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24), steps, strict=False)
    )
    radii = "".join(
        f'<div class="rad" style="border-radius:{r}">{n}<br>{v}</div>'
        for n, r, v in (
            ("none", "0", "0px"),
            ("sm", "var(--r-sm)", f"{num(spec, 'radius.sm'):g}px"),
            ("md", "var(--r-md)", f"{num(spec, 'radius.md'):g}px"),
            ("lg", "var(--r-lg)", f"{num(spec, 'radius.lg'):g}px"),
            ("xl", "var(--r-xl)", f"{num(spec, 'radius.xl'):g}px"),
        )
    )
    card = (
        '<div class="grid4"><div class="card"><button class="btn primary">Run</button><div><div style="font-weight:500">Laid on the grid</div>'
        f'<div class="quiet" style="font-size:12px">padding {unit * 3:g} and {unit * 4:g}, gap {unit * 3:g}, all in units of {unit:g}</div></div></div></div>'
    )
    body = (
        f'<div class="cols2"><div><h4>Spacing, in units of {unit:g}px</h4><div class="ladder">{ladder}</div></div>'
        f'<div><h4>Radius</h4><div class="radii">{radii}</div>{card}</div></div>'
    )
    return page(spec, body, mode=mode, css=KIT + SPACE_CSS, pad=22)


ELEV_CSS = """
.two{display:grid;grid-template-columns:1fr 1fr}.themed{padding:26px 24px}
.lv{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.lv>div{height:96px;padding:12px;font-size:12px}
.lv b{display:block;font-weight:600;font-size:13px;margin-bottom:2px}
"""


def elevation(spec: dict[str, str]) -> str:
    """The four levels, Dusk beside Dawn."""
    cells = (
        '<div class="lv"><div class="card"><b>0 flat</b><span class="quiet">ground-card, line</span></div>'
        '<div class="raised"><b>1 raised</b><span class="quiet">overlay, raised</span></div>'
        '<div class="floating"><b>2 floating</b><span class="quiet">menus, popovers</span></div>'
        '<div class="modal"><b>3 modal</b><span class="quiet">dialogs, sheets</span></div></div>'
    )
    sides = "".join(scoped(spec, t, cells) for t in THEMES)
    return page(spec, f'<div class="two">{sides}</div>', css=KIT + ELEV_CSS, pad=0)


MOTION_CSS = """
.stage{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.box{background:var(--ground-card);border:1px solid var(--line);border-radius:var(--r-lg);height:200px;position:relative;overflow:hidden;padding:12px}
.box .k{position:absolute;left:12px;bottom:10px}
.cap{position:absolute;right:12px;bottom:10px;font-family:var(--font-mono);font-size:11px;color:var(--ink-3)}
.m1{position:absolute;left:50%;top:44%;margin:-10px 0 0 -17px;transform:scale(1.4)}
.m1 .sw::after{animation:thumb 2.4s infinite}.m1 .sw{animation:fill 2.4s infinite}
@keyframes thumb{0%,40%{transform:translateX(0);animation-timing-function:var(--ease-out)}50%,90%{transform:translateX(14px);animation-timing-function:var(--ease-out)}100%{transform:translateX(0)}}
@keyframes fill{0%,40%{background:var(--line-strong)}50%,90%{background:var(--afterglow)}100%{background:var(--line-strong)}}
.m2{position:absolute;left:24px;top:22px}.m2 .floating{position:absolute;top:40px;left:0;transform-origin:top left;animation:menu 2.4s infinite}
@keyframes menu{0%,15%{opacity:0;transform:translateY(4px)}25%,75%{opacity:1;transform:none}85%,100%{opacity:0;transform:translateY(4px)}}
.scrim{position:absolute;inset:0;background:color-mix(in srgb,var(--ground-deep) 70%,transparent);animation:scrim 3s infinite}
.m3 .modal{position:absolute;left:50%;top:50%;width:70%;margin-left:-35%;margin-top:-44px;padding:14px;animation:dlg 3s infinite}
@keyframes scrim{0%,10%{opacity:0}30%,75%{opacity:1}90%,100%{opacity:0}}
@keyframes dlg{0%,10%{opacity:0;transform:scale(.98)}30%,75%{opacity:1;transform:none}90%,100%{opacity:0;transform:scale(.98)}}
"""


def motion(spec: dict[str, str], *, mode: str = "auto") -> str:
    """Three live loops, each at its step's duration and the spec's easing."""
    fast, base, slow = (num(spec, f"motion.{m}") for m in ("fast", "base", "slow"))

    body = f"""
<div class="stage">
 <div class="box"><div class="m1"><span class="sw"></span></div><div class="k">fast · switch</div><div class="cap">{fast:g}ms</div></div>
 <div class="box"><div class="m2"><button class="btn secondary sm">Actions &#9662;</button>
  <div class="floating menu"><div class="on">Open beside</div><div>Rename</div><div>Duplicate</div></div></div>
  <div class="k">base · menu</div><div class="cap">{base:g}ms</div></div>
 <div class="box m3"><div class="scrim"></div><div class="modal"><b style="font-weight:var(--fw-title)">Cut release v1.5.0?</b>
  <div class="quiet" style="font-size:12px;margin-top:4px">Forty files from the spec as it stands.</div></div>
  <div class="k">slow · dialog</div><div class="cap">{slow:g}ms</div></div>
</div>"""
    # The share of each loop a move takes is its duration over the loop's length.
    timing = (
        f".m1 .sw::after,.m1 .sw{{animation-duration:{fast * 20 / 1000:.2f}s}}"
        f".m2 .floating{{animation-duration:{base * 13.3 / 1000:.2f}s;animation-timing-function:var(--ease-out)}}"
        f".scrim,.m3 .modal{{animation-duration:{slow * 10.7 / 1000:.2f}s;animation-timing-function:var(--ease-in-out)}}"
    )
    return page(spec, body, mode=mode, css=KIT + MOTION_CSS + timing, pad=18)


# --- the mark ----------------------------------------------------------------------------------


BOARD = """
.ground{padding:26px 26px 20px}.label{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3);margin-bottom:16px}
.row{display:flex;flex-wrap:wrap;align-items:flex-end;gap:26px}.ladder{margin-top:26px;gap:20px}
figure{margin:0;display:flex;flex-direction:column;align-items:center;gap:8px}figcaption{font-size:11px;color:var(--ink-3)}
.lock{margin-top:24px;display:flex;align-items:center;gap:40px}
"""


def board(spec: dict[str, str]) -> str:
    """Every asset large on both grounds, the square down the size ladder, the lockup."""

    def ground(name: str) -> str:
        big = "".join(
            f"<figure>{_img(spec, n, 150)}<figcaption>{n}</figcaption></figure>"
            for n in logo.ASSETS
        )
        ladder = "".join(
            f"<figure>{_img(spec, 'square', s, small=s <= logo.SMALL)}<figcaption>{s}</figcaption></figure>"
            for s in (16, 24, 32, 48, 64, 96, 128)
        )
        inner = (
            f'<div class="ground"><div class="label">on {name}</div><div class="row">{big}</div>'
            f'<div class="row ladder">{ladder}</div><div class="lock">{_lockup(spec, 40, uid=name)}</div></div>'
        )
        return scoped(spec, name, inner)

    return page(spec, ground("dusk") + ground("dawn"), css=BOARD, pad=0, glyph=True)


def tile(spec: dict[str, str], ground: dict[str, str], *, mode: str = "auto") -> str:
    """One variant: the square mark on a ground of its own, small enough for a grid."""
    v = {**spec, **ground}
    body = f'<div style="display:flex;justify-content:center">{_img(v, "square", 104, uid=ground.get("name", ""))}</div>'
    return page(
        spec, body, mode=mode, css="body{background:var(--ground-card)}", pad=14, glyph=True
    )


# --- mocks ---------------------------------------------------------------------------------------


HERO_CSS = """
header{display:flex;justify-content:space-between;align-items:center;padding:16px 32px;border-bottom:1px solid var(--line-subtle)}
nav{display:flex;gap:24px;font-size:var(--fs-lg);color:var(--ink-2);align-items:center}nav .gh{color:var(--ink-1)}
main{max-width:920px;margin:0 auto;padding:58px 32px 0;text-align:center}
.eyebrow{display:inline-flex;gap:8px;align-items:center;font-size:var(--fs-sm);font-weight:500;color:var(--ink-2);
  border:1px solid var(--line);border-radius:999px;padding:4px 12px 4px 6px;background:var(--ground-card)}
.eyebrow .badge{height:18px}
h1{font-size:var(--fs-hero);line-height:1.04;letter-spacing:var(--tr-display);margin:20px auto 18px;max-width:780px;font-weight:var(--fw-title)}
h1 span{color:var(--ink-twilight)}
.lede{color:var(--ink-2);font-size:var(--fs-xl);max-width:560px;margin:0 auto;line-height:1.55}
.actions{display:flex;gap:12px;justify-content:center;margin-top:28px}.actions .btn{height:40px;padding:0 18px}
.cmd{font-family:var(--font-mono);font-size:var(--fs-base)}
.win{margin:52px auto 0;border-radius:var(--r-xl) var(--r-xl) 0 0;background:var(--ground-raised);border:1px solid var(--line);border-bottom:0;
  box-shadow:var(--sh-modal);text-align:left;overflow:hidden;display:grid;grid-template-columns:170px 1fr;height:220px}
.win aside{background:var(--ground-deep);border-right:1px solid var(--line-subtle);padding:12px 8px}
.win aside div{height:22px;border-radius:var(--r-sm);display:flex;align-items:center;padding:0 8px;font-size:12px;color:var(--ink-2)}
.win aside .on{background:var(--press);color:var(--ink-1)}
.doc{padding:18px 22px}.doc h2{margin:0 0 12px;font-size:var(--fs-2xl);font-weight:var(--fw-title)}
.cells{display:grid;grid-template-columns:1.2fr 1fr;gap:12px}.cellm{border:1px solid var(--line);border-radius:var(--r-lg);background:var(--ground-card);padding:10px 12px;height:116px}
"""


def hero(spec: dict[str, str], *, mode: str = "auto") -> str:
    """The nustack.dev landing's first screen, drawn from the spec."""
    body = f"""
<header>{_lockup(spec, 26)}<nav><a>nuspace</a><a>docs</a><a>blog</a><a class="gh">GitHub</a>
<button class="btn primary sm">Get started</button></nav></header>
<main>
 <span class="eyebrow"><span class="badge info">new</span>nuspace 0.5: spaces that build their own pages</span>
 <h1>Computational space <span>for everything you work with.</span></h1>
 <p class="lede">Notes, data, tools and agents as connected cells: living programs that hold data, logic and look in one form.</p>
 <div class="actions"><button class="btn primary">Get started</button><button class="btn secondary cmd">pip install nuspace</button></div>
 <div class="win"><aside><div class="on">&#9670; Design</div><div>&#9671; Tokens</div><div>&#9671; Components</div><div>&#9671; Mocks</div><div>&#9671; Export</div></aside>
 <div class="doc"><h2>Design</h2><div class="cells">
  <div class="cellm"><div class="k">checks</div><div style="margin-top:8px">{_bars([7, 9, 8, 12, 11, 14, 15, 13], ["chart-1"], h=70)}</div></div>
  <div class="cellm"><div class="k">live</div><div class="live" style="margin-top:10px"><i class="dot"></i>3 proposals arrived</div>
   <div class="prog" style="margin-top:14px"><i style="width:72%"></i></div><div class="quiet" style="font-size:11px;margin-top:6px">exporting v1.5.0</div></div>
 </div></div></div>
</main>"""
    return page(spec, body, mode=mode, css=KIT + HERO_CSS, pad=0, glyph=True)


APP_CSS = """
.app{display:grid;grid-template-columns:220px 1fr;height:470px;border:1px solid var(--line);border-radius:var(--r-xl);overflow:hidden}
.sb{background:var(--ground-deep);border-right:1px solid var(--line-subtle);padding:12px 8px;display:flex;flex-direction:column;gap:2px}
.brand{display:flex;align-items:center;gap:8px;font-weight:600;font-size:12px;letter-spacing:.08em;padding:4px 8px 12px}.brand b{color:var(--afterglow-text)}
.search{height:28px;border-radius:var(--r-md);background:var(--hover);display:flex;align-items:center;justify-content:space-between;padding:0 8px;color:var(--ink-3);font-size:12px;margin-bottom:8px}
.it{height:28px;border-radius:var(--r-md);display:flex;align-items:center;gap:8px;padding:0 8px;color:var(--ink-2);font-size:var(--fs-base)}
.it.on{background:var(--press);color:var(--ink-1);font-weight:500}.it.sub{padding-left:26px}
.it i{width:14px;height:14px;border-radius:4px;background:var(--line-strong);display:inline-block}.it.on i{background:var(--afterglow-text)}
.main{background:var(--ground-raised);display:flex;flex-direction:column}
.top{height:38px;border-bottom:1px solid var(--line-subtle);display:flex;align-items:center;justify-content:space-between;padding:0 16px;font-size:12px;color:var(--ink-3)}
.pagebody{padding:20px 28px;overflow:hidden}.pagebody h1{margin:0 0 4px;font-size:var(--fs-3xl);font-weight:var(--fw-title);letter-spacing:-.01em}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0}
.cellbox{border:1px solid var(--line);border-radius:var(--r-lg);background:var(--ground-card);padding:12px 14px}
.split{display:grid;grid-template-columns:1.3fr 1fr;gap:10px}
"""


def app(spec: dict[str, str], *, mode: str = "auto") -> str:
    """A nuspace screen: sidebar on ground-deep, the document on ground-raised, cells in the kit."""
    stats = "".join(
        f'<div class="cellbox stat"><div class="k">{k}</div><div class="v" style="font-size:var(--fs-2xl)">{v}</div><div class="d {c}">{d}</div></div>'
        for k, v, d, c in (
            ("runs", "128", "+12 today", "up"),
            ("best test", "99.1%", "run 37", "quiet"),
            ("models", "41", "2 training", "quiet"),
            ("failed", "3", "-2 this week", "up"),
        )
    )
    rows = "".join(
        f'<tr{" class=sel" if i == 0 else ""}><td>{n}</td><td><span class="badge {b}">{s}</span></td><td class="num">{a}</td></tr>'
        for i, (n, b, s, a) in enumerate(
            (
                ("adam-0.001", "info", "training", "98.7"),
                ("sweep-b", "ok", "done", "99.1"),
                ("sgd-wide", "ok", "done", "97.9"),
                ("tiny-8ch", "bad", "stopped", "91.2"),
            )
        )
    )
    body = f"""
<div class="app"><div class="sb"><div class="brand">{_img(spec, "square", 18, small=True)}<span><b>NU</b>SPACE</span></div>
<div class="search">Search<span class="kb">Ctrl K</span></div>
<div class="it"><i></i>Home</div><div class="it on"><i></i>MNIST</div><div class="it sub"><i></i>Launch</div><div class="it sub"><i></i>Compare</div>
<div class="it"><i></i>Design</div><div class="it"><i></i>Movies</div><div class="it"><i></i>Agents</div></div>
<div class="main"><div class="top"><span>MNIST</span><span class="live"><i class="dot"></i>2 runs live</span></div>
<div class="pagebody"><h1>MNIST</h1><div class="quiet">A small CNN learns to read digits, every run tracked live.</div>
<div class="grid">{stats}</div>
<div class="split"><div class="cellbox" style="padding:4px 0"><table class="tbl"><tr><th>run</th><th>status</th><th class="num">test %</th></tr>{rows}</table></div>
<div class="cellbox"><div class="k" style="margin-bottom:8px">test accuracy</div>{_lines([[60, 82, 90, 94, 96, 97.2, 98, 98.7], [55, 78, 88, 93, 95.5, 97.5, 98.6, 99.1], [40, 61, 74, 82, 87, 89, 90.4, 91.2]], ["chart-1", "chart-2", "chart-3"], h=118)}</div></div>
</div></div></div>"""
    return page(spec, body, mode=mode, css=KIT + GALLERY + APP_CSS, pad=14, glyph=True)


SOCIAL_CSS = """
.og{width:1200px;height:630px;transform-origin:top left;position:relative;overflow:hidden;background:var(--ground);border-radius:16px;border:1px solid var(--line-subtle)}
.og .dots{position:absolute;inset:0;background-image:radial-gradient(var(--line) 1.4px,transparent 1.4px);background-size:28px 28px;opacity:.7;
  -webkit-mask-image:linear-gradient(115deg,transparent 30%,#000 75%)}
.og .in{position:absolute;left:84px;top:84px;right:84px;bottom:84px;display:flex;flex-direction:column;justify-content:space-between}
.og h2{font-size:76px;line-height:1.02;letter-spacing:-.025em;margin:0;font-weight:var(--fw-title);max-width:880px}.og h2 span{color:var(--ink-twilight)}
.og .foot{display:flex;justify-content:space-between;align-items:flex-end;font-size:24px;color:var(--ink-2)}
.og .url{font-family:var(--font-mono);font-size:22px;color:var(--ink-3)}
.og .tag{position:absolute;right:84px;top:84px}
.scale{zoom:.34}.pair{display:grid;grid-template-columns:repeat(2,max-content);gap:16px;justify-content:center}
"""


def social(spec: dict[str, str]) -> str:
    """The 1200x630 card, Dusk and Dawn, shown at half size."""

    def card(name: str) -> str:
        inner = (
            f'<div class="og"><div class="dots"></div><div class="tag">{_img(spec, "square", 120, uid="og" + name)}</div>'
            f'<div class="in"><div>{_lockup(spec, 44, uid="ogl" + name)}</div>'
            "<h2>A space that runs <span>everything you work with.</span></h2>"
            '<div class="foot"><span>Notes, data, tools and agents as live cells.</span><span class="url">nustack.dev</span></div></div></div>'
        )
        return f'<div class="scale">{scoped(spec, name, inner, "og-wrap")}</div>'

    css = SOCIAL_CSS + ".og-wrap{background:transparent!important}"
    return page(
        spec, f'<div class="pair">{card("dusk")}{card("dawn")}</div>', css=css, pad=16, glyph=True
    )


README_CSS = """
.rm{border-radius:var(--r-xl);border:1px solid var(--line);overflow:hidden;margin-bottom:14px}
.rm .ban{height:150px;display:flex;align-items:center;justify-content:space-between;padding:0 40px;position:relative;
  background:linear-gradient(90deg,var(--ground) 40%,color-mix(in srgb,var(--afterglow) 16%,var(--ground)))}
.rm .tl{font-size:var(--fs-xl);color:var(--ink-2);margin-top:8px}
.rm .shields{display:flex;gap:6px;padding:12px 40px;border-top:1px solid var(--line-subtle);background:var(--ground-raised)}
.sh{display:inline-flex;font:500 11px/20px var(--font-sans);border-radius:var(--r-sm);overflow:hidden}.sh span{padding:0 7px;background:var(--line-strong);color:var(--ink-1)}
.sh b{padding:0 7px;font-weight:500;color:#fff}
"""


def readme(spec: dict[str, str]) -> str:
    """The README header, both themes, as GitHub shows one or the other."""

    def ban(name: str) -> str:
        th = theme(spec, name)
        shields = "".join(
            f'<span class="sh"><span>{a}</span><b style="background:{c}">{b}</b></span>'
            for a, b, c in (
                ("pypi", "v0.5.5", th["afterglow"]),
                ("python", "3.10+", th["starlight-soft"] if name == "dusk" else th["starlight"]),
                ("license", "Apache-2.0", th["aurora"] if name == "dawn" else "#1f613c"),
                ("discord", "join", th["chart-7"]),
            )
        )
        inner = (
            f'<div class="rm"><div class="ban"><div>{_lockup(spec, 46, uid="rm" + name)}<div class="tl">Computational space for everything you work with.</div></div>'
            f'{_img(spec, "square", 92, uid="rq" + name)}</div><div class="shields">{shields}</div></div>'
        )
        return scoped(spec, name, inner, "rmw")

    return page(
        spec, ban("dusk") + ban("dawn"), css=README_CSS + ".rmw{padding:0}", pad=16, glyph=True
    )


# --- the system at a glance, checks ----------------------------------------------------------------


GLANCE_CSS = """
.gl{display:grid;grid-template-columns:1.05fr 1fr 1fr;gap:0;border-radius:var(--r-xl);overflow:hidden;border:1px solid var(--line)}
.gl>div{padding:22px 24px;min-height:228px}.gl .k{margin-bottom:10px}
.markcell{display:flex;flex-direction:column;justify-content:space-between}
.strip{display:flex;height:34px;border-radius:var(--r-md);overflow:hidden;margin-bottom:8px}.strip i{flex:1}
.aa{font-size:46px;font-weight:var(--fw-title);letter-spacing:var(--tr-display);line-height:1}.aa span{color:var(--ink-twilight)}
.mini{display:flex;gap:8px;align-items:center;margin-top:14px;flex-wrap:wrap}
"""


def glance(spec: dict[str, str], *, mode: str = "auto") -> str:
    """The system in one frame: the mark, the sky and its lights, the voice, the controls."""
    d, n = theme(spec, "dusk"), theme(spec, "dawn")
    sky = "".join(
        f'<i style="background:{d[t]}"></i>'
        for t in (
            "ground-deep",
            "ground",
            "ground-raised",
            "ground-card",
            "ground-overlay",
            "line-strong",
            "ink-3",
            "ink-1",
        )
    )
    day = "".join(
        f'<i style="background:{n[t]}"></i>'
        for t in (
            "ink-1",
            "ink-3",
            "line-strong",
            "line",
            "ground-hover",
            "ground-deep",
            "ground",
            "ground-card",
        )
    )
    lights = "".join(
        f'<i style="background:{d[t]}"></i>'
        for t in (
            "afterglow",
            "afterglow-text",
            "starlight",
            "aurora",
            "sunset",
            "ember",
            "moonlight",
        )
    )
    body = f"""
<div class="gl">
 <div class="markcell" style="background:var(--ground-card)"><div class="k">the mark</div>
  <div style="display:flex;gap:18px;align-items:center">{_img(spec, "square", 104)}{_img(spec, "circle", 64, uid="c")}{_img(spec, "text-only", 52, uid="t")}</div>
  {_lockup(spec, 30)}</div>
 <div><div class="k">the sky and its lights</div><div class="strip">{sky}</div><div class="strip">{day}</div><div class="strip">{lights}</div></div>
 <div style="background:var(--ground-card)"><div class="k">the voice</div><div class="aa">Aa <span>Gg</span></div>
  <div class="quiet" style="margin-top:6px">{escape(spec["type.sans"])} for words, <code>{escape(spec["type.mono"])}</code> for code</div>
  <div class="mini"><button class="btn primary sm">Accept</button><button class="btn secondary sm">Decline</button><span class="badge ok">passing</span><span class="sw on"></span></div></div>
</div>"""
    return page(spec, body, mode=mode, css=KIT + GLANCE_CSS, pad=0, glyph=True)


SHEET_CSS = """
.themed{padding:18px 20px}
.sheet{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.pr{border-radius:var(--r-md);padding:9px 11px;display:flex;justify-content:space-between;align-items:center;border:1px solid var(--line-subtle);gap:8px}
.pr .t{font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pr .w{font-size:10.5px;opacity:.8}
.pr .r{font-family:var(--font-mono);font-size:12px;flex:none;padding:1px 6px;border-radius:var(--r-sm);background:rgba(127,127,127,.14)}
.pr.fail{outline:2px solid var(--ember);outline-offset:1px}.pr.under{outline:1px dashed var(--sunset);outline-offset:1px}
.head{display:flex;justify-content:space-between;margin-bottom:12px}.head b{font-size:var(--fs-xl);font-weight:var(--fw-title)}
"""


def contrast_sheet(spec: dict[str, str]) -> str:
    """Every pair set as itself, Dusk beside Dawn: a word on its ground, the ratio, a ring when it falls short."""
    rows = checks.run(spec)["pairs"]

    def side(name: str) -> str:
        cells = []
        fails = 0
        for r in rows:
            ratio = float(r[name])
            low = float(r["min"])
            state = "fail" if ratio < low else ("under" if ratio < float(r["target"]) else "")
            fails += state == "fail"
            cells.append(
                f'<div class="pr {state}" style="background:{r[f"{name}_bg"]};color:{r[f"{name}_fg"]}">'
                f'<div style="min-width:0"><div class="t">{escape(str(r["what"]))}</div><div class="w">{escape(str(r["pair"]))}</div></div>'
                f'<span class="r">{ratio:.2f}</span></div>'
            )
        verdict = "every pair reads" if not fails else f"{fails} under the bar"
        inner = f'<div class="head"><b>{name.title()}</b><span class="quiet">{verdict}</span></div><div class="sheet">{"".join(cells)}</div>'
        return scoped(spec, name, inner)

    return page(spec, side("dusk") + side("dawn"), css=SHEET_CSS, pad=0)


PROPOSAL_CSS = """
.diff{display:flex;flex-direction:column;gap:8px}
.dr{display:grid;grid-template-columns:150px 150px 24px 1fr;gap:10px;align-items:center;font-size:12px}
.dr .sw2{display:flex;align-items:center;gap:8px;font-family:var(--font-mono)}.dr .sw2 i{width:28px;height:20px;border-radius:var(--r-sm);border:1px solid var(--line)}
.dr .arrow{color:var(--ink-4);text-align:center}.dr .key{font-family:var(--font-mono);color:var(--ink-2)}
.ab{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:16px}.ab .k{margin-bottom:6px}
.prev{border:1px solid var(--line);border-radius:var(--r-lg);padding:16px;background:var(--ground)}
.prev h3{margin:0 0 6px;font-size:22px;letter-spacing:-.01em;font-weight:var(--fw-title)}.prev h3 span{color:var(--ink-twilight)}
.prev .row{display:flex;gap:8px;margin-top:12px;align-items:center}
.ver{margin-top:14px;display:flex;flex-direction:column;gap:6px}
"""


def proposal(spec: dict[str, str], prop: dict, *, mode: str = "auto") -> str:
    """A teammate's proposal: what it changes, before and after, and what the checks say about it."""
    if not prop:
        return page(
            spec,
            '<div class="quiet">Nothing open. Proposals from the team land here as they come in.</div>',
            mode=mode,
            pad=18,
        )
    changes = dict(prop.get("changes") or {})
    after = {**spec, **changes}
    diff = []
    for k, v in changes.items():
        old = spec.get(k, "")
        if color.is_hex(old) and color.is_hex(v):
            a, b = (
                f'<span class="sw2"><i style="background:{old}"></i>{old}</span>',
                f'<span class="sw2"><i style="background:{v}"></i>{v}</span>',
            )
        else:
            a, b = (
                f'<span class="sw2">{escape(old)}</span>',
                f'<span class="sw2">{escape(v)}</span>',
            )
        diff.append(
            f'<div class="dr"><span class="key">{escape(k)}</span>{a}<span class="arrow">&#8594;</span>{b}</div>'
        )
    before_rows = {r["key"]: r for r in checks.run(spec)["pairs"] + checks.run(spec)["rules"]}
    after_res = checks.run(after)
    notes = []
    for r in after_res["pairs"] + after_res["rules"]:
        was = before_rows.get(r["key"], {}).get("verdict")
        if r["verdict"] != was:
            cls = {"pass": "ok", "under target": "warn", "fail": "bad"}[str(r["verdict"])]
            where = (
                f"{r.get('dusk', '')} / {r.get('dawn', '')}"
                if "dusk" in r
                else str(r.get("seen", ""))
            )
            notes.append(
                f'<div class="call {cls}"><b>{escape(str(r["verdict"]).title())}.</b>{escape(str(r.get("pair", r["key"])))}, now {escape(where)}</div>'
            )
    if not notes:
        notes.append('<div class="call ok"><b>Clean.</b>Every check stays where it was.</div>')

    def preview(sp: dict[str, str], label: str) -> str:
        inner = (
            f'<div class="k">{label}</div><div class="prev"><h3>One spec, <span>every surface.</span></h3>'
            '<div class="quiet">Tokens drawn into the kit, live.</div>'
            '<div class="row"><button class="btn primary sm">Accept</button><button class="btn secondary sm">Later</button>'
            '<span class="badge">draft</span><span class="badge info">live</span><span class="sw on"></span></div></div>'
        )
        return f'<div style="{_scalars(sp)};{_vars(sp, mode if mode in THEMES else "dusk")};color:var(--ink-1)">{inner}</div>'

    body = (
        f'<div class="diff">{"".join(diff)}</div>'
        f'<div class="ab">{preview(spec, "now")}{preview(after, "with the proposal")}</div>'
        f'<div class="ver">{"".join(notes)}</div>'
    )
    return page(spec, body, mode=mode, css=KIT + PROPOSAL_CSS, pad=18)


def scalars_doc(spec: dict[str, str]) -> list[tuple[str, str, str]]:
    """Every scalar token as ``(group, key, value)``, for the export's token files."""
    return [(g, k, spec[k]) for g, k, _, _ in SCALARS]
