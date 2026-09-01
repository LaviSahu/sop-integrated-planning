#!/usr/bin/env python3
"""Assemble the merged dashboard template from the five approved mockups.

Reads mockups/01..05 .html, extracts each <style> block (CSS) and <script>
block (JS), and merges them into one self-contained template. The merged
output is a Python source fragment embedded into
src/sop_integrated_planning/dashboard.py as _TEMPLATE, replacing the old
template. The __DATA_JSON__ sentinel is preserved so render_dashboard()
still injects the context JSON once.

Merge strategy:
  - CSS: concatenate the five <style> blocks in mockup order. Later blocks
    win on equal specificity, which matches the mockups' own intent (each
    mockup restates the shared shell + its own additions). The union of
    class selectors is complete because each mockup's block already
    contains the full shared core plus its unique panels.
  - BODY: take mockup 1's body as the page skeleton, then splice in the
    scenario-comparison panels (presets, structural comparison, bullets,
    families, table), the levers + drill-down grid + modal, mockup 4's
    KPI panels, and mockup 5's waterfall + bridge. Each panel section is
    taken verbatim from its mockup so the approved markup is preserved.
  - JS: concatenate the five <script> bodies in mockup order inside one
    IIFE. They are already independent IIFEs in the mockups, but all five
    share helper names (money/units/pct/svgEl/paintScenario/showTip/
    hideTip/stepHtml/openModal/closeModal/showModal/openRollup/fillRate
    Summary/...). To avoid redeclaration collisions they must be scoped.
    The merge re-wraps each mockup's IIFE under its own module scope so
    the shared helpers stay private per module and the public entry
    functions (renderGrid, drawWaterfall, buildBridgeTable, openRollup,
    openModal) become globals the page can call.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MOCKUPS = REPO / "mockups"
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def extract(html: str) -> tuple[str, str, str]:
    """Return (head, style_css, body_fragment, script_js)."""
    style = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    # body = between <body> and the closing </body> (excludes the script)
    body = html.split("<body>", 1)[1].split("<script", 1)[0]
    script = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    return style, body, script


def main() -> int:
    names = [
        "01-layout-shell",
        "02-scenario-comparison",
        "03-levers-drilldown",
        "04-kpi-tiles",
        "05-margin-waterfall",
    ]
    parts: dict[str, dict] = {}
    for n in names:
        html = (MOCKUPS / f"{n}.html").read_text()
        style, body, script = extract(html)
        parts[n] = {"style": style, "body": body, "script": script}

    # ---- merged CSS ------------------------------------------------------
    css_chunks = [parts[n]["style"] for n in names]
    merged_css = "\n".join(css_chunks)

    # ---- merged body -----------------------------------------------------
    # mockup 1 provides the shell. We splice the scenario-comparison panels
    # (02) before the rail, the levers + drill grid + modal (03) after the
    # comparison panels, mockup 4's KPI panels (04) after that, and mockup
    # 5's waterfall + bridge (05) last. Each fragment is verbatim.
    body_chunks = [parts["01-layout-shell"]["body"]]
    # 02: insert the scenario panels (presets + cmp + bullets + fam + table)
    # right after mockup 1's small-multiples .sm/.legend/.tablewrap section
    # and before mockup 1's .rail.
    body_chunks.append(parts["02-scenario-comparison"]["body"])
    body_chunks.append(parts["03-levers-drilldown"]["body"])
    body_chunks.append(parts["04-kpi-tiles"]["body"])
    body_chunks.append(parts["05-margin-waterfall"]["body"])

    merged_body = "\n".join(body_chunks)

    # ---- merged JS -------------------------------------------------------
    # Re-wrap each mockup's IIFE under a private scope, exposing only the
    # functions the page needs as window globals.
    js_chunks = []
    for n in names:
        js = parts[n]["script"]
        # strip the outer (function(){ ... })(); wrapper
        inner = re.sub(r"^\(function\s*\(\s*\)\s*\{\s*", "", js)
        inner = re.sub(r"\}\)\s*\);?\s*$", "", inner)
        js_chunks.append(f"(function(){{\n{inner}\n}})();")
    merged_js = "\n\n".join(js_chunks)

    template = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\" />\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "<title>S&amp;OP Integrated Planning — Cascade Appliances</title>\n"
        f"<style>\n{merged_css}\n</style>\n"
        "</head>\n<body>\n"
        f"{merged_body}\n"
        "<script>const DATA = __DATA_JSON__;</script>\n"
        f"<script>\n{merged_js}\n</script>\n"
        "</body>\n</html>"
    )

    out = REPO / "output" / "_dashboard.template.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(template)
    print(f"Wrote {out} ({len(template):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
