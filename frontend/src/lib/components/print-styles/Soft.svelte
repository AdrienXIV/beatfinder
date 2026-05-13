<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';
	import BriefRenderer from '$lib/components/BriefRenderer.svelte';
	import type { StyleProps } from './types';
	import { pickBands, BAND_LABELS } from './types';

	let { detail, brief }: StyleProps = $props();

	const lp = $derived(detail.latest_pattern);
	const bands = $derived(pickBands(lp));
	const bpm = $derived(lp?.tempo?.bpm?.median ?? 0);
	const lufs = $derived(lp?.energy?.lufs_integrated?.median ?? 0);
	const minor = $derived(((lp?.tonality?.mode?.distribution as Record<string, number> | undefined)?.minor ?? 0) * 100);
	const sub = $derived((bands?.sub ?? 0) * 100);
	const bass = $derived((bands?.bass ?? 0) * 100);
	const drop = $derived((lp?.structure?.drop_position_ratio?.median ?? 0) * 100);

	let donutCanvas: HTMLCanvasElement | null = $state(null);
	let donutChart: Chart | null = null;

	// En mode print PDF (Chromium headless), désactiver l'animation Chart.js
	// pour que le canvas soit dessiné immédiatement, sans attendre 1s d'animation.
	const isHeadless =
		typeof navigator !== 'undefined' && /Headless/i.test(navigator.userAgent);

	const today = new Date().toLocaleDateString('fr-FR', {
		weekday: 'long',
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	});

	const pastel = ['#ffb3ba', '#ffdfba', '#ffffba', '#baffc9', '#bae1ff', '#d5baff'];

	const donutData = $derived.by(() => {
		if (!bands) return { labels: [] as string[], values: [] as number[] };
		return {
			labels: Object.keys(BAND_LABELS).map((k) => BAND_LABELS[k]),
			values: Object.keys(BAND_LABELS).map((k) => (bands[k] ?? 0) * 100)
		};
	});

	onMount(() => {
		if (!donutCanvas) return;
		donutChart = new Chart(donutCanvas, {
			type: 'doughnut',
			data: {
				labels: donutData.labels,
				datasets: [
					{
						data: donutData.values,
						backgroundColor: pastel,
						borderColor: '#fff8f0',
						borderWidth: 4,
						hoverOffset: 8
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				cutout: '60%',
				animation: isHeadless ? false : undefined,
				plugins: {
					legend: {
						position: 'right',
						labels: {
							color: '#5a4a4a',
							font: { size: 12, family: 'Plus Jakarta Sans', weight: 500 },
							boxWidth: 14,
							padding: 10
						}
					},
					tooltip: {
						callbacks: {
							label: (ctx) => ` ${ctx.label}: ${(ctx.parsed as number).toFixed(1)}%`
						}
					}
				}
			}
		});
	});

	$effect(() => {
		if (!donutChart) return;
		donutChart.data.labels = donutData.labels;
		donutChart.data.datasets[0].data = donutData.values;
		donutChart.update();
	});

	onDestroy(() => donutChart?.destroy());
</script>

<div class="soft">
	<header class="soft-header">
		<div class="ico">
			<span class="ico-dot a"></span>
			<span class="ico-dot b"></span>
			<span class="ico-dot c"></span>
		</div>
		<div class="head-meta">
			<div class="brand-line">Beatfinder · brief de production</div>
			<div class="date-line">{today}</div>
		</div>
	</header>

	<div class="title-card">
		<div class="card-meta">Playlist</div>
		<h1>{detail.name}</h1>
		<p class="lead">
			{detail.tracks.length} tracks
			{#if detail.owner_display_name}· par {detail.owner_display_name}{/if}
			· {detail.patterns.length} patterns d'analyse
		</p>
	</div>

	<section class="kpi-soft">
		<div class="kc kc-pink">
			<div class="kc-label">BPM médian</div>
			<div class="kc-value">{bpm.toFixed(0)}</div>
			<div class="kc-hint">battements par minute</div>
		</div>
		<div class="kc kc-peach">
			<div class="kc-label">LUFS</div>
			<div class="kc-value">{lufs.toFixed(1)}</div>
			<div class="kc-hint">niveau intégré dB</div>
		</div>
		<div class="kc kc-yellow">
			<div class="kc-label">Mode mineur</div>
			<div class="kc-value">{minor.toFixed(0)}%</div>
			<div class="kc-hint">des tracks</div>
		</div>
		<div class="kc kc-mint">
			<div class="kc-label">Sub-bass</div>
			<div class="kc-value">{sub.toFixed(0)}%</div>
			<div class="kc-hint">20-60 Hz</div>
		</div>
		<div class="kc kc-blue">
			<div class="kc-label">Bass</div>
			<div class="kc-value">{bass.toFixed(0)}%</div>
			<div class="kc-hint">60-250 Hz</div>
		</div>
		<div class="kc kc-purple">
			<div class="kc-label">Drop</div>
			<div class="kc-value">{drop.toFixed(0)}%</div>
			<div class="kc-hint">du track</div>
		</div>
	</section>

	<section class="chart-card">
		<h3>Profil spectral, par bande</h3>
		<p class="card-sub">Distribution de l'énergie sur l'ensemble du spectre, médiane.</p>
		<div class="donut-wrap">
			<canvas bind:this={donutCanvas}></canvas>
		</div>
	</section>

	{#if brief}
		<section class="brief-card">
			<h3>Le brief, en détail</h3>
			<div class="soft-prose">
				<BriefRenderer markdown={brief.markdown} />
			</div>
		</section>
	{/if}

	<footer class="soft-footer">
		Beatfinder · {detail.name} · {today}
	</footer>
</div>

<style>
	@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

	.soft {
		font-family: 'Plus Jakarta Sans', sans-serif;
		color: #3a2e2e;
		background: #fff8f0;
		padding: 1.5rem 1.75rem;
		max-width: 19cm;
		margin: 0 auto;
		font-size: 13px;
		line-height: 1.6;
	}
	@page {
		size: A4 portrait;
		margin: 1.5cm 1cm;
	}

	/* Header */
	.soft-header {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 2rem;
	}
	.ico {
		display: flex;
		gap: 6px;
	}
	.ico-dot {
		width: 16px;
		height: 16px;
		border-radius: 50%;
	}
	.ico-dot.a {
		background: #ffb3ba;
	}
	.ico-dot.b {
		background: #ffdfba;
	}
	.ico-dot.c {
		background: #baffc9;
	}
	.brand-line {
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.15em;
		color: #8a7676;
		font-weight: 600;
	}
	.date-line {
		font-size: 13px;
		color: #5a4a4a;
		margin-top: 2px;
	}

	/* Title card */
	.title-card {
		background: white;
		border-radius: 24px;
		padding: 2rem 2.25rem;
		margin-bottom: 1.5rem;
		box-shadow: 0 4px 16px rgba(255, 179, 186, 0.18);
		border: 1px solid #ffe5d6;
	}
	.card-meta {
		font-size: 11px;
		font-weight: 600;
		color: #b87a7a;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		margin-bottom: 0.5rem;
	}
	.title-card h1 {
		font-size: 36px;
		font-weight: 800;
		letter-spacing: -0.02em;
		margin: 0 0 0.5rem;
		color: #2a1a1a;
		line-height: 1.1;
	}
	.lead {
		font-size: 14px;
		color: #8a7676;
		margin: 0;
	}

	/* KPI cards */
	.kpi-soft {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	.kc {
		padding: 1.25rem 1.5rem;
		border-radius: 20px;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-height: 110px;
	}
	.kc-pink {
		background: #ffe5e9;
	}
	.kc-peach {
		background: #ffeed6;
	}
	.kc-yellow {
		background: #fff6d6;
	}
	.kc-mint {
		background: #d6f5e0;
	}
	.kc-blue {
		background: #d6e9ff;
	}
	.kc-purple {
		background: #e6d6ff;
	}
	.kc-label {
		font-size: 12px;
		font-weight: 600;
		color: #5a4a4a;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	.kc-value {
		font-size: 42px;
		font-weight: 800;
		color: #2a1a1a;
		line-height: 1;
		letter-spacing: -0.02em;
	}
	.kc-hint {
		font-size: 11px;
		color: #8a7676;
	}

	/* Chart card */
	.chart-card,
	.brief-card {
		background: white;
		border-radius: 24px;
		padding: 1.75rem 2rem;
		margin-bottom: 1.5rem;
		box-shadow: 0 4px 16px rgba(255, 179, 186, 0.12);
		border: 1px solid #ffe5d6;
	}
	.chart-card h3,
	.brief-card h3 {
		font-size: 18px;
		font-weight: 700;
		margin: 0 0 0.25rem;
		color: #2a1a1a;
	}
	.card-sub {
		font-size: 12px;
		color: #8a7676;
		margin: 0 0 1rem;
	}
	.donut-wrap {
		height: 280px;
	}

	/* Brief prose */
	.soft-prose :global(h1) {
		display: none;
	}
	.soft-prose :global(h2) {
		font-family: 'Plus Jakarta Sans', sans-serif;
		font-size: 22px;
		font-weight: 700;
		color: #2a1a1a;
		margin: 1.5rem 0 0.5rem;
		padding: 0;
		border: none;
		letter-spacing: -0.01em;
	}
	.soft-prose :global(h3) {
		font-size: 15px;
		font-weight: 600;
		margin: 1rem 0 0.25rem;
		color: #5a4a4a;
	}
	.soft-prose :global(p) {
		font-size: 13px;
		color: #3a2e2e;
		line-height: 1.65;
		margin: 0.4rem 0;
	}
	.soft-prose :global(strong) {
		color: #2a1a1a;
		font-weight: 700;
	}
	.soft-prose :global(em) {
		color: #8a7676;
		font-style: normal;
		font-size: 12px;
	}
	.soft-prose :global(code) {
		background: #ffe5d6;
		color: #b87a3a;
		padding: 0.1rem 0.4rem;
		border-radius: 6px;
		font-family: 'JetBrains Mono', 'Menlo', 'Consolas', monospace;
		font-size: 11px;
		font-weight: 500;
		font-feature-settings: 'tnum';
	}
	.soft-prose :global(table) {
		width: 100%;
		table-layout: fixed;
		border-collapse: separate;
		border-spacing: 0;
		margin: 1rem 0;
		border-radius: 16px;
		overflow: hidden;
		border: 1px solid #ffe5d6;
		font-size: 10.5px;
	}
	.soft-prose :global(thead th) {
		background: #ffe5e9;
		color: #5a4a4a;
		padding: 0.45rem 0.55rem;
		text-align: left;
		font-weight: 700;
		font-size: 9.5px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		border: none;
		overflow-wrap: anywhere;
		word-break: break-word;
	}
	.soft-prose :global(tbody tr:nth-child(even) td) {
		background: #fff8f0;
	}
	.soft-prose :global(tbody tr:nth-child(odd) td) {
		background: white;
	}
	.soft-prose :global(tbody td) {
		padding: 0.4rem 0.55rem;
		border: none;
		font-size: 10.5px;
		overflow-wrap: anywhere;
		word-break: break-word;
	}
	/* Tracks de référence (10 col) */
	.soft-prose :global(table:has(th:nth-child(10)) td:nth-child(n+5)),
	.soft-prose :global(table:has(th:nth-child(10)) th:nth-child(n+5)) {
		white-space: nowrap;
		overflow-wrap: normal;
		word-break: normal;
	}
	.soft-prose :global(table:has(th:nth-child(10)) th:nth-child(1)),
	.soft-prose :global(table:has(th:nth-child(10)) td:nth-child(1)) { width: 26px; text-align: right; white-space: nowrap; }
	.soft-prose :global(table:has(th:nth-child(10)) th:nth-child(2)),
	.soft-prose :global(table:has(th:nth-child(10)) td:nth-child(2)) { width: 36px; text-align: right; white-space: nowrap; }
	.soft-prose :global(table:has(th:nth-child(10)) th:nth-child(5)),
	.soft-prose :global(table:has(th:nth-child(10)) td:nth-child(5)) { width: 50px; text-align: right; }
	.soft-prose :global(table:has(th:nth-child(10)) th:nth-child(6)),
	.soft-prose :global(table:has(th:nth-child(10)) td:nth-child(6)) { width: 70px; }
	.soft-prose :global(table:has(th:nth-child(10)) th:nth-child(7)),
	.soft-prose :global(table:has(th:nth-child(10)) td:nth-child(7)) { width: 42px; text-align: center; }
	.soft-prose :global(table:has(th:nth-child(10)) th:nth-child(8)),
	.soft-prose :global(table:has(th:nth-child(10)) td:nth-child(8)) { width: 58px; text-align: right; }
	.soft-prose :global(table:has(th:nth-child(10)) th:nth-child(9)),
	.soft-prose :global(table:has(th:nth-child(10)) td:nth-child(9)) { width: 64px; text-align: right; }
	.soft-prose :global(table:has(th:nth-child(10)) th:nth-child(10)),
	.soft-prose :global(table:has(th:nth-child(10)) td:nth-child(10)) { width: 58px; text-align: right; }
	/* Profil spectral (5 col) */
	.soft-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(1)),
	.soft-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(1)) { width: 60px; }
	.soft-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(2)),
	.soft-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(2)) { width: 60px; }
	.soft-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(3)),
	.soft-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(3)) { width: 48px; text-align: right; }
	.soft-prose :global(ul) {
		padding-left: 1rem;
		list-style: none;
	}
	.soft-prose :global(li) {
		position: relative;
		padding-left: 1.25rem;
		margin: 0.35rem 0;
	}
	.soft-prose :global(li)::before {
		content: '';
		position: absolute;
		left: 0;
		top: 9px;
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: #ffb3ba;
	}

	/* Footer */
	.soft-footer {
		text-align: center;
		margin-top: 2rem;
		font-size: 11px;
		color: #8a7676;
		padding-top: 1rem;
		border-top: 1px dashed #ffe5d6;
	}



	/* Évite les coupures de blocs au milieu des sections lors du print PDF.
	   + Marges page généreuses + lignes de tableau atomiques + aération entre sections. */
	@media print {
		/* Items individuels protégés contre la coupure */
		.kc,
		.spec-item,
		.title-card,
		.lede,
		.quote-block,
		.lead-block,
		.stat-card,
		.stat-rail,
		.chart-card,
		.numbers,
		.spectral-section,
		.disc-row,
		.liner {
			break-inside: avoid;
			page-break-inside: avoid;
		}
		/* Une ligne de tableau ne doit jamais être coupée */
		tbody tr {
			break-inside: avoid;
			page-break-inside: avoid;
		}
		/* Header de table répété sur chaque page si break dans la table */
		thead {
			display: table-header-group;
		}
		/* Un titre n'est jamais orphelin en bas de page */
		h2,
		h3,
		h4 {
			break-after: avoid;
			page-break-after: avoid;
		}
		.soft-prose :global(.brief-tracks-ref-break) {
			break-before: page;
			page-break-before: always;
			height: 0;
		}
		/* Aération entre sections principales */
		section {
			margin-top: 1rem;
		}
	}
</style>
