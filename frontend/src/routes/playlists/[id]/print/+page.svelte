<script lang="ts">
	import '../../../../app.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import type { PageData } from './$types';
	import { isLocalProject } from '$lib/api';
	import BriefRenderer from '$lib/components/BriefRenderer.svelte';
	import SpectralRing from '$lib/components/charts/SpectralRing.svelte';
	import BpmHistogram from '$lib/components/charts/BpmHistogram.svelte';
	import { formatDateTime, formatNumber, formatPercent } from '$lib/utils';

	let { data }: { data: PageData } = $props();
	const { detail, brief } = $derived(data);

	const lp = $derived(detail.latest_pattern);
	const bpm = $derived(lp?.tempo?.bpm?.median);
	const lufs = $derived(lp?.energy?.lufs_integrated?.median);
	const modeDist = $derived(lp?.tonality?.mode?.distribution as Record<string, number> | undefined);
	const minor = $derived(modeDist?.minor ?? 0);
	const subPct = $derived(lp?.spectral?.band_energy?.sub?.median);
	const bassPct = $derived(lp?.spectral?.band_energy?.bass?.median);
	const drop = $derived(lp?.structure?.drop_position_ratio?.median);
	const isLocal = $derived(isLocalProject(detail.spotify_id));

	const bandsForRadar = $derived.by(() => {
		const be = lp?.spectral?.band_energy;
		if (!be) return null;
		return {
			sub: be.sub?.median,
			bass: be.bass?.median,
			low_mid: be.low_mid?.median,
			mid: be.mid?.median,
			high_mid: be.high_mid?.median,
			high: be.high?.median
		} as Record<string, number>;
	});

	const bpmRaw = $derived(((lp?.tempo?.bpm_raw as number[] | undefined) ?? []).filter(Boolean));

	const coherenceFlags = $derived(
		((lp?.coherence_flags as string[] | undefined) ?? []).filter(Boolean)
	);
	const coherenceLabels: Record<string, string> = {
		bpm: 'BPM',
		mode: 'mode mineur/majeur',
		sub: 'sub-bass'
	};
	const coherenceText = $derived(
		coherenceFlags.map((f) => coherenceLabels[f] ?? f).join(', ')
	);

	const todayStr = new Date().toLocaleDateString('fr-FR', {
		year: 'numeric',
		month: 'long',
		day: 'numeric'
	});

	function back() {
		goto(`/playlists/${encodeURIComponent(detail.spotify_id)}`);
	}

	let chartsReady = $state(false);
	onMount(() => {
		// Donne aux canvas Chart.js le temps de se mounter avant qu'un éventuel print
		// déclenché manuellement les capture.
		setTimeout(() => (chartsReady = true), 400);
	});
</script>

<div class="print-shell">
	<!-- Toolbar (cachée au print) -->
	<div class="no-print toolbar">
		<button class="tb-btn ghost" onclick={back}>← Retour</button>
		<span class="tb-spacer"></span>
		<button class="tb-btn primary" onclick={() => window.print()} disabled={!chartsReady}>
			{chartsReady ? 'Imprimer en PDF' : 'Préparation…'}
		</button>
	</div>

	<article class="page">
	<!-- Header brief -->
	<header class="brief-header">
		<div class="brief-mark">
			<span class="dot"></span>
			<span class="brand">Beatfinder</span>
			<span class="version">v1.7</span>
		</div>
		<h1>Brief de production</h1>
		<h2>
			{detail.name}
			<span class="src">· {isLocal ? 'Projet local' : 'Playlist Spotify'}</span>
		</h2>
		<p class="meta">
			{detail.tracks.length} tracks · {detail.patterns.length} patterns
			{#if detail.owner_display_name}· par {detail.owner_display_name}{/if}
			· généré le {todayStr}
		</p>
	</header>

	{#if coherenceFlags.length > 0}
		<div class="coherence-banner">
			<strong>⚠ Projet hétérogène</strong> — variabilité forte sur
			<strong>{coherenceText}</strong>. Pattern global bruité ; recos vs cible peu fiables.
		</div>
	{/if}

	<!-- KPI grid -->
	{#if lp}
		<section class="kpis">
			<div class="kpi">
				<span class="kpi-label">BPM médian</span>
				<span class="kpi-value">{formatNumber(bpm, 0)}</span>
			</div>
			<div class="kpi">
				<span class="kpi-label">LUFS</span>
				<span class="kpi-value">{formatNumber(lufs, 1)}</span>
				<span class="kpi-hint">dB intégré</span>
			</div>
			<div class="kpi">
				<span class="kpi-label">Mineur</span>
				<span class="kpi-value">{formatPercent(minor, 0)}</span>
			</div>
			<div class="kpi">
				<span class="kpi-label">Sub 20-60Hz</span>
				<span class="kpi-value">{formatPercent(subPct, 0)}</span>
			</div>
			<div class="kpi">
				<span class="kpi-label">Bass 60-250Hz</span>
				<span class="kpi-value">{formatPercent(bassPct, 0)}</span>
			</div>
			<div class="kpi">
				<span class="kpi-label">Drop pos</span>
				<span class="kpi-value">{formatPercent(drop, 0)}</span>
				<span class="kpi-hint">du track</span>
			</div>
		</section>

		<section class="charts">
			{#if bandsForRadar}
				<div class="chart-card">
					<h3>Profil spectral</h3>
					<SpectralRing bands={bandsForRadar} size={200} />
				</div>
			{/if}
			{#if bpmRaw.length > 0}
				<div class="chart-card">
					<h3>Distribution BPM</h3>
					<p class="chart-sub">{bpmRaw.length} tracks · médiane {formatNumber(bpm, 0)} BPM</p>
					<BpmHistogram bpms={bpmRaw} height={250} />
				</div>
			{/if}
		</section>
	{/if}

	<!-- Brief markdown rendu -->
	{#if brief}
		<section class="brief-body">
			<BriefRenderer markdown={brief.markdown} />
		</section>
	{:else}
		<p class="muted">Pas de brief disponible. Analyse cette playlist puis réessaie.</p>
	{/if}

	<footer class="page-footer">
		<span>Beatfinder · {detail.name}</span>
		<span>{todayStr}</span>
	</footer>
	</article>
</div>

<style>
	@page {
		size: A4 portrait;
		margin: 1.5cm 1.2cm;
	}

	/* La shell couvre toute la viewport en blanc et override les vars CSS pour
	   que tous les composants partagés (BriefRenderer, charts) suivent. */
	.print-shell {
		min-height: 100vh;
		background: white;
		color: #1a1a1a;
		--color-bg: white;
		--color-fg: #1a1a1a;
		--color-fg-muted: #525252;
		--color-surface: white;
		--color-surface-2: #f5f5f5;
		--color-border: #e5e5e5;
		--color-accent: #f97316;
		--color-accent-fg: white;
		--color-warn: #f59e0b;
		--color-ok: #10b981;
		--color-err: #ef4444;
	}

	/* Toolbar */
	.toolbar {
		position: sticky;
		top: 0;
		z-index: 50;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		background: #fafafa;
		border-bottom: 1px solid #e5e5e5;
	}
	.tb-spacer {
		flex: 1;
	}
	.tb-btn {
		appearance: none;
		border: 1px solid #d4d4d4;
		background: white;
		color: #1a1a1a;
		font: 500 14px/1 'Inter', sans-serif;
		padding: 0.5rem 1rem;
		border-radius: 6px;
		cursor: pointer;
	}
	.tb-btn:hover {
		background: #f5f5f5;
	}
	.tb-btn.primary {
		background: #f97316;
		color: white;
		border-color: #f97316;
	}
	.tb-btn.primary:hover {
		background: #ea580c;
	}
	.tb-btn:disabled {
		opacity: 0.5;
		cursor: wait;
	}

	/* Page wrapper */
	.page {
		max-width: 19cm;
		margin: 1.5rem auto;
		padding: 2rem 1.5rem;
		background: white;
		color: #1a1a1a;
		box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
	}
	@media print {
		.page {
			max-width: none;
			margin: 0;
			padding: 0;
			box-shadow: none;
		}
	}

	/* Header */
	.brief-header {
		border-bottom: 2px solid #f97316;
		padding-bottom: 1rem;
		margin-bottom: 1.5rem;
	}
	.brief-mark {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 12px;
		font-weight: 600;
		letter-spacing: 0.02em;
		color: #525252;
		margin-bottom: 0.75rem;
	}
	.dot {
		display: inline-block;
		width: 10px;
		height: 10px;
		border-radius: 2px;
		background: #f97316;
	}
	.brand {
		color: #1a1a1a;
	}
	.version {
		padding: 0.1rem 0.4rem;
		background: #f5f5f5;
		border-radius: 3px;
		font-family: 'JetBrains Mono', ui-monospace, monospace;
		font-size: 10px;
		text-transform: uppercase;
	}
	.brief-header h1 {
		margin: 0;
		font-size: 14px;
		text-transform: uppercase;
		letter-spacing: 0.15em;
		color: #737373;
		font-weight: 500;
	}
	.brief-header h2 {
		margin: 0.2rem 0 0.5rem;
		font-size: 28px;
		font-weight: 700;
		letter-spacing: -0.01em;
		color: #0a0a0b;
	}
	.brief-header .src {
		font-size: 14px;
		font-weight: 400;
		color: #737373;
	}
	.meta {
		margin: 0;
		font-size: 12px;
		color: #737373;
	}

	/* Coherence banner */
	.coherence-banner {
		background: #fef3c7;
		border-left: 4px solid #f59e0b;
		padding: 0.75rem 1rem;
		font-size: 13px;
		color: #78350f;
		margin-bottom: 1.5rem;
		border-radius: 4px;
	}

	/* KPIs grid */
	.kpis {
		display: grid;
		grid-template-columns: repeat(6, 1fr);
		gap: 0.75rem;
		margin-bottom: 1.5rem;
		page-break-inside: avoid;
	}
	.kpi {
		border: 1px solid #e5e5e5;
		border-radius: 6px;
		padding: 0.6rem 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}
	.kpi-label {
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: #737373;
		font-weight: 500;
	}
	.kpi-value {
		font-family: 'JetBrains Mono', ui-monospace, monospace;
		font-size: 22px;
		font-weight: 600;
		color: #0a0a0b;
		line-height: 1;
	}
	.kpi-hint {
		font-size: 9px;
		color: #a3a3a3;
	}

	/* Charts row */
	.charts {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		margin-bottom: 1.5rem;
		page-break-inside: avoid;
	}
	.chart-card {
		border: 1px solid #e5e5e5;
		border-radius: 6px;
		padding: 0.75rem;
		background: white;
	}
	.chart-card h3 {
		margin: 0 0 0.4rem;
		font-size: 13px;
		font-weight: 600;
		color: #0a0a0b;
	}
	.chart-sub {
		margin: 0 0 0.5rem;
		font-size: 11px;
		color: #737373;
	}

	/* Brief body */
	.brief-body {
		margin-top: 1.5rem;
		font-size: 13px;
		line-height: 1.55;
	}
	.muted {
		color: #737373;
		font-style: italic;
	}
	.page-footer {
		margin-top: 2rem;
		padding-top: 0.75rem;
		border-top: 1px solid #e5e5e5;
		display: flex;
		justify-content: space-between;
		font-size: 11px;
		color: #a3a3a3;
	}

	/* Print overrides */
	@media print {
		.toolbar {
			display: none !important;
		}
		.charts {
			grid-template-columns: 1fr 1fr;
		}
		.kpis {
			grid-template-columns: repeat(6, 1fr);
		}
		.brief-header,
		.kpis,
		.charts,
		.coherence-banner,
		.page-footer {
			page-break-inside: avoid;
		}
		.brief-body :global(h1) {
			page-break-after: avoid;
		}
	}
</style>
