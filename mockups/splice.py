#!/usr/bin/env python3
"""Regenerate dashboard.py's _TEMPLATE from the canonical mockup pieces.

The dashboard is a single self-contained HTML file (SCOPE §2 row 2). Its
template lives as a raw triple-quoted string `_TEMPLATE` in
src/sop_integrated_planning/dashboard.py (line ~348) and embeds three
things verbatim:

  - <style>…</style>   <- mockups/dashboard.css
  - <body>…</body>     <- mockups/dashboard-body.html
  - the app <script>   <- mockups/engine-port.js + mockups/dashboard-app.js

`render_dashboard()` only substitutes the __DATA_JSON__ sentinel, so the
built output/dashboard.html is exactly the template with the data blob
injected. This script rewrites ONLY those three literal regions of
_TEMPLATE, preserving the __DATA_JSON__ sentinel and the outer shell
(head, title, meta). It is the reproducible build step that makes the
mockup files canonical and _TEMPLATE derived — edit the mockups, run
`python3 mockups/splice.py`, then `make dashboard`.

The app script is: engine-port.js (the JS engine port, with its CommonJS
guards stripped and window.LEVER_ENGINE exposed for the browser) followed
by dashboard-app.js. engine-port.js must load first because dashboard-app.js
references LEVER_ENGINE at lever-input time.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DASHBOARD_PY = REPO / "src" / "sop_integrated_planning" / "dashboard.py"

CSS = REPO / "mockups" / "dashboard.css"
BODY = REPO / "mockups" / "dashboard-body.html"
ENGINE_JS = REPO / "mockups" / "engine-port.js"
APP_JS = REPO / "mockups" / "dashboard-app.js"

_TEMPLATE_BEGIN = "_TEMPLATE = r\"\"\""


def strip_commonjs_guard(js: str) -> str:
    """Remove the Node module.exports wrapper so only the browser path runs.

    engine-port.js is wrapped in `(function (root, factory) { ... })(...)`
    so it works under both Node (golden gate) and the browser. In the
    browser we want the factory to run and set window.LEVER_ENGINE, but the
    top IIFE's `module`/`exports` guard is harmless there. We keep the whole
    thing as-is; the IIFE self-executes and sets LEVER_ENGINE on `self`.
    """
    return js


def splice() -> None:
    src = DASHBOARD_PY.read_text(encoding="utf-8")
    i = src.find(_TEMPLATE_BEGIN)
    if i == -1:
        raise SystemExit("_TEMPLATE not found in dashboard.py")

    css = CSS.read_text(encoding="utf-8")
    body = BODY.read_text(encoding="utf-8")
    engine_js = ENGINE_JS.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    # dashboard-app.js has a 9-line header comment; strip it to match the
    # existing embedded form (the original _TEMPLATE embeds the body only).
    app_body = app_js
    first_fn = app_js.find("(function () {")
    if first_fn != -1:
        app_body = app_js[first_fn:]

    # Locate the three regions within _TEMPLATE.
    style_start = src.find("<style>", i)
    style_end = src.find("</style>", style_start) + len("</style>")
    body_open = src.find("<body>", i) + len("<body>")
    script_const = src.find("<script>const DATA", i)
    # The app <script> block is the <script> that follows the const-DATA
    # script's </script>. It runs to the LAST \n})(); (the dashboard-app IIFE
    # close). We replace the ENTIRE span — any previously-spliced engine-port.js
    # + dashboard-app.js — with a fresh engine-port.js + dashboard-app.js, so
    # re-splicing an already-spliced file is idempotent. Keep the <script>
    # open tag; app content goes after it.
    const_data_close = src.find("</script>", script_const)
    app_open = src.find("<script>", const_data_close) + len("<script>")
    # Replace everything up to (and including) the app script's </script> so
    # trailing blank lines from a previous splice can't accumulate.
    app_close = src.find("</script>", app_open)
    app_end = app_close + len("</script>")

    # Build the new app script block: engine-port.js then dashboard-app.js.
    app_block = engine_js + "\n" + app_body

    # Reassemble: [head incl. old style open] [new css + close] [head tail
    # through <body>] [new body fragment] [script-const + app head]
    # [new app block] [old tail after app].
    new_src = (
        src[:style_start]
        + "<style>\n" + css + "\n</style>"
        + src[style_end:body_open]
        + "\n" + body + "\n"
        + src[script_const:app_open]
        + "\n" + app_block + "\n</script>"
        + src[app_end:]
    )

    DASHBOARD_PY.write_text(new_src, encoding="utf-8")
    print(f"Spliced {CSS.name} ({len(css):,} B), {BODY.name} ({len(body):,} B), "
          f"{ENGINE_JS.name}+{APP_JS.name} ({len(app_block):,} B) into _TEMPLATE")


if __name__ == "__main__":
    splice()
