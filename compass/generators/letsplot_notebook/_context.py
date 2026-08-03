"""Context builder for the LetsPlot notebook generator.

Injects LetsPlot API knowledge, best practices, and available geoms
into the model's system prompt.
"""

from __future__ import annotations

from compass.generators._types import DomainSection, GenerationContext

# Key geoms and their use cases
_LETSPLOT_GEOMS = """\
## Key Geoms

### Scatter at Scale
- `geom_point()` — standard scatter, use with `sampling=sampling_random(N)` for large data
- `geom_hex(bins=[N, M])` — hexagonal binning, best for density patterns at any scale
- `geom_bin2d(bins=[N, M])` — rectangular 2D binning
- `geom_pointdensity(method='auto')` — density-colored points, renders ALL points
- `geom_density2d()` — 2D density contour lines
- `geom_density2df()` — 2D density filled contours

### Statistical Charts
- `geom_histogram(bins=N)` — histogram with bin count
- `geom_density()` — kernel density estimate
- `geom_boxplot()` — box and whisker plot
- `geom_violin()` — violin plot (distribution shape)
- `geom_bar()` — bar chart
- `geom_freqpoly()` — frequency polygon

### Multi-panel & Marginal
- `gggrid(plots, ncol=N)` — multi-panel grid layout with shared axes
- `ggmarginal(sides='t', layer=geom_density())` — marginal distributions on scatter
- `facet_wrap()` — small multiples by category

### Specialized
- `geom_qq()` + `geom_qq_line()` — quantile-quantile plot
- `geom_smooth()` — smoothed trend line with confidence band
- `geom_line()` + `geom_area()` — time series
- `geom_tile()` + `geom_raster()` — heatmaps

### Sampling Strategies
- `sampling_random(N, seed)` — random sample
- `sampling_random_stratified(N, seed)` — stratified by group
- `sampling_systematic(N)` — regular interval
- `sampling_pick(N)` — first N items
- `sampling_group_systematic(N)` — sample groups
- `sampling_group_random(N, seed)` — random groups

## Scales
- `scale_fill_viridis()` — perceptually uniform colormap
- `scale_fill_hue()` — categorical hue palette
- `scale_fill_grey()` — grayscale
- `scale_fill_brewer(palette='Plasma')` — ColorBrewer palettes
- `scale_fill_gradient(low='...', high='...')` — two-color gradient
- `scale_color_viridis()` / `scale_color_hue()` — same for color aesthetic

## Themes
- `theme_light()` — clean light background (recommended)
- `theme_dark()` — dark background
- `theme_gray()` — ggplot2-style gray
- `theme_void()` — minimal, no axes

## Export
- `ggsave(plot, 'filename.svg', w=8, h=6, unit='in')` — SVG export
- `ggsave(plot, 'filename.png', w=8, h=6, unit='in', dpi=150)` — PNG export
- `ggsave(plot, 'filename.html')` — interactive HTML export
- Output directory: `lets-plot-images/` by default, override with `path='...'`
"""

_LETSPLOT_PATTERNS = """\
## Code Patterns

### Standard import and setup
```python
import numpy as np
import matplotlib
matplotlib.use('Agg')
from lets_plot import *
LetsPlot.setup_html()
LetsPlot.set_theme(theme_light())
```

### Scatter with hex binning (recommended for >10K points)
```python
n = 50_000
x, y = np.random.multivariate_normal([0, 0], [[1, 0.5], [0.5, 1]], n).T
data = {'x': x, 'y': y}

p = (ggplot(data, aes(x='x', y='y')) +
     geom_hex(bins=[40, 40]) +
     scale_fill_viridis())
ggsave(p, 'scatter_hex.svg', w=8, h=6, unit='in')
p  # return plot for inline notebook rendering
```

### Marginal plot (scatter + distribution margins)
```python
p = (ggplot(data, aes(x='x', y='y')) +
     geom_hex(bins=[40, 40]) +
     scale_fill_viridis() +
     ggmarginal(sides='t', layer=geom_density(fill='steelblue', alpha=0.4)) +
     ggmarginal(sides='r', layer=geom_histogram(fill='steelblue', alpha=0.4, bins=40)))
ggsave(p, 'marginal.svg', w=7, h=6, unit='in')
p  # return plot for inline notebook rendering
```

### Multi-panel with gggrid
```python
plots = []
for cat in ['A', 'B', 'C', 'D']:
    sub = data[data['category'] == cat]
    plots.append(
        ggplot(sub, aes(x='x', y='y')) +
        geom_hex(bins=[30, 30]) +
        scale_fill_viridis() +
        ggtitle(cat)
    )
grid = gggrid(plots, ncol=2, sharex='all', sharey='all', guides='collect')
ggsave(grid, 'multipanel.svg', w=10, h=7, unit='in')
grid  # return grid for inline notebook rendering
```

### Statistical chart (histogram + density overlay)
```python
groups = np.random.choice(['A', 'B', 'C'], 50_000, p=[0.5, 0.3, 0.2])
values = np.where(groups == 'A', np.random.exponential(2, 50_000),
          np.where(groups == 'B', np.random.normal(5, 1.5, 50_000),
                   np.random.uniform(0, 10, 50_000)))
data = {'group': groups, 'value': values}

p = (ggplot(data, aes(x='value', fill='group')) +
     geom_histogram(aes(y='..density..'), bins=80, alpha=0.6, position='identity') +
     geom_density(alpha=0.8, size=1) +
     scale_fill_hue())
ggsave(p, 'histogram.svg', w=8, h=5, unit='in')
p  # return plot for inline notebook rendering
```

### QQ plot
```python
p = (ggplot({'sample': np.random.normal(0, 1, 30_000)}, aes(sample='sample')) +
     geom_qq(color='#2563eb', alpha=0.3, size=0.8,
             sampling=sampling_random(3000, 42)) +
     geom_qq_line(color='#dc2626', size=1))
ggsave(p, 'qqplot.svg', w=5, h=5, unit='in')
p  # return plot for inline notebook rendering
```
"""

_LETSPLOT_PRINCIPLES = """\
## Notebook Authoring Principles

### Structure
1. Title (H1 markdown cell)
2. Imports (first code cell — numpy, matplotlib Agg, lets_plot)
3. Data generation or loading
4. Chart sections (markdown explanation + code cell with geom + ggsave)
5. Summary or insights

### LetsPlot-specific rules
- First code cell MUST include all three setup calls:
  - `from lets_plot import *`
  - `LetsPlot.setup_html()` — required for inline rendering in Jupyter
  - `LetsPlot.set_theme(theme_light())`
- Use `from lets_plot import *` (the library uses star imports)
- For scatter >10K points: prefer `geom_hex()` or `geom_pointdensity()`
- For scatter <10K points: `geom_point()` with alpha and size control
- Always use `ggsave()` to export charts (SVG preferred, PNG for very large outputs)
- Use `scale_fill_viridis()` for density/binned charts
- Use `scale_fill_hue()` or `scale_color_hue()` for categorical coloring
- Use `ggmarginal()` for marginal distributions on scatter plots
- Use `gggrid()` for multi-panel layouts with `guides='collect'`
- Use `sampling_random()` or `sampling_systematic()` when geom_point needs downsampling

### Output rules
- Save all figures with descriptive filenames (e.g., 'scatter_hex.svg')
- Use `ggsave(p, 'filename.svg', w=8, h=6, unit='in')` format
- Print confirmation after each ggsave: `print(f'Saved to {path}')`
- **CRITICAL**: Always return the plot object as the last expression in chart cells (e.g. `p` or `grid` on its own line after `ggsave()`) so charts render inline in Jupyter notebooks
- All code must execute without errors
"""


def _discover_available_packages() -> str:
    """List installed Python packages relevant to LetsPlot notebooks."""
    try:
        from importlib.metadata import distributions
        pkgs = sorted(
            {d.metadata["Name"] for d in distributions() if d.metadata["Name"]},
            key=str.lower,
        )
        return ", ".join(pkgs)
    except Exception:
        return "numpy, matplotlib, lets-plot, pandas"


def build_letsplot_context(
    prompt: str | None = None,
) -> GenerationContext:
    """Build context for the LetsPlot notebook generator."""
    return GenerationContext(
        domain_context=(
            DomainSection("LetsPlot Geoms & API", _LETSPLOT_GEOMS),
            DomainSection("Code Patterns", _LETSPLOT_PATTERNS),
            DomainSection("Authoring Principles", _LETSPLOT_PRINCIPLES),
        ),
        available_packages=_discover_available_packages(),
        user_prompt=prompt,
        default_task=(
            "Generate a well-structured Jupyter notebook that demonstrates "
            "LetsPlot charting capabilities with real data and exported charts."
        ),
    )
