"""Dashboard 'System in 3D' section: self-contained, reads only two read-only endpoints, names match the dependency map."""
import json
import re

from multiagent_copilot import api as api_mod
from multiagent_copilot.config import REPO_ROOT

HTML = api_mod._STATIC.read_text(encoding="utf-8")
DEP_MAP = json.loads((REPO_ROOT / "config" / "dependency_map.json").read_text(encoding="utf-8"))


def _between(start: str, end: str) -> str:
    i = HTML.index(start)
    return HTML[i:HTML.index(end, i) + len(end)]


SECTION = _between('<section class="card" id="sys3d"', "</section>")
SCRIPT = _between('<script id="s3js">', "</script>")
DATA = json.loads(_between('<script type="application/json" id="s3data">', "</script>")
                  .split(">", 1)[1].rsplit("</script>", 1)[0])


def test_section_exists_directly_under_the_header():
    assert "System in 3D" in SECTION and 'id="s3reset"' in SECTION and "Reset view" in SECTION
    after_header = HTML[HTML.index("</header>") + len("</header>"):].lstrip()
    assert after_header.startswith('<section class="card" id="sys3d"')


def test_no_external_urls_or_libraries():
    for block in (SECTION, SCRIPT, json.dumps(DATA)):
        assert not re.search(r"https?://|//cdn|<script[^>]+src=|<link[^>]+href=|@import|url\(", block)
    assert "<canvas" not in SECTION or "getContext" in SCRIPT     # CSS 3D, or a hand-written canvas, nothing else


def test_reads_only_status_and_latest_team_session():
    urls = set(re.findall(r'fetch\(\s*"([^"?]+)', SCRIPT))
    assert urls == {"/api/status", "/api/team/sessions/latest"}
    assert "fetch(" not in SCRIPT.replace('fetch("/api/status"', "").replace('fetch("/api/team/sessions/latest', "")
    assert not re.search(r"method\s*:|XMLHttpRequest|WebSocket|EventSource|sendBeacon", SCRIPT)   # read-only


def test_node_names_and_links_match_the_dependency_map():
    blueprint = [n for n in DEP_MAP["nodes"] if n != "multiagent-copilot"]
    assert len(blueprint) == 8 and sorted(DATA["nodes"]) == sorted(blueprint)
    edges = {tuple(sorted((e["from"], e["to"]))) for e in DEP_MAP["edges"]
             if e["from"] in blueprint and e["to"] in blueprint}
    assert {tuple(sorted(l)) for l in DATA["links"]} == edges and len(DATA["links"]) == len(edges)
    assert DATA["telemetry_path"] == DEP_MAP["telemetry_path"]


def test_shows_the_agent_pipeline_and_the_safety_layer():
    for name in ("Monitor", "Planner", "Human gate", "Safety Executor", "Analyst",
                 "Allowlist", "Kill switch", "Rollback", "Watchdog"):
        assert f'"{name}"' in SCRIPT
    assert "not recorded" in SCRIPT and "no live data" in SECTION + SCRIPT and "HTTP 200 but STALE" in SCRIPT


def test_respects_reduced_motion_and_both_colour_schemes():
    assert "prefers-reduced-motion" in SCRIPT and "prefers-reduced-motion" in HTML.split("</style>")[0]
    assert "prefers-color-scheme:dark" in HTML.split("</style>")[0]
    css = HTML.split("</style>")[0][HTML.index("System in 3D"):]
    assert not re.search(r"#[0-9a-fA-F]{6}\b", css.replace("#fff", ""))   # colours come from the theme variables


def test_api_down_stops_all_motion():
    down = SCRIPT[SCRIPT.index("function goDown"):SCRIPT.index("function applyStatus")]
    assert "p.flow=false" in down and "motion()" in down and '"no live data"' in down
