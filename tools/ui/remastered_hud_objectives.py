"""The Remastered objectives display and notices (guis/wristcomm.gui and
guis/wristcomm_strogg.gui; ui-visual-design.md 14.11).

The display keeps the stock construction (the black 0.80 back bar, the open
plates on a 143 u pitch, the heading, the serial) and drops its limits: every
active objective is listed newest first and the list scrolls three entries at
a time, titles wrap to two lines and descriptions without a limit, and the
completed objectives follow in a COMPLETED section, title only at 0.40 behind
a check. The notices drop the stock back bars: ">>NEW OBJECTIVE" on a 200 u
plate at the top-leading corner with its title and screenshot, and
">>OBJECTIVE COMPLETE" mirrored at the top-trailing corner below the radio
chatter; each plate carries its own black backing inside its fade. A failed
objective names itself under OBJECTIVE FAILED:.

The game publishes the Remastered fields beside the stock ones (idPlayer):
oq4_new_title/oq4_new_shot and oq4_done_title for the notices, closed one at a
time by oq4_closeNewObjective/oq4_closeDoneObjective; oq4_obj_count with
oq4_obj{i}_title/_text/_shot, oq4_done_count with oq4_done{i}, and the scroll
position oq4_obj_scroll for the display; oq4_failed_title.
"""
from __future__ import annotations

import build_retained_screens as ui
from build_retained_screens import objective_frame, picture
from remastered_hud_base import (AND, NOT, OR, S, U, HudDocument, anchor, beyond_minimal, box, cancel, face_metrics,
                                 layout_state, num, op,
                                 play, pts_path, rgb, sel, shadowed, text_box, tr, transform_value, u, vec)
from remastered_hud_status import full

HEAD = "#FF8000"
FRAME, MARK = "#B0CD6B", "#B0CD6B"
ST_FRAME, ST_MARK = "#FF9000", "#FF9900"
TEXT, SERIAL = "#D0DEB6", "#D9E7BF"
NOTICE_W = 200.0
NOTICE_FADE = (0.66, 0.80, 0.93, 1.0)   # Remastered notice plates: full to 66%, half at 80%, gone at the end
ENTRY_ROWS = 3                         # entries in view at the stock pitch
OBJ_ROWS = 8                           # objectives the game publishes
DONE_ROWS = 8
LINE = 13.75                           # the stock text pitch, u


def heading_face(strogg: bool) -> tuple:
    """Marine 0.25 headings, R_Strogg on the Strogg display."""
    return ("r_strogg", 17.0) if strogg else ("marine", 18.0)


def first_line_top(face: str, size_dp: float, line_u: float, baseline_u: float) -> float:
    """The top (dp) of a line box whose first baseline sits at baseline_u."""
    leading = (u(line_u) - size_dp) / 2
    return u(baseline_u) - leading - size_dp * face_metrics(face)["ascent"]


def wrapped(ident: str, key: str, *, face: str, size: float, colour: list, x: float, baseline: float, width: float,
            lines: int | None, align: str = "left", right: float | None = None) -> dict:
    """Wrapping text whose first baseline sits at `baseline` u, `lines` at most."""
    props = {**ui.typeface(face, size, u(LINE), colour), "white-space": ui.keyword("normal"), "position": ui.keyword("absolute"),
             "top": ui.length(first_line_top(face, size, LINE, baseline)), "width": ui.length(u(width)),
             "display": ui.keyword("block"), "text-align": ui.keyword(align)}
    if right is not None:
        props["left"] = ui.length(u(right - width))
    else:
        props["left"] = ui.length(u(x))
    if lines:
        props["max-height"] = ui.length(u(LINE * lines))
        props["overflow"] = ui.keyword("hidden")
    return ui.label(ident, key, props)


def plate_paths(x: float, y: float, w: float, body_h: float, foot_h: float, colour: str, fade: tuple, *,
                mirror: bool = False, underlay: bool = True) -> list:
    """The atlas objPlate in u: an open plate whose foot is cut at the lower
    leading corner, its fill and rail dissolving toward the trailing side,
    and (Remastered) a black 0.50 backing inside the same outline and fade.
    Mirrored, the rail and cut sit on the trailing side."""
    cut = foot_h * 0.9
    bottom = y + body_h + foot_h

    def m(points):
        return [(2 * x + w - px if mirror else px, py) for px, py in points]
    outline = m([(x, y), (x + w, y), (x + w, bottom), (x + cut, bottom), (x, bottom - cut)])
    rail = m([(x + 0.5, y), (x + 0.5, bottom - cut), (x + cut, bottom - 0.6), (x + w, bottom - 0.6)])
    start, end = ((x + w, 0), (x, 0)) if mirror else ((x, 0), (x + w, 0))

    def gradient(stops):
        return {"type": "linear", "from": [u(start[0]), 0], "to": [u(end[0]), 0],
                "stops": [{"at": at, "color": ui.colour(c)} for at, c in stops]}
    f0, f1, f2, f3 = fade
    paths = []
    if underlay:
        paths.append(pts_path("under", [(u(px), u(py)) for px, py in outline],
                              fill=gradient([(0, [0, 0, 0, 0.5]), (f0, [0, 0, 0, 0.5]), (f1, [0, 0, 0, 0.25]), (1, [0, 0, 0, 0])])))
    paths.append(pts_path("fill", [(u(px), u(py)) for px, py in outline],
                          fill=gradient([(0, rgb(colour, 0.49)), (f0, rgb(colour, 0.49)), (f1, rgb(colour, 0.245)),
                                         (f2, rgb(colour, 0.05)), (1, rgb(colour, 0))])))
    paths.append(pts_path("rail", [(u(px), u(py)) for px, py in rail], closed=False,
                          stroke={"paint": gradient([(0, rgb(colour, 1)), (f0, rgb(colour, 1)), (f1, rgb(colour, 0.5)),
                                                     (f2, rgb(colour, 0.1)), (1, rgb(colour, 0))]),
                                  "widthDp": u(1.2), "minimumPixels": 0, "join": "miter", "cap": "butt"}))
    return paths


def screenshot(ident: str, x: float, y: float, source) -> list:
    """A 134x100 u screenshot behind a 1 u black border."""
    frame = vec(ident + "-frame", [pts_path("frame", [(u(x), u(y)), (u(x + 134), u(y)), (u(x + 134), u(y + 100)), (u(x), u(y + 100))],
                                            fill=ui.solid([0, 0, 0, 0.5]),
                                            stroke={"paint": ui.solid([0, 0, 0, 1]), "widthDp": u(1), "minimumPixels": 1,
                                                    "join": "miter", "cap": "butt"})])
    image = picture(ident, "", {**ui.absolute(left=u(x + 1), top=u(y + 1), width=u(132), height=u(98)), "display": ui.keyword("block")})
    return [frame, image], image["id"]


# ------------------------------------------------------------------ notices

def notice_timelines(doc: HudDocument, prefix: str, frame: str, grow: str, start_scale: float, text: str, shot: str | None,
                     done: str) -> None:
    """Entry: the frame fades to 0.80 while growing from a strip (150 ms),
    settles to 0.40 as the heading, text and screenshot fade in (100 ms).
    Exit (100 ms): the frame from 0.80 to nothing, text in 50 ms, the
    screenshot in 20 ms (stock anim_obj_in/out)."""
    tracks_in = [tr(frame, "opacity", [(0, num(0)), (150, num(0.8)), (250, num(0.4))]),
                 tr(grow, "transform", [(0, transform_value(0, 0, 1, start_scale)), (150, transform_value())]),
                 tr(text, "opacity", [(0, num(0)), (150, num(0)), (250, num(1))])]
    tracks_out = [tr(frame, "opacity", [(0, num(0.8)), (100, num(0))]), tr(text, "opacity", [(0, num(1)), (50, num(0))])]
    if shot:
        tracks_in.append(tr(shot, "opacity", [(0, num(0)), (150, num(0)), (250, num(1))]))
        tracks_out.append(tr(shot, "opacity", [(0, num(1)), (20, num(0))]))
    doc.timeline(prefix + "-in", 250, tracks_in)
    doc.timeline(prefix + "-out", 100, tracks_out, complete=done)


def new_notice(doc: HudDocument, strogg: bool) -> dict:
    """>>NEW OBJECTIVE at the top-leading corner: a 200 u plate with the
    title on two lines of 134 u, the screenshot and the serial."""
    colour, mark = (ST_FRAME, ST_MARK) if strogg else (FRAME, MARK)
    face, size = heading_face(strogg)
    doc.string("oq4_new_title")
    doc.string("oq4_new_shot")
    doc.boolean("oq4.newOn")
    plate = vec("on-plate", plate_paths(6, 0, NOTICE_W, 127, 17, colour, NOTICE_FADE))
    grow = box("on-grow", 0, u(52), u(640), u(144), [plate], transform=ui.transform())
    marker = vec("on-mark", [pts_path("m", [(u(16), u(59)), (u(24), u(59)), (u(24), u(67.5))], fill=ui.solid(rgb(mark)))])
    frame = full("on-frame", [grow, marker], opacity=num(0.4))
    heading = shadowed("on-head", "#str_200274", face=face, size=size, colour=rgb(HEAD), baseline=u(47), x=u(9), width=u(300),
                       extra={"letter-spacing": ui.length(-1.5)})
    title = wrapped("on-title", "#str_230007", face="lowpixel", size=14.4, colour=[1, 1, 1, 1], x=26, baseline=68, width=134,
                    lines=2)
    doc.bind("on-title.text", "on-title", "text", S("oq4_new_title"))
    serial = text_box("on-serial", "#str_200280" if strogg else "#str_200275", face="r_strogg" if strogg else "marine", size=13,
                      colour=rgb(SERIAL, 0.25), baseline=u(204), x=u(26), width=u(300))
    text = full("on-text", heading + [title, serial], opacity=num(1))
    shot_nodes, shot_id = screenshot("on-shot-image", 28, 84, None)
    doc.bind(shot_id + ".image", shot_id, "image", S("oq4_new_shot"))
    shot = full("on-shot", shot_nodes, opacity=num(1))
    notice_timelines(doc, "on", "on-frame", "on-grow", 32 / 144, "on-text", "on-shot", "onDone")
    group = full("on", [frame, shot, text], display=ui.keyword("none"))
    doc.show("on", S("oq4.newOn"))
    doc.on("newObjective", {"op": "setState", "values": {"oq4.newOn": True}}, cancel("on-out"), play("on-in"))
    doc.on("oq4_closeNewObjective", {"op": "if", "condition": S("oq4.newOn"), "then": [cancel("on-in"), play("on-out")]})
    doc.on("onDone", {"op": "setState", "values": {"oq4.newOn": False}})
    return group


def done_notice(doc: HudDocument, strogg: bool) -> dict:
    """>>OBJECTIVE COMPLETE mirrored at the top-trailing corner, below the
    radio chatter: its rail and cut on the trailing side, the fill
    dissolving toward the centre and its text trailing-aligned."""
    colour, mark = (ST_FRAME, ST_MARK) if strogg else (FRAME, MARK)
    face, size = heading_face(strogg)
    doc.string("oq4_done_title")
    doc.boolean("oq4.doneOn")
    x = 634 - NOTICE_W
    plate = vec("od-plate", plate_paths(x, 0, NOTICE_W, 22, 17, colour, NOTICE_FADE, mirror=True))
    grow = box("od-grow", 0, u(75), u(640), u(39), [plate], transform=ui.transform())
    marker = vec("od-mark", [pts_path("m", [(u(624), u(83)), (u(616), u(83)), (u(616), u(91.5))], fill=ui.solid(rgb(mark)))])
    frame = full("od-frame", [grow, marker], opacity=num(0.4))
    heading = shadowed("od-head", "#str_200276", face=face, size=size, colour=rgb(HEAD), baseline=u(69), right=u(631), width=u(400),
                       extra={"letter-spacing": ui.length(-1.5)})
    title = wrapped("od-title", "#str_230007", face="lowpixel", size=14.4, colour=[1, 1, 1, 1], x=0, baseline=92, width=178,
                    lines=2, align="right", right=612)
    doc.bind("od-title.text", "od-title", "text", S("oq4_done_title"))
    text = full("od-text", heading + [title], opacity=num(1))
    notice_timelines(doc, "od", "od-frame", "od-grow", 18 / 39, "od-text", None, "odDone")
    group = full("od", [frame, text], display=ui.keyword("none"))
    doc.show("od", S("oq4.doneOn"))
    doc.on("newObjectiveComplete", {"op": "setState", "values": {"oq4.doneOn": True}}, cancel("od-out"), play("od-in"))
    doc.on("oq4_closeDoneObjective", {"op": "if", "condition": S("oq4.doneOn"), "then": [cancel("od-in"), play("od-out")]})
    doc.on("odDone", {"op": "setState", "values": {"oq4.doneOn": False}})
    return group


def failed_notice(doc: HudDocument) -> dict:
    """OBJECTIVE FAILED: in Marine 0.50 #FF0000 with the objective's title in
    white below it, centred at 200-280 u; it appears at once and stays while
    the view fades."""
    doc.string("oq4_failed_title")
    doc.boolean("oq4.failed")
    lines = [text_box("of-head", "#str_200271", face="marine", size=36, colour=rgb("#FF0000"), baseline=u(232), center=u(320),
                      width=u(640), extra={"letter-spacing": ui.length(-3)}),
             text_box("of-title", "#str_230007", face="marine", size=36, colour=[1, 1, 1, 1], baseline=u(272), center=u(320),
                      width=u(640), extra={"letter-spacing": ui.length(-3)})]
    doc.bind("of-title.text", "of-title", "text", S("oq4_failed_title"))
    group = full("of", lines, display=ui.keyword("none"))
    doc.show("of", S("oq4.failed"))
    doc.on("objectiveFailed", {"op": "setState", "values": {"oq4.failed": True, "oq4.display": False}})
    return group


# ------------------------------------------------------------------ the display

def display(doc: HudDocument, strogg: bool) -> tuple:
    """The objectives display (wristcommShow/Hide): the back bar, the heading,
    the entries three at a time from oq4_obj_scroll, the COMPLETED section as
    the list's last item, the scrollbar, the serial, or the empty plate."""
    colour, mark = (ST_FRAME, ST_MARK) if strogg else (FRAME, MARK)
    face, size = heading_face(strogg)
    doc.boolean("oq4.display")
    doc.number("oq4_obj_count")
    doc.number("oq4_done_count")
    doc.number("oq4_obj_scroll")
    count, done, scroll = S("oq4_obj_count"), S("oq4_done_count"), S("oq4_obj_scroll")
    items = op("+", count, sel(op(">", done, 0), 1, 0))
    # The back bar: black 0.80 from the view's leading edge, opaque to 190 u,
    # half at 285 u, clear by 380 u; it slides 220 u in as it fades up.
    left, right = -1400.0, 380.0
    span = right - left
    # The box reaches well past the canvas so a tall or wide view stays covered.
    bar = vec("odisp-bar", [pts_path("bar", [(0, 0), (u(span), 0), (u(span), u(1280)), (0, u(1280))],
                                     fill={"type": "linear", "from": [u(190 - left), 0], "to": [u(380 - left), 0],
                                           "stops": [{"at": 0, "color": ui.colour([0, 0, 0, 0.8])},
                                                     {"at": 0.5, "color": ui.colour([0, 0, 0, 0.4])},
                                                     {"at": 1, "color": ui.colour([0, 0, 0, 0])}]})],
              {**ui.absolute(left=u(left), top=u(-400), width=u(span), height=u(1280)), "transform": ui.transform(),
               "opacity": num(0)})
    heading = ui.label("odisp-head", "#str_200291", {**ui.typeface(face, size, 24, rgb(HEAD)), "position": ui.keyword("relative"),
                                                     "display": ui.keyword("block"), "margin-left": ui.length(u(9)),
                                                     "margin-bottom": ui.length(u(2)), "letter-spacing": ui.length(-1.5),
                                                     "white-space": ui.keyword("nowrap")})
    entries = []
    for index in range(OBJ_ROWS):
        ident = f"odisp-e{index}"
        doc.string(f"oq4_obj{index}_title")
        doc.string(f"oq4_obj{index}_text")
        doc.string(f"oq4_obj{index}_shot")
        marker = vec(f"{ident}-mark", [pts_path("m", [(u(10), u(5)), (u(18), u(5)), (u(18), u(13.5))], fill=ui.solid(rgb(mark, 0.4)))],
                     {**ui.absolute(left=0, top=0, width=u(30), height=u(20))})
        title = ui.label(f"{ident}-title", "#str_230007", {"position": ui.keyword("relative"), "display": ui.keyword("block"),
                         "margin-left": ui.length(u(20)), "padding-top": ui.length(u(4)), "width": ui.length(u(308)),
                         "max-height": ui.length(u(24)), "overflow": ui.keyword("hidden"),
                         **ui.typeface("lowpixel", 14.4, u(12), [1, 1, 1, 1]), "white-space": ui.keyword("normal")})
        doc.bind(f"{ident}-title.text", f"{ident}-title", "text", S(f"oq4_obj{index}_title"))
        shot_frame = vec(f"{ident}-shot-frame", [pts_path("frame", [(0, 0), (u(134), 0), (u(134), u(100)), (0, u(100))],
                                                          fill=ui.solid([0, 0, 0, 0.5]),
                                                          stroke={"paint": ui.solid([0, 0, 0, 1]), "widthDp": u(1), "minimumPixels": 1,
                                                                  "join": "miter", "cap": "butt"})],
                         {**ui.absolute(left=0, top=0, width=u(134), height=u(100))})
        shot = picture(f"{ident}-shot", "", {**ui.absolute(left=u(1), top=u(1), width=u(132), height=u(98))})
        doc.bind(f"{ident}-shot.image", f"{ident}-shot", "image", S(f"oq4_obj{index}_shot"))
        shot_box = ui.group(f"{ident}-shotbox", {"position": ui.keyword("relative"), "display": ui.keyword("block"),
                            "margin-left": ui.length(u(22)), "width": ui.length(u(134)), "height": ui.length(u(100)),
                            "flex-shrink": ui.number(0)}, [shot_frame, shot])
        text = ui.label(f"{ident}-text", "#str_230007", {"position": ui.keyword("relative"), "display": ui.keyword("block"),
                        "margin-left": ui.length(u(8)), "width": ui.length(u(178)),
                        **ui.typeface("lowpixel", 14.4, u(LINE), rgb(TEXT)), "white-space": ui.keyword("normal")})
        doc.bind(f"{ident}-text.text", f"{ident}-text", "text", S(f"oq4_obj{index}_text"))
        body = ui.group(f"{ident}-body", {"position": ui.keyword("relative"), "display": ui.keyword("flex"),
                        "flex-direction": ui.keyword("row"), "align-items": ui.keyword("flex-start"),
                        "margin-top": ui.length(u(2))}, [shot_box, text])
        entry = ui.group(ident, {"position": ui.keyword("relative"), "display": ui.keyword("none"), "margin-left": ui.length(u(6)),
                         "box-sizing": ui.keyword("border-box"), "width": ui.length(u(600)), "min-height": ui.length(u(132)),
                         "padding-bottom": ui.length(u(14)), "margin-bottom": ui.length(u(11))},
                         [objective_frame(f"{ident}-frame", colour), marker, title, body])
        shown = AND(op(">", count, index), op(">=", index, scroll), op("<", index, op("+", scroll, ENTRY_ROWS)))
        doc.bind(f"{ident}.display", ident, "display", sel(shown, "block", "none"))
        entries.append(entry)
    # The empty plate: the stock static screenshot and its line.
    empty = ui.group("odisp-empty", {"position": ui.keyword("relative"), "display": ui.keyword("none"),
                     "margin-left": ui.length(u(6)), "width": ui.length(u(600)), "height": ui.length(u(132)),
                     "margin-bottom": ui.length(u(11))}, [
        objective_frame("odisp-empty-frame", colour),
        vec("odisp-empty-shot-frame", [pts_path("frame", [(0, 0), (u(134), 0), (u(134), u(100)), (0, u(100))],
                                                fill=ui.solid([0, 0, 0, 0.5]),
                                                stroke={"paint": ui.solid([0, 0, 0, 1]), "widthDp": u(1), "minimumPixels": 1,
                                                        "join": "miter", "cap": "butt"})],
            {**ui.absolute(left=u(22), top=u(17), width=u(134), height=u(100))}),
        picture("odisp-empty-shot", "gfx/objectives/none", {**ui.absolute(left=u(23), top=u(18), width=u(132), height=u(98))}),
        ui.label("odisp-empty-text", "#str_200935", {**ui.absolute(left=u(164), top=u(43), width=u(164), height=u(73)),
                 **ui.typeface("lowpixel", 22.3, u(16), rgb(TEXT)), "white-space": ui.keyword("normal")})])
    doc.bind("odisp-empty.display", "odisp-empty", "display", sel(op("==", count, 0), "block", "none"))
    # COMPLETED: the list's last item, title only at 0.40 behind a check.
    head_row = ui.group("odisp-done-head", {"position": ui.keyword("relative"), "display": ui.keyword("flex"),
                        "flex-direction": ui.keyword("row"), "margin-bottom": ui.length(u(4))}, [
        ui.label("odisp-done-label", "#str_230047", {"position": ui.keyword("relative"), "display": ui.keyword("block"),
                 **ui.typeface("lowpixel", 13, u(12), [1, 1, 1, 0.4]), "white-space": ui.keyword("nowrap")}),
        ui.label("odisp-done-count", "#str_230007", {"position": ui.keyword("relative"), "display": ui.keyword("block"),
                 "margin-left": ui.length(u(6)), **ui.typeface("lowpixel", 13, u(12), [1, 1, 1, 0.4]),
                 "white-space": ui.keyword("nowrap")})])
    doc.bind("odisp-done-count.text", "odisp-done-count", "text", op("numberText", done))
    rows = [head_row]
    for index in range(DONE_ROWS):
        ident = f"odisp-d{index}"
        doc.string(f"oq4_done{index}")
        check = vec(f"{ident}-check", [pts_path("check", [(u(0.5), u(4)), (u(3), u(6.6)), (u(7.6), u(1.2))], closed=False,
                                                 stroke={"paint": ui.solid(rgb(mark if strogg else "#B5C784", 0.4)), "widthDp": u(1.4),
                                                         "minimumPixels": 0, "join": "round", "cap": "round"})],
                    {**ui.absolute(left=0, top=u(2), width=u(9), height=u(8))})
        title = ui.label(f"{ident}-title", "#str_230007", {**ui.absolute(left=u(12), top=0, width=u(560), height=u(12)),
                         **ui.typeface("lowpixel", 14.4, u(12), [1, 1, 1, 0.4]), "white-space": ui.keyword("nowrap"),
                         "overflow": ui.keyword("hidden"), "text-overflow": ui.keyword("ellipsis")})
        doc.bind(f"{ident}-title.text", f"{ident}-title", "text", S(f"oq4_done{index}"))
        row = ui.group(ident, {"position": ui.keyword("relative"), "display": ui.keyword("none"), "height": ui.length(u(13))},
                       [check, title])
        doc.bind(f"{ident}.display", ident, "display", sel(op(">", done, index), "block", "none"))
        rows.append(row)
    completed = ui.group("odisp-done", {"position": ui.keyword("relative"), "display": ui.keyword("none"),
                         "margin-left": ui.length(u(18)), "margin-top": ui.length(u(2))}, rows)
    done_in_view = AND(op(">", done, 0), op("<", count, op("+", scroll, ENTRY_ROWS)))
    doc.bind("odisp-done.display", "odisp-done", "display", sel(done_in_view, "block", "none"))
    # Out of view, the section shows as its collapsed header, pointing on.
    more = ui.group("odisp-more", {"position": ui.keyword("relative"), "display": ui.keyword("none"), "margin-left": ui.length(u(18)),
                    "margin-top": ui.length(u(2))}, [
        ui.label("odisp-more-label", "#str_230047", {"position": ui.keyword("relative"), "display": ui.keyword("inline-block"),
                 **ui.typeface("lowpixel", 13, u(12), [1, 1, 1, 0.4]), "white-space": ui.keyword("nowrap")}),
        ui.label("odisp-more-count", "#str_230007", {"position": ui.keyword("relative"), "display": ui.keyword("inline-block"),
                 "margin-left": ui.length(u(6)), **ui.typeface("lowpixel", 13, u(12), [1, 1, 1, 0.4]),
                 "white-space": ui.keyword("nowrap")}),
        vec("odisp-more-arrow", [pts_path("a", [(0, u(3)), (u(7), u(3)), (u(3.5), u(8))], fill=ui.solid([1, 1, 1, 0.4]))],
            {"position": ui.keyword("relative"), "display": ui.keyword("inline-block"), "margin-left": ui.length(u(6)),
             "width": ui.length(u(7)), "height": ui.length(u(10))})])
    doc.bind("odisp-more-count.text", "odisp-more-count", "text", op("numberText", done))
    doc.bind("odisp-more.display", "odisp-more", "display", sel(AND(op(">", done, 0), NOT(done_in_view)), "block", "none"))
    serial = ui.label("odisp-serial", "#str_200280" if strogg else "#str_200275", {"position": ui.keyword("relative"),
                      "display": ui.keyword("block"), "margin-left": ui.length(u(26)), "margin-top": ui.length(u(12)),
                      **ui.typeface("r_strogg" if strogg else "marine", 13, 18, rgb(SERIAL, 0.25)), "white-space": ui.keyword("nowrap")})
    column = ui.group("odisp-column", {**ui.absolute(left=0, top=0, width=u(640), height=u(480)), "display": ui.keyword("flex"),
                      "flex-direction": ui.keyword("column"), "justify-content": ui.keyword("center")},
                      [heading, *entries, empty, completed, more, serial])
    # The scrollbar at the plates' trailing end while the list is longer
    # than its view: a trough at 0.15 and a thumb at 0.55 in the frame color.
    track_top, track_h = 35.0, 420.0
    trough = vec("odisp-trough", [pts_path("t", [(u(614), u(track_top)), (u(617), u(track_top)), (u(617), u(track_top + track_h)),
                                                 (u(614), u(track_top + track_h))], fill=ui.solid(rgb(colour, 0.15)))])
    thumb = vec("odisp-thumb", [pts_path("t", [(u(613), 0), (u(618), 0), (u(618), u(track_h)), (u(613), u(track_h))],
                                         fill=ui.solid(rgb(colour, 0.55)))],
                {**ui.absolute(left=0, top=u(track_top), width=u(640), height=u(track_h)), "transform": ui.transform()})
    fraction = op("/", ENTRY_ROWS, op("max", items, 1))
    offset = op("/", scroll, op("max", items, 1))
    # Scaled from its top: the box centre sits half the track down.
    doc.bind("odisp-thumb.place", "odisp-thumb", "transform",
             [0, op("+", op("*", u(track_h), offset), op("*", u(track_h / 2), op("-", fraction, 1))), 1, op("min", fraction, 1), 0])
    scrollbar = full("odisp-scroll", [trough, thumb], display=ui.keyword("none"))
    doc.show("odisp-scroll", op(">", items, ENTRY_ROWS))
    content = full("odisp-content", [column, scrollbar], opacity=num(0))
    doc.timeline("odisp-in", 250, [tr("odisp-bar", "transform", [(0, transform_value(u(-220))), (150, transform_value())]),
                                   tr("odisp-bar", "opacity", [(0, num(0)), (150, num(1))]),
                                   tr("odisp-content", "opacity", [(0, num(0)), (150, num(0)), (250, num(1))])])
    group = full("odisp", [bar, content], display=ui.keyword("none"))
    doc.show("odisp", S("oq4.display"))
    doc.on("wristcommShow", {"op": "setState", "values": {"oq4.display": True}}, play("odisp-in"))
    doc.on("wristcommHide", {"op": "setState", "values": {"oq4.display": False}}, cancel("odisp-in"))
    return group


def close_prompt(doc: HudDocument) -> dict:
    """With Toggle Objectives (g_objectivesToggle), the HUD prompt (14.8)
    names the control that closes the open display: the scores key's cap and
    Close at the bottom-trailing corner, where the hidden HUD leaves room."""
    from remastered_hud_mp import flex_row, label, plate_vec
    from remastered_hud_vehicle import prompt_chip
    doc.boolean("oq4_obj_toggle")
    doc.string("oq4_key_scores")
    item = flex_row("opr-close", [prompt_chip(doc, "opr", S("oq4_key_scores")),
                                  label("opr-close-word", "#str_41537", 10.6, [1, 1, 1, 0.92], line=16)])
    row = flex_row("opr-row", [plate_vec("opr-plate", 16, 0.5), item],
                   **{"height": ui.length(u(16)), "padding-left": ui.length(u(5.5)), "padding-right": ui.length(u(5.5))})
    group = ui.group("opr", {**ui.absolute(right=u(640 - 629), bottom=u(480 - 476)), "display": ui.keyword("none")}, [row])
    doc.bind("opr.display", "opr", "display", sel(AND(S("oq4.display"), S("oq4_obj_toggle")), "flex", "none"))
    return group


def objectives_document(*, strogg: bool) -> dict:
    doc = HudDocument(f"openq4.hud.remastered.objectives{'.strogg' if strogg else ''}")
    layout_state(doc)
    shown = display(doc, strogg)
    new = new_notice(doc, strogg)
    done = done_notice(doc, strogg)
    failed = failed_notice(doc)
    close = close_prompt(doc)
    doc.on("hudJoin", *doc.joins)
    doc.on("onInit", *doc.joins)
    root = full("objectives-root", [
        anchor(doc, "cl", [shown]),
        # Minimal (ui_hudLayout 2) drops the notices; the held display and a failure stay.
        anchor(doc, "tl", [beyond_minimal(doc, "tl-full", [new])]),
        anchor(doc, "tr", [beyond_minimal(doc, "tr-full", [done])]),
        anchor(doc, "cc", [failed]),
        anchor(doc, "br", [close]),
    ])
    return doc.build(root, {"canvas": {"height": 720, "minWidth": 960},
                            "extensions": {"openq4": {"reference": "ui-visual-design.md 14.11",
                                                      "stock": "guis/wristcomm_strogg.gui" if strogg else "guis/wristcomm.gui"}}})
