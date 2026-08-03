"""IO boundaries for the LetsPlot notebook generator.

G_letsplot: invoke model, return LetsPlotNotebookSpec
V_letsplot: structural -> AST -> exec (with lets-plot chart generation)
G'_letsplot: patch-based ouroboros
IO: emit .ipynb + chart artifacts
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from compass.generators._types import (
    AskFn,
    Err,
    GenerationContext,
    Ok,
    Result,
)
from compass.generators._invoke import (
    build_system_prompt,
    build_user_message,
    resolve_ask_fn,
)
from compass.generators._validation import (
    validate_python_sources,
)

from ._types import (
    Cell,
    LetsPlotNotebookSpec,
    NotebookPatch,
    apply_notebook_patch,
    validate_spec_instance,
)

logger = logging.getLogger(__name__)

_TYPES_SOURCE = (Path(__file__).parent / "_types.py").read_text()


# ---------------------------------------------------------------------------
# Model invocation
# ---------------------------------------------------------------------------


def invoke_model(
    ctx: GenerationContext,
    base_url: str = "",
    ask_fn: AskFn | None = None,
) -> Result:
    """Call the model and return a LetsPlotNotebookSpec. G_letsplot."""
    fn = resolve_ask_fn(base_url, ask_fn)

    system = build_system_prompt(
        ctx,
        _TYPES_SOURCE,
        role=(
            "You are an expert Jupyter notebook author specializing in "
            "LetsPlot (JetBrains/lets-plot), a Grammar of Graphics charting "
            "library for Python. You generate well-structured, executable "
            "notebooks with clear explanations, correct Python code, and "
            "beautiful LetsPlot charts."
        ),
        contract_preamble=(
            "Respond with a Python expression constructing "
            "LetsPlotNotebookSpec.\n"
            "See the docstring for the exact response format."
        ),
    )

    user = build_user_message(
        ctx,
        suffix_lines=(
            "Write a LetsPlotNotebookSpec(...) expression.",
            "Put source content INLINE in each Cell() — do NOT use source=None.",
            "No markdown fencing.",
            "",
            "Guidelines:",
            "- Start with a markdown cell containing the title as an H1 heading.",
            "- First code cell: imports (numpy, matplotlib Agg) then LetsPlot setup:\n"
            "  `from lets_plot import *`, `LetsPlot.setup_html()`, `LetsPlot.set_theme(theme_light())`.",
            "- Interleave markdown explanation with code cells.",
            "- Each chart code cell should end with ggsave() to export the chart, "
            "then return the plot object on its own line (e.g. `p`) so it renders inline in Jupyter.",
            "- Use geom_hex() or geom_pointdensity() for scatter > 10K points.",
            "- Use scale_fill_viridis() for density charts, scale_fill_hue() for categorical.",
            "- All code must execute without errors.",
            "- Use ggsave(p, 'filename.svg', w=8, h=6, unit='in') for exports.",
        ),
    )

    match fn(system, user):
        case Err() as e:
            return e
        case Ok(raw_text):
            pass

    # Parse Python-as-schema response
    try:
        spec = _parse_response(raw_text)
        return Ok(spec)
    except ValueError as e:
        return Err(str(e))


def _parse_response(raw_text: str) -> LetsPlotNotebookSpec:
    """Parse the model's Python constructor response into a spec.

    Supports inline source: Cell(cell_type="...", source="actual code here")
    """
    import re

    # Extract the constructor body — balance parens
    start_marker = "LetsPlotNotebookSpec("
    start_idx = raw_text.find(start_marker)
    if start_idx < 0:
        raise ValueError("No LetsPlotNotebookSpec constructor found in response")

    depth = 0
    end_idx = start_idx
    for i in range(start_idx, len(raw_text)):
        if raw_text[i] == '(':
            depth += 1
        elif raw_text[i] == ')':
            depth -= 1
            if depth == 0:
                end_idx = i
                break

    constructor_body = raw_text[start_idx + len(start_marker):end_idx]

    # Extract title and claim
    title_match = re.search(r"title\s*=\s*['\"](.*?)['\"]", constructor_body)
    claim_match = re.search(r"claim\s*=\s*['\"](.*?)['\"]", constructor_body)

    if not title_match:
        raise ValueError("Missing title in LetsPlotNotebookSpec")
    if not claim_match:
        raise ValueError("Missing claim in LetsPlotNotebookSpec")

    title = title_match.group(1)
    claim = claim_match.group(1)

    # Extract each Cell declaration by balancing parens
    cells: list[Cell] = []
    pos = 0
    while pos < len(constructor_body):
        cell_start = constructor_body.find("Cell(", pos)
        if cell_start < 0:
            break

        # Find matching closing paren
        depth = 0
        cell_end = cell_start
        for i in range(cell_start, len(constructor_body)):
            if constructor_body[i] == '(':
                depth += 1
            elif constructor_body[i] == ')':
                depth -= 1
                if depth == 0:
                    cell_end = i
                    break

        cell_body = constructor_body[cell_start + 5:cell_end]  # strip "Cell(" and ")"

        # Extract cell_type
        ct_match = re.search(r"cell_type\s*=\s*['\"](\w+)['\"]", cell_body)
        if not ct_match:
            pos = cell_end + 1
            continue
        cell_type = ct_match.group(1)

        # Extract source — handle source=None and source="..."
        src_match = re.search(r"source\s*=\s*(None|['\"])", cell_body)
        if not src_match:
            pos = cell_end + 1
            continue

        src_val = src_match.group(1)
        if src_val == "None":
            raise ValueError(
                f"Cell with cell_type={cell_type} has source=None. "
                f"All cells must have inline source content."
            )

        # src_val is the opening quote — find matching closing quote
        # cell_body is a slice of constructor_body starting at (cell_start + 5)
        quote_char = src_val
        base_offset = cell_start + 5  # where cell_body starts in constructor_body
        source_start = base_offset + src_match.end()

        source_end = None
        i = source_start
        while i < len(constructor_body):
            ch = constructor_body[i]
            if ch == '\\' and i + 1 < len(constructor_body):
                i += 2  # skip escaped character
                continue
            if ch == quote_char:
                source_end = i
                break
            i += 1

        if source_end is None:
            raise ValueError(f"Unclosed source string in Cell declaration")

        source = constructor_body[source_start:source_end]
        # Decode Python string escape sequences (\n, \t, \", etc.)
        source = source.encode().decode('unicode_escape')
        cells.append(Cell(cell_type=cell_type, source=source))
        pos = cell_end + 1

    if not cells:
        raise ValueError("No cells found in LetsPlotNotebookSpec")

    return LetsPlotNotebookSpec(
        title=title,
        claim=claim,
        cells=tuple(cells),
    )


# ---------------------------------------------------------------------------
# Validation pipeline -- V_letsplot
# ---------------------------------------------------------------------------


def validate_notebook(spec: LetsPlotNotebookSpec) -> Result[LetsPlotNotebookSpec, str]:
    """Full V_letsplot pipeline. Cheapest first:

    1. Structural: validate_spec_instance
    2. Semantic: ast.parse() every code cell
    3. Executive: exec() every code cell (generates actual charts)
    """
    # 1. Structural
    match validate_spec_instance(spec):
        case Err(e):
            return Err(e)

    # 1a. Structural: import cell must have LetsPlot setup
    match _validate_setup_cell(spec):
        case Err(e):
            return Err(e)

    # 1b. Structural: chart cells must return plot for inline rendering
    match _validate_inline_rendering(spec):
        case Err(e):
            return Err(e)

    code_sources = tuple(
        c.source for c in spec.cells if c.cell_type == "code"
    )

    # 2. Semantic: syntax check all code cells
    match validate_python_sources(code_sources, label="cells"):
        case Err(e):
            return Err(e)

    logger.info("All %d code cells parse cleanly", len(code_sources))

    # 3. Executive: exec each code cell in sequence
    match _exec_notebook(spec):
        case Err(e):
            return Err(e)
        case Ok(_):
            pass

    logger.info("All code cells executed successfully")
    return Ok(spec)


def _validate_setup_cell(spec: LetsPlotNotebookSpec) -> Result[None, str]:
    """Check the import cell has proper LetsPlot setup."""
    code_cells = [c for c in spec.cells if c.cell_type == "code"]
    if not code_cells:
        return Err("No code cells found")

    first_code = code_cells[0].source

    checks = {
        "from lets_plot import *": "import lets_plot",
        "LetsPlot.set_theme": "set theme",
        "LetsPlot.setup_html": "setup_html() for inline rendering",
    }

    missing = [
        desc for pattern, desc in checks.items() if pattern not in first_code
    ]
    if missing:
        return Err(
            f"cells[0] (import cell) is missing: {', '.join(missing)}. "
            f"Add these lines: `from lets_plot import *`, "
            f"`LetsPlot.setup_html()`, `LetsPlot.set_theme(theme_light())`"
        )

    return Ok(None)


def _verify_chart_render(
    source: str,
    namespace: dict[str, Any],
    cell_idx: int,
) -> Result[None, str]:
    """Verify that a chart cell's last expression is a renderable PlotSpec.

    Checks:
    1. Last expression variable exists in namespace
    2. Object is a lets_plot PlotSpec (has _repr_html_)
    3. _repr_html_() produces HTML containing 'lets-plot' script tag
    """
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return Ok(None)  # Can't verify, AST check will catch it

    if not tree.body:
        return Ok(None)

    last = tree.body[-1]
    if not isinstance(last, ast.Expr):
        return Ok(None)

    # Extract variable name from last expression
    var_name = None
    if isinstance(last.value, ast.Name):
        var_name = last.value.id
    elif isinstance(last.value, ast.Call):
        func = last.value.func
        # Handle p.show() — extract base name
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            var_name = func.value.id

    if not var_name:
        return Ok(None)

    # Look up in namespace
    obj = namespace.get(var_name)
    if obj is None:
        return Err(f"cells[{cell_idx}]: variable '{var_name}' not found after exec")

    # Verify it's a renderable plot object
    if not hasattr(obj, "_repr_html_"):
        return Err(
            f"cells[{cell_idx}]: '{var_name}' has no _repr_html_ — "
            f"not a displayable lets-plot PlotSpec (got {type(obj).__name__})"
        )

    try:
        html = obj._repr_html_()
    except Exception as exc:
        return Err(
            f"cells[{cell_idx}]: _repr_html_() raised {type(exc).__name__}: {exc}"
        )

    if not html or "lets-plot" not in html.lower():
        return Err(
            f"cells[{cell_idx}]: '{var_name}._repr_html_()' does not contain 'lets-plot' — "
            f"chart may not render inline in Jupyter"
        )

    return Ok(None)


def _validate_inline_rendering(spec: LetsPlotNotebookSpec) -> Result[None, str]:
    """Check chart cells return the plot object for inline Jupyter rendering."""
    import ast

    for i, cell in enumerate(spec.cells):
        if cell.cell_type != "code":
            continue
        src = cell.source.strip()
        if "ggsave" not in src:
            continue

        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue  # will be caught by AST validation

        # Last statement should be an Expression (bare plot object), not an Expr(Call)
        if not tree.body:
            return Err(f"cells[{i}]: chart cell has ggsave but is empty")

        last = tree.body[-1]
        if isinstance(last, ast.Expr) and isinstance(last.value, ast.Name):
            continue  # good — e.g. `p` or `grid` at end

        if isinstance(last, ast.Expr) and isinstance(last.value, ast.Call):
            func = last.value.func
            # Accept p.show() as valid — lib author confirms this works
            if isinstance(func, ast.Attribute) and func.attr == "show":
                continue  # good — e.g. `p.show()`
            name = ast.unparse(func) if hasattr(ast, "unparse") else "call"
            return Err(
                f"cells[{i}]: chart cell ends with `{name}` call — "
                f"add the plot object (e.g. `p`) or call `p.show()` so it renders inline in Jupyter"
            )

        return Err(
            f"cells[{i}]: chart cell with ggsave doesn't end with a bare plot object — "
            f"add `p` (or whatever the plot variable is) as the last line"
        )

    return Ok(None)


def _exec_notebook(spec: LetsPlotNotebookSpec) -> Result[None, str]:
    """Execute all code cells in sequence, sharing a namespace.

    Sets up matplotlib Agg backend and lets-plot output directory.
    Captures stdout/stderr to catch warnings, verifies ggsave output files,
    and validates that chart cells produce renderable PlotSpec objects.
    """
    import io
    import matplotlib
    import sys
    matplotlib.use("Agg")

    # Create output directory for chart artifacts
    output_dir = Path("lets-plot-images")
    output_dir.mkdir(exist_ok=True)

    namespace: dict[str, Any] = {
        "__name__": "__notebook__",
        "__output_dir__": str(output_dir),
    }

    # Track which ggsave calls should produce files
    saved_files: list[Path] = []

    for i, cell in enumerate(spec.cells):
        if cell.cell_type != "code":
            continue
        if not cell.source.strip():
            continue

        # Capture stdout and stderr
        old_stdout, old_stderr = sys.stdout, sys.stderr
        buf_stdout, buf_stderr = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = buf_stdout, buf_stderr

        try:
            exec(compile(cell.source, f"<cell {i}>", "exec"), namespace)  # noqa: S102
        except Exception as exc:
            sys.stdout, sys.stderr = old_stdout, old_stderr
            stderr_text = buf_stderr.getvalue()
            extra = f"\nstderr: {stderr_text}" if stderr_text else ""
            return Err(f"cells[{i}]: {type(exc).__name__}: {exc}{extra}")
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

        # Check stderr for warnings
        stderr_text = buf_stderr.getvalue().strip()
        if stderr_text:
            # Filter out benign warnings
            skip_patterns = ("DeprecationWarning", "FutureWarning", "Matplotlib is building")
            if not any(p in stderr_text for p in skip_patterns):
                return Err(
                    f"cells[{i}]: stderr warning during execution: {stderr_text[:500]}"
                )

        # Track ggsave calls — extract filenames from source
        import ast
        try:
            tree = ast.parse(cell.source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
                    if func_name == "ggsave" and node.args:
                        # Second arg is the filename
                        if len(node.args) >= 2:
                            fname_node = node.args[1]
                            if isinstance(fname_node, ast.Constant) and isinstance(fname_node.value, str):
                                fname = fname_node.value
                                # Resolve relative path
                                if fname.startswith("/"):
                                    saved_files.append(Path(fname))
                                else:
                                    saved_files.append(Path(fname))
        except SyntaxError:
            pass  # AST check already passed, this is just best-effort

        # Verify chart cells produce renderable PlotSpec objects
        if "ggsave" in cell.source:
            match _verify_chart_render(cell.source, namespace, i):
                case Err(e):
                    return Err(e)

    # Verify ggsave files were actually created
    missing_files = []
    for f in saved_files:
        if not f.exists():
            # Try in lets-plot-images/ subdirectory (default lets-plot behavior)
            alt = output_dir / f.name
            if not alt.exists():
                missing_files.append(str(f))

    if missing_files:
        return Err(
            f"ggsave() did not produce expected files: {', '.join(missing_files)}"
        )

    return Ok(None)


# ---------------------------------------------------------------------------
# Ouroboros -- patch-based
# ---------------------------------------------------------------------------


def ouroboros_notebook(
    spec: LetsPlotNotebookSpec,
    error: str,
    ctx: GenerationContext,
    base_url: str = "",
    ask_fn: AskFn | None = None,
) -> LetsPlotNotebookSpec | None:
    """G'_letsplot: model sees prior notebook + error, returns a NotebookPatch."""
    fn = resolve_ask_fn(base_url, ask_fn)

    cell_listing: list[str] = []
    for i, cell in enumerate(spec.cells):
        cell_listing.append(f"### Cell {i} ({cell.cell_type})")
        cell_listing.append(cell.source)

    system_parts = [
        "You are correcting a LetsPlot Jupyter notebook you previously generated.",
        f"Notebook: {spec.title}",
        "",
        "You will receive your prior notebook cells and an error.",
        "Write a NotebookPatch(...) expression with targeted edits.",
        "Each patch targets a cell by index with either full replacement or search-and-replace edits.",
        "Only include the cells that need to change.",
        "",
        "NotebookPatch format (targeted edits -- preferred for surgical changes):",
        "NotebookPatch(",
        "    cells=(",
        "        CellPatch(index=2, edits=(",
        '            CellEdit(old="exact text to find", new="replacement text"),',
        "        )),",
        "    ),",
        ")",
        "",
        "NotebookPatch format (full cell replacement):",
        'CellPatch(index=2, cell=Cell(cell_type="code", source="..."))',
        "",
        "Rules:",
        "- Use edits for surgical changes. Use cell for full replacement.",
        "- 'old' must be an EXACT substring of the current cell source.",
        "- 'old' should include enough surrounding context to be unique.",
        "- Each cell patch must have either 'edits' or 'cell', not both.",
        "- Use matplotlib.use('Agg') before pyplot imports if plotting.",
        "- Use ggsave() for chart exports, not plt.show().",
        "- After ggsave(), add the plot object on its own line (e.g. `p`) for inline Jupyter rendering.",
        "- No markdown fencing, no explanation.",
    ]

    user_parts = [
        f"# Your notebook: {spec.title} ({len(spec.cells)} cells)",
        "",
        "\n".join(cell_listing),
        "",
        "# Error",
        "",
        error,
        "",
        "Write a NotebookPatch(...) expression with targeted edits to fix this error.",
        "No markdown fencing.",
    ]

    match fn("\n".join(system_parts), "\n".join(user_parts)):
        case Err(e):
            logger.warning("Ouroboros model error: %s", e)
            return None
        case Ok(raw_text):
            pass

    try:
        patch = _parse_patch_response(raw_text)
    except ValueError as e:
        logger.warning("Ouroboros parse error: %s", e)
        return None

    total_edits = sum(len(cp.edits) for cp in patch.cells)
    total_replacements = sum(1 for cp in patch.cells if cp.cell is not None)
    logger.info(
        "Ouroboros patch: %d cell(s), %d edit(s), %d replacement(s): indices %s",
        len(patch.cells), total_edits, total_replacements,
        [cp.index for cp in patch.cells],
    )

    match apply_notebook_patch(spec, patch):
        case Err(e):
            logger.warning("Ouroboros patch apply failed: %s", e)
            return None
        case Ok(corrected):
            return corrected


def _parse_patch_response(raw_text: str) -> NotebookPatch:
    """Parse NotebookPatch from model response."""
    import re

    # Extract CellPatch entries
    # CellPatch(index=N, edits=(CellEdit(old="...", new="..."),))
    # or CellPatch(index=N, cell=Cell(cell_type="code", source="..."))

    patches: list[CellPatch] = []

    # Pattern for CellPatch with edits
    edit_pattern = re.compile(
        r"CellPatch\(\s*index\s*=\s*(\d+)\s*,\s*edits\s*=\s*\((.*?)\)\s*\)",
        re.DOTALL,
    )
    for m in edit_pattern.finditer(raw_text):
        idx = int(m.group(1))
        edits_str = m.group(2)
        edits: list[tuple[str, str]] = []
        # CellEdit(old="...", new="...")
        for em in re.finditer(
            r"CellEdit\(\s*old\s*=\s*['\"](.*?)['\"]\s*,\s*new\s*=\s*['\"](.*?)['\"]",
            edits_str, re.DOTALL,
        ):
            edits.append((em.group(1), em.group(2)))
        if edits:
            patches.append(CellPatch(
                index=idx,
                edits=tuple(CellEdit(old=o, new=n) for o, n in edits),
            ))

    # Pattern for CellPatch with full cell replacement
    cell_pattern = re.compile(
        r"CellPatch\(\s*index\s*=\s*(\d+)\s*,\s*cell\s*=\s*Cell\(\s*"
        r"cell_type\s*=\s*['\"](\w+)['\"]"
        r"(?:\s*,\s*source\s*=\s*['\"](.*?)['\"])?\s*\)",
        re.DOTALL,
    )
    for m in cell_pattern.finditer(raw_text):
        idx = int(m.group(1))
        cell_type = m.group(2)
        source = m.group(3)
        # Skip if already matched by edit pattern
        if not any(p.index == idx for p in patches):
            patches.append(CellPatch(
                index=idx,
                cell=Cell(cell_type=cell_type, source=source),
            ))

    if not patches:
        raise ValueError("No valid CellPatch entries found in response")

    return NotebookPatch(cells=tuple(patches))


# ---------------------------------------------------------------------------
# Emit -- write notebook to disk as .ipynb
# ---------------------------------------------------------------------------


def _cell_to_ipynb(cell: Cell, outputs: list[dict] | None = None) -> dict:
    """Convert a Cell to Jupyter notebook cell format."""
    source_lines = cell.source.splitlines(keepends=True)
    if source_lines and not source_lines[-1].endswith("\n"):
        source_lines[-1] = source_lines[-1]

    base = {
        "cell_type": cell.cell_type,
        "metadata": {},
        "source": source_lines,
    }

    if cell.cell_type == "code":
        base["execution_count"] = None
        base["outputs"] = outputs if outputs is not None else []

    return base


def emit_notebook(
    spec: LetsPlotNotebookSpec,
    output_dir: Path,
    version: int = 0,
) -> Path:
    """Write a LetsPlotNotebookSpec to disk as a .ipynb file.

    Executes all code cells, captures outputs, and embeds PNG images
    for GitHub rendering (GitHub strips <script> tags).
    """
    import ast
    import base64
    import glob as glob_mod
    import io
    import os
    import matplotlib
    import sys
    matplotlib.use("Agg")

    output_dir.mkdir(parents=True, exist_ok=True)

    safe_title = "".join(
        c if c.isalnum() or c in " _-" else "_"
        for c in spec.title
    ).strip().replace(" ", "_").lower()

    if version > 0:
        filename = f"{safe_title}_v{version}.ipynb"
    else:
        filename = f"{safe_title}.ipynb"

    # Execute cells and capture outputs
    charts_dir = Path("lets-plot-images")
    charts_dir.mkdir(exist_ok=True)

    namespace: dict[str, Any] = {
        "__name__": "__notebook__",
        "__output_dir__": str(charts_dir),
    }

    cell_outputs: list[list[dict]] = []
    exec_count = 0

    # Track SVG files created during execution so we can associate them with cells
    all_svg_files: set[str] = set()

    for cell in spec.cells:
        if cell.cell_type != "code":
            cell_outputs.append([])
            continue

        old_stdout, old_stderr = sys.stdout, sys.stderr
        buf_stdout, buf_stderr = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = buf_stdout, buf_stderr

        try:
            exec(compile(cell.source, f"<cell>", "exec"), namespace)  # noqa: S102
            exec_count += 1
        except Exception as exc:
            exec_count = 0
            out = [{
                "output_type": "error",
                "ename": type(exc).__name__,
                "evalue": str(exc),
                "traceback": [f"{type(exc).__name__}: {exc}"],
            }]
            cell_outputs.append(out)
            sys.stdout, sys.stderr = old_stdout, old_stderr
            continue
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

        outputs: list[dict] = []

        # Capture stdout
        stdout_text = buf_stdout.getvalue()
        if stdout_text:
            outputs.append({
                "output_type": "stream",
                "name": "stdout",
                "text": stdout_text.splitlines(keepends=True),
            })

        # Capture last expression result + embed PNG for GitHub
        try:
            tree = ast.parse(cell.source)
            last = tree.body[-1] if tree.body else None
            if isinstance(last, ast.Expr):
                var_name = None
                if isinstance(last.value, ast.Name):
                    var_name = last.value.id
                elif isinstance(last.value, ast.Call):
                    func = last.value.func
                    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                        var_name = func.value.id

                if var_name and var_name in namespace:
                    obj = namespace[var_name]
                    # Find SVG files created during THIS cell execution only.
                    # Collect all known SVG paths before exec, then find new ones after.
                    svg_files = glob_mod.glob("*.svg") + glob_mod.glob(f"{charts_dir}/*.svg")
                    current_svgs = set()
                    for f in svg_files:
                        try:
                            current_svgs.add(os.path.getsize(f))
                        except OSError:
                            pass
                    new_svg_files = []
                    for f in svg_files:
                        try:
                            sz = os.path.getsize(f)
                            if sz not in all_svg_files:
                                new_svg_files.append(f)
                                all_svg_files.add(sz)
                        except OSError:
                            pass

                    if new_svg_files:
                        # Use the largest new SVG (most complete chart)
                        chosen = max(new_svg_files, key=lambda f: os.path.getsize(f))
                        try:
                            import cairosvg
                            png_buf = io.BytesIO()
                            cairosvg.svg2png(url=chosen, write_to=png_buf)
                            outputs.append({
                                "output_type": "execute_result",
                                "execution_count": exec_count,
                                "data": {
                                    "image/png": base64.b64encode(png_buf.getvalue()).decode("ascii")
                                },
                                "metadata": {},
                            })
                        except ImportError:
                            pass  # No cairosvg, skip PNG
        except (SyntaxError, Exception) as _e:
            import traceback as _tb
            print(f"PNG embed error: {_e}", file=sys.stderr)
            _tb.print_exc(file=sys.stderr)

        cell_outputs.append(outputs)

    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0",
            },
            "notebook_generator": {
                "title": spec.title,
                "claim": spec.claim,
                "generator": "letsplot-notebook",
            },
        },
        "cells": [
            _cell_to_ipynb(cell, outputs)
            for cell, outputs in zip(spec.cells, cell_outputs)
        ],
    }

    out_path = output_dir / filename
    out_path.write_text(json.dumps(nb, indent=1, ensure_ascii=False))
    logger.info("Notebook written to %s", out_path)
    return out_path


# ---------------------------------------------------------------------------
# Load -- read .ipynb back into LetsPlotNotebookSpec
# ---------------------------------------------------------------------------


def load_notebook(path: Path) -> Result[LetsPlotNotebookSpec, str]:
    """Load a .ipynb file into a LetsPlotNotebookSpec."""
    if not path.exists():
        return Err(f"File not found: {path}")

    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return Err(f"JSON parse error: {e}")

    cells_raw = raw.get("cells", [])
    meta = raw.get("metadata", {}).get("notebook_generator", {})
    title = meta.get("title", path.stem)
    claim = meta.get("claim", "")

    cells: list[Cell] = []
    for c in cells_raw:
        source = c.get("source", [])
        if isinstance(source, list):
            source = "".join(source)
        cells.append(Cell(
            cell_type=c.get("cell_type", "code"),
            source=source,
        ))

    return Ok(LetsPlotNotebookSpec(
        title=title,
        claim=claim,
        cells=tuple(cells),
    ))
