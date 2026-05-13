<script lang="ts">
	import BriefRenderer from '$lib/components/BriefRenderer.svelte';
	import type { StyleProps } from './types';
	import { pickBands, BAND_LABELS } from './types';

	let { detail, brief }: StyleProps = $props();

	const lp = $derived(detail.latest_pattern);
	const bands = $derived(pickBands(lp));
	const bpm = $derived(lp?.tempo?.bpm?.median ?? 0);
	const lufs = $derived(lp?.energy?.lufs_integrated?.median ?? 0);
	const crest = $derived(lp?.energy?.crest_factor_db?.median ?? 0);
	const dr = $derived(lp?.energy?.dynamic_range_db?.median ?? 0);
	const peak = $derived(lp?.energy?.true_peak_db?.median ?? 0);
	const centroid = $derived(lp?.spectral?.centroid_hz?.median ?? 0);
	const rolloff = $derived(lp?.spectral?.rolloff85_hz?.median ?? 0);
	const minor = $derived(((lp?.tonality?.mode?.distribution as Record<string, number> | undefined)?.minor ?? 0) * 100);
	const drop = $derived((lp?.structure?.drop_position_ratio?.median ?? 0) * 100);
	const sections = $derived(lp?.structure?.n_sections?.median ?? 0);

	const bandEntries = $derived.by(() => {
		if (!bands) return [];
		return Object.entries(BAND_LABELS).map(([key, label]) => ({
			key,
			label,
			value: (bands[key] ?? 0) * 100
		}));
	});

	const maxBand = $derived(bandEntries.length ? Math.max(...bandEntries.map((b) => b.value), 1) : 1);

	const today = new Date().toLocaleDateString('fr-FR', {
		year: 'numeric',
		month: '2-digit',
		day: '2-digit'
	});

	const docId = $derived(`BF-${detail.spotify_id.slice(0, 8).toUpperCase()}-${detail.patterns.length.toString().padStart(2, '0')}`);
</script>

<div class="bp">
	<!-- Corner marks -->
	<svg class="corner tl" viewBox="0 0 30 30">
		<path d="M0 0h12M0 0v12" stroke="#e8e0c8" stroke-width="1.5" fill="none" />
	</svg>
	<svg class="corner tr" viewBox="0 0 30 30">
		<path d="M30 0h-12M30 0v12" stroke="#e8e0c8" stroke-width="1.5" fill="none" />
	</svg>
	<svg class="corner bl" viewBox="0 0 30 30">
		<path d="M0 30h12M0 30v-12" stroke="#e8e0c8" stroke-width="1.5" fill="none" />
	</svg>
	<svg class="corner br" viewBox="0 0 30 30">
		<path d="M30 30h-12M30 30v-12" stroke="#e8e0c8" stroke-width="1.5" fill="none" />
	</svg>

	<!-- Title block (architectural drawing style) -->
	<header class="title-block">
		<div class="tb-left">
			<div class="tb-logo">
				<svg viewBox="0 0 40 40" class="lg">
					<rect x="2" y="2" width="36" height="36" stroke="#1a3a6e" stroke-width="2" fill="none" />
					<line x1="2" y1="20" x2="38" y2="20" stroke="#1a3a6e" stroke-width="1" />
					<line x1="20" y1="2" x2="20" y2="38" stroke="#1a3a6e" stroke-width="1" />
					<circle cx="20" cy="20" r="4" fill="#1a3a6e" />
				</svg>
				<div class="lg-info">
					<div class="lg-name">BEATFINDER</div>
					<div class="lg-sub">Department of Production Engineering</div>
				</div>
			</div>
		</div>
		<div class="tb-right">
			<table class="meta-table">
				<tbody>
					<tr><td>DOC. ID</td><td>{docId}</td></tr>
					<tr><td>DATE</td><td>{today}</td></tr>
					<tr><td>REV</td><td>{detail.patterns.length}</td></tr>
					<tr><td>SCALE</td><td>1:1</td></tr>
					<tr><td>SHEET</td><td>1 / 1</td></tr>
				</tbody>
			</table>
		</div>
	</header>

	<div class="proj-title">
		<div class="pt-label">PROJECT</div>
		<h1>{detail.name}</h1>
		<div class="pt-spec">
			{detail.tracks.length} tracks · {detail.spotify_id.startsWith('local:')
				? 'LOCAL UPLOAD'
				: 'SPOTIFY PLAYLIST'}
		</div>
	</div>

	<!-- Specifications grid -->
	<section class="spec-block">
		<div class="block-hdr">
			<span class="bh-num">01</span>
			<span class="bh-name">SPECIFICATIONS</span>
			<span class="bh-line"></span>
		</div>
		<div class="spec-grid">
			<div class="spec-item">
				<div class="si-ref">1.1</div>
				<div class="si-lbl">Tempo médian</div>
				<div class="si-val">{bpm.toFixed(1)}<span class="su">BPM</span></div>
			</div>
			<div class="spec-item">
				<div class="si-ref">1.2</div>
				<div class="si-lbl">LUFS intégré</div>
				<div class="si-val">{lufs.toFixed(1)}<span class="su">dB</span></div>
			</div>
			<div class="spec-item">
				<div class="si-ref">1.3</div>
				<div class="si-lbl">True peak</div>
				<div class="si-val">{peak >= 0 ? '+' : ''}{peak.toFixed(1)}<span class="su">dBFS</span></div>
			</div>
			<div class="spec-item">
				<div class="si-ref">1.4</div>
				<div class="si-lbl">Crest factor</div>
				<div class="si-val">{crest.toFixed(1)}<span class="su">dB</span></div>
			</div>
			<div class="spec-item">
				<div class="si-ref">1.5</div>
				<div class="si-lbl">Dynamic range</div>
				<div class="si-val">{dr.toFixed(1)}<span class="su">dB</span></div>
			</div>
			<div class="spec-item">
				<div class="si-ref">1.6</div>
				<div class="si-lbl">Spectral centroid</div>
				<div class="si-val">{centroid.toFixed(0)}<span class="su">Hz</span></div>
			</div>
			<div class="spec-item">
				<div class="si-ref">1.7</div>
				<div class="si-lbl">Rolloff 85%</div>
				<div class="si-val">{rolloff.toFixed(0)}<span class="su">Hz</span></div>
			</div>
			<div class="spec-item">
				<div class="si-ref">1.8</div>
				<div class="si-lbl">Mode mineur</div>
				<div class="si-val">{minor.toFixed(0)}<span class="su">%</span></div>
			</div>
			<div class="spec-item">
				<div class="si-ref">1.9</div>
				<div class="si-lbl">Drop position</div>
				<div class="si-val">{drop.toFixed(0)}<span class="su">%</span></div>
			</div>
			<div class="spec-item">
				<div class="si-ref">1.10</div>
				<div class="si-lbl">Sections / track</div>
				<div class="si-val">{sections.toFixed(1)}<span class="su"></span></div>
			</div>
		</div>
	</section>

	<!-- Spectral wireframe -->
	<section class="wf-block">
		<div class="block-hdr">
			<span class="bh-num">02</span>
			<span class="bh-name">SPECTRAL DISTRIBUTION</span>
			<span class="bh-line"></span>
		</div>
		<div class="wf-chart">
			<svg viewBox="0 0 600 240" class="wf-svg">
				<!-- Grid -->
				{#each [0, 1, 2, 3, 4, 5] as i}
					<line x1="40" y1={20 + i * 36} x2="580" y2={20 + i * 36} stroke="#e8e0c8" stroke-width="0.5" />
				{/each}
				<line x1="40" y1="20" x2="40" y2="200" stroke="#1a3a6e" stroke-width="1" />
				<line x1="40" y1="200" x2="580" y2="200" stroke="#1a3a6e" stroke-width="1" />
				<!-- Y axis labels -->
				{#each [60, 50, 40, 30, 20, 10] as v, i}
					<text x="30" y={24 + i * 36} text-anchor="end" class="ax-lbl">{v}%</text>
				{/each}
				<!-- Bars with technical marks -->
				{#each bandEntries as b, i}
					{@const x = 80 + i * 86}
					{@const h = (b.value / 60) * 180}
					<rect
						x={x - 26}
						y={200 - h}
						width="52"
						height={h}
						fill="none"
						stroke="#1a3a6e"
						stroke-width="1.5"
					/>
					<line
						x1={x - 30}
						y1={200 - h}
						x2={x + 30}
						y2={200 - h}
						stroke="#c1402b"
						stroke-width="1"
						stroke-dasharray="3 2"
					/>
					<text x={x} y={200 - h - 6} text-anchor="middle" class="bar-val">{b.value.toFixed(1)}%</text>
					<text x={x} y="218" text-anchor="middle" class="bar-lbl">{b.label.split(' ')[0]}</text>
					<text x={x} y="232" text-anchor="middle" class="bar-sub">02.{(i + 1).toString().padStart(2, '0')}</text>
				{/each}
			</svg>
		</div>
		<div class="wf-caption">FIG. 02 — Distribution énergétique normalisée par bande spectrale. Mesure prise sur N={detail.tracks.length} échantillons.</div>
	</section>

	<!-- Brief -->
	{#if brief}
		<section class="brief-block">
			<div class="block-hdr">
				<span class="bh-num">03</span>
				<span class="bh-name">TECHNICAL REPORT</span>
				<span class="bh-line"></span>
			</div>
			<div class="bp-prose">
				<BriefRenderer markdown={brief.markdown} />
			</div>
		</section>
	{/if}

	<footer class="bp-footer">
		<div class="ff-meta">
			<span>BEATFINDER</span><span class="ff-sep">|</span>
			<span>{docId}</span><span class="ff-sep">|</span>
			<span>{today}</span><span class="ff-sep">|</span>
			<span>CONFIDENTIAL — INTERNAL USE</span>
		</div>
	</footer>
</div>

<style>
	@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

	.bp {
		font-family: 'IBM Plex Sans', sans-serif;
		color: #1a3a6e;
		background: #faf6e8;
		padding: 1.5rem 1.5rem;
		max-width: 19cm;
		margin: 0 auto;
		font-size: 12px;
		line-height: 1.5;
		position: relative;
		background-image: linear-gradient(to right, rgba(26, 58, 110, 0.04) 1px, transparent 1px),
			linear-gradient(to bottom, rgba(26, 58, 110, 0.04) 1px, transparent 1px);
		background-size: 20px 20px;
	}
	@page {
		size: A4 portrait;
		margin: 1.5cm 1cm;
	}

	/* Corner marks */
	.corner {
		position: absolute;
		width: 30px;
		height: 30px;
	}
	.corner.tl { top: 8px; left: 8px; }
	.corner.tr { top: 8px; right: 8px; }
	.corner.bl { bottom: 8px; left: 8px; }
	.corner.br { bottom: 8px; right: 8px; }

	/* Title block (drafting style) */
	.title-block {
		display: grid;
		grid-template-columns: 1fr 280px;
		gap: 2rem;
		border: 1.5px solid #1a3a6e;
		padding: 0.75rem 1rem;
		margin-bottom: 1rem;
		background: white;
	}
	.tb-logo {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		height: 100%;
	}
	.lg {
		width: 36px;
		height: 36px;
	}
	.lg-name {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 14px;
		font-weight: 600;
		letter-spacing: 0.05em;
	}
	.lg-sub {
		font-family: 'IBM Plex Sans', sans-serif;
		font-size: 9px;
		color: #5a6f8c;
		letter-spacing: 0.05em;
	}
	.meta-table {
		width: 100%;
		font-family: 'IBM Plex Mono', monospace;
		font-size: 9px;
		border-collapse: collapse;
	}
	.meta-table tr {
		border-bottom: 1px solid #d8d0b8;
	}
	.meta-table tr:last-child {
		border-bottom: none;
	}
	.meta-table td {
		padding: 0.15rem 0.25rem;
	}
	.meta-table td:first-child {
		color: #5a6f8c;
		letter-spacing: 0.1em;
	}
	.meta-table td:last-child {
		text-align: right;
		font-weight: 500;
	}

	/* Project title */
	.proj-title {
		border: 1.5px solid #1a3a6e;
		border-top: none;
		padding: 1rem;
		margin-bottom: 1.5rem;
		background: white;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.pt-label {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.2em;
		color: #5a6f8c;
	}
	.proj-title h1 {
		font-family: 'IBM Plex Sans', sans-serif;
		font-size: 36px;
		font-weight: 600;
		margin: 0;
		line-height: 1;
		letter-spacing: -0.01em;
		color: #1a3a6e;
	}
	.pt-spec {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.1em;
		color: #5a6f8c;
	}

	/* Block header */
	.block-hdr {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
		font-family: 'IBM Plex Mono', monospace;
	}
	.bh-num {
		font-size: 18px;
		font-weight: 500;
		color: #c1402b;
	}
	.bh-name {
		font-size: 12px;
		letter-spacing: 0.15em;
		color: #1a3a6e;
		font-weight: 600;
	}
	.bh-line {
		flex: 1;
		height: 1px;
		background: #1a3a6e;
	}

	/* Spec grid */
	.spec-block {
		margin-bottom: 1.75rem;
	}
	.spec-grid {
		display: grid;
		grid-template-columns: repeat(5, 1fr);
		gap: 0;
		border: 1.5px solid #1a3a6e;
		background: white;
	}
	.spec-item {
		padding: 0.75rem 0.85rem;
		border-right: 1px dashed #c8c0a8;
		border-bottom: 1px dashed #c8c0a8;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.spec-item:nth-child(5n) {
		border-right: none;
	}
	.spec-item:nth-last-child(-n + 5) {
		border-bottom: none;
	}
	.si-ref {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 9px;
		color: #c1402b;
		letter-spacing: 0.1em;
	}
	.si-lbl {
		font-size: 10px;
		color: #5a6f8c;
	}
	.si-val {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 22px;
		font-weight: 500;
		color: #1a3a6e;
		line-height: 1.1;
		font-variant-numeric: tabular-nums;
	}
	.su {
		font-size: 10px;
		color: #5a6f8c;
		margin-left: 4px;
	}

	/* Wireframe chart */
	.wf-block {
		margin-bottom: 1.75rem;
	}
	.wf-chart {
		background: white;
		border: 1.5px solid #1a3a6e;
		padding: 1rem 0.5rem 0.25rem;
	}
	.wf-svg {
		width: 100%;
		height: auto;
		display: block;
	}
	.ax-lbl,
	.bar-lbl,
	.bar-sub,
	.bar-val {
		font-family: 'IBM Plex Mono', monospace;
	}
	.ax-lbl {
		font-size: 8px;
		fill: #5a6f8c;
	}
	.bar-lbl {
		font-size: 8px;
		fill: #1a3a6e;
		font-weight: 500;
	}
	.bar-sub {
		font-size: 7px;
		fill: #c1402b;
		letter-spacing: 0.05em;
	}
	.bar-val {
		font-size: 9px;
		fill: #1a3a6e;
		font-weight: 600;
	}
	.wf-caption {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 9px;
		color: #5a6f8c;
		margin-top: 0.4rem;
		font-style: italic;
	}

	/* Brief */
	.brief-block {
		margin-bottom: 2rem;
	}
	.bp-prose {
		background: white;
		border: 1.5px solid #1a3a6e;
		padding: 1.5rem 1.75rem;
		font-family: 'IBM Plex Sans', sans-serif;
		font-size: 11.5px;
		line-height: 1.55;
		color: #1a3a6e;
	}
	.bp-prose :global(h1) {
		display: none;
	}
	.bp-prose :global(h2) {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.15em;
		text-transform: uppercase;
		color: #c1402b;
		margin: 1.5rem 0 0.5rem;
		padding-bottom: 0.3rem;
		border-bottom: 1px solid #1a3a6e;
		font-weight: 500;
	}
	.bp-prose :global(h2):first-child {
		margin-top: 0;
	}
	.bp-prose :global(h3) {
		font-family: 'IBM Plex Sans', sans-serif;
		font-size: 13px;
		font-weight: 600;
		margin: 0.75rem 0 0.25rem;
		color: #1a3a6e;
	}
	.bp-prose :global(p) {
		margin: 0.4rem 0;
	}
	.bp-prose :global(strong) {
		color: #1a3a6e;
		font-weight: 600;
		background: #fff5e8;
		padding: 0 0.2rem;
	}
	.bp-prose :global(em) {
		font-style: normal;
		color: #5a6f8c;
		font-size: 11px;
	}
	.bp-prose :global(code) {
		font-family: 'IBM Plex Mono', monospace;
		background: #fff5e8;
		color: #c1402b;
		padding: 0.05rem 0.3rem;
		font-size: 11px;
		border-radius: 0;
	}
	.bp-prose :global(table) {
		width: 100%;
		table-layout: fixed;
		border-collapse: collapse;
		margin: 0.75rem 0;
		font-family: 'IBM Plex Mono', monospace;
		font-size: 9px;
		border: 1px solid #1a3a6e;
	}
	.bp-prose :global(thead th) {
		text-align: left;
		padding: 0.35rem 0.45rem;
		color: #1a3a6e;
		background: #f0e8d0;
		border-bottom: 1px solid #1a3a6e;
		font-family: 'IBM Plex Mono', monospace;
		font-size: 8.5px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-weight: 500;
		overflow-wrap: anywhere;
		word-break: break-word;
	}
	.bp-prose :global(tbody td) {
		padding: 0.3rem 0.45rem;
		border-bottom: 1px dashed #c8c0a8;
		color: #1a3a6e;
		overflow-wrap: anywhere;
		word-break: break-word;
	}
	/* Tracks de référence (10 col) */
	.bp-prose :global(table:has(th:nth-child(10)) td:nth-child(n+5)),
	.bp-prose :global(table:has(th:nth-child(10)) th:nth-child(n+5)) {
		white-space: nowrap;
		overflow-wrap: normal;
		word-break: normal;
	}
	.bp-prose :global(table:has(th:nth-child(10)) th:nth-child(1)),
	.bp-prose :global(table:has(th:nth-child(10)) td:nth-child(1)) { width: 24px; text-align: right; white-space: nowrap; }
	.bp-prose :global(table:has(th:nth-child(10)) th:nth-child(2)),
	.bp-prose :global(table:has(th:nth-child(10)) td:nth-child(2)) { width: 34px; text-align: right; white-space: nowrap; }
	.bp-prose :global(table:has(th:nth-child(10)) th:nth-child(5)),
	.bp-prose :global(table:has(th:nth-child(10)) td:nth-child(5)) { width: 48px; text-align: right; }
	.bp-prose :global(table:has(th:nth-child(10)) th:nth-child(6)),
	.bp-prose :global(table:has(th:nth-child(10)) td:nth-child(6)) { width: 68px; }
	.bp-prose :global(table:has(th:nth-child(10)) th:nth-child(7)),
	.bp-prose :global(table:has(th:nth-child(10)) td:nth-child(7)) { width: 42px; text-align: center; }
	.bp-prose :global(table:has(th:nth-child(10)) th:nth-child(8)),
	.bp-prose :global(table:has(th:nth-child(10)) td:nth-child(8)) { width: 56px; text-align: right; }
	.bp-prose :global(table:has(th:nth-child(10)) th:nth-child(9)),
	.bp-prose :global(table:has(th:nth-child(10)) td:nth-child(9)) { width: 62px; text-align: right; }
	.bp-prose :global(table:has(th:nth-child(10)) th:nth-child(10)),
	.bp-prose :global(table:has(th:nth-child(10)) td:nth-child(10)) { width: 56px; text-align: right; }
	/* Profil spectral (5 col) */
	.bp-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(1)),
	.bp-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(1)) { width: 54px; }
	.bp-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(2)),
	.bp-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(2)) { width: 54px; }
	.bp-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(3)),
	.bp-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(3)) { width: 44px; text-align: right; }
	.bp-prose :global(ul) {
		padding-left: 0;
		list-style: none;
	}
	.bp-prose :global(li) {
		position: relative;
		padding-left: 1.25rem;
		margin: 0.35rem 0;
	}
	.bp-prose :global(li)::before {
		content: '+';
		position: absolute;
		left: 0;
		color: #c1402b;
		font-family: 'IBM Plex Mono', monospace;
		font-weight: 600;
	}

	/* Footer */
	.bp-footer {
		margin-top: 2rem;
		border-top: 1.5px solid #1a3a6e;
		padding-top: 0.5rem;
	}
	.ff-meta {
		font-family: 'IBM Plex Mono', monospace;
		font-size: 9px;
		color: #5a6f8c;
		letter-spacing: 0.1em;
		text-align: center;
	}
	.ff-sep {
		margin: 0 0.6rem;
		color: #c8c0a8;
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
		.brief-block {
			break-before: page;
			page-break-before: always;
		}
		/* Aération entre sections principales */
		section {
			margin-top: 1rem;
		}
	}
</style>
