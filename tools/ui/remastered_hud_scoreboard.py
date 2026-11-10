"""The Remastered scoreboard (guis/scoreboard.gui; ui-visual-design.md 14.14).

Held on the scores button, instant and non-interactive. The board is the
multiplayer card of sections 6 and 14.18, the construction of the Escape and
Welcome cards: a 0.94 black body inside one rail, with 12 dp cuts at the
top-trailing and bottom-leading corners and 3 dp cuts at the other two,
centred over the view and as tall as its lists, up to a limit past which they
scroll. Its 40 dp header carries the triangle, the server's name, your place
("3RD OF 12") and the clock in the value color, and the match line under it
the mode and map with the limits. The column headings stand once above the
lists: your team's, the other team's and the spectators', each opening with a
band in its color carrying its name and score, then the Players page's rows:
a band at 0.08 (0.29 and the orange marker for yours), the speaker crossed
when muted, the friend symbol, a skull while dead (the row at 0.50), the flag
a carrier holds or the warm-up's ready check, the name, the clan or a BOT tag,
the score, kills (flag modes), deaths and minutes, and ping beside the
network-quality bars. Under the lists, the server's address and, while the
board scrolls, the count of the rows below. Tourney's card is wider and sets
the bracket tree under its header, scaled into its inset, above the lists.

The game publishes the rows as fields (idMultiplayerGame::PublishRemasteredScoreboard):
oq4_sb{p}_kind/_score/_count per panel (0 your team or the players, 1 the other
team, 2 the spectators), oq4_sb{p}_{r}_name/_clan/_score/_kills/_deaths/_time/
_ping/_flags per row, oq4_sb_pitch (the row pitch in u), oq4_sb_kills (the
KILLS column shows), oq4_sb_rank and, while the board scrolls, the rows below
as oq4_sb_below and its text oq4_sb_below_text; the panels it publishes are
the window the scroll shows. The header, match line and address read the
stock keys (servername, serverip, servergametype, servermap, serverlimit,
servertimelimit, timeleft, infinity).
"""
from __future__ import annotations

import build_retained_screens as ui
from remastered_hud_base import AND, NOT, OR, S, U, HudDocument, anchor, layout_state, op, pts_path, rgb, sel, svg_path, text_box, u, vec, when
from remastered_hud_mp import colour_of
from remastered_hud_status import full

NOTE, VALUE, ORANGE, MARKER, RAIL_CARD, ERROR = "#FFFF8D", "#FFBE23", "#E38900", "#909A49", "#A0A040", "#E46D56"
TEAM_COLOURS = {0: "#8B964B", 1: "#6AA42B", 2: "#FF7B04", 3: "#999999"}   # players, marine, strogg, spectators
TITLES = {0: "#str_200038", 1: "#str_200917", 2: "#str_200199", 3: "#str_200281"}
NAME_KEY, CLAN_KEY, SCORE_KEY, KILLS_KEY, DEATHS_KEY, TIME_KEY, PING_KEY = (
    "#str_200242", "#str_200256", "#str_200198", "#str_200201", "#str_200202", "#str_200244", "#str_200037")
TOURNEY_TITLE = "#str_200285"
# Row slots per panel (your team or the players, the other team, the
# spectators): the most rows a panel shows at once in the tallest card. The
# game publishes the window of rows the scroll shows (PublishRemasteredScoreboard).
ROWS = (20, 20, 16)
# Flags bits (PublishRemasteredScoreboard).
ME, DEAD, BOT, GREYED, READY_SHOWN, READY, MUTED, CARRIER, FRIEND = 1, 2, 4, 8, 16, 32, 64, 128, 256

# The card (dp): the section 6 construction with a 24 dp content inset.
CARD_W, CARD_MAX_H = 744.0, 630.0
TOURNEY_W, TOURNEY_MAX_H = 928.0, 690.0     # 4:3's 960 dp less 16 dp a side
HEADER_H, INSET, CUT_MAJOR, CUT_MINOR = 40.0, 24.0, 12.0, 3.0
MATCH_TOP, MATCH_H = 52.0, 22.0
HEADINGS_H = 16.0
LIST_TOP = 98.0                             # the headings 82-98 dp, under the match line
PANEL_GAP, BAND_H = 6.0, 22.0               # each panel opens 6 dp down with its 22 dp band
BOTTOM, STRIP_H, STRIP_PAD = 36.0, 18.0, 10.0   # 8 dp, the address strip, 10 dp to the edge
# Tourney's bracket chart sits under the match line, then the lists.
TREE_TOP, CHART_H = 82.0, 224.0
TOURNEY_HEADINGS_TOP = TREE_TOP + CHART_H + 8.0
TOURNEY_LIST_TOP = TOURNEY_HEADINGS_TOP + HEADINGS_H
# The lists' room in the tallest card (dp). PublishRemasteredScoreboard lays
# its window out on these numbers (496 and 324 dp).
LIST_VIEW = CARD_MAX_H - LIST_TOP - BOTTOM
TOURNEY_LIST_VIEW = TOURNEY_MAX_H - TOURNEY_LIST_TOP - BOTTOM
# Row columns (dp): the marker, speaker, friend and state slots, the name
# taking what is left, the clan or BOT tag, the four numbers, and ping after
# its bars, which keep 10 dp from the minutes.
MARK_W, ICON_W, CLAN_W, NUMBER_W, BARS_GAP, BARS_W, PING_W = 12.0, 18.0, 96.0, 52.0, 10.0, 22.0, 40.0
ROW_FACE = 14.0


def bit(value, flag):
    return op("==", op("%", op("floor", op("/", value, flag)), 2), 1)


def end(dp: float = 0.0) -> dict:
    """A coordinate `dp` before the node's far edge."""
    return {"fraction": 1, "dp": -dp} if dp else {"fraction": 1}


def card_frame(ident: str) -> dict:
    """The section 6 card filling its node: a black body at 0.94 inside one
    marine.rail.card rail, the 12 dp cuts at the top-trailing and
    bottom-leading corners and the 3 dp cuts at the other two."""
    def outline(inset: float) -> list:
        d = inset * 0.4142   # a 45-degree corner moves this far along each side per unit of inset
        return [(CUT_MINOR + d, inset), (end(CUT_MAJOR + d), inset), (end(inset), CUT_MAJOR + d),
                (end(inset), end(CUT_MINOR + d)), (end(CUT_MINOR + d), end(inset)), (CUT_MAJOR + d, end(inset)),
                (inset, end(CUT_MAJOR + d)), (inset, CUT_MINOR + d)]
    return vec(ident, [ui.path("body", outline(0), fill=ui.solid([0, 0, 0, 0.94])),
                       ui.path("rail", outline(0.75), stroke=ui.stroke(ui.solid(rgb(RAIL_CARD)), 1.5))])


def flow_label(ident: str, key: str, face: str, size: float, colour: list, *, width: float | None = None, grow: bool = False,
               align: str | None = None, line: float | None = None, **more) -> dict:
    """A label in a flex row: `width` dp wide or growing into what is left,
    clipped with an ellipsis, or otherwise as wide as its text."""
    props = {"position": ui.keyword("relative"), "display": ui.keyword("block"), "white-space": ui.keyword("nowrap"),
             "flex-shrink": ui.number(1 if grow else 0), **ui.typeface(face, size, line if line is not None else size * 1.4, colour)}
    if grow or width is not None:
        props.update({"overflow": ui.keyword("hidden"), "text-overflow": ui.keyword("ellipsis")})
    if grow:
        props.update({"flex-grow": ui.number(1), "min-width": ui.length(0)})
    if width is not None:
        props["width"] = ui.length(width)
    if align:
        props["text-align"] = ui.keyword(align)
    props.update(more)
    return ui.label(ident, key, props)


def slot(ident: str, width: float, children=(), **more) -> dict:
    return ui.group(ident, {"position": ui.keyword("relative"), "display": ui.keyword("block"), "width": ui.length(width),
                            "height": ui.length(16), "flex-shrink": ui.number(0), **more}, children)


def flex(ident: str, props: dict, children: list) -> dict:
    return ui.group(ident, {"display": ui.keyword("flex"), "flex-direction": ui.keyword("row"), "align-items": ui.keyword("center"),
                            **props}, children)


def card_header(doc: HudDocument, tourney) -> list:
    """The 40 dp header (sections 6 and 14.18): a white 0.16 wash in the light
    plate's shape fading toward the trailing edge, a 1 dp rule below, the 8 dp
    triangle and the title in Marine (the server's name; Tourney's TOURNAMENT
    BRACKETS), then your place and the clock in the value color."""
    wash = vec("sb-wash", [ui.path("wash", [(0, 3), (end(), 3), (end(), HEADER_H - 3), (19, HEADER_H - 3), (0, HEADER_H - 22)],
                                   fill=ui.linear((0, 0), (end(), 0), [(0, [1, 1, 1, 0.16]), (0.5, [1, 1, 1, 0.16]), (1, [1, 1, 1, 0])]))],
               ui.absolute(left=1.5, top=0, right=1.5, height=HEADER_H))
    rule = vec("sb-rule", [ui.path("rule", [(0, 0.5), (end(), 0.5)], closed=False, stroke=ui.stroke(ui.solid(rgb(RAIL_CARD, 0.8)), 1))],
               ui.absolute(left=1.5, top=HEADER_H, right=1.5, height=1))
    triangle = vec("sb-triangle", [pts_path("mark", [(0, 0), (8, 0), (8, 8)], fill=ui.solid(rgb(MARKER)))],
                   {"position": ui.keyword("relative"), "display": ui.keyword("block"), "width": ui.length(8), "height": ui.length(8),
                    "flex-shrink": ui.number(0), "margin-right": ui.length(8)})
    title = flow_label("sb-title", "#str_230007", "marine", 20, [1, 1, 1, 0.9], grow=True, line=HEADER_H)
    doc.bind("sb-title.text", "sb-title", "text", S("servername"))
    doc.show("sb-title", NOT(tourney))
    tourney_title = flow_label("sb-title-t", TOURNEY_TITLE, "marine", 20, [1, 1, 1, 0.9], grow=True, line=HEADER_H,
                               display=ui.keyword("none"))
    doc.show("sb-title-t", tourney)
    rank = flow_label("sb-rank", "#str_230007", "lowpixel", 15, [1, 1, 1, 0.8], line=HEADER_H, **{"margin-left": ui.length(16)})
    doc.bind("sb-rank.text", "sb-rank", "text", S("oq4_sb_rank"))
    doc.show("sb-rank", op("!=", S("oq4_sb_rank"), ""))
    clock = flow_label("sb-clock", "#str_230007", "lowpixel", 17, rgb(VALUE), line=HEADER_H, **{"margin-left": ui.length(16)})
    doc.bind("sb-clock.text", "sb-clock", "text", S("timeleft"))
    doc.show("sb-clock", NOT(S("infinity")))
    row = flex("sb-head", {**ui.absolute(left=INSET, top=0, right=INSET, height=HEADER_H)}, [triangle, title, tourney_title, rank, clock])
    return [wash, rule, row]


def match_line(doc: HudDocument, tourney) -> dict:
    """The mode and map in Marine, a short rule between them, then the limits;
    Tourney's frags to win a round and the tournament count instead."""
    doc.string("tourney_frag_count")
    doc.string("tourney_count")
    mode = flow_label("sb-mode", "#str_230007", "marine", 16, [1, 1, 1, 0.9], line=MATCH_H)
    doc.bind("sb-mode.text", "sb-mode", "text", S("servergametype"))
    dash = vec("sb-dash", [pts_path("d", [(0, 0), (8, 0), (8, 1.5), (0, 1.5)], fill=ui.solid([1, 1, 1, 0.5]))],
               {"position": ui.keyword("relative"), "display": ui.keyword("block"), "width": ui.length(8), "height": ui.length(1.5),
                "flex-shrink": ui.number(0), "margin-left": ui.length(10), "margin-right": ui.length(10)})
    world = flow_label("sb-map", "#str_230007", "marine", 16, [1, 1, 1, 0.9], grow=True, line=MATCH_H)
    doc.bind("sb-map.text", "sb-map", "text", S("servermap"))
    limits = []
    for ident, key, shown in (("sb-limit", "serverlimit", NOT(tourney)), ("sb-timelimit", "servertimelimit", NOT(tourney)),
                              ("sb-frags", "tourney_frag_count", tourney), ("sb-count", "tourney_count", tourney)):
        node = flow_label(ident, "#str_230007", "lowpixel", 14, [1, 1, 1, 0.6], line=MATCH_H, **{"margin-left": ui.length(16)})
        doc.bind(ident + ".text", ident, "text", S(key))
        doc.show(ident, shown)
        limits.append(node)
    return flex("sb-match", ui.absolute(left=INSET, top=MATCH_TOP, right=INSET, height=MATCH_H), [mode, dash, world, *limits])


def headings(doc: HudDocument) -> dict:
    """The column headings once above the lists, in Lowpixel at 0.40 over a
    white 0.10 rule; KILLS only in the flag modes."""
    colour = [1, 1, 1, 0.4]
    cells = [slot("sb-h-lead", MARK_W + 3 * ICON_W),
             flow_label("sb-h-name", NAME_KEY, "lowpixel", 11, colour, grow=True, line=HEADINGS_H),
             flow_label("sb-h-clan", CLAN_KEY, "lowpixel", 11, colour, width=CLAN_W, line=HEADINGS_H)]
    for name, key in (("score", SCORE_KEY), ("kills", KILLS_KEY), ("deaths", DEATHS_KEY), ("time", TIME_KEY)):
        cells.append(flow_label(f"sb-h-{name}", key, "lowpixel", 11, colour, width=NUMBER_W, align="right", line=HEADINGS_H))
    doc.show("sb-h-kills", S("oq4_sb_kills"))
    cells += [slot("sb-h-bars", BARS_W, **{"margin-left": ui.length(BARS_GAP)}),
              flow_label("sb-h-ping", PING_KEY, "lowpixel", 11, colour, width=PING_W, align="right", line=HEADINGS_H)]
    rule = vec("sb-h-rule", [ui.path("rule", [(0, 0.5), (end(), 0.5)], closed=False, stroke=ui.stroke(ui.solid([1, 1, 1, 0.1]), 1))],
               ui.absolute(left=0, bottom=0, right=0, height=1))
    row = flex("sb-h-row", {**ui.absolute(left=0, top=0, right=0, height=HEADINGS_H)}, cells)
    return ui.group("sb-headings", {**ui.absolute(left=INSET, top=LIST_TOP - HEADINGS_H, right=INSET, height=HEADINGS_H),
                                    "display": ui.keyword("block")}, [row, rule])


def team_band(ident: str, tint: str) -> dict:
    """A header band in a team's color (section 6, the Players page's band):
    an upper-leading cut, top and leading rails, the fill full to half the
    width and fading toward the end."""
    cut = 6.0
    return vec(ident, [
        ui.path("fill", [(cut, 0), (end(), 0), (end(), BAND_H), (0, BAND_H), (0, cut)],
                fill=ui.linear((0, 0), (end(), 0), [(0, rgb(tint, 0.49)), (0.5, rgb(tint, 0.49)), (0.75, rgb(tint, 0.25)),
                                                    (0.95, rgb(tint, 0.05)), (1, rgb(tint, 0))])),
        ui.path("rail", [(0.75, BAND_H), (0.75, cut), (cut, 0.75), ({"fraction": 0.6}, 0.75)], closed=False,
                stroke=ui.stroke(ui.linear((0, 0), ({"fraction": 0.6}, 0), [(0, rgb(tint)), (0.7, rgb(tint)), (1, rgb(tint, 0))]), 1.5)),
    ], {**ui.absolute(left=0, top=0, right=0, height=BAND_H), "display": ui.keyword("none")})


def speaker(ident: str) -> dict:
    """The speaker with a wave (section 6, the Players page's), crossed with a
    red slash while muted."""
    tint = [1, 1, 1, 0.7]
    slash = vec(f"{ident}-slash", [ui.path("slash", [(1.5, 12.5), (12.5, 1.5)], closed=False, stroke=ui.stroke(ui.solid(rgb(ERROR)), 1.6))],
                {**ui.absolute(left=0, top=0, width=14, height=14), "display": ui.keyword("none")})
    return vec(ident, [ui.path("body", [(1.5, 5), (4.5, 5), (8, 2), (8, 12), (4.5, 9), (1.5, 9)], fill=ui.solid(tint)),
                       ui.path("wave", [(10, 4), (11.6, 7), (10, 10)], closed=False, stroke=ui.stroke(ui.solid(tint), 1.2))],
               {**ui.absolute(left=0, top=1, width=14, height=14)}, [slash])


def friend(ident: str) -> dict:
    """The friend silhouette (section 6), 0.125 for a player who is not one."""
    head = [(7 + 2.6 * x, 4.6 + 2.6 * y) for x, y in ((0, -1), (0.71, -0.71), (1, 0), (0.71, 0.71), (0, 1), (-0.71, 0.71), (-1, 0),
                                                      (-0.71, -0.71))]
    return vec(ident, [ui.path("head", head, fill=ui.solid([1, 1, 1, 1])),
                       ui.path("shoulders", [(1.5, 13.5), (2.2, 10.4), (4.6, 8.6), (9.4, 8.6), (11.8, 10.4), (12.5, 13.5)],
                               fill=ui.solid([1, 1, 1, 1]))],
               {**ui.absolute(left=0, top=1, width=14, height=14), "opacity": ui.number(0.125)})


def ping_bars(doc: HudDocument, ident: str, ping) -> list:
    """The network-quality bars (13.13): four steps by ping, #B5C784 for three
    or four, #E3AD36 for two, #E46D56 for one, unlit bars at 0.20, standing on
    the text's baseline."""
    level = sel(op("<=", ping, 60), 4, sel(op("<=", ping, 120), 3, sel(op("<=", ping, 200), 2, 1)))
    nodes = []
    for lit in (1, 2, 3, 4):
        colour = "#B5C784" if lit >= 3 else "#E3AD36" if lit == 2 else "#E46D56"
        paths = []
        for b in range(4):
            x, height = 2 + b * 5, 4.5 + b * 3.3
            paths.append(pts_path(f"b{b}", [(x, 15 - height), (x + 3.3, 15 - height), (x + 3.3, 15), (x, 15)],
                                  fill=ui.solid(rgb(colour, 1 if b < lit else 0.2))))
        node = vec(f"{ident}-bars{lit}", paths, {**ui.absolute(left=0, top=0, width=BARS_W, height=16), "display": ui.keyword("none")})
        doc.show(node["id"], op("==", level, lit))
        nodes.append(node)
    return nodes


def state_icons(doc: HudDocument, ident: str, flags, kind) -> list:
    """The row's state: a skull while dead, else the flag a carrier holds (in
    the other team's color), else the warm-up's ready check."""
    dead, carrier = bit(flags, DEAD), bit(flags, CARRIER)
    skull = vec(f"{ident}-skull", [svg_path("k", "M4 0a4 4 0 0 1 4 4c0 1.4-.7 2-1.3 2.7v1.3H1.3V6.7C.7 6 0 5.4 0 4a4 4 0 0 1 4-4zM2.4 3.4h1.2v1.2H2.4zM4.4 3.4h1.2v1.2H4.4z",
                                            matrix=(1.5, 0, 0, 1.5, 1, 1.5), fill=ui.solid([1, 1, 1, 1]), rule="evenodd")],
                {**ui.absolute(left=0, top=0, width=14, height=16), "display": ui.keyword("none")})
    doc.show(skull["id"], dead)
    flag_nodes = []
    for team, tint in ((1, TEAM_COLOURS[2]), (2, TEAM_COLOURS[1])):
        node = vec(f"{ident}-flag{team}", [ui.path("pole", [(2, 1.5), (3.4, 1.5), (3.4, 14.5), (2, 14.5)], fill=ui.solid([1, 1, 1, 0.85])),
                                           ui.path("cloth", [(3.4, 1.5), (13, 4.6), (3.4, 7.8)], fill=ui.solid(rgb(tint)))],
                   {**ui.absolute(left=0, top=0, width=14, height=16), "display": ui.keyword("none")})
        doc.show(node["id"], AND(NOT(dead), carrier, op("==", kind, team)))
        flag_nodes.append(node)
    check = vec(f"{ident}-ready", [ui.path("r", [(1.5, 8), (5, 11.5), (12, 4)], closed=False,
                                           stroke=ui.stroke(ui.solid(rgb("#B5C784")), 2.1, join="round", cap="round"))],
                {**ui.absolute(left=0, top=0, width=14, height=16), "display": ui.keyword("none")})
    doc.show(check["id"], AND(NOT(dead), NOT(carrier), bit(flags, READY_SHOWN), bit(flags, READY)))
    return [skull, *flag_nodes, check]


def row_node(doc: HudDocument, p: int, r: int, kind) -> dict:
    """One row (the Players page's, section 14.18): its band at 0.08, 0.29
    and the orange marker for yours, the slots and the columns, at 0.50
    while its player is dead or eliminated."""
    ident = f"sb{p}r{r}"
    field = lambda name: S(f"oq4_sb{p}_{r}_{name}")
    for name, initial in (("name", ""), ("clan", ""), ("score", 0), ("kills", 0), ("deaths", 0), ("time", 0), ("ping", 0), ("flags", 0)):
        if isinstance(initial, str):
            doc.string(f"oq4_sb{p}_{r}_{name}", initial)
        else:
            doc.number(f"oq4_sb{p}_{r}_{name}", initial)
    flags = field("flags")
    me, bot = bit(flags, ME), bit(flags, BOT)
    spectators = op("==", kind, 3)
    band = vec(f"{ident}-band", [ui.path("band", [(0, 1), (end(), 1), (end(), end(1)), (0, end(1))], fill=ui.solid([1, 1, 1, 1]))],
               {**ui.FULL, "opacity": ui.number(0.08)})
    doc.bind(f"{ident}-band.opacity", f"{ident}-band", "opacity", sel(me, 0.29, 0.08))
    marker = vec(f"{ident}-marker", [pts_path("m", [(0, 0), (8, 0), (8, 8)], fill=ui.solid(rgb(ORANGE)))],
                 {**ui.absolute(left=0, top=4, width=8, height=8), "display": ui.keyword("none")})
    doc.show(marker["id"], me)
    talk = speaker(f"{ident}-speaker")
    doc.show(f"{ident}-speaker-slash", bit(flags, MUTED))
    pal = friend(f"{ident}-friend")
    doc.bind(f"{ident}-friend.opacity", f"{ident}-friend", "opacity", sel(bit(flags, FRIEND), 1, 0.125))
    white = [1, 1, 1, 0.85]
    name = flow_label(f"{ident}-name", "#str_230007", "lowpixel", ROW_FACE, white, grow=True, line=16)
    doc.bind(f"{ident}-name.text", f"{ident}-name", "text", field("name"))
    clan = flow_label(f"{ident}-clan", "#str_230007", "lowpixel", ROW_FACE, [1, 1, 1, 0.6], width=CLAN_W, line=16)
    doc.bind(f"{ident}-clan.text", f"{ident}-clan", "text", field("clan"))
    doc.show(clan["id"], NOT(bot))
    # openQ4 bots carry a BOT tag in the header-band construction.
    tag = ui.group(f"{ident}-bot", {"position": ui.keyword("relative"), "display": ui.keyword("none"), "width": ui.length(CLAN_W),
                                    "height": ui.length(16), "flex-shrink": ui.number(0)}, [
        vec(f"{ident}-bot-plate", [{"id": "t", "fill": ui.solid(rgb("#8B964B", 0.6)), "commands": [
            {"id": "a", "op": "move", "points": [[0, 0]]}, {"id": "b", "op": "line", "points": [[33, 0]]},
            {"id": "c", "op": "line", "points": [[33, 16]]}, {"id": "d", "op": "line", "points": [[5, 16]]},
            {"id": "e", "op": "line", "points": [[0, 11]]}, {"id": "f", "op": "close"}]}],
            ui.absolute(left=0, top=0, width=33, height=16)),
        ui.label(f"{ident}-bot-text", "#str_231231", {**ui.absolute(left=0, top=0, width=33, height=16),
                 **ui.typeface("lowpixel", 10.8, 16, [1, 1, 1, 1]), "text-align": ui.keyword("center"),
                 "white-space": ui.keyword("nowrap"), "display": ui.keyword("block")})])
    doc.show(tag["id"], bot)
    numbers = []
    for col, shown in (("score", NOT(spectators)), ("kills", AND(NOT(spectators), S("oq4_sb_kills"))),
                       ("deaths", NOT(spectators)), ("time", NOT(spectators))):
        node = flow_label(f"{ident}-{col}", "#str_230007", "lowpixel", ROW_FACE, white, width=NUMBER_W, align="right", line=16,
                          opacity=ui.number(1))
        doc.bind(f"{ident}-{col}.text", f"{ident}-{col}", "text", op("numberText", field(col)))
        numbers.append(node)
        if col == "kills":
            doc.show(node["id"], S("oq4_sb_kills"))
        # The spectators keep the columns' room, unlit, so ping stays aligned.
        doc.bind(f"{ident}-{col}.opacity", f"{ident}-{col}", "opacity", sel(shown, 1, 0))
    # A bot's row keeps the bars' room, empty, so its columns line up.
    meter = ui.group(f"{ident}-meter", {**ui.FULL, "display": ui.keyword("block")}, ping_bars(doc, ident, field("ping")))
    doc.show(meter["id"], NOT(bot))
    bars = slot(f"{ident}-bars", BARS_W, [meter], **{"margin-left": ui.length(BARS_GAP)})
    ping = flow_label(f"{ident}-ping", "#str_230007", "lowpixel", ROW_FACE, [1, 1, 1, 0.6], width=PING_W, align="right", line=16)
    doc.bind(f"{ident}-ping.text", f"{ident}-ping", "text", op("numberText", field("ping")))
    cells = [slot(f"{ident}-mark", MARK_W, [marker]), slot(f"{ident}-talk", ICON_W, [talk]), slot(f"{ident}-pal", ICON_W, [pal]),
             slot(f"{ident}-state", ICON_W, state_icons(doc, ident, flags, kind)), name, clan, tag, *numbers, bars, ping]
    content = flex(f"{ident}-content", {**ui.absolute(left=0, top=0, right=0, bottom=0), "opacity": ui.number(1)}, cells)
    doc.bind(f"{ident}-content.dim", f"{ident}-content", "opacity", sel(OR(bit(flags, DEAD), bit(flags, GREYED)), 0.5, 1))
    row = ui.group(ident, {"position": ui.keyword("relative"), "display": ui.keyword("none"), "width": ui.length(100, "%"),
                           "height": ui.length(24)}, [band, content])
    doc.bind(f"{ident}.display", ident, "display", sel(op(">", S(f"oq4_sb{p}_count"), r), "block", "none"))
    doc.bind(f"{ident}.height", ident, "height", op("*", S("oq4_sb_pitch"), U))
    return row


def panel(doc: HudDocument, p: int) -> dict:
    """One panel: 6 dp down, its band in the team's color with the title and
    the team's score in the value color, then its rows."""
    kind = S(f"oq4_sb{p}_kind")
    doc.number(f"oq4_sb{p}_kind", -1)
    doc.string(f"oq4_sb{p}_score")
    doc.number(f"oq4_sb{p}_count")
    bands, titles = [], []
    for k, colour in TEAM_COLOURS.items():
        band = team_band(f"sb{p}-band{k}", colour)
        doc.show(band["id"], op("==", kind, k))
        bands.append(band)
        title = ui.label(f"sb{p}-title{k}", TITLES[k], {**ui.absolute(left=16, top=0, right=120, height=BAND_H),
                         **ui.typeface("marine", 15, BAND_H, [1, 1, 1, 0.95]), "white-space": ui.keyword("nowrap"),
                         "overflow": ui.keyword("hidden"), "display": ui.keyword("none")})
        doc.show(title["id"], op("==", kind, k))
        titles.append(title)
    score = ui.label(f"sb{p}-score", "#str_230007", {**ui.absolute(right=4, top=0, width=110, height=BAND_H),
                     **ui.typeface("lowpixel", 16, BAND_H, rgb(VALUE)), "text-align": ui.keyword("right"), "white-space": ui.keyword("nowrap")})
    doc.bind(f"sb{p}-score.text", f"sb{p}-score", "text", S(f"oq4_sb{p}_score"))
    head = ui.group(f"sb{p}-head", {"position": ui.keyword("relative"), "display": ui.keyword("block"), "width": ui.length(100, "%"),
                                    "height": ui.length(BAND_H)}, [*bands, *titles, score])
    rows = [row_node(doc, p, r, kind) for r in range(ROWS[p])]
    group = ui.group(f"sb{p}", {"position": ui.keyword("relative"), "display": ui.keyword("none"), "width": ui.length(100, "%"),
                                "margin-top": ui.length(PANEL_GAP)}, [head, *rows])
    doc.show(group["id"], op(">=", kind, 0))
    return group


def bottom_strip(doc: HudDocument) -> dict:
    """Under the lists: the server's address, and while the board scrolls
    the count of the rows below after a downward triangle."""
    doc.number("oq4_sb_below")
    doc.string("oq4_sb_below_text")
    address = flow_label("sb-address", "#str_230007", "lowpixel", 13, [1, 1, 1, 0.45], grow=True, line=STRIP_H)
    doc.bind("sb-address.text", "sb-address", "text", S("serverip"))
    colour = [1, 1, 1, 0.5]
    arrow = vec("sb-more-arrow", [pts_path("a", [(0, 1), (8, 1), (4, 6)], fill=ui.solid(colour))],
                {"position": ui.keyword("relative"), "display": ui.keyword("block"), "width": ui.length(8), "height": ui.length(7),
                 "flex-shrink": ui.number(0), "margin-right": ui.length(6)})
    text = flow_label("sb-more-text", "#str_230007", "lowpixel", 12, colour, line=STRIP_H)
    doc.bind("sb-more-text.text", "sb-more-text", "text", S("oq4_sb_below_text"))
    more = flex("sb-more", {"position": ui.keyword("relative"), "display": ui.keyword("none"), "flex-shrink": ui.number(0)}, [arrow, text])
    doc.bind("sb-more.display", "sb-more", "display", sel(op(">", S("oq4_sb_below"), 0), "flex", "none"))
    return flex("sb-strip", ui.absolute(left=INSET, right=INSET, bottom=STRIP_PAD, height=STRIP_H), [address, more])


# ------------------------------------------------------------------ Tourney

# The bracket chart (14.14): sixteen players meet in eight arenas, then four,
# two and the final, the two halves converging on the final in the card's
# centre. (round, bracket) -> (column, row): seven columns from the leading
# edge, rows down the column.
ARENAS = {**{(1, b): (0 if b <= 4 else 6, (b - 1) % 4) for b in range(1, 9)},
          **{(2, b): (1 if b <= 2 else 5, (b - 1) % 2) for b in range(1, 5)},
          (3, 1): (2, 0), (3, 2): (4, 0), (4, 1): (3, 0)}
PLATE_W, FINAL_W, CHART_GAP = 110.0, 136.0, 14.0
PLATE_H, FINAL_H, PLATE_CUT = 38.0, 56.0, 10.0
FIRST_TOP, FIRST_PITCH = 22.0, 52.0         # the first round's plates under the round titles, 14 dp apart
assert FIRST_TOP + 3 * FIRST_PITCH + PLATE_H + 8 == CHART_H, "the chart's height holds its first round"
ROUND_TITLES = {1: "#str_200286", 2: "#str_200287", 3: "#str_200288", 4: "#str_200289"}
AQUA, FINISHED = "#5EB987", "#3E57B7"


def column_x(column: int) -> float:
    pitch = PLATE_W + CHART_GAP
    if column <= 3:
        return column * pitch
    return 3 * pitch + FINAL_W + CHART_GAP + (column - 4) * pitch


assert column_x(6) + PLATE_W == TOURNEY_W - 2 * INSET, "the chart spans the Tourney card's inset"


def arena_centre(r: int, row: int) -> float:
    """A plate's vertical centre: the first round's down the column, each
    later round's between the two arenas that feed it."""
    first = [FIRST_TOP + k * FIRST_PITCH + PLATE_H / 2 for k in range(4)]
    if r == 1:
        return first[row]
    if r == 2:
        return (first[2 * row] + first[2 * row + 1]) / 2
    return (first[0] + first[3]) / 2


def arena_box(r: int, b: int) -> tuple:
    column, row = ARENAS[(r, b)]
    w, h = (FINAL_W, FINAL_H) if r == 4 else (PLATE_W, PLATE_H)
    return column_x(column), arena_centre(r, row) - h / 2, w, h


def open_plate(ident: str, w: float, h: float, tint: str, mirrored: bool, *, fill: float = 0.34, display: str = "block") -> dict:
    """An open plate (section 2, trait 3, the in-game card's plates): rails
    on the leading edge, the 45-degree lower-leading cut and the bottom edge
    only, fill and rails dissolving toward the trailing end; the second half
    of the chart mirrors it so every leading edge faces out."""
    def x(value: float) -> float:
        return w - value if mirrored else value
    start, stop = (x(0), 0), (x(w), 0)
    return vec(ident, [
        pts_path("fill", [(x(0), 0), (x(w), 0), (x(w), h), (x(PLATE_CUT), h), (x(0), h - PLATE_CUT)],
                 fill=ui.linear(start, stop, [(0, rgb(tint, fill)), (0.6, rgb(tint, fill * 0.45)), (1, rgb(tint, fill * 0.1))])),
        pts_path("rail", [(x(0.75), 0), (x(0.75), h - PLATE_CUT), (x(PLATE_CUT), h - 0.75), (x(w), h - 0.75)], closed=False,
                 stroke=ui.stroke(ui.linear(start, stop, [(0, rgb(tint)), (0.7, rgb(tint, 0.6)), (1, rgb(tint, 0.12))]), 1.5)),
    ], {**ui.absolute(left=0, top=0, width=w, height=h), "display": ui.keyword(display)})


def arena(doc: HudDocument, r: int, b: int) -> dict:
    """One arena: an open plate holding its two players, a name in white and
    a score per row over a hairline. Your arena's rails turn aqua (and its
    whole plate when you follow it), your half of it takes an aqua band; a
    decided arena turns blue, its winner's score takes the value color and its
    loser drops to 0.45; the final's champion gains the marker. An arena with
    no one in it reads EMPTY."""
    x, y, w, h = arena_box(r, b)
    column = ARENAS[(r, b)][0]
    mirrored = column > 3
    final = r == 4
    prefix = f"tb{r}{b}"
    for name in ("done", "empty"):
        doc.boolean(f"{prefix}_{name}")
    doc.number(f"{prefix}_winner")
    doc.number(f"{prefix}_focus")
    for part in ("name1", "score1", "name2", "score2"):
        doc.string(f"{part}_round{r}_bracket{b}")
    done, empty, winner, focus = (S(f"{prefix}_done"), S(f"{prefix}_empty"), S(f"{prefix}_winner"), S(f"{prefix}_focus"))
    plain = open_plate(f"{prefix}-plain", w, h, "#8B964B", mirrored, fill=0.40 if final else 0.30)
    doc.show(plain["id"], AND(NOT(done), op("==", focus, 0)))
    mine = open_plate(f"{prefix}-mine", w, h, AQUA, mirrored, fill=0.22, display="none")
    doc.show(mine["id"], AND(NOT(done), op(">", focus, 0)))
    whole = vec(f"{prefix}-focus", [pts_path("f", [(0, 0), (w, 0), (w, h), (0, h)], fill=ui.solid(rgb(AQUA, 0.22)))],
                {**ui.absolute(left=0, top=0, width=w, height=h), "display": ui.keyword("none")})
    doc.show(whole["id"], AND(NOT(done), op("==", focus, 3)))
    decided = open_plate(f"{prefix}-done", w, h, FINISHED, mirrored, fill=0.40, display="none")
    doc.show(decided["id"], done)
    half = h / 2
    face = 16.0 if final else 13.0
    nodes = [plain, mine, whole, decided]
    words = []
    for player in (1, 2):
        top = (player - 1) * half
        band = vec(f"{prefix}-sel{player}", [pts_path("b", [(1.5, top + 1), (w, top + 1), (w, top + half - 1), (1.5, top + half - 1)],
                                                     fill=ui.solid(rgb(AQUA, 0.34)))],
                   {**ui.absolute(left=0, top=0, width=w, height=h), "display": ui.keyword("none")})
        doc.show(band["id"], AND(NOT(done), op("==", focus, player)))
        nodes.append(band)
        other = 3 - player
        lost = AND(done, op("==", winner, other))
        won = AND(done, op("==", winner, player))
        lead = 18.0 if final else 8.0
        name = ui.label(f"{prefix}-n{player}", "#str_230007", {**ui.absolute(left=lead, top=top, width=w - lead - 26, height=half),
                        **ui.typeface("lowpixel", face, half, [1, 1, 1, 0.9]), "white-space": ui.keyword("nowrap"),
                        "overflow": ui.keyword("hidden"), "text-overflow": ui.keyword("ellipsis")})
        doc.bind(f"{prefix}-n{player}.text", f"{prefix}-n{player}", "text", S(f"name{player}_round{r}_bracket{b}"))
        doc.bind(f"{prefix}-n{player}.tint", f"{prefix}-n{player}", "color", colour_of([(lost, [1, 1, 1, 0.45])], [1, 1, 1, 0.9]))
        score = ui.label(f"{prefix}-s{player}", "#str_230007", {**ui.absolute(right=6, top=top, width=20, height=half),
                         **ui.typeface("lowpixel", face + (2 if final else 0), half, [1, 1, 1, 0.7]), "text-align": ui.keyword("right"),
                         "white-space": ui.keyword("nowrap")})
        doc.bind(f"{prefix}-s{player}.text", f"{prefix}-s{player}", "text", S(f"score{player}_round{r}_bracket{b}"))
        doc.bind(f"{prefix}-s{player}.tint", f"{prefix}-s{player}", "color",
                 colour_of([(won, rgb(VALUE)), (lost, [1, 1, 1, 0.45])], [1, 1, 1, 0.7]))
        words += [name, score]
        if final:
            crown = vec(f"{prefix}-champion{player}", [pts_path("m", [(0, 0), (7, 0), (7, 7)], fill=ui.solid(rgb(VALUE)))],
                        {**ui.absolute(left=6, top=top + half / 2 - 4, width=7, height=7), "display": ui.keyword("none")})
            doc.show(crown["id"], won)
            words.append(crown)
    divider = vec(f"{prefix}-rule", [pts_path("r", [(PLATE_CUT, half - 0.5), (w - 4, half - 0.5)], closed=False,
                                              stroke=ui.stroke(ui.solid([1, 1, 1, 0.12]), 1))],
                  ui.absolute(left=0, top=0, width=w, height=h))
    group = ui.group(f"{prefix}-words", {**ui.FULL, "display": ui.keyword("block")}, [divider, *words])
    doc.show(group["id"], NOT(empty))
    blank = ui.label(f"{prefix}-empty", "#str_200952", {**ui.FULL, **ui.typeface("lowpixel", 12, h, [1, 1, 1, 0.35]),
                     "text-align": ui.keyword("center"), "white-space": ui.keyword("nowrap"), "display": ui.keyword("none")})
    doc.show(blank["id"], empty)
    return ui.group(prefix, {**ui.absolute(left=x, top=y, width=w, height=h), "display": ui.keyword("block"),
                             "opacity": ui.number(1)}, [*nodes, group, blank])


def connector(doc: HudDocument, ident: str, points: list, lit) -> dict:
    """A link of the chart: a 1.5 dp line at 0.22, lit to 0.70 once the
    arenas it leaves are decided."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    left, top = min(xs) - 1, min(ys) - 1
    node = vec(ident, [pts_path("l", [(px - left, py - top) for px, py in points], closed=False,
                                stroke=ui.stroke(ui.solid([1, 1, 1, 1]), 1.5))],
               {**ui.absolute(left=left, top=top, width=max(xs) - left + 1, height=max(ys) - top + 1), "opacity": ui.number(0.22)})
    doc.bind(f"{ident}.opacity", ident, "opacity", sel(lit, 0.7, 0.22))
    return node


def chart_links(doc: HudDocument) -> list:
    """Each later arena's two feeders: from each feeder's outer edge a stub
    to the gap's middle, a riser between them, and a stub into the arena.
    The semi-finals feed the final straight across."""
    links = []
    for (r, t) in sorted(ARENAS):
        if r == 1:
            continue
        feeders = [(r - 1, 2 * t - 1), (r - 1, 2 * t)]
        tx, ty, tw, th = arena_box(r, t)
        both = AND(S(f"tb{feeders[0][0]}{feeders[0][1]}_done"), S(f"tb{feeders[1][0]}{feeders[1][1]}_done"))
        if r == 4:
            for (fr, fb) in feeders:
                fx, fy, fw, fh = arena_box(fr, fb)
                centre = fy + fh / 2
                out, into = (fx + fw, tx) if fx < tx else (fx, tx + tw)
                links.append(connector(doc, f"tl{fr}{fb}", [(out, centre), (into, centre)], S(f"tb{fr}{fb}_done")))
            continue
        fx0 = arena_box(*feeders[0])[0]
        leading = fx0 < tx
        mid = (fx0 + PLATE_W + CHART_GAP / 2) if leading else (fx0 - CHART_GAP / 2)
        centres = []
        for (fr, fb) in feeders:
            fx, fy, fw, fh = arena_box(fr, fb)
            centre = fy + fh / 2
            centres.append(centre)
            out = fx + fw if leading else fx
            links.append(connector(doc, f"tl{fr}{fb}", [(out, centre), (mid, centre)], S(f"tb{fr}{fb}_done")))
        into = tx if leading else tx + tw
        links.append(connector(doc, f"tj{r}{t}", [(mid, centres[0]), (mid, centres[1])], both))
        links.append(connector(doc, f"ti{r}{t}", [(mid, ty + th / 2), (into, ty + th / 2)], both))
    return links


def chart_titles() -> list:
    """The round titles over their columns in Marine at 0.50; the final's in
    the value color."""
    titles = []
    for column in range(7):
        r = {0: 1, 1: 2, 2: 3, 3: 4, 4: 3, 5: 2, 6: 1}[column]
        final = r == 4
        w = FINAL_W if final else PLATE_W
        x = column_x(column)
        titles.append(ui.label(f"sbt-round{column}", ROUND_TITLES[r], {
            **ui.absolute(left=x - CHART_GAP / 2, top=0, width=w + CHART_GAP, height=16),
            **ui.typeface("marine", 13 if final else 11, 16, rgb(VALUE) if final else [1, 1, 1, 0.5]),
            "text-align": ui.keyword("center"), "white-space": ui.keyword("nowrap"), "overflow": ui.keyword("hidden")}))
    return titles


def bracket_chart(doc: HudDocument) -> dict:
    """Tourney (14.14): the bracket chart under the match line, answering
    the stock arenaInit, arenaDone and arenaFocus events."""
    doc.number("round")
    doc.number("bracket")
    doc.number("winner")
    doc.number("sel")
    doc.boolean("empty")
    nodes = [*chart_titles(), *chart_links(doc), *[arena(doc, r, b) for (r, b) in sorted(ARENAS)]]
    # The stock events address one arena by round and bracket.
    def at(r, b):
        return AND(op("==", S("round"), r), op("==", S("bracket"), b))
    init, finish, clear, focus = [], [], [], []
    for (r, b) in sorted(ARENAS):
        p = f"tb{r}{b}"
        init.append(when(at(r, b), [{"op": "setState", "values": {f"{p}_done": False, f"{p}_winner": 0, f"{p}_focus": 0,
                                                                     f"{p}_empty": S("empty")}}]))
        finish.append(when(at(r, b), [{"op": "setState", "values": {f"{p}_done": True, f"{p}_winner": S("winner"), f"{p}_focus": 0}}]))
        clear.append(when(NOT(S(f"{p}_done")), [{"op": "setState", "values": {f"{p}_focus": 0}}]))
        focus.append(when(AND(at(r, b), NOT(S(f"{p}_done"))), [{"op": "setState", "values": {
            f"{p}_focus": sel(op("==", S("sel"), 1), 1, sel(op("==", S("sel"), 2), 2, 3))}}]))
    doc.on("arenaInit", *init)
    doc.on("arenaDone", *finish)
    doc.on("arenaFocus", *clear, *focus)
    group = ui.group("sbt", {**ui.absolute(left=INSET, top=TREE_TOP, width=TOURNEY_W - 2 * INSET, height=CHART_H),
                             "display": ui.keyword("none")}, nodes)
    doc.show("sbt", op("==", S("gametype"), 2))
    return group


def scoreboard_document() -> dict:
    doc = HudDocument("openq4.hud.remastered.scoreboard")
    layout_state(doc)
    doc.number("oq4_sb_pitch", 16)
    doc.boolean("oq4_sb_kills")
    doc.string("oq4_sb_rank")
    for key in ("servername", "serverip", "servergametype", "servermap", "serverlimit", "servertimelimit", "timeleft"):
        doc.string(key)
    doc.boolean("infinity")
    doc.number("gametype")
    tourney = op("==", S("gametype"), 2)
    panels = ui.group("sb-panels", {**ui.absolute(left=INSET, top=LIST_TOP, right=INSET), "display": ui.keyword("block")},
                      [panel(doc, 0), panel(doc, 1), panel(doc, 2)])
    list_top = sel(tourney, round(TOURNEY_LIST_TOP, 3), LIST_TOP)
    doc.bind("sb-panels.top", "sb-panels", "top", list_top)
    heads = headings(doc)
    doc.bind("sb-headings.top", "sb-headings", "top", op("-", list_top, HEADINGS_H))
    match = match_line(doc, tourney)
    # The card is as tall as its lists: their top, each shown panel's gap,
    # band and rows, then the strip under them, centred over the view.
    lists = 0
    for p in range(3):
        rows = op("*", S(f"oq4_sb{p}_count"), op("*", S("oq4_sb_pitch"), U))
        lists = op("+", lists, sel(op(">=", S(f"oq4_sb{p}_kind"), 0), op("+", PANEL_GAP + BAND_H, rows), 0))
    height = op("+", op("+", list_top, lists), BOTTOM)
    width = sel(tourney, TOURNEY_W, CARD_W)
    card = ui.group("sb-card", {**ui.absolute(left=u(320) - CARD_W / 2, top=u(240) - CARD_MAX_H / 2, width=CARD_W, height=CARD_MAX_H),
                                "display": ui.keyword("block")},
                    [card_frame("sb-frame"), *card_header(doc, tourney), match, bracket_chart(doc), heads, panels, bottom_strip(doc)])
    doc.bind("sb-card.left", "sb-card", "left", op("-", u(320), op("/", width, 2)))
    doc.bind("sb-card.top", "sb-card", "top", op("-", u(240), op("/", height, 2)))
    doc.bind("sb-card.width", "sb-card", "width", width)
    doc.bind("sb-card.height", "sb-card", "height", height)
    board = full("sb-all", [card])
    doc.on("hudJoin", *doc.joins)
    doc.on("onInit", *doc.joins)
    root = full("scoreboard-root", [anchor(doc, "cc", [board], scale="hud.centerScale")])
    return doc.build(root, {"canvas": {"height": 720, "minWidth": 960},
                            "extensions": {"openq4": {"reference": "ui-visual-design.md 14.14", "stock": "guis/scoreboard.gui"}}})
