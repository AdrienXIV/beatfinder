<script lang="ts">
	import { onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';
	import type { SessionVersion } from '$lib/api';
	import {
		EVOLUTION_FEATURES,
		type FeatureRow,
		getFeatureValue,
		getPatternStats,
		formatValue
	} from '$lib/session-comparison';

	let {
		versions,
		targetPattern
	}: {
		versions: SessionVersion[];
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		targetPattern: Record<string, any>;
	} = $props();

	// Refs DOM (reactifs, pour bind:this)
	let fitCanvas: HTMLCanvasElement | null = $state(null);
	let featureCanvases: (HTMLCanvasElement | null)[] = $state(
		EVOLUTION_FEATURES.map(() => null)
	);

	// Instances Chart.js — NON-reactives pour éviter une boucle infinie
	// avec le $effect qui les construit (lecture + écriture sur le même state).
	let fitChart: Chart | null = null;
	let featureCharts: (Chart | null)[] = EVOLUTION_FEATURES.map(() => null);

	const labels = $derived(versions.map((v) => v.name));

	const fitValues = $derived(
		versions.map((v) => (v.fit_score !== null ? Math.round(v.fit_score * 100) : null))
	);

	function featureValues(row: FeatureRow): (number | null)[] {
		const scale = row.displayScale ?? 1;
		return versions.map((v) => {
			const raw = getFeatureValue(v.features_json, row.path);
			return raw === null ? null : raw * scale;
		});
	}

	function featureTarget(row: FeatureRow): number | null {
		const stats = getPatternStats(targetPattern, row.path);
		if (stats === null || stats.median === undefined) return null;
		const scale = row.displayScale ?? 1;
		return stats.median * scale;
	}

	// Adapte la taille des points selon le nombre de versions pour rester lisible
	// à 50+ versions (sinon les points se chevauchent en blob orange).
	function adaptivePointRadius(n: number, base: number): number {
		if (n > 25) return 1;
		if (n > 10) return Math.max(2, base - 1);
		return base;
	}

	function buildFitChart(canvas: HTMLCanvasElement): Chart {
		const n = versions.length;
		return new Chart(canvas, {
			type: 'line',
			data: {
				labels,
				datasets: [
					{
						label: 'Fit score',
						data: fitValues,
						borderColor: '#f97316',
						backgroundColor: '#f9731633',
						fill: true,
						borderWidth: 2.5,
						pointRadius: adaptivePointRadius(n, 4),
						pointHoverRadius: 5,
						pointBackgroundColor: '#f97316',
						tension: 0.25
					},
					{
						label: 'Cible (100%)',
						data: versions.map(() => 100),
						borderColor: 'rgba(34, 197, 94, 0.55)',
						borderDash: [4, 4],
						borderWidth: 1.5,
						pointRadius: 0,
						fill: false
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: false,
				interaction: { mode: 'index', intersect: false },
				plugins: {
					legend: { display: false },
					tooltip: {
						mode: 'index',
						intersect: false,
						callbacks: {
							label: (ctx) =>
								ctx.datasetIndex === 0
									? `${ctx.parsed.y}%`
									: 'Cible : 100%'
						}
					}
				},
				scales: {
					x: {
						display: true,
						grid: { display: false },
						ticks: { font: { size: 10 }, autoSkip: true, maxTicksLimit: 12 }
					},
					y: {
						min: 0,
						max: 100,
						ticks: {
							font: { size: 10 },
							callback: (v) => `${v}%`
						},
						grid: { color: 'rgba(255,255,255,0.04)' }
					}
				}
			}
		});
	}

	function buildFeatureChart(canvas: HTMLCanvasElement, row: FeatureRow): Chart {
		const vals = featureValues(row);
		const target = featureTarget(row);
		const n = versions.length;
		return new Chart(canvas, {
			type: 'line',
			data: {
				labels,
				datasets: [
					{
						label: row.label,
						data: vals,
						borderColor: '#f97316',
						backgroundColor: '#f9731622',
						fill: true,
						borderWidth: 2,
						pointRadius: adaptivePointRadius(n, 3),
						pointHoverRadius: 4,
						pointBackgroundColor: '#f97316',
						tension: 0.25
					},
					...(target !== null
						? [
								{
									label: 'Cible',
									data: versions.map(() => target),
									borderColor: 'rgba(34, 197, 94, 0.55)',
									borderDash: [4, 4],
									borderWidth: 1.5,
									pointRadius: 0,
									fill: false
								}
							]
						: [])
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: false,
				interaction: { mode: 'index', intersect: false },
				plugins: {
					legend: { display: false },
					tooltip: {
						mode: 'index',
						intersect: false,
						callbacks: {
							label: (ctx) => {
								const v = ctx.parsed.y;
								if (ctx.datasetIndex === 1) return `Cible : ${formatValue(target, row)}${row.unit}`;
								return `${typeof v === 'number' ? v.toFixed(row.decimals ?? 1) : '—'}${row.unit}`;
							}
						}
					}
				},
				scales: {
					x: {
						display: true,
						grid: { display: false },
						ticks: { font: { size: 9 }, autoSkip: true, maxTicksLimit: 8 }
					},
					y: {
						ticks: { font: { size: 9 } },
						grid: { color: 'rgba(255,255,255,0.04)' }
					}
				}
			}
		});
	}

	$effect(() => {
		// Deps explicites : on rebuild si nb versions OU pattern target change.
		// Identifier au nb de versions (le contenu d'une version donnée ne
		// change pas en place — invalidateAll renvoie un nouveau session.versions).
		versions.length;
		void targetPattern;

		// Cleanup avant rebuild (au cas où on était déjà monté)
		fitChart?.destroy();
		featureCharts.forEach((c) => c?.destroy());
		fitChart = null;
		featureCharts = EVOLUTION_FEATURES.map(() => null);

		if (!fitCanvas) return;
		fitChart = buildFitChart(fitCanvas);
		featureCharts = featureCanvases.map((c, i) =>
			c ? buildFeatureChart(c, EVOLUTION_FEATURES[i]) : null
		);

		return () => {
			fitChart?.destroy();
			featureCharts.forEach((c) => c?.destroy());
		};
	});

	onDestroy(() => {
		fitChart?.destroy();
		featureCharts.forEach((c) => c?.destroy());
	});
</script>

<div class="space-y-4">
	<!-- Fit score (gros) -->
	<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
		<div class="flex items-baseline justify-between mb-2">
			<h3 class="text-xs font-semibold uppercase tracking-wider text-[var(--color-fg-muted)]">
				Fit score — convergence vers la cible
			</h3>
			<span class="text-xs text-[var(--color-fg-muted)]">
				100% = chaque feature dans p25-p75
			</span>
		</div>
		<div style="height: 140px;" class="w-full">
			<canvas bind:this={fitCanvas}></canvas>
		</div>
	</div>

	<!-- Features critiques (grid) -->
	<div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
		{#each EVOLUTION_FEATURES as row, i (row.key)}
			{@const target = featureTarget(row)}
			<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
				<div class="flex items-baseline justify-between mb-1.5 gap-2">
					<h4 class="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-fg-muted)] truncate">
						{row.label}
					</h4>
					{#if target !== null}
						<span class="text-[10px] font-mono text-[var(--color-fg-muted)] shrink-0">
							→ {formatValue(target, row)}{row.unit}
						</span>
					{/if}
				</div>
				<div style="height: 70px;" class="w-full">
					<canvas bind:this={featureCanvases[i]}></canvas>
				</div>
			</div>
		{/each}
	</div>
</div>
