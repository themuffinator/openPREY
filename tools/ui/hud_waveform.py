"""The installed legacy radio/voice trace and hud.mtr's UV animation.

The 21 samples are the measured wavTable values from the stock material.
Centre scaling operates on UVs, so values above one reduce apparent height.
Keep its duplicate final .95 sample: the decl parser adds a separate wrap
sample, giving 21 intervals per 5/3 second period, not twenty.
"""
import build_retained_screens as ui
from remastered_hud_base import cancel, num, play, tr, u

WAVE_TABLE = (.95, .4, 1, .5, .8, 1, .6, 1.4, .95, .6, .75,
              1.2, .7, 1.3, .6, .8, .95, .6, 1, .7, .95)
WAVE_PERIOD = 1000 / .6


def waveform(doc, ident, width, height, colour):
    node = ui.picture(ident, "gfx/guis/hud/waveform.tga",
                      {**ui.absolute(left=0, top=0, width=u(width), height=u(height)),
                       "image-blend": ui.keyword("additive"), "image-color": ui.colour(colour),
                       "image-offset-x": num(0), "image-scale-y": num(WAVE_TABLE[0])}, fit="fill")
    keys = [(WAVE_PERIOD * i / len(WAVE_TABLE), num(value))
            for i, value in enumerate((*WAVE_TABLE, WAVE_TABLE[0]))]
    # The stock table interpolates uniformly across all 21 intervals. Avoid
    # the general HUD helper's 1 ms authored-start hold on this sampled trace.
    run = doc.timelines.add(ident + "-run", WAVE_PERIOD,
                       [tr(ident, "image-offset-x", [(0, num(0)), (WAVE_PERIOD, num(1))]),
                        tr(ident, "image-scale-y", keys)], iterations=0)
    # Establish ownership before restoring the base: Reduced Motion may have
    # already completed the old track. Restarting must not interpolate from
    # that stopped UV value for the entire first texture period.
    doc.joins.extend([play(run), cancel(run), play(run)])
    return node
