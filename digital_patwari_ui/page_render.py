"""Synthetic Fard page rendering for the beta UI.

The evidence viewer needs two things that a real citizen record must never
supply during development: a page image, and coordinates for the region a
given reading came from. This module produces both from an invented page
description, so no real land record is used as UI development data.

Evidence-region convention
--------------------------
``FieldObservation.evidence_region`` is typed ``str | None`` in the canonical
schema, deliberately free-form. This UI writes and reads ONE convention:

    "x,y,w,h"   four floats in 0..1, fractions of the page's width/height,
                origin at the top-left corner.

Anything that does not parse as four floats is treated as "no highlight
available" -- the evidence viewer still shows the page, the raw text and the
column reference. A missing highlight is never reported as a missing reading.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from xml.sax.saxutils import escape

PAGE_WIDTH = 1000
PAGE_HEIGHT = 1414

# Relative widths of the modern 8-column Fard layout, left to right:
# 1 Khewat, 2 Khatauni, 3 owners+shares, 4 cultivator, 5 irrigation,
# 6 Murabba/Khasra, 7 area, 8 Vishesh Kathan (remarks).
COLUMN_WEIGHTS = (0.07, 0.07, 0.20, 0.12, 0.08, 0.11, 0.13, 0.22)

COLUMN_HEADINGS = (
    ("1", "ਖੇਵਟ", "Khewat"),
    ("2", "ਖਤੌਨੀ", "Khatauni"),
    ("3", "ਮਾਲਕਾਨ", "Owners"),
    ("4", "ਕਾਸ਼ਤਕਾਰ", "Cultivator"),
    ("5", "ਸਿੰਜਾਈ", "Irrigation"),
    ("6", "ਮੁਰੱਬਾ/ਖਸਰਾ", "Murabba/Khasra"),
    ("7", "ਰਕਬਾ", "Area"),
    ("8", "ਵਿਸ਼ੇਸ਼ ਕਥਨ", "Remarks"),
)

MARGIN_X = 28
HEADER_TOP = 24
HEADER_HEIGHT = 132
COLUMN_HEADER_HEIGHT = 66


@dataclass(frozen=True)
class Cell:
    """One printed cell. ``col`` is the 1-based Fard column number."""

    col: int
    lines: tuple[str, ...] = ()
    span: int = 1
    blank: bool = False
    faint: bool = False  # rendered greyed, for a deliberately smudged reading


@dataclass(frozen=True)
class Row:
    row_id: str
    cells: tuple[Cell, ...]
    height: int = 116


@dataclass(frozen=True)
class PageSpec:
    page_number: int
    total_pages: int
    title_lines: tuple[str, ...]
    rows: tuple[Row, ...]
    footer: str = ""
    unreadable: bool = False  # renders a "could not be read" page surface
    regions: dict[str, str] = field(default_factory=dict)


def _column_x_bounds() -> list[tuple[float, float]]:
    usable = PAGE_WIDTH - (2 * MARGIN_X)
    bounds: list[tuple[float, float]] = []
    cursor = float(MARGIN_X)
    for weight in COLUMN_WEIGHTS:
        width = usable * weight
        bounds.append((cursor, cursor + width))
        cursor += width
    return bounds


def region_key(row_id: str, col: int) -> str:
    return f"{row_id}.c{col}"


def compute_regions(spec: PageSpec) -> dict[str, str]:
    """Map every cell to its "x,y,w,h" fractional page region."""
    bounds = _column_x_bounds()
    regions: dict[str, str] = {}
    y = HEADER_TOP + HEADER_HEIGHT + COLUMN_HEADER_HEIGHT
    for row in spec.rows:
        for cell in row.cells:
            start = bounds[cell.col - 1][0]
            end = bounds[min(cell.col + cell.span - 2, len(bounds) - 1)][1]
            regions[region_key(row.row_id, cell.col)] = format_region(
                start / PAGE_WIDTH,
                y / PAGE_HEIGHT,
                (end - start) / PAGE_WIDTH,
                row.height / PAGE_HEIGHT,
            )
        y += row.height
    return regions


def format_region(x: float, y: float, width: float, height: float) -> str:
    return ",".join(f"{value:.4f}" for value in (x, y, width, height))


def parse_region(value: str | None) -> tuple[float, float, float, float] | None:
    """Tolerant parse. Returns None for anything that is not four floats,
    so an unrecognised region degrades to "no highlight", never to an error."""
    if not value:
        return None
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        return None
    try:
        x, y, width, height = (float(part) for part in parts)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


def _text_element(x: float, y: float, text: str, *, size: int, weight: str = "400", fill: str = "#1d2b24", anchor: str = "start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" '
        f'font-family="Noto Sans Gurmukhi, Nirmala UI, Gurmukhi MN, Helvetica, Arial, sans-serif">'
        f"{escape(text)}</text>"
    )


def render_page_svg(spec: PageSpec) -> str:
    """Render one synthetic page as a standalone SVG string."""
    bounds = _column_x_bounds()
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PAGE_WIDTH} {PAGE_HEIGHT}" '
        f'width="{PAGE_WIDTH}" height="{PAGE_HEIGHT}" role="img" '
        f'aria-label="Synthetic Fard page {spec.page_number}">',
        f'<rect width="{PAGE_WIDTH}" height="{PAGE_HEIGHT}" fill="#fbfaf6"/>',
        f'<rect x="6" y="6" width="{PAGE_WIDTH - 12}" height="{PAGE_HEIGHT - 12}" fill="none" stroke="#c9c4b4" stroke-width="2"/>',
    ]

    if spec.unreadable:
        parts.append(
            f'<rect x="6" y="6" width="{PAGE_WIDTH - 12}" height="{PAGE_HEIGHT - 12}" fill="#efece2"/>'
        )
        parts.append(_text_element(PAGE_WIDTH / 2, PAGE_HEIGHT / 2 - 14, "ਇਹ ਸਫ਼ਾ ਪੜ੍ਹਿਆ ਨਹੀਂ ਜਾ ਸਕਿਆ", size=34, weight="600", fill="#7b7466", anchor="middle"))
        parts.append(_text_element(PAGE_WIDTH / 2, PAGE_HEIGHT / 2 + 32, "This page could not be read", size=28, fill="#7b7466", anchor="middle"))
        parts.append("</svg>")
        return "".join(parts)

    y = HEADER_TOP + 44
    for index, line in enumerate(spec.title_lines):
        parts.append(_text_element(
            PAGE_WIDTH / 2, y, line,
            size=30 if index == 0 else 22,
            weight="700" if index == 0 else "400",
            fill="#1d2b24" if index == 0 else "#4a5750",
            anchor="middle",
        ))
        y += 34

    grid_top = HEADER_TOP + HEADER_HEIGHT
    total_height = COLUMN_HEADER_HEIGHT + sum(row.height for row in spec.rows)

    for column_index, (number, gurmukhi, english) in enumerate(COLUMN_HEADINGS):
        start, end = bounds[column_index]
        centre = (start + end) / 2
        parts.append(
            f'<rect x="{start:.1f}" y="{grid_top}" width="{end - start:.1f}" '
            f'height="{COLUMN_HEADER_HEIGHT}" fill="#efeee6" stroke="#b9b3a2" stroke-width="1"/>'
        )
        parts.append(_text_element(centre, grid_top + 24, f"{number}. {gurmukhi}", size=16, weight="600", anchor="middle"))
        parts.append(_text_element(centre, grid_top + 46, english, size=14, fill="#5d6a62", anchor="middle"))

    row_top = grid_top + COLUMN_HEADER_HEIGHT
    for row in spec.rows:
        for cell in row.cells:
            start = bounds[cell.col - 1][0]
            end = bounds[min(cell.col + cell.span - 2, len(bounds) - 1)][1]
            parts.append(
                f'<rect x="{start:.1f}" y="{row_top}" width="{end - start:.1f}" '
                f'height="{row.height}" fill="{"#f6f4ec" if cell.blank else "none"}" '
                f'stroke="#b9b3a2" stroke-width="1"/>'
            )
            text_y = row_top + 30
            for line in cell.lines:
                parts.append(_text_element(
                    start + 10, text_y, line,
                    size=16,
                    fill="#9a9488" if cell.faint else "#1d2b24",
                ))
                text_y += 24
        row_top += row.height

    parts.append(
        f'<rect x="{MARGIN_X}" y="{grid_top}" width="{PAGE_WIDTH - 2 * MARGIN_X:.1f}" '
        f'height="{total_height}" fill="none" stroke="#8c8676" stroke-width="2"/>'
    )

    footer = spec.footer or f"Page {spec.page_number} of {spec.total_pages}"
    parts.append(_text_element(PAGE_WIDTH / 2, grid_top + total_height + 44, footer, size=18, fill="#5d6a62", anchor="middle"))
    parts.append(_text_element(
        PAGE_WIDTH / 2, grid_top + total_height + 74,
        "SYNTHETIC SAMPLE — not a real land record",
        size=15, fill="#a08a4e", anchor="middle",
    ))
    parts.append("</svg>")
    return "".join(parts)
