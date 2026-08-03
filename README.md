# LetsPlot Analysis

Research deep-dive into [JetBrains/lets-plot](https://github.com/JetBrains/lets-plot) — three complementary analyses covering architecture, theory, and hands-on usage, plus a notebook generator.

## Pages

| # | File | Focus | Live URL |
|---|------|-------|----------|
| 1 | [analysis1.html](analysis1.html) | **Architecture Deep Dive** — XY (reflex.dev) rendering engine: Rust core, WebGL2 renderer, tier ladder system, LOD thresholds, mean-color compositing formulas | [compsci.boutique/letsplot-analysis.html](https://www.compsci.boutique/letsplot-analysis.html) |
| 2 | [analysis2.html](analysis2.html) | **Grammar of Graphics at Scale** — Conceptual synthesis: extending ggplot's "statistical function" paradigm with viewport-driven density aggregation | [compsci.boutique/letsplot-analysis2.html](https://www.compsci.boutique/letsplot-analysis2.html) |
| 3 | [analysis3.html](analysis3.html) | **Hands-On Charts & Code** — 12 charts generated with LetsPlot itself, exercising the full API surface with executable Python code | [compsci.boutique/letsplot-analysis3.html](https://www.compsci.boutique/letsplot-analysis3.html) |

## Architecture — The Five-Function Loop

The generator framework is parameterized over five functions. The loop itself is invariant — it doesn't know what artifact it's generating.

```
invoke   : G   -- Context → Result[raw]
parse    : V1  -- raw → Result[Spec]
validate : V2  -- Spec → Result[Artifact]
fix      : G'  -- (Spec, error, ctx) → Spec | None
emit     : IO  -- (Spec, Artifact, ...) → Result[Path]
```

**The flow:** `G → V1 → (V2 → G' → V2)* → emit`

- **Outer loop** (`max_rounds`): wholesale generation. The model produces a new spec from context. If the ouroboros can't fix it, the spec is discarded and errors become feedback — learnings travel forward even when the page is scrapped.
- **Inner loop** (`max_fixes`): ouroboros repair. The model receives its own prior output + the error and returns a corrected version. Same type in, same type out. Spec is never discarded within this loop.
- **Result monad** (`Ok[T] | Err[E]`): carries errors through the pipeline without explicit try/catch. Every step returns `Result`, composed via bind/flatMap (implemented with Python `match`).

**Total budget:** `max_rounds × max_fixes` iterations.

The same loop generates Python code, Jupyter notebooks, CLI tools, and new generators. Only the five functions change. The invariant is the architecture.

### Framework vs Generator Module

```
compass/generators/
  _types.py          # Result monad, GenerationContext, DomainSection
  _loop.py           # Parameterized generation_loop, refine_loop, repl_loop
  _invoke.py         # Model invocation: SimpleProvider (OpenAI-compatible)
  _validation.py     # Python source validation: AST + variable flow

  letsplot_notebook/ # LetsPlot-specific generator module
    _types.py        # LetsPlotNotebookSpec, NotebookPatch, validators
    _runtime.py      # invoke_model, validate_notebook, ouroboros, emit
    _context.py      # LetsPlot API domain context (geoms, patterns, principles)
    generate.py      # Wires five functions into generation_loop + CLI
```

The generator module injects LetsPlot API knowledge as domain context. Validation runs cheapest-first: structural → AST syntax → full execution (generates actual chart SVGs). The framework handles the iteration; the module defines what to iterate over.

### Usage

```bash
# One-shot generation
python -m compass.generators.letsplot_notebook.generate \
    --prompt "Compare geom_hex vs geom_pointdensity for large scatter" \
    --output-dir ./notebooks

# Interactive REPL
python -m compass.generators.letsplot_notebook.generate --live

# Dry run (print prompts, don't call model)
python -m compass.generators.letsplot_notebook.generate \
    --prompt "Show marginal plots with ggmarginal" --dry-run

# Refine existing notebook
python -m compass.generators.letsplot_notebook.generate \
    --refine notebooks/scatter_analysis.ipynb \
    --claim "Add a geom_density2d comparison"
```

### Configuration

Set `LLM_BASE_URL` or `LLAMACPP_HOST` to point to an OpenAI-compatible endpoint
(llama.cpp, vLLM, etc.), or pass `--base-url` explicitly:

```bash
export LLM_BASE_URL=http://192.168.1.157:8080/v1
python -m compass.generators.letsplot_notebook.generate \
    --prompt "Demonstrate gggrid multi-panel layouts"
```

## Charts

The `charts/` directory contains 12 SVG/PNG exports generated with `lets-plot==4.11.0`:

| Chart | Geom | Dataset | Format |
|-------|------|---------|--------|
| `scatter_sampled.svg` | `geom_point` + `sampling_random(2000)` | 100K pts → 2K | SVG |
| `hex_bin.svg/png` | `geom_hex(bins=[50,50])` | 100K pts | SVG + PNG |
| `bin2d.svg` | `geom_bin2d(bins=[60,40])` | 100K pts | SVG |
| `pointdensity.png` | `geom_pointdensity(method='auto')` | 100K pts | PNG (SVG was 15MB) |
| `density2d.svg` | `geom_density2d` | 100K pts | SVG |
| `marginal.svg` | `geom_hex` + `ggmarginal()` | 20K pts | SVG |
| `gggrid_multipanel.svg/png` | `gggrid(2×2)` + `geom_hex` | 60K pts | SVG + PNG |
| `histogram_density.svg` | `geom_histogram` + `geom_density` | 50K pts | SVG |
| `boxplot.svg` | `geom_boxplot` | 50K pts | SVG |
| `violin.svg` | `geom_violin` + `geom_boxplot` | 50K pts | SVG |
| `qqplot.svg/png` | `geom_qq` + `geom_qq_line` | 30K pts | SVG + PNG |
| `timeseries.svg` | `geom_point` + `geom_smooth` | 10K pts | SVG |

## Reproducing Charts

```bash
pip install lets-plot numpy pillow
python generate_letsplot_charts.py
```

Output goes to `letsplot_charts/` (run from the parent directory).

## Key Findings

1. **`geom_pointdensity()`** is the best current option for large scatter — renders all points, density-colored, auto-selects algorithm
2. **`ggmarginal()`** is a unique LetsPlot differentiator — no direct ggplot2 equivalent
3. **SVG output size** is the main bottleneck at scale (15MB for 100K density points)
4. **Statistical charts** (histogram, boxplot, violin) are inherently O(bins) — no scaling issue
5. **Three paths forward**: WebGL output mode, viewport-aware stats, auto-format selection

## Deployed To

All pages are live at [compsci.boutique](https://compsci.boutique) via S3 + CloudFront.

## License

Research notes — MIT
