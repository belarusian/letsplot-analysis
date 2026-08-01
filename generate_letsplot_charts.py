#!/usr/bin/env python3
"""
Generate LetsPlot charts demonstrating the library's capabilities.
Exports SVGs for embedding in the analysis page.
"""

import numpy as np
import os
from lets_plot import *

# Configure output
output_dir = "/Users/av4nda/Research/letsplot_charts"
os.makedirs(output_dir, exist_ok=True)

LetsPlot.set_theme(theme_light())

np.random.seed(42)

# ============================================================
# Dataset 1: Large bivariate scatter (100K points, 2 clusters)
# Demonstrates the core problem: scatter at scale
# ============================================================
n = 100_000
cov0 = [[1, -.7], [-.7, 1]]
cov1 = [[.5, .3], [.3, .5]]
x0, y0 = np.random.multivariate_normal(mean=[-2, 0], cov=cov0, size=n//2).T
x1, y1 = np.random.multivariate_normal(mean=[2, 1], cov=cov1, size=n//2).T
x = np.concatenate([x0, x1])
y = np.concatenate([y0, y1])
cluster = np.concatenate([np.full(n//2, 'Cluster A'), np.full(n//2, 'Cluster B')])

data_large = {'x': x, 'y': y, 'cluster': cluster}

# Chart 1: geom_point with sampling (the naive approach)
print("Chart 1: geom_point with sampling...")
p1 = (ggplot(data_large, aes(x='x', y='y')) +
      geom_point(aes(color='cluster'), size=1.5, alpha=0.3,
                 sampling=sampling_random(2000, seed=42)) +
      ggsize(700, 450) +
      ggtitle('Scatter Plot (100K pts, sampled to 2K)'))
ggsave(p1, 'scatter_sampled.svg', path=output_dir, w=7, h=4.5, unit='in')

# Chart 2: geom_hex — hexagonal binning for large data
print("Chart 2: geom_hex...")
p2 = (ggplot(data_large, aes(x='x', y='y')) +
      geom_hex(bins=[50, 50]) +
      scale_fill_viridis() +
      ggsize(700, 450) +
      ggtitle('Hexagonal Binning (geom_hex, 50×50 bins)'))
ggsave(p2, 'hex_bin.svg', path=output_dir, w=7, h=4.5, unit='in')

# Chart 3: geom_bin2d — rectangular 2D binning
print("Chart 3: geom_bin2d...")
p3 = (ggplot(data_large, aes(x='x', y='y')) +
      geom_bin2d(bins=[60, 40]) +
      scale_fill_viridis() +
      ggsize(700, 450) +
      ggtitle('2D Rectangular Binning (geom_bin2d, 60×40 bins)'))
ggsave(p3, 'bin2d.svg', path=output_dir, w=7, h=4.5, unit='in')

# Chart 4: geom_pointdensity — density-colored points
print("Chart 4: geom_pointdensity...")
p4 = (ggplot(data_large, aes(x='x', y='y')) +
      geom_pointdensity(method='auto', size=2) +
      scale_fill_viridis() +
      ggsize(700, 450) +
      ggtitle('Point Density (geom_pointdensity, auto method)'))
ggsave(p4, 'pointdensity.svg', path=output_dir, w=7, h=4.5, unit='in')

# Chart 5: geom_density2d — 2D density contours
print("Chart 5: geom_density2d...")
p5 = (ggplot(data_large, aes(x='x', y='y')) +
      geom_density2d(aes(color='cluster'), size=0.4, n=50) +
      scale_color_hue() +
      ggsize(700, 450) +
      ggtitle('2D Density Contours (geom_density2d)'))
ggsave(p5, 'density2d.svg', path=output_dir, w=7, h=4.5, unit='in')

# ============================================================
# Dataset 2: Marginal plot demo — scatter + distribution margins
# ============================================================
n2 = 20_000
x2, y2 = np.random.multivariate_normal(mean=[0, 0], cov=[[1, .6], [.6, 1]], size=n2).T
data_marg = {'x': x2, 'y': y2}

# Chart 6: Marginal plot with density on top and histogram on right
print("Chart 6: Marginal plot (ggmarginal)...")
p6 = (ggplot(data_marg, aes(x='x', y='y')) +
      geom_hex(bins=[40, 40]) +
      scale_fill_viridis() +
      ggmarginal(sides='t', layer=geom_density(fill='steelblue', alpha=0.4)) +
      ggmarginal(sides='r', layer=geom_histogram(fill='steelblue', alpha=0.4, bins=40)) +
      ggsize(600, 500) +
      ggtitle('Marginal Plot: Hex + Density + Histogram'))
ggsave(p6, 'marginal.svg', path=output_dir, w=6, h=5, unit='in')

# ============================================================
# Dataset 3: gggrid multi-panel — small multiples
# ============================================================
categories = ['Alpha', 'Beta', 'Gamma', 'Delta']
all_x, all_y, all_cat = [], [], []
for i, cat in enumerate(categories):
    cx, cy = (i - 1.5) * 2, (i % 2) * 2
    cx_, cy_ = np.random.multivariate_normal(mean=[cx, cy], cov=[[.8, .2], [.2, .8]], size=15000).T
    all_x.extend(cx_)
    all_y.extend(cy_)
    all_cat.extend(np.full(15000, cat))

data_multi = {'x': np.array(all_x), 'y': np.array(all_y), 'cat': np.array(all_cat)}

# Chart 7: gggrid with faceted hex bins
print("Chart 7: gggrid multi-panel...")
plots = []
for cat in categories:
    sub = {k: v[data_multi['cat'] == cat] for k, v in data_multi.items()}
    plots.append(
        ggplot(sub, aes(x='x', y='y')) +
        geom_hex(bins=[30, 30]) +
        scale_fill_viridis() +
        ggsize(300, 280) +
        ggtitle(cat)
    )
grid = gggrid(plots, ncol=2, sharex='all', sharey='all', guides='collect')
ggsave(grid, 'gggrid_multipanel.svg', path=output_dir, w=10, h=6, unit='in')

# ============================================================
# Dataset 4: Statistical charts — showing ggplot's strength
# (histogram, boxplot, density — the creator's point)
# ============================================================
n3 = 50_000
groups = np.random.choice(['A', 'B', 'C'], n3, p=[0.5, 0.3, 0.2])
values = np.where(groups == 'A', np.random.exponential(2, n3),
          np.where(groups == 'B', np.random.normal(5, 1.5, n3),
                   np.random.uniform(0, 10, n3)))

data_stat = {'group': groups, 'value': values}

# Chart 8: Histogram with density overlay
print("Chart 8: Histogram + density...")
p8 = (ggplot(data_stat, aes(x='value', fill='group')) +
      geom_histogram(aes(y='..density..'), bins=80, alpha=0.6, position='identity') +
      geom_density(alpha=0.8, size=1) +
      scale_fill_hue() +
      ggsize(700, 400) +
      ggtitle('Distribution by Group (Histogram + Density)'))
ggsave(p8, 'histogram_density.svg', path=output_dir, w=7, h=4, unit='in')

# Chart 9: Boxplot
print("Chart 9: Boxplot...")
p9 = (ggplot(data_stat, aes(x='group', y='value', fill='group')) +
      geom_boxplot(alpha=0.7, outlier_size=0.5) +
      scale_fill_hue() +
      ggsize(500, 400) +
      ggtitle('Boxplot by Group (50K observations)'))
ggsave(p9, 'boxplot.svg', path=output_dir, w=5, h=4, unit='in')

# Chart 10: Violin plot
print("Chart 10: Violin plot...")
p10 = (ggplot(data_stat, aes(x='group', y='value', fill='group')) +
       geom_violin(alpha=0.6, scale='area') +
       geom_boxplot(width=0.15, alpha=0.8, fill='white') +
       scale_fill_hue() +
       ggsize(500, 400) +
       ggtitle('Violin + Boxplot by Group'))
ggsave(p10, 'violin.svg', path=output_dir, w=5, h=4, unit='in')

# ============================================================
# Dataset 5: Time series with geom_smooth
# ============================================================
n4 = 10_000
t = np.linspace(0, 100, n4)
signal = np.sin(t / 10) * 5 + np.random.normal(0, 1.5, n4)
data_ts = {'t': t, 'signal': signal}

# Chart 11: Time series with smoothing
print("Chart 11: Time series + geom_smooth...")
p11 = (ggplot(data_ts, aes(x='t', y='signal')) +
       geom_point(size=0.5, alpha=0.2, sampling=sampling_systematic(500)) +
       geom_smooth(color='#2563eb', size=1.2, se=True, alpha=0.15) +
       ggsize(700, 350) +
       ggtitle('Time Series with Smoothing (10K pts)'))
ggsave(p11, 'timeseries.svg', path=output_dir, w=7, h=3.5, unit='in')

# ============================================================
# Dataset 6: QQ plot
# ============================================================
n5 = 30_000
data_qq = {'normal': np.random.normal(0, 1, n5),
           'exponential': np.random.exponential(2, n5)}

# Chart 12: QQ plot
print("Chart 12: QQ plot...")
p12 = (ggplot(data_qq, aes(sample='normal')) +
       geom_qq(color='#2563eb', alpha=0.3, size=0.8, sampling=sampling_random(3000, 42)) +
       geom_qq_line(color='#dc2626', size=1) +
       ggsize(450, 400) +
       ggtitle('Q-Q Plot (Normal distribution, 30K pts)'))
ggsave(p12, 'qqplot.svg', path=output_dir, w=4.5, h=4, unit='in')

print(f"\nDone! Generated {len(os.listdir(output_dir))} SVGs in {output_dir}")
