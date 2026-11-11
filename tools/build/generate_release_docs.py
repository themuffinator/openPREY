#!/usr/bin/env python3
"""Generate packaged HTML documentation for openPREY releases."""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit


ROOT_DOCS = (
    Path("README.md"),
    Path("BUILDING.md"),
    Path("TECHNICAL.md"),
    Path("LICENSING.md"),
)
COMMUNITY_DOCS = (
    Path(".github") / "CONTRIBUTING.md",
    Path(".github") / "CODE_OF_CONDUCT.md",
)
SAFE_LINK_SCHEMES = {
    "http",
    "https",
    "mailto",
}
REPOSITORY_BLOB_BASE = "https://github.com/themuffinator/openQ4/blob/main/"
REPOSITORY_TREE_BASE = "https://github.com/themuffinator/openQ4/tree/main/"
DEVELOPMENT_ROADMAP = Path("docs/dev/roadmap.md")


SITE_CSS = r"""
/* openPREY documentation portal. Styled after docs/dev/prey-ui-visual-design.md: steel glass over
   space, claw-cornered frames, side tabs for navigation and Prey's own display and body faces, which
   tools/assets/fonts/embed_atlas_fonts.py writes to assets/docs/fonts/ and this site ships in fonts/. */
@font-face{font-family:"openPREY Menu";src:url("fonts/openprey-menu.woff") format("woff");font-weight:400;font-style:normal;font-display:swap}
@font-face{font-family:"openPREY Default";src:url("fonts/openprey-default.woff") format("woff");font-weight:400;font-style:normal;font-display:swap}

:root {
  color-scheme: dark;
  --u: 1.1px;
  --space: #04060A;
  --rail: #B3C6E2;
  --nav: #B3CCE6;
  --nav-hover: #CCE6FF;
  --label: rgba(255, 255, 255, 0.9);
  --text: rgba(255, 255, 255, 0.86);
  --muted: #A6BAD4;
  --dim: #8798B0;
  --value: #B8C9E6;
  --button: #CCDEFA;
  --plate: #6F86A1;
  --row: #546579;
  --wash: rgba(166, 196, 230, 0.15);
  --separator: rgba(189, 207, 224, 0.35);
  --f-display: "openPREY Menu", "Eurostile Extended", "Microgramma", "Bahnschrift", sans-serif;
  --f-body: "openPREY Default", "Bahnschrift SemiCondensed", "Arial Narrow", sans-serif;
  --f-prose: "Bahnschrift", "Saira Condensed", "Roboto Condensed", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  --f-mono: "Cascadia Code", "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace;
  --claw-tl: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 128 128' preserveAspectRatio='none'%3E%3Cdefs%3E%3ClinearGradient id='b' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%23576272'/%3E%3Cstop offset='.55' stop-color='%233B4351'/%3E%3Cstop offset='1' stop-color='%232E3541'/%3E%3C/linearGradient%3E%3CradialGradient id='s'%3E%3Cstop offset='0' stop-color='%2314171B'/%3E%3Cstop offset='.72' stop-color='%23171B20'/%3E%3Cstop offset='1' stop-color='%23363E4A'/%3E%3C/radialGradient%3E%3CclipPath id='c'%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z'/%3E%3C/clipPath%3E%3C/defs%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z' fill='url(%23b)'/%3E%3Cellipse cx='43.5' cy='66.5' rx='16.5' ry='21.5' fill='url(%23s)'/%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z' fill='none' stroke='%23B3C6E2' stroke-width='14' clip-path='url(%23c)'/%3E%3C/svg%3E");
  --claw-tr: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 128 128' preserveAspectRatio='none'%3E%3Cdefs%3E%3ClinearGradient id='b' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%23576272'/%3E%3Cstop offset='.55' stop-color='%233B4351'/%3E%3Cstop offset='1' stop-color='%232E3541'/%3E%3C/linearGradient%3E%3CradialGradient id='s'%3E%3Cstop offset='0' stop-color='%2314171B'/%3E%3Cstop offset='.72' stop-color='%23171B20'/%3E%3Cstop offset='1' stop-color='%23363E4A'/%3E%3C/radialGradient%3E%3CclipPath id='c'%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg transform='translate(128 0) scale(-1 1)'%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z' fill='url(%23b)'/%3E%3Cellipse cx='43.5' cy='66.5' rx='16.5' ry='21.5' fill='url(%23s)'/%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z' fill='none' stroke='%23B3C6E2' stroke-width='14' clip-path='url(%23c)'/%3E%3C/g%3E%3C/svg%3E");
  --claw-bl: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 128 128' preserveAspectRatio='none'%3E%3Cdefs%3E%3ClinearGradient id='b' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%23576272'/%3E%3Cstop offset='.55' stop-color='%233B4351'/%3E%3Cstop offset='1' stop-color='%232E3541'/%3E%3C/linearGradient%3E%3CradialGradient id='s'%3E%3Cstop offset='0' stop-color='%2314171B'/%3E%3Cstop offset='.72' stop-color='%23171B20'/%3E%3Cstop offset='1' stop-color='%23363E4A'/%3E%3C/radialGradient%3E%3CclipPath id='c'%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg transform='translate(0 128) scale(1 -1)'%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z' fill='url(%23b)'/%3E%3Cellipse cx='43.5' cy='66.5' rx='16.5' ry='21.5' fill='url(%23s)'/%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z' fill='none' stroke='%23B3C6E2' stroke-width='14' clip-path='url(%23c)'/%3E%3C/g%3E%3C/svg%3E");
  --claw-br: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 128 128' preserveAspectRatio='none'%3E%3Cdefs%3E%3ClinearGradient id='b' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%23576272'/%3E%3Cstop offset='.55' stop-color='%233B4351'/%3E%3Cstop offset='1' stop-color='%232E3541'/%3E%3C/linearGradient%3E%3CradialGradient id='s'%3E%3Cstop offset='0' stop-color='%2314171B'/%3E%3Cstop offset='.72' stop-color='%23171B20'/%3E%3Cstop offset='1' stop-color='%23363E4A'/%3E%3C/radialGradient%3E%3CclipPath id='c'%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg transform='translate(128 128) scale(-1 -1)'%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z' fill='url(%23b)'/%3E%3Cellipse cx='43.5' cy='66.5' rx='16.5' ry='21.5' fill='url(%23s)'/%3E%3Cpath d='M47 0H128V7.5C116 9.5 103 14.5 93 18.5C89 42 84 74 71.5 106C64 115 36 117 17 104.5C6 96 1 79 2 60C3 42 10 28 19 19C28 10 37 3.5 47 0Z' fill='none' stroke='%23B3C6E2' stroke-width='14' clip-path='url(%23c)'/%3E%3C/g%3E%3C/svg%3E");
}

* {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
  background: var(--space);
}

body {
  margin: 0;
  min-height: 100vh;
  color: var(--text);
  font: 400 16.5px/1.68 var(--f-prose);
  background-color: var(--space);
  background-image:
    radial-gradient(1px 1px at 23px 41px, rgba(220, 232, 248, 0.7), transparent 1.5px),
    radial-gradient(1px 1px at 151px 97px, rgba(220, 232, 248, 0.4), transparent 1.5px),
    radial-gradient(1px 1px at 87px 183px, rgba(220, 232, 248, 0.55), transparent 1.5px),
    radial-gradient(1.5px 1.5px at 211px 13px, rgba(240, 248, 255, 0.8), transparent 2px),
    radial-gradient(1px 1px at 302px 211px, rgba(220, 232, 248, 0.3), transparent 1.5px),
    radial-gradient(1px 1px at 47px 263px, rgba(220, 232, 248, 0.28), transparent 1.5px),
    radial-gradient(1px 1px at 129px 307px, rgba(200, 214, 236, 0.35), transparent 1.5px);
  background-size: 331px 331px;
  background-attachment: fixed;
}

/* The portal rim bounds the leading edge of every page. */
body::before {
  content: "";
  position: fixed;
  z-index: -1;
  top: -10vh;
  left: calc(-1 * min(18vw, 260px));
  width: min(22vw, 320px);
  height: 120vh;
  border-radius: 50%;
  pointer-events: none;
  background: #000;
  box-shadow:
    0 0 0 1.5px #A4F9FE,
    0 0 0 5px rgba(47, 100, 220, 0.85),
    0 0 26px 10px rgba(47, 100, 220, 0.45);
}

a {
  color: var(--nav);
  text-decoration: underline;
  text-decoration-color: rgba(179, 198, 226, 0.4);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}

a:hover,
a:focus-visible {
  color: #FFFFFF;
  text-decoration-color: #FFFFFF;
}

:focus-visible {
  outline: 1.5px solid var(--rail);
  outline-offset: 3px;
}

img {
  max-width: 100%;
}

code,
pre,
kbd,
samp {
  font-family: var(--f-mono);
}

::selection {
  background: rgba(166, 186, 212, 0.3);
  color: #FFFFFF;
}

.shell {
  width: min(1400px, calc(100% - 32px));
  margin: 22px auto 48px;
}

/* Claw-cornered frames: a black body that stops 25 u inside each end, four mirrored claws and a
   1.5 u rail along the top and bottom. No side rails. */
.topbar,
.article,
.hero,
.catalog,
.footer {
  position: relative;
  isolation: isolate;
  padding: calc(18 * var(--u) + 14px) calc(25 * var(--u) + 18px);
}

.topbar::before,
.article::before,
.hero::before,
.catalog::before,
.footer::before {
  content: "";
  position: absolute;
  inset: calc(1 * var(--u)) calc(25 * var(--u)) 0;
  z-index: -1;
  background:
    linear-gradient(180deg, rgba(34, 42, 49, 0.55), rgba(34, 42, 49, 0) 160px),
    rgba(0, 0, 0, 0.72);
}

.topbar::after,
.article::after,
.hero::after,
.catalog::after,
.footer::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background:
    var(--claw-tl) left top / calc(38 * var(--u)) calc(32 * var(--u)) no-repeat,
    var(--claw-tr) right top / calc(38 * var(--u)) calc(32 * var(--u)) no-repeat,
    var(--claw-bl) left bottom / calc(38 * var(--u)) calc(32 * var(--u)) no-repeat,
    var(--claw-br) right bottom / calc(38 * var(--u)) calc(32 * var(--u)) no-repeat,
    linear-gradient(var(--rail), var(--rail)) center top / calc(100% - 76 * var(--u)) calc(1.53 * var(--u)) no-repeat,
    linear-gradient(var(--rail), var(--rail)) center bottom / calc(100% - 76 * var(--u)) calc(1.53 * var(--u)) no-repeat;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.brand {
  display: grid;
  gap: 2px;
}

.brand a {
  color: var(--nav);
  text-decoration: none;
}

.brand a:hover {
  color: var(--nav-hover);
}

.eyebrow {
  display: inline-block;
  font: 400 12px/1.5 var(--f-display);
  color: var(--dim);
}

.brand-title {
  font: 400 clamp(17px, 2.4vw, 23px)/1.3 var(--f-display);
  text-shadow: 1px 1px 0 #000;
}

.brand-subtitle {
  color: var(--muted);
  font-size: 0.95rem;
}

.action-row,
.hero-actions,
.hero-meta,
.article-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

/* 3-slice buttons: a curved slope on the leading end, a slanted chamfer on the trailing end, a plate
   that fades from the leading edge. Hover evens the fill and brightens the label to white. */
.button {
  --bp: polygon(11.4px 6%, calc(100% - 10.8px) 6%, calc(100% - 3.6px) 50%, calc(100% - 2.8px) 95%, 3.6px 95%, 2.2px 80%, 3.4px 50%, 5px 26%, 7.6px 12%);
  position: relative;
  isolation: isolate;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 6px 22px;
  background: var(--plate);
  clip-path: var(--bp);
  font: 400 16px/1.2 var(--f-body);
  color: var(--button);
  text-decoration: none;
  text-shadow: 1px 1px 0 #000;
}

.button::before {
  content: "";
  position: absolute;
  inset: 1.2px;
  z-index: -1;
  clip-path: var(--bp);
  background: linear-gradient(90deg, rgba(111, 134, 161, 0.77), rgba(111, 134, 161, 0.06)), #05080C;
}

.button.primary::before {
  background: linear-gradient(90deg, rgba(111, 134, 161, 0.95), rgba(111, 134, 161, 0.25)), #05080C;
}

.button:hover,
.button:focus-visible {
  color: #FFFFFF;
  outline: none;
}

.button:hover::before,
.button:focus-visible::before {
  background: linear-gradient(rgba(111, 134, 161, 0.3), rgba(111, 134, 161, 0.3)), #05080C;
}

.chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  background: var(--wash);
  border-left: 2px solid var(--rail);
  color: var(--value);
  font: 400 15px/1.5 var(--f-body);
}

.layout {
  display: grid;
  grid-template-columns: 270px minmax(0, 1fr) 240px;
  gap: 18px;
}

/* Side columns are tab containers: a separator outline round a shaded page, links as side tabs. */
.sidebar,
.toc {
  position: sticky;
  top: 18px;
  align-self: start;
  max-height: calc(100vh - 36px);
  overflow-y: auto;
  padding: 16px 14px;
  border: 1px solid var(--separator);
  background:
    linear-gradient(90deg, rgba(34, 42, 49, 0.93), rgba(34, 42, 49, 0.28) 30%, rgba(34, 42, 49, 0) 60%),
    linear-gradient(rgba(74, 82, 99, 0.1), rgba(74, 82, 99, 0.1)),
    rgba(0, 0, 0, 0.6);
}

.sidebar h2,
.toc h2 {
  margin: 0 0 12px;
  font: 400 15px/1.3 var(--f-display);
  color: var(--nav);
  text-align: center;
}

.nav-group + .nav-group {
  margin-top: 16px;
}

.nav-group h3 {
  margin: 0 0 8px;
  padding: 3px 10px;
  background: rgba(17, 26, 37, 0.6);
  border-top: 1px solid #6D7F95;
  border-bottom: 1px solid #6D7F95;
  font: 400 12px/1.5 var(--f-display);
  color: var(--dim);
  text-align: center;
}

.nav-links,
.toc-links {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 3px;
}

.nav-links a,
.toc-links a {
  display: block;
  padding: 6px 14px 6px 14px;
  background: rgba(62, 76, 97, 0.45);
  clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 50%, calc(100% - 8px) 100%, 0 100%);
  color: rgba(181, 201, 227, 0.8);
  font: 400 15px/1.35 var(--f-body);
  text-decoration: none;
}

.nav-links a:hover,
.toc-links a:hover {
  color: var(--button);
  background: rgba(98, 112, 130, 0.6);
}

.nav-links a.active,
.toc-links a.active {
  color: #FFFFFF;
  background: linear-gradient(90deg, #5A6E80, #3B4854 55%, #222A31);
  box-shadow: inset 0 1px 0 #A7BFD7, inset 0 -1px 0 #A7BFD7;
}

.toc-links ul {
  list-style: none;
  margin: 3px 0 0 10px;
  padding: 0 0 0 8px;
  display: grid;
  gap: 3px;
  border-left: 1px solid var(--separator);
}

.hero {
  margin-bottom: 0;
}

/* Picture frame: an outline only, rounded, in prey.frame.picture. */
.hero-banner {
  width: 100%;
  display: block;
  margin-bottom: 18px;
  padding: 4px;
  border: 2px solid #A7C4E8;
  border-radius: 10px;
  background: #000;
  box-shadow: 0 0 24px rgba(47, 100, 220, 0.22);
}

.hero h1,
.article-header h1 {
  margin: 0 0 12px;
  font: 400 clamp(18px, 2.5vw, 26px)/1.3 var(--f-display);
  color: var(--nav);
  text-shadow: 1px 1px 0 #000, 0 0 18px rgba(51, 128, 177, 0.35);
}

.hero p,
.article-header p {
  margin: 0 0 14px;
}

.hero .lead,
.article-header .lead {
  max-width: 820px;
  color: var(--label);
  font-size: 1.04rem;
}

.catalog {
  margin-top: 18px;
}

.catalog h2 {
  margin: 0 0 14px;
  font: 400 clamp(17px, 2.4vw, 22px)/1.3 var(--f-display);
  color: var(--nav);
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

/* Group boxes: a horizontal fade with a rim and rounded ends. */
.card {
  padding: 14px 18px 16px;
  background: linear-gradient(90deg, rgba(84, 101, 121, 0.5), rgba(84, 101, 121, 0.05));
  border: 1.5px solid rgba(84, 101, 121, 0.95);
  border-radius: 14px 14px 14px 14px / 18px;
}

.card h3 {
  margin: 0 0 10px;
  font: 400 15.5px/1.35 var(--f-display);
  color: var(--nav);
}

.card p {
  margin: 0 0 10px;
  color: var(--label);
}

.card ul {
  margin: 0;
  padding-left: 18px;
  color: var(--text);
}

.card li + li {
  margin-top: 6px;
}

.article-header {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--separator);
  margin-bottom: 18px;
}

.article-content {
  min-width: 0;
}

.article-content h1,
.article-content h2,
.article-content h3,
.article-content h4,
.article-content h5,
.article-content h6 {
  margin: 28px 0 12px;
  font-family: var(--f-display);
  font-weight: 400;
  line-height: 1.3;
  color: var(--nav);
  text-shadow: 1px 1px 0 #000;
}

/* Section headings sit on a header bar: a flat band with rims. */
.article-content h2 {
  padding: 5px 16px;
  font-size: 1.2rem;
  background: rgba(17, 26, 37, 0.6);
  border-top: 1px solid #6D7F95;
  border-bottom: 1px solid #6D7F95;
  border-radius: 10px 10px 10px 10px / 50%;
}

.article-content h3 {
  font-size: 1.05rem;
}

.article-content h4,
.article-content h5,
.article-content h6 {
  font-size: 0.95rem;
}

.article-content p {
  margin: 0 0 16px;
}

.article-content ul,
.article-content ol {
  margin: 0 0 16px;
  padding-left: 24px;
}

.article-content li + li {
  margin-top: 5px;
}

.article-content li::marker {
  color: #9AB1CA;
}

.article-content strong {
  color: #FFFFFF;
}

.article-content hr {
  border: 0;
  height: 1.5px;
  margin: 26px 0;
  background: linear-gradient(90deg, transparent, var(--rail), transparent);
  opacity: 0.6;
}

.article-content blockquote,
.article-content .admonition {
  margin: 18px 0;
  padding: 12px 16px;
  border-left: 2px solid var(--rail);
  background: var(--wash);
}

.article-content .admonition-title {
  margin: 0 0 6px;
  font: 400 0.9rem/1.4 var(--f-display);
  color: var(--nav);
}

/* Callout rails borrow from the world: Sphere green, portal blue, the hawk's red. */
.article-content .admonition.tip {
  border-left-color: #3FA37A;
}

.article-content .admonition.important {
  border-left-color: #2F64DC;
}

.article-content .admonition.warning,
.article-content .admonition.caution {
  border-left-color: #C2230A;
}

.article-content pre {
  margin: 16px 0;
  padding: 14px 16px;
  overflow-x: auto;
  border-left: 2px solid var(--rail);
  background: #05080C;
  color: var(--value);
  font-size: 0.88rem;
  line-height: 1.58;
}

.article-content code {
  padding: 0.08em 0.4em;
  background: var(--wash);
  color: var(--value);
  font-size: 0.88em;
}

.article-content pre code {
  padding: 0;
  background: transparent;
}

.article-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 18px 0;
  display: block;
  overflow-x: auto;
}

.article-content thead {
  background: var(--wash);
}

.article-content th {
  color: #FFFFFF;
  font: 400 15.5px/1.35 var(--f-body);
  border: 1px solid #000;
}

.article-content th,
.article-content td {
  padding: 9px 12px;
  text-align: left;
  vertical-align: top;
}

.article-content td {
  border-bottom: 1px solid rgba(84, 101, 121, 0.6);
}

.article-content tbody tr:nth-child(even) {
  background: rgba(84, 101, 121, 0.12);
}

.article-content details {
  margin: 18px 0;
  padding: 10px 16px;
  border-top: 1px solid var(--row);
  border-bottom: 1px solid var(--row);
  background: linear-gradient(90deg, rgba(84, 101, 121, 0.4), rgba(84, 101, 121, 0.04));
}

.article-content summary {
  cursor: pointer;
  color: var(--label);
  font: 400 16px/1.4 var(--f-body);
}

.article-content .task-box {
  display: inline-grid;
  place-items: center;
  width: 1rem;
  height: 1rem;
  margin-right: 0.45rem;
  border: 1px solid var(--value);
  background: #39424A;
  color: transparent;
  font-size: 0.75rem;
}

.article-content .task-box.done {
  color: #ABC5DD;
}

.article-content img {
  display: block;
  margin: 18px auto;
  border: 2px solid #A7C4E8;
  border-radius: 8px;
}

.article-content p[align="center"],
.article-content div[align="center"] {
  text-align: center;
}

.article-content sub {
  color: var(--muted);
}

.footer {
  margin-top: 18px;
  color: var(--muted);
  font-size: 0.92rem;
}

.footer p:last-child {
  margin-bottom: 0;
}

@media (max-width: 1180px) {
  .layout {
    grid-template-columns: 250px minmax(0, 1fr);
  }

  .toc {
    display: none;
  }
}

@media (max-width: 860px) {
  :root {
    --u: 0.85px;
  }

  .shell {
    width: calc(100% - 24px);
    margin-top: 14px;
  }

  body::before {
    display: none;
  }

  .topbar {
    align-items: start;
    flex-direction: column;
  }

  .layout,
  .card-grid {
    grid-template-columns: 1fr;
  }

  .sidebar,
  .toc {
    position: static;
    max-height: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  html {
    scroll-behavior: auto;
  }
}
"""


@dataclass(frozen=True)
class DocSpec:
    source_relative: Path
    output_relative: Path
    group: str
    title: str
    nav_title: str
    summary: str


@dataclass(frozen=True)
class GeneratedDocSite:
    output_root: Path
    index_path: Path
    page_count: int


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate packaged HTML documentation for an openPREY release."
    )
    parser.add_argument("--source-root", default=".", help="openPREY repository root.")
    parser.add_argument("--output-dir", required=True, help="Directory to populate with HTML docs.")
    parser.add_argument("--version", required=True, help="Release version string.")
    parser.add_argument("--platform", required=True, help="Target package platform.")
    parser.add_argument("--arch", required=True, help="Target package architecture.")
    return parser.parse_args(argv[1:])


def require_markdown_module() -> Any:
    try:
        import markdown as markdown_lib
    except ImportError as exc:
        raise RuntimeError(
            "Release HTML docs require the Python-Markdown package. "
            "Install it with: python -m pip install markdown"
        ) from exc
    return markdown_lib


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_output_root(source_root: Path, output_root: Path) -> None:
    source_root = source_root.resolve()
    raw_output_root = output_root
    output_root = output_root.resolve()
    output_anchor = Path(output_root.anchor).resolve()

    if raw_output_root.is_symlink():
        raise RuntimeError(f"refusing to generate release docs into a symlinked output directory: {raw_output_root}")
    if output_root == output_anchor:
        raise RuntimeError(f"refusing to replace filesystem root while generating docs: {output_root}")
    if output_root == source_root or is_relative_to(source_root, output_root):
        raise RuntimeError(
            "refusing to generate release docs into the source root or one of its parent directories: "
            f"{output_root}"
        )
    if is_relative_to(output_root, source_root):
        relative = output_root.relative_to(source_root)
        first_part = relative.parts[0] if relative.parts else ""
        if first_part not in {".tmp", ".install"} and not first_part.startswith("builddir"):
            raise RuntimeError(
                "refusing to replace a source-controlled repository directory while generating docs: "
                f"{output_root}"
            )
    if output_root.exists() and not output_root.is_dir():
        raise RuntimeError(f"release docs output path exists but is not a directory: {output_root}")


def validate_source_root(source_root: Path) -> Path:
    if source_root.is_symlink():
        raise RuntimeError(f"release docs source root must not be a symlink: {source_root}")
    resolved = source_root.resolve()
    if not resolved.is_dir():
        raise RuntimeError(f"release docs source root not found: {resolved}")
    return resolved


def require_regular_doc_source(path: Path, relative: Path) -> None:
    if path.is_symlink():
        raise RuntimeError(f"refusing to package symlinked documentation source: {relative.as_posix()}")
    if not path.is_file():
        raise RuntimeError(f"documentation source is not a regular file: {relative.as_posix()}")


def collect_doc_sources(source_root: Path) -> list[Path]:
    docs: list[Path] = []
    seen: set[str] = set()

    for relative in (*ROOT_DOCS, *COMMUNITY_DOCS):
        candidate = source_root / relative
        if candidate.exists() or candidate.is_symlink():
            require_regular_doc_source(candidate, relative)
            docs.append(relative)
            seen.add(relative.as_posix().lower())

    for base in (Path("docs/user"), Path("docs/dev")):
        base_path = source_root / base
        if not base_path.is_dir():
            continue
        for path in sorted(base_path.rglob("*")):
            relative = path.relative_to(source_root)
            if path.is_symlink():
                raise RuntimeError(f"refusing to package symlinked documentation source: {relative.as_posix()}")
            if path.suffix.lower() != ".md":
                continue
            if not path.is_file():
                continue
            key = relative.as_posix().lower()
            if key in seen:
                continue
            docs.append(relative)
            seen.add(key)

    return docs


def classify_group(relative: Path) -> str:
    if relative.parent == Path("."):
        return "Project"
    if relative.parts[0] == ".github":
        return "Project"
    if len(relative.parts) >= 2 and relative.parts[0] == "docs" and relative.parts[1] == "user":
        return "User Guides"
    if relative.parts[:3] == ("docs", "dev", "archive"):
        return "Planning Archive"
    if len(relative.parts) >= 3 and relative.parts[0] == "docs" and relative.parts[1] == "dev" and relative.parts[2] == "proposals":
        return "Research and Proposals"
    if len(relative.parts) >= 3 and relative.parts[0] == "docs" and relative.parts[1] == "dev" and relative.parts[2] == "legacy":
        return "Legacy Notes"
    return "Developer Guides"


def default_nav_title(relative: Path) -> str:
    if relative == DEVELOPMENT_ROADMAP:
        return "Development roadmap"
    if relative == Path("README.md"):
        return "Overview"
    if relative == Path("BUILDING.md"):
        return "Build Guide"
    if relative == Path("TECHNICAL.md"):
        return "Technical Reference"
    if relative == Path(".github") / "CONTRIBUTING.md":
        return "Contributing"
    if relative == Path(".github") / "CODE_OF_CONDUCT.md":
        return "Code of Conduct"

    stem = relative.stem.replace("-", " ").replace("_", " ").strip()
    if not stem:
        stem = relative.name
    return " ".join(part.capitalize() if part.islower() else part for part in stem.split())


def resolve_site_relative(source_relative: Path, target: str) -> str | None:
    """Resolve a relative link target against a document's site location.

    Returns the normalized root-relative posix path, or None when the target
    escapes the documentation root.
    """
    parts: list[str] = []
    combined = PurePosixPath(source_relative.parent.as_posix()) / target
    for part in combined.parts:
        if part == ".":
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def rewrite_markdown_links(
    text: str,
    *,
    source_relative: Path | None = None,
    rendered_sources: set[str] | None = None,
) -> str:
    pattern = re.compile(r"(!?\[(?:[^\[\]]|!\[[^\]]*\]\([^)]+\))+\]\()([^)]+)(\))")

    def replace(match: re.Match[str]) -> str:
        prefix, target, suffix = match.groups()
        stripped_target = target.strip()
        if stripped_target.startswith("#"):
            return match.group(0)

        parsed = urlsplit(stripped_target)
        if parsed.scheme:
            scheme = parsed.scheme.lower()
            if scheme not in SAFE_LINK_SCHEMES:
                return prefix + "#" + suffix
            return match.group(0)

        hash_suffix = ""
        if "#" in stripped_target:
            base, fragment = stripped_target.split("#", 1)
            stripped_target = base
            hash_suffix = "#" + fragment

        if stripped_target.lower().endswith(".md"):
            if rendered_sources is not None and source_relative is not None:
                resolved = resolve_site_relative(source_relative, stripped_target)
                if resolved is None or resolved.lower() not in rendered_sources:
                    # The target exists in the repository but is not part of the
                    # generated site; keep the link alive by pointing at the
                    # repository copy instead of a dead local page.
                    repo_target = resolved if resolved is not None else stripped_target
                    return prefix + REPOSITORY_BLOB_BASE + repo_target + hash_suffix + suffix
            stripped_target = stripped_target[:-3] + ".html"

        elif stripped_target.endswith("/") and source_relative is not None:
            # Source directories are browsed in the repository, rather than
            # copied into player documentation with compiler inputs.
            resolved = resolve_site_relative(source_relative, stripped_target)
            if resolved is not None:
                return prefix + REPOSITORY_TREE_BASE + resolved + hash_suffix + suffix

        return prefix + stripped_target + hash_suffix + suffix

    return pattern.sub(replace, text)


def copy_docs_asset_tree(source_root: Path, destination_root: Path) -> None:
    if source_root.is_symlink():
        raise RuntimeError(f"refusing to copy symlinked documentation asset directory: {source_root}")
    if not source_root.is_dir():
        return

    for path in sorted(source_root.rglob("*")):
        relative = path.relative_to(source_root)
        if path.is_symlink():
            raise RuntimeError(f"refusing to copy symlinked documentation asset: {relative.as_posix()}")
        destination = destination_root / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        else:
            raise RuntimeError(f"refusing to copy non-regular documentation asset: {relative.as_posix()}")


def copy_docs_auxiliary_file(source_root: Path, relative: Path, destination: Path) -> None:
    source = source_root / relative
    if source.is_symlink():
        raise RuntimeError(f"refusing to copy symlinked documentation auxiliary file: {relative.as_posix()}")
    if not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def convert_github_callouts(text: str) -> str:
    lines = text.splitlines()
    result: list[str] = []
    index = 0

    while index < len(lines):
        stripped = lines[index].strip()
        match = re.match(r"^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$", stripped)
        if match is None:
            result.append(lines[index])
            index += 1
            continue

        level = match.group(1).lower()
        result.append(f"!!! {level}")
        index += 1
        while index < len(lines) and lines[index].lstrip().startswith(">"):
            content = lines[index].lstrip()[1:]
            if content.startswith(" "):
                content = content[1:]
            if content:
                result.append("    " + content)
            else:
                result.append("")
            index += 1

    return "\n".join(result)


def convert_task_lists(text: str) -> str:
    result: list[str] = []
    pattern = re.compile(r"^(\s*[-*+]\s+)\[( |x|X)\]\s+(.*)$")

    for line in text.splitlines():
        match = pattern.match(line)
        if match is None:
            result.append(line)
            continue

        prefix, state, body = match.groups()
        classes = "task-box done" if state.lower() == "x" else "task-box"
        symbol = "&#10003;" if state.lower() == "x" else "&nbsp;"
        result.append(f'{prefix}<span class="{classes}">{symbol}</span> {body}')

    return "\n".join(result)


def prepare_markdown(
    text: str,
    *,
    source_relative: Path | None = None,
    rendered_sources: set[str] | None = None,
) -> str:
    normalized = text.replace("\r\n", "\n")
    normalized = re.sub(
        r"(?m)^<details(?![^>]*markdown=)",
        '<details markdown="1"',
        normalized,
    )
    normalized = re.sub(
        r"(?m)^<div(?![^>]*markdown=)",
        '<div markdown="1"',
        normalized,
    )
    normalized = rewrite_markdown_links(
        normalized,
        source_relative=source_relative,
        rendered_sources=rendered_sources,
    )
    normalized = convert_task_lists(normalized)
    normalized = convert_github_callouts(normalized)
    return normalized


def strip_markdown_preview(text: str) -> str:
    preview = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    preview = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", preview)
    preview = re.sub(r"`([^`]+)`", r"\1", preview)
    preview = re.sub(r"<[^>]+>", "", preview)
    preview = preview.replace("**", "").replace("__", "").replace("*", "").replace("_", "")
    preview = re.sub(r"\s+", " ", preview)
    return preview.strip()


def extract_title_and_summary(relative: Path, text: str) -> tuple[str, str]:
    lines = text.replace("\r\n", "\n").splitlines()

    title = default_nav_title(relative)
    for line in lines:
        match = re.match(r"^#\s+(.*)$", line.strip())
        if match is not None:
            title = strip_markdown_preview(match.group(1))
            break

    summary_lines: list[str] = []
    in_code_block = False
    title_found = False
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if not title_found:
            if re.match(r"^#\s+", stripped):
                title_found = True
            continue

        if not stripped:
            if summary_lines:
                break
            continue

        if stripped.startswith(("#", ">", "-", "*", "|", "<")):
            if summary_lines:
                break
            continue

        if re.match(r"^\d+\.\s+", stripped):
            if summary_lines:
                break
            continue

        summary_lines.append(stripped)

    summary = strip_markdown_preview(" ".join(summary_lines))
    return title, summary


def build_doc_specs(source_root: Path) -> list[DocSpec]:
    specs: list[DocSpec] = []
    for relative in collect_doc_sources(source_root):
        title, summary = extract_title_and_summary(
            relative,
            (source_root / relative).read_text(encoding="utf-8"),
        )
        if not summary and relative == Path("README.md"):
            summary = (
                "Project overview, runtime scope, compatibility goals, and the main "
                "documentation map for openPREY."
            )
        specs.append(
            DocSpec(
                source_relative=relative,
                output_relative=relative.with_suffix(".html"),
                group=classify_group(relative),
                title=title,
                nav_title=default_nav_title(relative) if relative == DEVELOPMENT_ROADMAP or relative.parent in (Path("."), Path(".github")) else title,
                summary=summary,
            )
        )
    # Keep the active plan first within developer navigation; retain the
    # established relative order of all other documents.
    specs.sort(key=lambda spec: spec.source_relative != DEVELOPMENT_ROADMAP)
    return specs


def relative_href(current_parent: Path, target: Path) -> str:
    return os.path.relpath(target, start=current_parent if current_parent != Path(".") else Path(".")).replace("\\", "/")


def render_sidebar(specs: list[DocSpec], current_output: Path) -> str:
    grouped: dict[str, list[DocSpec]] = {}
    for spec in specs:
        grouped.setdefault(spec.group, []).append(spec)

    group_order = (
        "Project",
        "User Guides",
        "Developer Guides",
        "Research and Proposals",
        "Legacy Notes",
        "Planning Archive",
    )

    sections: list[str] = []
    current_parent = current_output.parent
    for group in group_order:
        group_specs = grouped.get(group)
        if not group_specs:
            continue

        links = []
        for spec in group_specs:
            href = relative_href(current_parent, spec.output_relative)
            if spec.output_relative == current_output:
                links.append(
                    f'<li><a class="active" href="{html.escape(href)}">{html.escape(spec.nav_title)}</a></li>'
                )
            else:
                links.append(
                    f'<li><a href="{html.escape(href)}">{html.escape(spec.nav_title)}</a></li>'
                )

        sections.append(
            "\n".join(
                [
                    '<section class="nav-group">',
                    f"<h3>{html.escape(group)}</h3>",
                    '<ul class="nav-links">',
                    *links,
                    "</ul>",
                    "</section>",
                ]
            )
        )

    return "\n".join(sections)


def normalize_toc_tokens(tokens: list[dict[str, Any]], title: str) -> list[dict[str, Any]]:
    if len(tokens) == 1 and tokens[0].get("level") == 1:
        token_name = strip_markdown_preview(str(tokens[0].get("name", "")))
        if token_name == title:
            return list(tokens[0].get("children", []))
    return tokens


def render_toc_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""

    rendered: list[str] = ['<ul class="toc-links">']
    for item in items:
        heading_id = html.escape(str(item.get("id", "")))
        heading_name = strip_markdown_preview(str(item.get("name", "")))
        rendered.append(f'<li><a href="#{heading_id}">{html.escape(heading_name)}</a>')
        children = item.get("children") or []
        if children:
            rendered.append(render_toc_items(list(children)))
        rendered.append("</li>")
    rendered.append("</ul>")
    return "\n".join(rendered)


def render_doc_page(
    spec: DocSpec,
    specs: list[DocSpec],
    version: str,
    platform: str,
    arch: str,
    body_html: str,
    toc_tokens: list[dict[str, Any]],
) -> str:
    current_parent = spec.output_relative.parent
    css_href = relative_href(current_parent, Path("_static") / "site.css")
    docs_home_href = relative_href(current_parent, Path("index.html"))
    package_home_href = relative_href(current_parent, Path("..") / "README.html")
    overview_href = relative_href(current_parent, Path("README.html"))

    sidebar_html = render_sidebar(specs, spec.output_relative)
    toc_html = render_toc_items(normalize_toc_tokens(toc_tokens, spec.title))
    if not toc_html:
        toc_html = '<p class="brand-subtitle">This page has no generated section index.</p>'

    summary_html = (
        f'<p class="lead">{html.escape(spec.summary)}</p>'
        if spec.summary
        else '<p class="lead">Included in the packaged openPREY offline documentation set.</p>'
    )

    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="UTF-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            '  <meta name="color-scheme" content="dark">',
            f"  <title>{html.escape(spec.title)} | openPREY Documentation</title>",
            f'  <link rel="stylesheet" href="{html.escape(css_href)}">',
            "</head>",
            "<body>",
            '  <div class="shell">',
            '    <header class="topbar">',
            '      <div class="brand">',
            '        <span class="eyebrow">Packaged HTML documentation</span>',
            f'        <a class="brand-title" href="{html.escape(docs_home_href)}">openPREY Documentation</a>',
            f'        <div class="brand-subtitle">Release {html.escape(version)} · {html.escape(platform)} · {html.escape(arch)}</div>',
            "      </div>",
            '      <div class="action-row">',
            f'        <a class="button primary" href="{html.escape(docs_home_href)}">Docs Home</a>',
            f'        <a class="button" href="{html.escape(overview_href)}">Project Overview</a>',
            f'        <a class="button" href="{html.escape(package_home_href)}">Package Home</a>',
            '        <a class="button" href="https://github.com/themuffinator/openPREY">GitHub</a>',
            "      </div>",
            "    </header>",
            '    <div class="layout">',
            '      <aside class="sidebar">',
            '        <h2>Documentation</h2>',
            sidebar_html,
            "      </aside>",
            '      <main class="article">',
            '        <header class="article-header">',
            f'          <span class="eyebrow">{html.escape(spec.group)}</span>',
            f"          <h1>{html.escape(spec.title)}</h1>",
            summary_html,
            '          <div class="article-meta">',
            f'            <span class="chip">{html.escape(spec.source_relative.as_posix())}</span>',
            f'            <span class="chip">Release {html.escape(version)}</span>',
            "          </div>",
            "        </header>",
            f'        <article class="article-content">{body_html}</article>',
            "      </main>",
            '      <aside class="toc">',
            '        <h2>On This Page</h2>',
            toc_html,
            "      </aside>",
            "    </div>",
            '    <footer class="footer">',
            f'      <p>Offline release documentation generated from the openPREY repository sources for version <strong>{html.escape(version)}</strong>.</p>',
            f'      <p><a href="{html.escape(docs_home_href)}">Documentation home</a> | <a href="{html.escape(package_home_href)}">Package home</a> | <a href="https://www.darkmatter-quake.com">Website</a></p>',
            "    </footer>",
            "  </div>",
            "</body>",
            "</html>",
        ]
    )


def render_index_page(
    specs: list[DocSpec],
    version: str,
    platform: str,
    arch: str,
) -> str:
    grouped: dict[str, list[DocSpec]] = {}
    for spec in specs:
        grouped.setdefault(spec.group, []).append(spec)

    def render_group(group: str, description: str) -> str:
        links = grouped.get(group, [])
        if not links:
            return ""

        items = [
            f'<li><a href="{html.escape(spec.output_relative.as_posix())}">{html.escape(spec.nav_title)}</a></li>'
            for spec in links
        ]
        return "\n".join(
            [
                '<article class="card">',
                f'<span class="eyebrow">{html.escape(group)}</span>',
                f"<h3>{html.escape(description)}</h3>",
                '<ul>',
                *items,
                "</ul>",
                "</article>",
            ]
        )

    cards = [
        render_group("Project", "Core project guides and high-level references."),
        render_group("User Guides", "Runtime settings, gameplay-facing features, and troubleshooting."),
        render_group("Developer Guides", "Implementation notes, audits, and current engineering references."),
        render_group("Research and Proposals", "Long-form technical investigations and design proposals."),
        render_group("Legacy Notes", "Historical context and archived notes kept for reference."),
        render_group("Planning Archive", "Historical plans and proposals, superseded by the development roadmap."),
    ]
    cards = [card for card in cards if card]

    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="UTF-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            '  <meta name="color-scheme" content="dark">',
            "  <title>openPREY Documentation Portal</title>",
            '  <link rel="stylesheet" href="_static/site.css">',
            "</head>",
            "<body>",
            '  <div class="shell">',
            '    <header class="topbar">',
            '      <div class="brand">',
            '        <span class="eyebrow">Offline HTML documentation</span>',
            '        <a class="brand-title" href="index.html">openPREY Documentation Portal</a>',
            f'        <div class="brand-subtitle">Release {html.escape(version)} · {html.escape(platform)} · {html.escape(arch)} · {len(specs)} documents</div>',
            "      </div>",
            '      <div class="action-row">',
            '        <a class="button primary" href="README.html">Project Overview</a>',
            '        <a class="button" href="BUILDING.html">Build Guide</a>',
            '        <a class="button" href="TECHNICAL.html">Technical Reference</a>',
            '        <a class="button" href="../README.html">Package Home</a>',
            "      </div>",
            "    </header>",
            '    <section class="hero">',
            '      <img class="hero-banner" src="assets/docs/img/banner.png" alt="openPREY banner">',
            '      <span class="eyebrow">openPREY Release Documentation</span>',
            '      <h1>Full offline HTML docs, shipped with the release package.</h1>',
            '      <p class="lead">This package includes the project overview, build and technical references, user guides, developer notes, and proposal research converted into a browsable HTML site with internal links preserved.</p>',
            '      <div class="hero-actions">',
            '        <a class="button primary" href="README.html">Open Project Overview</a>',
            '        <a class="button" href="docs/user/light-grids.html">User Guide Example</a>',
            '        <a class="button" href="docs/dev/roadmap.html">Development roadmap</a>',
            '      </div>',
            '      <div class="hero-meta">',
            f'        <span class="chip">Release {html.escape(version)}</span>',
            f'        <span class="chip">{html.escape(platform)}</span>',
            f'        <span class="chip">{html.escape(arch)}</span>',
            '        <span class="chip">Generated from repository Markdown sources</span>',
            "      </div>",
            "    </section>",
            '    <section class="catalog">',
            "      <h2>Included Documentation</h2>",
            '      <div class="card-grid">',
            *cards,
            "      </div>",
            "    </section>",
            '    <footer class="footer">',
            '      <p>These pages are bundled directly into the release archive so the package remains self-documenting even when viewed offline.</p>',
            '      <p><a href="../README.html">Package home</a> | <a href="https://github.com/themuffinator/openPREY">Repository</a> | <a href="https://www.darkmatter-quake.com">Website</a></p>',
            "    </footer>",
            "  </div>",
            "</body>",
            "</html>",
        ]
    )


def generate_release_docs_site(
    *,
    source_root: Path,
    output_root: Path,
    version: str,
    platform: str,
    arch: str,
) -> GeneratedDocSite:
    source_root = validate_source_root(source_root)
    validate_output_root(source_root, output_root)
    output_root = output_root.resolve()

    markdown_lib = require_markdown_module()
    specs = build_doc_specs(source_root)
    if not specs:
        raise RuntimeError(f"no Markdown documentation sources were found under {source_root}")

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    (output_root / "_static").mkdir(parents=True, exist_ok=True)
    (output_root / "_static" / "site.css").write_text(SITE_CSS, encoding="utf-8")

    docs_assets_source = source_root / "assets" / "docs" / "img"
    if docs_assets_source.is_dir():
        docs_assets_dest = output_root / "assets" / "docs" / "img"
        copy_docs_asset_tree(docs_assets_source, docs_assets_dest)

    # Prey's display and body faces for site.css, as written by tools/assets/fonts/embed_atlas_fonts.py.
    copy_docs_asset_tree(source_root / "assets" / "docs" / "fonts", output_root / "_static" / "fonts")

    for auxiliary in (
        Path("LICENSE"),
        Path("LICENSES/PREY-SDK-EULA.rtf"),
        Path("LICENSES/DOOM-3-ADDITIONAL-TERMS.txt"),
        Path("LICENSES/DOOM-3-BFG-ADDITIONAL-TERMS.txt"),
        Path("src/game/LICENSE"),
    ):
        copy_docs_auxiliary_file(source_root, auxiliary, output_root / auxiliary)
    khronos_notice = Path("LICENSES") / "KHRONOS-GLES-MIT.txt"
    copy_docs_auxiliary_file(source_root, khronos_notice, output_root / khronos_notice)

    # Keep linked requirement/archive records, UI sources and licence notices
    # available offline. These are authored records/fixtures, not extracted art.
    for relative in (
        "LICENSES/RmlUi.txt", "LICENSES/JsonCpp.txt", "LICENSES/libtess2.txt",
        "LICENSES/openxr-sdk.txt", "LICENSES/MD4.txt", "LICENSES/glslang.txt",
        "subprojects/openxr.wrap",
        "docs/dev/performance-budgets.json",
        "docs/dev/android-device-budgets.json",
        "docs/dev/archive/2026-10-18/manifest.json",
        # The Prey Interface Atlas that docs/dev/prey-ui-visual-design.md links (section 14).
        "docs/dev/prey-ui/atlas/prey-interface-atlas.html",
        "subprojects/rmlui.wrap", "subprojects/packagefiles/libtess2/double-precision.patch",
        "subprojects/packagefiles/rmlui/masked-hit-test.patch",
        "subprojects/packagefiles/jsoncpp/subnormal-numbers.patch",
    ):
        auxiliary = Path(relative)
        copy_docs_auxiliary_file(source_root, auxiliary, output_root / auxiliary)

    rendered_sources = {spec.source_relative.as_posix().lower() for spec in specs}
    for spec in specs:
        raw_text = (source_root / spec.source_relative).read_text(encoding="utf-8")
        prepared_text = prepare_markdown(
            raw_text,
            source_relative=spec.source_relative,
            rendered_sources=rendered_sources,
        )
        markdown_engine = markdown_lib.Markdown(
            extensions=[
                "extra",
                "admonition",
                "sane_lists",
                "toc",
                "md_in_html",
            ],
            extension_configs={
                "toc": {
                    "permalink": False,
                }
            },
        )
        body_html = markdown_engine.convert(prepared_text)
        body_html = re.sub(r"<h1[^>]*>.*?</h1>\s*", "", body_html, count=1, flags=re.S)
        body_html = re.sub(r"<div align=\"center\">\s*</div>", "", body_html, flags=re.S)
        page_html = render_doc_page(
            spec,
            specs,
            version,
            platform,
            arch,
            body_html,
            list(markdown_engine.toc_tokens),
        )

        destination = output_root / spec.output_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(page_html, encoding="utf-8")

    index_path = output_root / "index.html"
    index_path.write_text(
        render_index_page(specs, version, platform, arch),
        encoding="utf-8",
    )

    return GeneratedDocSite(
        output_root=output_root,
        index_path=index_path,
        page_count=len(specs),
    )


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = generate_release_docs_site(
        source_root=Path(args.source_root),
        output_root=Path(args.output_dir),
        version=args.version,
        platform=args.platform,
        arch=args.arch,
    )
    print(f"Generated openPREY HTML docs: {result.index_path} ({result.page_count} pages)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
