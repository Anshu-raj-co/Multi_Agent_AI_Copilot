"""Generate the 8-slide hackathon submission deck (python-pptx).

    python scripts/make_official_ppt.py
    -> docs/submission/ResiliencePilot_Official_Submission.pptx

Every number on the slides comes from a committed document or run record (sources in each slide's speaker notes).
Bracketed values such as [YOUR_COLLEGE_NAME] are placeholders the team fills in before submitting.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt
from lxml import etree
import re
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "submission" / "ResiliencePilot_Official_Submission.pptx"
SHOTS = ROOT / "docs" / "scene" / "screenshots"
CANVAS = (380, 240, 1100, 620)  # the 3D view inside a 1440x900 twin screenshot
DEMO = ROOT / "docs" / "demo"

BG, CARD, BORDER = "0D131F", "162032", "26354D"
WHITE, MUTED, RED, CYAN = "FFFFFF", "A0AEC0", "E21A22", "00E5FF"
FONT, MONO = "Calibri", "Courier New"
SLIDE_W, LEFT, RIGHT = 13.333, 0.6, 12.733
TOTAL = 8


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


# ---------------------------------------------------------------- primitives

def text(slide, x, y, w, h, paras, *, anchor="top", name=None):
    """paras: list of str | dict(runs=[str | (str, opts)], size, color, bold, italic, align, after, bullet, font)."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        box.name = name
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}[anchor]
    for i, p in enumerate(paras):
        p = {"runs": [p]} if isinstance(p, str) else p
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}[p.get("align", "left")]
        para.space_after = Pt(p.get("after", 0))
        if p.get("line"):
            para.line_spacing = p["line"]
        if p.get("bullet"):
            pPr = para._p.get_or_add_pPr()
            pPr.set("marL", str(Inches(0.22)))
            pPr.set("indent", str(-Inches(0.22)))
            clr = etree.SubElement(pPr, qn("a:buClr"))
            etree.SubElement(clr, qn("a:srgbClr")).set("val", p.get("bullet_color", CYAN))
            etree.SubElement(pPr, qn("a:buFont")).set("typeface", "Arial")
            etree.SubElement(pPr, qn("a:buChar")).set("char", "•")
        for r in p["runs"]:
            r_text, ro = (r, {}) if isinstance(r, str) else r
            opt = {**p, **ro}
            run = para.add_run()
            run.text = r_text
            f = run.font
            f.name = opt.get("font", FONT)
            f.size = Pt(opt.get("size", 14))
            f.bold = opt.get("bold", False)
            f.italic = opt.get("italic", False)
            f.color.rgb = rgb(opt.get("color", MUTED))
            if opt.get("spacing"):
                run._r.get_or_add_rPr().set("spc", str(opt["spacing"]))
            if opt.get("link"):
                run.hyperlink.address = opt["link"]
    return box


def card(slide, x, y, w, h, *, fill=CARD, line=BORDER, line_w=1.0, name=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.adjustments[0] = min(0.5, 0.12 / min(w, h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(fill)
    if line:
        shp.line.color.rgb = rgb(line)
        shp.line.width = Pt(line_w)
    else:
        shp.line.fill.background()
    shp.shadow.inherit = False
    if name:
        shp.name = name
    return shp


def badge(slide, x, y, d, label, *, fill=CYAN, color=BG, size=14):
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(fill)
    shp.line.fill.background()
    shp.shadow.inherit = False
    tf = shp.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(size), True, rgb(color)
    return shp


def arrow(slide, x, y, w=0.22, h=0.2, color=CYAN):
    shp = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(color)
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def picture(slide, path: Path, x, y, w, h=None, *, crop_px=None, name=None):
    """Place an image in a w x h box, cropping (centre/top) to fill it. crop_px=(l, t, r, b) pre-selects a region.
    With h=None the box takes the (cropped) image's aspect ratio."""
    iw, ih = Image.open(path).size
    l, t, r, b = crop_px or (0, 0, iw, ih)
    cw, ch = r - l, b - t
    if h is None:
        h = w * ch / cw
    box_r, img_r = w / h, cw / ch
    if img_r > box_r:  # too wide: trim sides equally
        extra = cw - ch * box_r
        l, r = l + extra / 2, r - extra / 2
    else:  # too tall: keep the top
        b = t + cw / box_r
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
    pic.crop_left, pic.crop_top = l / iw, t / ih
    pic.crop_right, pic.crop_bottom = 1 - r / iw, 1 - b / ih
    pic.line.color.rgb = rgb(BORDER)
    pic.line.width = Pt(1)
    if name:
        pic.name = name
    return pic


def label(slide, x, y, w, s, color=CYAN, size=11):
    return text(slide, x, y, w, 0.25, [{"runs": [s.upper()], "size": size, "bold": True, "color": color, "spacing": 120}])


def frame(prs, section_no: int, kicker: str, title: str, notes: str):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(BG)
    if title:
        label(s, LEFT, 0.42, 10, f"Section {section_no} · {kicker}")
        text(s, LEFT, 0.68, RIGHT - LEFT, 0.62, [{"runs": [title], "size": 30, "bold": True, "color": WHITE}], name="Title")
    text(s, LEFT, 7.02, 8, 0.25, [{"runs": ["ResiliencePilot SDV · AI-Driven Chaos Engineering for Cloud-Native Resilience"],
                                     "size": 10, "color": MUTED}])
    text(s, RIGHT - 1.5, 7.02, 1.5, 0.25, [{"runs": [f"{section_no} / {TOTAL}"], "size": 10, "color": MUTED, "align": "right"}])
    s.notes_slide.notes_text_frame.text = notes
    return s


def card_header(slide, x, y, w, glyph, title, *, fill=CYAN, size=18):
    badge(slide, x, y, 0.42, glyph, fill=fill, color=BG if fill == CYAN else WHITE, size=14)
    text(slide, x + 0.58, y, w - 0.58, 0.42, [{"runs": [title], "size": size, "bold": True, "color": WHITE}], anchor="middle")


def bullets(items, size=14, after=8, color=MUTED, bullet_color=CYAN):
    return [{"runs": it if isinstance(it, list) else [it], "size": size, "color": color, "bullet": True,
             "bullet_color": bullet_color, "after": after} for it in items]


def code(s, color=CYAN, size=12):
    return (s, {"font": MONO, "color": color, "size": size})


# ---------------------------------------------------------------- slides

def slide1(prs):
    s = frame(prs, 1, "Team details", "", (
        "Section 1 - Team details. Fill in the bracketed roll numbers and institute before submitting. "
        "Screenshot: the offline 3D digital twin (docs/scene/index.html)."))
    label(s, LEFT, 0.6, 6, "Section 1 · Team details")
    text(s, LEFT, 0.95, 6.2, 0.95, [{"runs": ["ResiliencePilot SDV"], "size": 50, "bold": True, "color": WHITE}])
    text(s, LEFT, 1.95, 6.0, 0.8, [{"runs": ["AI-Driven Chaos Engineering for Cloud-Native Fleet Resilience"],
                                     "size": 20, "color": MUTED}])
    text(s, LEFT, 2.9, 6.2, 0.45, [{"runs": [("HTTP 200 is not recovery. ", {"color": WHITE}),
                                              ("Fresh data is.", {"color": CYAN, "bold": True})],
                                     "size": 22, "italic": True}])
    label(s, LEFT, 3.6, 4, "Team", color=MUTED)
    text(s, LEFT, 3.85, 6, 0.4, [{"runs": ["Team ResiliencePilot"], "size": 20, "bold": True, "color": WHITE}])

    picture(s, SHOTS / "layout-retina-2x-1280x800.png", 7.0, 0.6, 5.733, name="Digital twin screenshot")
    text(s, 7.0, 4.24, 5.733, 0.25, [{"runs": ["Offline 3D digital twin of the blueprint, replaying a recorded run"],
                                      "size": 10, "color": MUTED}])

    people = [("VR", "Vaibhav Raghav", "Lead Architect & Safety Controller", "[YOUR_ROLL_NO]"),
              ("AR", "Anshu Raj", "Full-Stack Observability & 3D Twin", "[ANSHU_ROLL_NO]"),
              ("NT", "Nishant Tripathi", "Chaos Engineering & Systems", "[NISHANT_ROLL_NO]"),
              ("J", "Jahnavi", "Data Quality & AI Safety", "[JAHNAVI_ROLL_NO]"),
              ("S", "Samhithaa", "Validation & Test Automation", "[SAMHIT_ROLL_NO]")]
    w, gap, y, h = 2.267, 0.2, 4.65, 1.75
    for i, (ini, name, role, roll) in enumerate(people):
        x = LEFT + i * (w + gap)
        card(s, x, y, w, h, name=f"Participant {name}")
        badge(s, x + 0.18, y + 0.18, 0.46, ini, size=13)
        text(s, x + 0.18, y + 0.75, w - 0.36, 0.3, [{"runs": [name], "size": 14, "bold": True, "color": WHITE}])
        text(s, x + 0.18, y + 1.03, w - 0.36, 0.4, [{"runs": [role], "size": 11, "color": MUTED}])
        text(s, x + 0.18, y + 1.43, w - 0.36, 0.22, [{"runs": [("Roll No: ", {"color": MUTED}), (roll, {"color": CYAN})],
                                                       "size": 11}])
    text(s, LEFT, 6.55, RIGHT - LEFT, 0.3, [{"runs": [("INSTITUTE & BATCH   ", {"color": MUTED, "size": 11, "bold": True, "spacing": 120}),
                                                       ("[YOUR_COLLEGE_NAME] — Batch of 2026", {"color": WHITE})], "size": 14}])


def slide2(prs):
    s = frame(prs, 2, "Problem understanding & approach", "Problem Understanding & AI-Driven Approach", (
        "Sources: docs/PROJECT_A_TO_Z.md (two timestamps), docs/AI_LAYER.md (planner/analyst/grounding), "
        "reports/day1/explainer.html run 20261010T094045Z-3155f1 (34/34 polls HTTP 200, stale detected at 4.85 s)."))
    x, w = LEFT, 6.3
    card(s, x, 1.55, w, 2.55, name="Problem card")
    card_header(s, x + 0.25, 1.75, w - 0.5, "!", "The problem", fill=RED)
    text(s, x + 0.25, 2.33, w - 0.5, 1.7, bullets([
        "Fleet monitoring usually trusts container health and HTTP status codes.",
        ["The Eclipse SDV rFMS API keeps returning HTTP 200 while the vehicle's ", code("createdDateTime", WHITE, 13), " is frozen."],
        [code("receivedDateTime", WHITE, 13), " (server clock) keeps ticking and masks the silent failure of ",
         code("createdDateTime", WHITE, 13), " (vehicle clock)."],
    ], bullet_color=RED))

    card(s, x, 4.3, w, 2.55, name="Approach card")
    card_header(s, x + 0.25, 4.5, w - 0.5, "AI", "The approach")
    text(s, x + 0.25, 5.08, w - 0.5, 1.7, bullets([
        "A black-box observer polls the rFMS API and tests data freshness, not just status codes.",
        "Three tiers: advisory AI (planner + analyst) → human approver → deterministic safety controller.",
        "The AI reorders allowlisted experiments and proposes verify / mitigate / fix playbooks; a deterministic "
        "grounding check audits every claim.",
    ]))

    rx, rw = 7.2, 5.533
    picture(s, DEMO / "explainer-chart.png", rx, 1.55, rw, crop_px=(96, 95, 1105, 515), name="Explainer chart")
    text(s, rx, 3.92, rw, 0.25, [{"runs": ["telemetry_stall run 3155f1: data age climbs past the 5 s threshold, every HTTP chip stays green"],
                                  "size": 10, "color": MUTED}])
    tw = (rw - 0.3) / 2
    for i, (big, small) in enumerate([("34 / 34", "polls returned HTTP 200, including every poll while the data was stale"),
                                      ("4.85 s", "until the observer flagged stale data; a status check never would")]):
        tx = rx + i * (tw + 0.3)
        card(s, tx, 4.3, tw, 2.55, name=f"Stat {big}")
        text(s, tx + 0.25, 4.55, tw - 0.5, 0.8, [{"runs": [big], "size": 40, "bold": True, "color": CYAN if i else RED}])
        text(s, tx + 0.25, 5.45, tw - 0.5, 1.2, [{"runs": [small], "size": 14, "color": MUTED}])


def slide3(prs):
    s = frame(prs, 3, "Sample application", "Target Application — Eclipse SDV Fleet Management Blueprint", (
        "Sources: docs/DECISIONS.md D-001 (pinned 3d514ac72a, Zenoh transport), docs/PROJECT_A_TO_Z.md service table. "
        "The forwarder and InfluxDB are outlined in red: they are the fault targets."))
    w = (RIGHT - LEFT - 0.6) / 3
    blocks = [
        ("What it is", [{"runs": ["Open-source reference blueprint by the Eclipse Software Defined Vehicle (SDV) working group."],
                         "size": 14, "color": WHITE}]),
        ("Repo & license", [{"runs": [("github.com/eclipse-sdv-blueprints/fleet-management",
                                       {"color": CYAN, "link": "https://github.com/eclipse-sdv-blueprints/fleet-management"})],
                             "size": 13, "after": 6},
                            {"runs": ["Pinned at ", code("3d514ac72a", WHITE, 13), " · Apache-2.0"], "size": 14}]),
        ("Deployment", [{"runs": ["8 containers in an isolated local Docker Compose sandbox. Reproducible, zero cloud cost."],
                         "size": 14, "color": WHITE}]),
    ]
    for i, (lab, body) in enumerate(blocks):
        x = LEFT + i * (w + 0.3)
        card(s, x, 1.5, w, 1.65, name=f"Info {lab}")
        label(s, x + 0.25, 1.68, w - 0.5, lab)
        text(s, x + 0.25, 2.0, w - 0.5, 1.05, body)

    label(s, LEFT, 3.38, 6, "Key services & data flow", color=MUTED)
    chips = [("csv-provider", "replays vehicle data"), ("KUKSA.val databroker", "VSS signals"),
             ("fms-forwarder", "stamps createdDateTime"), ("fms-zenoh-router", "Eclipse Zenoh / uProtocol"),
             ("fms-consumer", "writes telemetry"), ("InfluxDB", "time-series store"), ("fms-server", "rFMS REST API")]
    cw, gap = 1.45, (RIGHT - LEFT - 7 * 1.45) / 6
    for i, (n, sub) in enumerate(chips):
        x = LEFT + i * (cw + gap)
        target = n in ("fms-forwarder", "InfluxDB")
        card(s, x, 3.7, cw, 1.0, line=RED if target else BORDER, line_w=1.75 if target else 1.0, name=f"Flow {n}")
        text(s, x + 0.08, 3.78, cw - 0.16, 0.84, [{"runs": [n], "size": 12, "bold": True, "color": WHITE, "align": "center", "after": 2},
                                                  {"runs": [sub], "size": 10, "color": MUTED, "align": "center"}], anchor="middle")
        if i < 6:
            arrow(s, x + cw + (gap - 0.2) / 2, 4.1, w=0.2, h=0.2)

    card(s, LEFT, 5.0, 6.0, 1.85, name="Run card")
    label(s, LEFT + 0.25, 5.18, 5, "Steps to run")
    card(s, LEFT + 0.25, 5.5, 5.5, 0.75, fill=BG, name="Command")
    text(s, LEFT + 0.4, 5.55, 5.2, 0.65, [{"runs": [code("git submodule update --init")], "after": 2},
                                          {"runs": [code("./scripts/stack-up.sh")]}], anchor="middle")
    text(s, LEFT + 0.25, 6.35, 5.5, 0.4, [{"runs": ["Then ", code("scripts/stack-status.sh", WHITE, 12),
                                                     " to confirm all 8 containers are up."], "size": 12}])
    iw = 2.72
    for i, (f, cap) in enumerate([("m2-building-fms-forwarder.png", "3D twin: the fms-forwarder building"),
                                  ("m2-road-forwarder-router.png", "Data road: forwarder → Zenoh router")]):
        x = RIGHT - 2 * iw - 0.3 + i * (iw + 0.3)
        picture(s, SHOTS / f, x, 5.0, iw, 1.6, crop_px=CANVAS, name=cap)
        text(s, x, 6.65, iw, 0.22, [{"runs": [cap], "size": 10, "color": MUTED}])


def slide4(prs):
    s = frame(prs, 4, "Solution architecture", "Solution Architecture & Safety Framework", (
        "Sources: CLAUDE.md safety rules 1-7, config/safety.json, backend/multiagent_copilot/guardrails.py, scripts/kill-switch.sh. "
        "Watchdog is a thread in the backend with a 30 s total cap including grace; config may only lower it."))
    picture(s, DEMO / "dashboard-day2.png", LEFT, 1.5, 3.9, 5.1, name="Dashboard Day 2")
    text(s, LEFT, 6.65, 3.9, 0.25, [{"runs": ["Local dashboard: data age, HTTP status, phases, score"], "size": 10, "color": MUTED}])

    rx, rw = 4.8, RIGHT - 4.8
    flow = [("Advisory AI", BORDER), ("Human approver", BORDER), ("Safety controller", RED),
            ("Fault adapter", BORDER), ("Recovery verifier", CYAN)]
    cw = 1.42
    gap = (rw - 5 * cw) / 4
    for i, (n, ln) in enumerate(flow):
        x = rx + i * (cw + gap)
        card(s, x, 1.5, cw, 0.55, line=ln, line_w=1.5, name=f"Tier {n}")
        text(s, x, 1.5, cw, 0.55, [{"runs": [n], "size": 12, "bold": True, "color": WHITE, "align": "center"}], anchor="middle")
        if i < 4:
            arrow(s, x + cw + (gap - 0.2) / 2, 1.68, w=0.2, h=0.2)

    comps = [
        ("Observer", ["Polls the rFMS API and computes true data age: server time − ", code("createdDateTime", WHITE, 13),
                      ". Older than 5 s = stale."]),
        ("Automatic guardrails", ["Roll back on the first non-200, latency p95 above max(5× baseline p95, 250 ms), "
                                  "or any change outside the blast radius."]),
        ("Deterministic safety controller", ["Exact-name allowlist + Compose-project label, one run at a time (",
                                             code("run.lock", WHITE, 13), "), watchdog thread with a 30 s cap."]),
        ("Verified recovery gate", ["Rollback checked by docker inspect, then 3 successive fresh (≤ 5 s) advances. "
                                    "HTTP 200 alone never counts."]),
        ("LATCHED_UNSAFE", ["Unverified rollback or recovery blocks new runs until a logged human reset "
                            "on fresh telemetry."]),
        ("Independent kill switch", [code("kill-switch.sh", WHITE, 13), " works even if the backend has crashed: "
                                     "unpauses or starts the allowlisted targets."]),
    ]
    cw2, ch, top = (rw - 0.25) / 2, 1.42, 2.3
    for i, (t, body) in enumerate(comps):
        x = rx + (i % 2) * (cw2 + 0.25)
        y = top + (i // 2) * (ch + 0.14)
        card(s, x, y, cw2, ch, name=f"Component {t}")
        badge(s, x + 0.2, y + 0.18, 0.34, str(i + 1), fill=RED if t == "LATCHED_UNSAFE" else CYAN,
              color=WHITE if t == "LATCHED_UNSAFE" else BG, size=12)
        text(s, x + 0.66, y + 0.18, cw2 - 0.86, 0.34, [{"runs": [t], "size": 15, "bold": True, "color": WHITE}], anchor="middle")
        text(s, x + 0.2, y + 0.6, cw2 - 0.4, 0.78, [{"runs": body, "size": 13}])


def slide5(prs):
    s = frame(prs, 5, "Tools & technologies", "Tools, Technologies & Platform Capabilities", (
        "Sources: backend/pyproject.toml, docs/PROJECT_A_TO_Z.md tool table, config/ai.json (qwen2.5:7b via local Ollama), "
        "docs/scene/index.html (three.r160.min.js bundled, no network). Run records are JSON files committed under reports/."))
    cols = [("</>", "Languages & Backend", ["Python 3.13", "FastAPI + Uvicorn", "httpx · Pydantic", "pytest (317 tests)"]),
            ("V", "Automotive & Transport", ["Eclipse KUKSA.val", "COVESA VSS", "Eclipse Zenoh", "uProtocol"]),
            ("DB", "Cloud & Storage", ["Docker + Docker Compose", "InfluxDB (time series)", "JSON run records (evidence store)"]),
            ("AI", "AI & Visualization", ["Ollama + qwen2.5:7b (local, advisory only)", "Three.js r160 (offline 3D twin)"])]
    w = (RIGHT - LEFT - 0.9) / 4
    for i, (g, t, items) in enumerate(cols):
        x = LEFT + i * (w + 0.3)
        card(s, x, 1.5, w, 2.7, name=f"Tech {t}")
        badge(s, x + 0.22, 1.7, 0.46, g, size=11 if len(g) > 2 else 13)
        text(s, x + 0.22, 2.3, w - 0.44, 0.35, [{"runs": [t], "size": 16, "bold": True, "color": WHITE}])
        text(s, x + 0.22, 2.75, w - 0.44, 1.4, bullets(items, after=5))

    picture(s, SHOTS / "m3-hud-impact-graph-gauges.png", LEFT, 4.45, 3.6, 2.25, name="HUD impact graph")
    text(s, LEFT, 6.72, 3.6, 0.22, [{"runs": ["3D twin HUD: impact graph and gauges"], "size": 10, "color": MUTED}])
    cx = LEFT + 3.9
    cwid = RIGHT - cx
    card(s, cx, 4.45, cwid, 2.4, name="Capabilities")
    label(s, cx + 0.25, 4.62, 6, "Platform capabilities · CLI: rp <command>")
    text(s, cx + 0.25, 4.92, cwid - 0.5, 0.5, [{"runs": ["One CLI and one local API share the same safety path. Runs offline on a laptop: "
                                                         "no cloud account, no API keys."], "size": 14, "color": WHITE}])
    cmds = ["observe", "baseline", "run", "stop", "reset", "plan", "advise", "score", "findings", "discover", "report", "serve"]
    n, gap = 6, 0.14
    chip_w = (cwid - 0.5 - (n - 1) * gap) / n
    for i, c in enumerate(cmds):
        x = cx + 0.25 + (i % n) * (chip_w + gap)
        y = 5.6 + (i // n) * 0.55
        card(s, x, y, chip_w, 0.42, fill=BG, name=f"Cmd {c}")
        text(s, x, y, chip_w, 0.42, [{"runs": [code(c, CYAN, 12)], "align": "center"}], anchor="middle")


def slide6(prs):
    s = frame(prs, 6, "Failure scenarios selected", "Selected Chaos Experiments & AI Ordering", (
        "Sources: docs/PROJECT_A_TO_Z.md results table and top findings; backend/multiagent_copilot/planner.py docstring. "
        "The name-lookup failures after the database returned are observed; DNS caching as the cause is a hypothesis, not verified."))
    exps = [("telemetry_stall", "docker pause fms-forwarder", "Vehicle-edge publisher freeze, e.g. a cellular stall.",
             "HTTP 200 on 100 % of fault polls while data froze: the HTTP 200 illusion of health."),
            ("service_crash", "docker stop fms-forwarder", "Publisher crash or unhandled exception.",
             "Same silent HTTP 200 failure; verified recovery in 2.5–3.7 s after restart."),
            ("dependency_failure", "docker stop influxDB", "Cloud database outage.",
             "Visible HTTP 500s. After the DB returned, name lookups kept failing for ~21–24 s and stale data "
             "came back as HTTP 200.")]
    w = (RIGHT - LEFT - 0.6) / 3
    for i, (n, cmd, sim, obs) in enumerate(exps):
        x = LEFT + i * (w + 0.3)
        card(s, x, 1.5, w, 3.4, name=f"Scenario {n}")
        badge(s, x + 0.22, 1.7, 0.4, str(i + 1), size=13)
        text(s, x + 0.78, 1.7, w - 1.0, 0.4, [{"runs": [code(n, WHITE, 16)], "bold": True}], anchor="middle")
        card(s, x + 0.22, 2.25, w - 0.44, 0.42, fill=BG, name=f"Cmd {n}")
        text(s, x + 0.35, 2.25, w - 0.7, 0.42, [{"runs": [code(cmd, CYAN, 12)]}], anchor="middle")
        label(s, x + 0.22, 2.85, w - 0.44, "Simulates", color=MUTED, size=10)
        text(s, x + 0.22, 3.08, w - 0.44, 0.5, [{"runs": [sim], "size": 14}])
        label(s, x + 0.22, 3.62, w - 0.44, "Observed", color=RED, size=10)
        text(s, x + 0.22, 3.85, w - 0.44, 1.0, [{"runs": [obs], "size": 14, "color": WHITE}])

    bw = 4.5
    for i, (t, body) in enumerate([
        ("Why these three", "Reversible, no host contamination, and they hit real failure modes on the verified data path "
                            "instead of artificial CPU burn."),
        ("Ordering logic", "Rule-based priority = 0.6 × information + 0.4 × risk (untested hypotheses, dependents in the "
                           "dependency map, latch rate). The AI may only reorder it; a human approves each run.")]):
        x = LEFT + i * (bw + 0.3)
        card(s, x, 5.15, bw, 1.7, name=t)
        label(s, x + 0.22, 5.3, bw - 0.44, t)
        text(s, x + 0.22, 5.6, bw - 0.44, 1.2, [{"runs": [body], "size": 13}])
    ix = LEFT + 2 * (bw + 0.3)
    picture(s, SHOTS / "m1-dependency-failure-http500-t9.png", ix, 5.15, RIGHT - ix, 1.7, crop_px=CANVAS, name="Dependency failure HTTP 500")


def slide7(prs):
    s = frame(prs, 7, "Implementation & demonstration", "Live Demonstration, Results & Resilience Score", (
        "Sources: docs/coordination/CURRENT_STATUS.md (317 passed, 11 skipped; 320 with MCOP_LIVE=1), HANDOFF.md (37 runs), "
        "docs/REQUIREMENTS_TRACE.md and reports/guardrail-demo (guardrails tripped live with deliberately tight demo profiles; "
        "latency guard: 30 ms cap, tripped 1.88 s into the fault), docs/SCORING.md (formula), docs/PROJECT_A_TO_Z.md (medians: "
        "telemetry_stall 62.2 (60.9-63.5, Day 2), service_crash 65.1 (61.9-65.3), dependency_failure 61.6 (57.5-63.2))."))
    stats = [("37", "recorded runs, each kept as a JSON evidence record"),
             ("317", "automated tests passed (11 skipped; 320 with live tests)"),
             ("3 / 3", "guardrails tripped live: error rate, latency, blast radius"),
             ("1.88 s", "into the fault, the latency guard tripped and rolled back")]
    sw, sh = 3.0, 1.2
    for i, (big, small) in enumerate(stats):
        y = 1.5 + i * (sh + 0.15)
        card(s, LEFT, y, sw, sh, name=f"Stat {big}")
        text(s, LEFT + 0.22, y + 0.1, sw - 0.44, 0.55, [{"runs": [big], "size": 28, "bold": True, "color": CYAN}])
        text(s, LEFT + 0.22, y + 0.65, sw - 0.44, 0.5, [{"runs": [small], "size": 11}])

    mx, mw = 3.9, 4.5
    card(s, mx, 1.5, mw, 2.45, name="Score chart card")
    label(s, mx + 0.22, 1.64, mw - 0.44, "Median resilience score (0–100)")
    data = CategoryChartData()
    data.categories = ["service_crash", "telemetry_stall", "dependency_failure"]
    data.add_series("Median score", (65.1, 62.2, 61.6))
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(mx + 0.1), Inches(1.9), Inches(mw - 0.25), Inches(2.0), data)
    gf.name = "Median score chart"
    style_chart(gf.chart)

    card(s, mx, 4.1, mw, 2.75, name="Formula card")
    label(s, mx + 0.22, 4.25, mw - 0.44, "Resilience score")
    text(s, mx + 0.22, 4.55, mw - 0.44, 1.0, [
        {"runs": ["Score = 100 × M × (1 − 0.5 × P", ("silent", {"size": 11}), ")"], "size": 16, "color": WHITE, "font": "Cambria", "after": 4},
        {"runs": ["M = weighted mean of"], "size": 14, "color": WHITE, "font": "Cambria"},
        {"runs": ["0.25 D · 0.30 R · 0.20 G · 0.25 B"], "size": 14, "color": WHITE, "font": "Cambria"}])
    text(s, mx + 0.22, 5.55, mw - 0.44, 1.25, [
        {"runs": ["D detection · R recovery · G data integrity · B blast radius. P", ("silent", {"size": 9}),
                  " = share of polls that were HTTP 200 but stale. Unmeasured parts drop out; nothing is imputed."], "size": 12}])

    rx, rw = 8.7, RIGHT - 8.7
    picture(s, DEMO / "dashboard-stale.png", rx, 1.5, rw, crop_px=(0, 0, 1170, 740), name="Dashboard stale while HTTP 200")
    picture(s, SHOTS / "m3-findings-score-tab.png", rx, 4.31, rw, 2.54, name="Findings and score tab")


def style_chart(chart):
    chart.has_legend = False
    chart.has_title = False
    chart.font.name, chart.font.size, chart.font.color.rgb = FONT, Pt(12), rgb(MUTED)
    plot = chart.plots[0]
    plot.gap_width = 70
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = "0.0", False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.bold, dl.font.color.rgb = Pt(13), True, rgb(WHITE)
    ser = plot.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = rgb(CYAN)
    va = chart.value_axis
    va.minimum_scale, va.maximum_scale, va.major_unit = 0, 100, 25
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb(BORDER)
    va.format.line.fill.background()
    va.tick_labels.font.size, va.tick_labels.font.color.rgb = Pt(10), rgb(MUTED)
    ca = chart.category_axis
    ca.reverse_order = True
    ca.format.line.color.rgb = rgb(BORDER)
    ca.tick_labels.font.size, ca.tick_labels.font.color.rgb = Pt(11), rgb(WHITE)
    # transparent chart and plot area (PowerPoint otherwise paints them white)
    cs = chart._chartSpace
    for parent, before in ((cs, cs.find(qn("c:txPr"))), (cs.find(qn("c:chart")).find(qn("c:plotArea")), None)):
        sp = etree.Element(qn("c:spPr"))
        etree.SubElement(sp, qn("a:noFill"))
        ln = etree.SubElement(sp, qn("a:ln"))
        etree.SubElement(ln, qn("a:noFill"))
        if before is not None:
            before.addprevious(sp)
        else:
            parent.append(sp)


def slide8(prs):
    s = frame(prs, 8, "Key learnings & future enhancements", "Key Learnings, Limitations & Future Roadmap", (
        "Sources: docs/AI_LAYER.md (analyst 1/7 accepted, 6/7 rejected by the grounding check against recorded run facts), "
        "docs/DECISIONS.md D-005 (CRLF to LF in stack-up.sh). Replace [VIDEO_LINK] with the uploaded demo video URL."))
    card(s, LEFT, 1.5, 6.0, 5.35, name="Challenges")
    label(s, LEFT + 0.25, 1.68, 5.5, "Challenges → solutions")
    rows = [("HTTP 200 masked a frozen vehicle feed",
             "Track both timestamps; judge freshness from the age of createdDateTime."),
            ("AI root causes contradicted the evidence",
             "Deterministic grounding check against the recorded run facts: 1 of 7 accepted, 6 rejected and replaced by the rules."),
            ("Windows CRLF line endings broke InfluxDB init",
             "stack-up.sh normalizes the mounted blueprint files to LF before starting.")]
    for i, (c, sol) in enumerate(rows):
        y = 2.08 + i * 1.2
        badge(s, LEFT + 0.25, y, 0.4, str(i + 1), size=13)
        text(s, LEFT + 0.82, y, 4.95, 1.1, [{"runs": [c], "size": 15, "bold": True, "color": WHITE, "after": 4},
                                             {"runs": [("→ ", {"color": CYAN, "bold": True}), sol], "size": 14}])

    card(s, LEFT + 0.25, 5.75, 5.5, 0.85, fill=BG, line=CYAN, name="Key learning")
    text(s, LEFT + 0.45, 5.75, 5.1, 0.85, [{"runs": [("Key learning: ", {"bold": True, "italic": False}), "verify recovery from the data, never from the status code."], "size": 15, "italic": True, "color": CYAN}], anchor="middle")

    rx = 6.9
    cw = (RIGHT - rx - 0.25) / 2
    for i, (t, items, col) in enumerate([
        ("Limitations", ["Single simulated vehicle in the current catalogue.",
                         "Container-level faults only (pause / stop); no packet-level proxy in the data path."], RED),
        ("Future enhancements", ["Multi-vehicle fleets across distributed edge nodes.",
                                 "Network chaos (packet loss, corruption, jitter) via Toxiproxy."], CYAN)]):
        x = rx + i * (cw + 0.25)
        card(s, x, 1.5, cw, 2.55, name=t)
        label(s, x + 0.22, 1.68, cw - 0.44, t, color=col)
        text(s, x + 0.22, 2.02, cw - 0.44, 1.95, bullets(items, size=13, bullet_color=col))

    picture(s, SHOTS / "m4-tour-step6.png", rx, 4.3, 3.3, 2.06, name="Guided tour step 6")
    text(s, rx, 6.42, 3.3, 0.22, [{"runs": ["Guided tour, step 6 (docs/scene/index.html)"], "size": 10, "color": MUTED}])
    vx = rx + 3.55
    vw = RIGHT - vx
    card(s, vx, 4.3, vw, 2.55, line=CYAN, line_w=1.5, name="Video demo")
    label(s, vx + 0.2, 4.45, vw - 0.4, "Demo video")
    text(s, vx + 0.2, 4.72, vw - 0.4, 0.5, [{"runs": ["< 3 min"], "size": 26, "bold": True, "color": WHITE}])
    text(s, vx + 0.2, 5.3, vw - 0.4, 1.5, [
        {"runs": [("[VIDEO_LINK]", {"color": CYAN})], "size": 12, "after": 6},
        {"runs": [("▶ 90 s guided tour", {"color": CYAN, "link": "../scene/index.html"})], "size": 12, "after": 6},
        {"runs": [("▶ Demo script", {"color": CYAN, "link": "../demo/DAY2_DEMO_SCRIPT.md"})], "size": 12}])


def main() -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SLIDE_W), Inches(7.5)
    prs.core_properties.title = "ResiliencePilot SDV — Final Submission"
    prs.core_properties.author = "Team ResiliencePilot"
    theme = prs.slide_masters[0].part.part_related_by(RT.THEME)
    xml = theme.blob.decode("utf-8")
    for tag in ("hlink", "folHlink"):
        xml = re.sub(rf"<a:{tag}>.*?</a:{tag}>", f'<a:{tag}><a:srgbClr val="{CYAN}"/></a:{tag}>', xml, flags=re.S)
    theme._blob = xml.encode("utf-8")
    for build in (slide1, slide2, slide3, slide4, slide5, slide6, slide7, slide8):
        build(prs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
