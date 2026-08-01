# LetsPlot Analysis

Research deep-dive into [JetBrains/lets-plot](https://github.com/JetBrains/lets-plot) — three complementary analyses covering architecture, theory, and hands-on usage.

## Pages

| # | File | Focus | Live URL |
|---|------|-------|----------|
| 1 | [analysis1.html](analysis1.html) | **Architecture Deep Dive** — XY (reflex.dev) rendering engine: Rust core, WebGL2 renderer, tier ladder system, LOD thresholds, mean-color compositing formulas | [compsci.boutique/letsplot-analysis.html](https://compsci.boutique/letsplot-analysis.html) |
| 2 | [analysis2.html](analysis2.html) | **Grammar of Graphics at Scale** — Conceptual synthesis: extending ggplot's "statistical function" paradigm with viewport-driven density aggregation | [compsci.boutique/letsplot-analysis2.html](https://compsci.boutique/letsplot-analysis2.html) |
| 3 | [analysis3.html](analysis3.html) | **Hands-On Charts & Code** — 12 charts generated with LetsPlot itself, exercising the full API surface with executable Python code | [compsci.boutique/letsplot-analysis3.html](https://compsci.boutique/letsplot-analysis3.html) |

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
