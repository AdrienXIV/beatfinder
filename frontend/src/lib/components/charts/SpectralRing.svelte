<script lang="ts">
	import {
		SPECTRAL_BAND_KEYS,
		SPECTRAL_BAND_COLORS,
		SPECTRAL_BAND_LABELS,
		type SpectralBandKey
	} from './spectral-colors';

	let {
		bands,
		size = 220,
		strokeWidth = 12,
		ringGap = 4,
		fillColors = SPECTRAL_BAND_COLORS,
		trackColor = null,
		legendSide = 'right',
		showLegend = true,
		legendLabels = null
	}: {
		bands: Record<string, number | undefined>;
		size?: number;
		strokeWidth?: number;
		ringGap?: number;
		fillColors?: Record<SpectralBandKey, string>;
		trackColor?: string | null;
		legendSide?: 'right' | 'bottom' | 'none';
		showLegend?: boolean;
		legendLabels?: Record<string, string> | null;
	} = $props();

	const labels = $derived(legendLabels ?? SPECTRAL_BAND_LABELS);

	const cx = $derived(size / 2);
	const cy = $derived(size / 2);
	const outerR = $derived(size / 2 - strokeWidth / 2 - 2);
	const ringStep = $derived(strokeWidth + ringGap);

	const rings = $derived(
		SPECTRAL_BAND_KEYS.map((key, i) => {
			const r = outerR - i * ringStep;
			const value = Math.max(0, Math.min(1, bands[key] ?? 0));
			const circumference = 2 * Math.PI * r;
			return {
				key,
				label: labels[key] ?? key,
				color: fillColors[key],
				value,
				r,
				circumference,
				filled: value * circumference
			};
		})
	);
</script>

<div class={`ring-wrap legend-${legendSide}`}>
	<div class="ring-chart" style="--size: {size}px;">
		<svg viewBox="0 0 {size} {size}" class="rings" aria-label="Profil spectral par bande">
			{#each rings as r (r.key)}
				<!-- Track -->
				<circle
					cx={cx}
					cy={cy}
					r={r.r}
					fill="none"
					stroke={trackColor ?? 'var(--color-surface-2)'}
					stroke-width={strokeWidth}
				/>
				<!-- Filled arc -->
				<circle
					cx={cx}
					cy={cy}
					r={r.r}
					fill="none"
					stroke={r.color}
					stroke-width={strokeWidth}
					stroke-dasharray="{r.filled} {r.circumference}"
					stroke-linecap="butt"
					transform="rotate(-90 {cx} {cy})"
				/>
			{/each}
		</svg>
	</div>

	{#if showLegend && legendSide !== 'none'}
		<ol class="ring-legend">
			{#each rings as r, i (r.key)}
				<li>
					<span class="swatch" style:background={r.color}></span>
					<span class="idx">{(i + 1).toString().padStart(2, '0')}</span>
					<span class="lbl">{r.label}</span>
					<span class="dots"></span>
					<span class="val">{(r.value * 100).toFixed(1)}<span class="pc">%</span></span>
				</li>
			{/each}
		</ol>
	{/if}
</div>

<style>
	.ring-wrap {
		display: grid;
		gap: 1.25rem;
		align-items: center;
	}
	.legend-right {
		grid-template-columns: auto 1fr;
	}
	.legend-bottom {
		grid-template-rows: auto auto;
	}
	.legend-none {
		grid-template-columns: 1fr;
	}

	.ring-chart {
		width: var(--size);
		max-width: 100%;
		aspect-ratio: 1;
	}
	.rings {
		width: 100%;
		height: 100%;
		display: block;
	}

	.ring-legend {
		list-style: none;
		padding: 0;
		margin: 0;
		font-size: 12px;
	}
	.ring-legend li {
		display: grid;
		grid-template-columns: auto auto 1fr auto auto;
		gap: 0.5rem;
		align-items: baseline;
		padding: 0.35rem 0;
		border-bottom: 1px dotted var(--color-border);
	}
	.swatch {
		display: inline-block;
		width: 10px;
		height: 10px;
		border-radius: 2px;
		align-self: center;
	}
	.ring-legend li:last-child {
		border-bottom: none;
	}
	.idx {
		font-family: 'JetBrains Mono', ui-monospace, monospace;
		font-size: 10px;
		color: var(--color-accent);
		font-weight: 600;
		letter-spacing: 0.05em;
	}
	.lbl {
		color: var(--color-fg);
		font-weight: 500;
	}
	.dots {
		border-bottom: 1px dotted var(--color-border);
		min-width: 1rem;
	}
	.val {
		font-family: 'JetBrains Mono', ui-monospace, monospace;
		font-size: 13px;
		font-weight: 600;
		color: var(--color-fg);
		font-variant-numeric: tabular-nums;
	}
	.pc {
		font-size: 10px;
		color: var(--color-fg-muted);
		margin-left: 1px;
	}
</style>
