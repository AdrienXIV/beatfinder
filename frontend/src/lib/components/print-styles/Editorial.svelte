<script lang="ts">
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

	// Concentric ring chart : 6 anneaux empilés, chacun pour une bande
	const ringData = $derived.by(() => {
		if (!bands) return [];
		return Object.entries(BAND_LABELS).map(([key, label]) => ({
			key,
			label,
			value: bands[key] ?? 0
		}));
	});

	const today = new Date().toLocaleDateString('fr-FR', {
		year: 'numeric',
		month: 'long',
		day: 'numeric'
	});
</script>

<div class="editorial">
	<!-- Top header magazine -->
	<header class="masthead">
		<div class="masthead-left">
			<div class="issue">Volume 1 · Numéro {detail.patterns.length}</div>
			<h1>BEATFINDER</h1>
			<div class="subtitle">Le brief de production</div>
		</div>
		<div class="masthead-right">
			<div class="date">{today}</div>
			<div class="meta">{detail.tracks.length} tracks analysées</div>
		</div>
	</header>

	<!-- Title block -->
	<section class="title-block">
		<div class="kicker">DOSSIER · PROFIL DE PLAYLIST</div>
		<h2 class="title">{detail.name}</h2>
		<p class="byline">
			Une étude des médianes, dispersions et signatures acoustiques sur l'ensemble du catalogue.
		</p>
	</section>

	<!-- Big numbers row -->
	<section class="numbers">
		<div class="num">
			<div class="n">{bpm.toFixed(0)}</div>
			<div class="lbl">BPM<br />médian</div>
		</div>
		<div class="sep"></div>
		<div class="num">
			<div class="n">{lufs.toFixed(1)}</div>
			<div class="lbl">LUFS<br />intégré</div>
		</div>
		<div class="sep"></div>
		<div class="num">
			<div class="n">{minor.toFixed(0)}<span class="pc">%</span></div>
			<div class="lbl">Mode<br />mineur</div>
		</div>
		<div class="sep"></div>
		<div class="num">
			<div class="n">{(sub + bass).toFixed(0)}<span class="pc">%</span></div>
			<div class="lbl">Énergie<br />sous 250 Hz</div>
		</div>
		<div class="sep"></div>
		<div class="num">
			<div class="n">{drop.toFixed(0)}<span class="pc">%</span></div>
			<div class="lbl">Position<br />du drop</div>
		</div>
	</section>

	<!-- Spectral concentric ring chart -->
	<section class="spectral-section">
		<h3 class="section-title">Anatomie spectrale</h3>
		<div class="spectral-grid">
			<div class="spectral-chart">
				{#if bands}
					<svg viewBox="0 0 240 240" class="rings">
						{#each ringData as ring, i (ring.key)}
							{@const radius = 110 - i * 16}
							{@const circumference = 2 * Math.PI * radius}
							{@const filled = ring.value * circumference}
							<circle
								cx="120"
								cy="120"
								r={radius}
								fill="none"
								stroke="#e8dccc"
								stroke-width="11"
							/>
							<circle
								cx="120"
								cy="120"
								r={radius}
								fill="none"
								stroke="#1a1a1a"
								stroke-width="11"
								stroke-dasharray="{filled} {circumference}"
								stroke-linecap="butt"
								transform="rotate(-90 120 120)"
							/>
						{/each}
					</svg>
				{/if}
			</div>
			<div class="spectral-legend">
				{#each ringData as ring, i (ring.key)}
					<div class="legend-row">
						<span class="legend-idx">{String(i + 1).padStart(2, '0')}</span>
						<span class="legend-label">{ring.label}</span>
						<span class="legend-dots"></span>
						<span class="legend-value">{(ring.value * 100).toFixed(1)}<span class="ppc">%</span></span>
					</div>
				{/each}
			</div>
		</div>
	</section>

	<!-- Brief body in 2 columns with drop cap -->
	{#if brief}
		<section class="brief-prose">
			<h3 class="section-title">Le détail</h3>
			<div class="prose-columns">
				<BriefRenderer markdown={brief.markdown} />
			</div>
		</section>
	{/if}

	<footer class="ed-footer">
		<span class="brand-mark">— Beatfinder ·</span>
		<span>{detail.name}</span>
		<span class="dot">·</span>
		<span>{today}</span>
	</footer>
</div>

<style>
	@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;700;900&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

	.editorial {
		font-family: 'Inter', sans-serif;
		color: #1a1a1a;
		background: #faf8f4;
		padding: 1.75rem 2rem;
		max-width: 19cm;
		margin: 0 auto;
		font-size: 13px;
		line-height: 1.5;
	}
	@page {
		size: A4 portrait;
		margin: 1.5cm 1cm;
	}

	/* Masthead */
	.masthead {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		border-bottom: 3px solid #1a1a1a;
		padding-bottom: 1rem;
		margin-bottom: 2.5rem;
	}
	.masthead h1 {
		font-family: 'Playfair Display', serif;
		font-weight: 900;
		font-size: 56px;
		line-height: 0.9;
		letter-spacing: -0.02em;
		margin: 0.25rem 0;
	}
	.issue,
	.subtitle,
	.date,
	.meta {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.2em;
		color: #5c544a;
	}
	.subtitle {
		font-family: 'Playfair Display', serif;
		font-style: italic;
		text-transform: none;
		font-size: 14px;
		letter-spacing: 0;
	}
	.masthead-right {
		text-align: right;
	}

	/* Title block */
	.title-block {
		margin-bottom: 2.5rem;
		padding-bottom: 2rem;
		border-bottom: 1px solid #d4c8b4;
	}
	.kicker {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.25em;
		color: #b8651b;
		font-weight: 600;
		margin-bottom: 0.75rem;
	}
	.title {
		font-family: 'Playfair Display', serif;
		font-size: 52px;
		font-weight: 700;
		line-height: 1.05;
		letter-spacing: -0.02em;
		margin: 0 0 1rem;
	}
	.byline {
		font-family: 'Playfair Display', serif;
		font-style: italic;
		font-size: 18px;
		color: #5c544a;
		max-width: 32rem;
		margin: 0;
	}

	/* Big numbers */
	.numbers {
		display: grid;
		grid-template-columns: 1fr 1px 1fr 1px 1fr 1px 1fr 1px 1fr;
		gap: 1.5rem;
		padding: 2rem 0;
		margin-bottom: 2.5rem;
		border-top: 1px solid #d4c8b4;
		border-bottom: 1px solid #d4c8b4;
		align-items: center;
	}
	.num {
		text-align: center;
	}
	.n {
		font-family: 'Playfair Display', serif;
		font-size: 56px;
		font-weight: 700;
		line-height: 1;
		letter-spacing: -0.02em;
	}
	.pc {
		font-size: 28px;
		color: #b8651b;
		margin-left: 2px;
	}
	.lbl {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.15em;
		color: #5c544a;
		margin-top: 0.5rem;
	}
	.sep {
		background: #d4c8b4;
		width: 1px;
		height: 80px;
		justify-self: center;
	}

	/* Section title */
	.section-title {
		font-family: 'Playfair Display', serif;
		font-size: 24px;
		font-weight: 700;
		margin: 0 0 1.5rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid #1a1a1a;
		display: inline-block;
		min-width: 100%;
		letter-spacing: -0.01em;
	}

	/* Spectral */
	.spectral-section {
		margin-bottom: 3rem;
	}
	.spectral-grid {
		display: grid;
		grid-template-columns: 280px 1fr;
		gap: 3rem;
		align-items: center;
	}
	.spectral-chart {
		background: #f0e8d8;
		padding: 1.5rem;
		border-radius: 50%;
		aspect-ratio: 1;
	}
	.rings {
		width: 100%;
		height: 100%;
		display: block;
	}
	.spectral-legend {
		font-family: 'Inter', sans-serif;
	}
	.legend-row {
		display: grid;
		grid-template-columns: auto 1fr auto auto;
		gap: 0.6rem;
		align-items: baseline;
		padding: 0.5rem 0;
		border-bottom: 1px dotted #d4c8b4;
	}
	.legend-idx {
		font-family: 'Playfair Display', serif;
		font-size: 13px;
		color: #b8651b;
		font-weight: 600;
	}
	.legend-label {
		font-family: 'Playfair Display', serif;
		font-style: italic;
		font-size: 15px;
	}
	.legend-dots {
		border-bottom: 1px dotted #b8a98f;
	}
	.legend-value {
		font-family: 'Playfair Display', serif;
		font-size: 20px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.ppc {
		font-size: 13px;
		color: #b8651b;
	}

	/* Brief prose en 2 colonnes */
	.brief-prose {
		margin-bottom: 2rem;
	}
	.prose-columns {
		column-count: 2;
		column-gap: 2.5rem;
		column-rule: 1px solid #d4c8b4;
		font-family: 'Inter', sans-serif;
		font-size: 12px;
		line-height: 1.65;
	}
	.prose-columns :global(h1) {
		display: none;
	}
	.prose-columns :global(h2) {
		font-family: 'Playfair Display', serif;
		font-size: 22px;
		font-weight: 700;
		margin: 1.5rem 0 0.5rem;
		letter-spacing: -0.01em;
		break-after: avoid;
		column-span: none;
	}
	.prose-columns :global(h3) {
		font-family: 'Playfair Display', serif;
		font-size: 16px;
		font-weight: 600;
		font-style: italic;
		margin: 0.75rem 0 0.25rem;
	}
	.prose-columns :global(p) {
		margin: 0.4rem 0;
		text-align: justify;
		hyphens: auto;
	}
	.prose-columns :global(strong) {
		font-weight: 600;
		color: #1a1a1a;
	}
	.prose-columns :global(em) {
		font-style: italic;
		color: #5c544a;
	}
	.prose-columns :global(code) {
		font-family: 'JetBrains Mono', 'Menlo', 'Consolas', monospace;
		background: #f0e8d8;
		padding: 0.05rem 0.3rem;
		border-radius: 0;
		font-size: 0.85em;
		font-feature-settings: 'tnum';
	}
	.prose-columns :global(table) {
		width: 100%;
		table-layout: fixed;
		font-size: 9px;
		border-collapse: collapse;
		margin: 0.75rem 0;
		break-inside: avoid;
		column-span: all;
	}
	.prose-columns :global(thead th) {
		font-family: 'Playfair Display', serif;
		font-style: italic;
		font-weight: 500;
		text-align: left;
		padding: 0.3rem 0.4rem;
		border-bottom: 2px solid #1a1a1a;
		font-size: 10px;
		text-transform: none;
		letter-spacing: 0;
		color: #1a1a1a;
		background: transparent;
		overflow-wrap: anywhere;
		word-break: break-word;
	}
	.prose-columns :global(tbody td) {
		padding: 0.3rem 0.4rem;
		border-bottom: 1px solid #d4c8b4;
		overflow-wrap: anywhere;
		word-break: break-word;
	}
	/* Tracks de référence (10 col) : numériques étroits, artiste/titre flex */
	.prose-columns :global(table:has(th:nth-child(10)) td:nth-child(n+5)),
	.prose-columns :global(table:has(th:nth-child(10)) th:nth-child(n+5)) {
		white-space: nowrap;
		overflow-wrap: normal;
		word-break: normal;
	}
	.prose-columns :global(table:has(th:nth-child(10)) th:nth-child(1)),
	.prose-columns :global(table:has(th:nth-child(10)) td:nth-child(1)) {
		width: 24px;
		text-align: right;
		white-space: nowrap;
	}
	.prose-columns :global(table:has(th:nth-child(10)) th:nth-child(2)),
	.prose-columns :global(table:has(th:nth-child(10)) td:nth-child(2)) {
		width: 32px;
		text-align: right;
		white-space: nowrap;
	}
	.prose-columns :global(table:has(th:nth-child(10)) th:nth-child(5)),
	.prose-columns :global(table:has(th:nth-child(10)) td:nth-child(5)) {
		width: 46px;
		text-align: right;
	}
	.prose-columns :global(table:has(th:nth-child(10)) th:nth-child(6)),
	.prose-columns :global(table:has(th:nth-child(10)) td:nth-child(6)) {
		width: 64px;
	}
	.prose-columns :global(table:has(th:nth-child(10)) th:nth-child(7)),
	.prose-columns :global(table:has(th:nth-child(10)) td:nth-child(7)) {
		width: 40px;
		text-align: center;
	}
	.prose-columns :global(table:has(th:nth-child(10)) th:nth-child(8)),
	.prose-columns :global(table:has(th:nth-child(10)) td:nth-child(8)) {
		width: 54px;
		text-align: right;
	}
	.prose-columns :global(table:has(th:nth-child(10)) th:nth-child(9)),
	.prose-columns :global(table:has(th:nth-child(10)) td:nth-child(9)) {
		width: 60px;
		text-align: right;
	}
	.prose-columns :global(table:has(th:nth-child(10)) th:nth-child(10)),
	.prose-columns :global(table:has(th:nth-child(10)) td:nth-child(10)) {
		width: 54px;
		text-align: right;
	}
	/* Profil spectral (5 col) : col 1-3 étroites, col 4 (bar) min, col 5 flex */
	.prose-columns :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(1)),
	.prose-columns :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(1)) {
		width: 56px;
	}
	.prose-columns :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(2)),
	.prose-columns :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(2)) {
		width: 56px;
	}
	.prose-columns :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(3)),
	.prose-columns :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(3)) {
		width: 44px;
		text-align: right;
	}
	.prose-columns :global(ul) {
		padding-left: 1.2rem;
		margin: 0.4rem 0;
	}
	.prose-columns :global(li) {
		margin: 0.2rem 0;
	}

	/* Footer */
	.ed-footer {
		margin-top: 3rem;
		padding-top: 1rem;
		border-top: 3px solid #1a1a1a;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.2em;
		color: #5c544a;
		display: flex;
		gap: 0.5rem;
	}
	.brand-mark {
		font-weight: 600;
		color: #1a1a1a;
	}
	.dot {
		color: #b8a98f;
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
		/* Aération entre sections principales */
		section {
			margin-top: 1rem;
		}
	}
</style>
