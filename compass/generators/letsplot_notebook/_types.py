"""LetsPlot notebook generator types.

Extends the notebook model with LetsPlot-specific knowledge:
- geom_* functions, aes(), ggplot(), ggsave()
- Chart output tracking (SVG/PNG files produced by ggsave)
- Scale and theme awareness
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from four.generators._types import Err, Ok, Result


@dataclass(frozen=True)
class Cell:
    """A single notebook cell.

    cell_type: 'code' or 'markdown'
    source: the cell content (Python code or markdown text)
    """
    cell_type: str   # 'code' | 'markdown'
    source: str | None = None


@dataclass(frozen=True)
class LetsPlotNotebookSpec:
    """Complete LetsPlot notebook specification.

    A notebook that demonstrates LetsPlot charting capabilities.
    Each code cell may produce chart artifacts via ggsave().

    Response format -- Python constructor with inline source:

    LetsPlotNotebookSpec(
        title="LetsPlot Scatter Plot Analysis",
        claim="Demonstrates geom_hex and geom_pointdensity for large scatter data.",
        cells=(
            Cell(cell_type="markdown",
                 source="# LetsPlot Scatter Plot Analysis\n\nThis notebook explores LetsPlot's capabilities..."),
            Cell(cell_type="code",
                 source="import numpy as np\nfrom lets_plot import *\nLetsPlot.set_theme(theme_light())"),
            Cell(cell_type="code",
                 source="np.random.seed(42)\nn = 50_000\nx, y = np.random.multivariate_normal([0, 0], [[1, 0.5], [0.5, 1]], n).T\ndata = {'x': x, 'y': y}"),
            Cell(cell_type="markdown",
                 source="## Hexagonal Binning\n\ngeom_hex bins points into hexagons..."),
            Cell(cell_type="code",
                 source="p = (ggplot(data, aes(x='x', y='y')) +\n     geom_hex(bins=[40, 40]) +\n     scale_fill_viridis())\nggsave(p, 'scatter_hex.svg', w=8, h=6, unit='in')"),
        ),
    )
    """

    title: str
    claim: str
    cells: tuple[Cell, ...]


# ============================================================================
# Patch types for targeted ouroboros
# ============================================================================


@dataclass(frozen=True)
class CellEdit:
    """A targeted edit within a cell: find old text, replace with new."""
    old: str
    new: str


@dataclass(frozen=True)
class CellPatch:
    """Patch for a single cell by index.

    If cell is set, replaces the entire cell.
    If edits is set, applies search-and-replace edits to the cell source.
    Exactly one of cell or edits must be provided.
    """
    index: int
    cell: Cell | None = None
    edits: tuple[CellEdit, ...] = ()


@dataclass(frozen=True)
class NotebookPatch:
    """A partial update to a LetsPlotNotebookSpec.

    Ouroboros returns this instead of the full spec. Each CellPatch
    targets a single cell by index with either full replacement or
    search-and-replace edits.

    NotebookPatch(
        cells=(
            CellPatch(index=2, edits=(
                CellEdit(old="text to find", new="replacement text"),
            )),
        ),
    )
    """
    cells: tuple[CellPatch, ...]


# ============================================================================
# Validators
# ============================================================================


def validate_spec_instance(spec: LetsPlotNotebookSpec) -> Result[LetsPlotNotebookSpec, str]:
    """Validate a LetsPlotNotebookSpec instance."""
    errors: list[str] = []
    if not spec.title:
        errors.append("title must be non-empty")
    if not spec.claim:
        errors.append("claim must be non-empty")
    if not spec.cells:
        errors.append("cells must be non-empty")
    for i, c in enumerate(spec.cells):
        if c.cell_type not in ("code", "markdown"):
            errors.append(f"cells[{i}].cell_type: must be 'code' or 'markdown'")
        if c.source is None:
            errors.append(f"cells[{i}].source: content is empty")
    code_cells = [c for c in spec.cells if c.cell_type == "code"]
    if not code_cells:
        errors.append("notebook must contain at least one code cell")

    # LetsPlot-specific: must import lets_plot
    letsplot_imported = False
    for c in code_cells:
        if c.source and "from lets_plot" in c.source:
            letsplot_imported = True
            break
    if not letsplot_imported:
        errors.append("notebook must import lets_plot (from lets_plot import *)")

    # Must use at least one geom_* function
    uses_geom = False
    for c in code_cells:
        if c.source and "geom_" in c.source:
            uses_geom = True
            break
    if not uses_geom:
        errors.append("notebook must use at least one geom_* function")

    if errors:
        return Err("; ".join(errors))
    return Ok(spec)


def apply_notebook_patch(
    spec: LetsPlotNotebookSpec,
    patch: NotebookPatch,
) -> Result[LetsPlotNotebookSpec, str]:
    """Apply a NotebookPatch to a LetsPlotNotebookSpec."""
    cells = list(spec.cells)
    errors: list[str] = []

    for cp in patch.cells:
        if cp.index < 0 or cp.index >= len(cells):
            errors.append(
                f"cells[{cp.index}]: index out of range "
                f"(notebook has {len(cells)} cells)"
            )
            continue

        if cp.cell is not None:
            cells[cp.index] = cp.cell
        else:
            source = cells[cp.index].source
            for edit in cp.edits:
                if edit.old not in source:
                    errors.append(
                        f"cells[{cp.index}]: old text not found: "
                        f"{edit.old[:80]}..."
                    )
                    continue
                source = source.replace(edit.old, edit.new, 1)
            cells[cp.index] = Cell(
                cell_type=cells[cp.index].cell_type,
                source=source,
            )

    if errors:
        return Err("; ".join(errors))

    return Ok(LetsPlotNotebookSpec(
        title=spec.title,
        claim=spec.claim,
        cells=tuple(cells),
    ))
