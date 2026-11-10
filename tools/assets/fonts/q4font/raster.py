"""Analytic-coverage scanline rasteriser.

This is the Python twin of the C++ rasteriser the engine uses, and exists so the
generator can score a traced outline against the retail bitmap it came from.
Both implementations use the same signed-area accumulation: each edge deposits
its exact per-pixel area contribution into an accumulation buffer, and a running
sum along each scanline turns those deltas into coverage.  No supersampling is
involved, so the result is exact for polygons.
"""
from __future__ import annotations

import numpy as np

from .path import Path2D


def _accumulate_line(acc: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> None:
	"""Deposit one directed edge into the accumulation buffer."""
	height, width = acc.shape
	if y0 == y1:
		return

	direction = 1.0
	if y0 > y1:
		x0, y0, x1, y1 = x1, y1, x0, y0
		direction = -1.0

	dxdy = (x1 - x0) / (y1 - y0)
	y_start = max(0, int(np.floor(y0)))
	y_end = min(height, int(np.ceil(y1)))

	x = x0
	if y0 < y_start:
		x += dxdy * (y_start - y0)

	for y in range(y_start, y_end):
		# Vertical span of the edge inside this scanline.
		row_y0 = max(y0, float(y))
		row_y1 = min(y1, float(y + 1))
		dy = row_y1 - row_y0
		if dy <= 0.0:
			continue

		x_row0 = x0 + dxdy * (row_y0 - y0)
		x_row1 = x0 + dxdy * (row_y1 - y0)
		if x_row0 > x_row1:
			x_row0, x_row1 = x_row1, x_row0

		x_left = int(np.floor(x_row0))
		x_right = int(np.floor(x_row1))
		signed_dy = direction * dy

		if x_left == x_right:
			# Whole sub-span lives in a single pixel column.
			xmid = 0.5 * (x_row0 + x_row1)
			col = x_left
			if col < 0:
				if 0 < width:
					acc[y, 0] += signed_dy
				continue
			if col >= width:
				continue
			coverage = 1.0 - (xmid - col)
			acc[y, col] += signed_dy * coverage
			if col + 1 < width:
				acc[y, col + 1] += signed_dy * (1.0 - coverage)
			continue

		# The sub-span crosses column boundaries; split it proportionally.
		inv_dx = 1.0 / (x_row1 - x_row0)
		prev_t = 0.0
		for col in range(x_left, x_right + 1):
			boundary = min(float(col + 1), x_row1)
			t = (boundary - x_row0) * inv_dx
			t = min(1.0, max(0.0, t))
			seg = t - prev_t
			prev_t = t
			if seg <= 0.0:
				continue
			seg_x0 = max(x_row0, float(col))
			seg_x1 = min(x_row1, float(col + 1))
			xmid = 0.5 * (seg_x0 + seg_x1)
			contrib = signed_dy * seg
			if col < 0:
				if 0 < width:
					acc[y, 0] += contrib
				continue
			if col >= width:
				continue
			coverage = 1.0 - (xmid - col)
			acc[y, col] += contrib * coverage
			if col + 1 < width:
				acc[y, col + 1] += contrib * (1.0 - coverage)


def rasterize(path: Path2D, width: int, height: int, flatness: float = 0.05) -> np.ndarray:
	"""Rasterise ``path`` (y-down pixel space) into a float coverage image."""
	acc = np.zeros((height, width + 2), dtype=np.float64)
	for contour in path.flatten(flatness):
		count = len(contour)
		for index in range(count):
			x0, y0 = contour[index]
			x1, y1 = contour[(index + 1) % count]
			_accumulate_line(acc, x0, y0, x1, y1)

	coverage = np.cumsum(acc, axis=1)[:, :width]
	return np.clip(np.abs(coverage), 0.0, 1.0).astype(np.float32)


def coverage_error(traced: np.ndarray, source: np.ndarray) -> dict[str, float]:
	"""Compare a rasterised trace against the retail coverage it models."""
	if traced.shape != source.shape:
		raise ValueError(f"shape mismatch {traced.shape} vs {source.shape}")
	if traced.size == 0:
		return {"mae": 0.0, "max": 0.0, "iou": 1.0, "area_ratio": 1.0}

	diff = np.abs(traced - source)
	inter = np.minimum(traced, source).sum()
	union = np.maximum(traced, source).sum()
	source_area = float(source.sum())
	return {
		"mae": float(diff.mean()),
		"max": float(diff.max()),
		"iou": float(inter / union) if union > 0 else 1.0,
		"area_ratio": float(traced.sum() / source_area) if source_area > 0 else 1.0,
	}
