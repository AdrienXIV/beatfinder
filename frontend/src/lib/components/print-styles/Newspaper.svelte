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
	const minor = $derived(((lp?.tonality?.mode?.distribution as Record<string, number> | undefined)?.minor ?? 0) * 100);
	const sub = $derived((bands?.sub ?? 0) * 100);
	const bass = $derived((bands?.bass ?? 0) * 100);
	const drop = $derived((lp?.structure?.drop_position_ratio?.median ?? 0) * 100);
	const centroid = $derived(lp?.spectral?.centroid_hz?.median ?? 0);
	const sections = $derived(lp?.structure?.n_sections?.median ?? 0);
	const duration = $derived(lp?.duration_sec?.median ?? 0);

	const todayLong = new Date().toLocaleDateString('fr-FR', {
		weekday: 'long',
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	}).toUpperCase();

	const bandRows = $derived.by(() => {
		if (!bands) return [];
		const total = Object.values(bands).reduce((a, b) => a + b, 0);
		return Object.entries(BAND_LABELS).map(([key, label]) => ({
			label,
			value: bands[key] ?? 0,
			share: total ? ((bands[key] ?? 0) / total) * 100 : 0
		}));
	});
</script>

<div class="paper">
	<!-- Nameplate -->
	<header class="nameplate">
		<div class="np-date">{todayLong}</div>
		<h1 class="np-title">LE BRIEF</h1>
		<div class="np-tag">Une publication Beatfinder · Section production</div>
		<div class="np-rule"></div>
	</header>

	<!-- Headline -->
	<section class="lede">
		<div class="kicker">DOSSIER · PROFIL ACOUSTIQUE</div>
		<h2 class="headline">{detail.name}</h2>
		<div class="deck">
			Une analyse statistique de {detail.tracks.length} titres explore les médianes
			rythmiques, tonales et spectrales d'un catalogue
			{detail.owner_display_name ? `signé ${detail.owner_display_name}` : 'analysé en interne'}.
		</div>
		<div class="byline">Par BEATFINDER STAFF · Édition n°{detail.patterns.length}</div>
	</section>

	<!-- Body en 3 colonnes -->
	<section class="body-3col">
		<div class="col">
			<div class="lead-block">
				<p class="first-p">
					Le tempo médian s'établit à <strong>{bpm.toFixed(0)} BPM</strong>, niveau intégré médian
					<strong>{lufs.toFixed(1)} LUFS</strong>, conforme aux pratiques modernes du genre.
					L'analyse révèle un profil spectral dominé par le bas du spectre, signature classique
					du registre.
				</p>
			</div>
			<h4 class="ssect">FAITS CHIFFRÉS</h4>
			<table class="fact-table">
				<tbody>
					<tr><td>BPM médian</td><td>{bpm.toFixed(1)}</td></tr>
					<tr><td>LUFS intégré</td><td>{lufs.toFixed(1)}</td></tr>
					<tr><td>Crest factor</td><td>{crest.toFixed(1)} dB</td></tr>
					<tr><td>DR p95-p10</td><td>{dr.toFixed(1)} dB</td></tr>
					<tr><td>Mode mineur</td><td>{minor.toFixed(0)}%</td></tr>
					<tr><td>Centroid</td><td>{centroid.toFixed(0)} Hz</td></tr>
					<tr><td>Sections / track</td><td>{sections.toFixed(1)}</td></tr>
					<tr><td>Durée médiane</td><td>{duration.toFixed(0)}s</td></tr>
				</tbody>
			</table>
		</div>

		<div class="col">
			<h4 class="ssect">PROFIL SPECTRAL</h4>
			<table class="spec-table">
				<thead>
					<tr><th>Bande</th><th>Médiane</th><th>Share</th><th></th></tr>
				</thead>
				<tbody>
					{#each bandRows as r}
						<tr>
							<td class="band-lbl">{r.label}</td>
							<td>{(r.value * 100).toFixed(1)}%</td>
							<td class="band-share">{r.share.toFixed(0)}%</td>
							<td class="band-bar-cell">
								<span class="band-bar" style="width: {Math.min(r.share, 100)}%"></span>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
			<p class="caption">
				Tableau 1. Distribution énergétique par bande, médiane sur l'ensemble du catalogue.
			</p>
		</div>

		<div class="col">
			<h4 class="ssect">STRUCTURE</h4>
			<div class="quote-block">
				<blockquote>
					Le drop principal s'inscrit autour de
					<strong>{drop.toFixed(0)}%</strong> du titre, structure typique du rap moderne où
					l'intro et le buildup occupent près d'un tiers du morceau.
				</blockquote>
			</div>
			<h4 class="ssect">SUB ÉCRASANT</h4>
			<p>
				Avec <strong>{sub.toFixed(0)}%</strong> d'énergie sous 60 Hz et
				<strong>{bass.toFixed(0)}%</strong> entre 60 et 250 Hz, le bas du spectre cumule
				<strong>{(sub + bass).toFixed(0)}%</strong> de l'énergie totale — un trait
				caractéristique du genre dominé par la 808.
			</p>
		</div>
	</section>

	<div class="big-rule"></div>

	{#if brief}
		<section class="brief-paper">
			<h3 class="paper-h3">Le détail de l'analyse</h3>
			<div class="paper-prose">
				<BriefRenderer markdown={brief.markdown} />
			</div>
		</section>
	{/if}

	<footer class="paper-footer">
		<span>BEATFINDER</span><span>·</span>
		<span>{detail.name}</span><span>·</span>
		<span>{todayLong}</span><span>·</span>
		<span>p. 1</span>
	</footer>
</div>

<style>
	@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Inter+Tight:wght@500;600;800&family=JetBrains+Mono:wght@400;500&display=swap');

	.paper {
		font-family: 'Lora', Georgia, serif;
		color: #1a1a1a;
		background: #f7f3e9;
		padding: 1.5rem 1.5rem;
		max-width: 19cm;
		margin: 0 auto;
		font-size: 12.5px;
		line-height: 1.55;
	}
	@page {
		size: A4 portrait;
		margin: 1.5cm 1cm;
	}

	/* Nameplate */
	.nameplate {
		text-align: center;
		margin-bottom: 2rem;
	}
	.np-date {
		font-family: 'Inter Tight', sans-serif;
		font-size: 11px;
		letter-spacing: 0.2em;
		font-weight: 600;
		color: #555;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid #aaa;
	}
	.np-title {
		font-family: 'Lora', serif;
		font-weight: 700;
		font-size: 92px;
		line-height: 1;
		letter-spacing: -0.03em;
		margin: 0.75rem 0 0.25rem;
		font-style: italic;
	}
	.np-tag {
		font-family: 'Inter Tight', sans-serif;
		font-size: 10px;
		letter-spacing: 0.15em;
		color: #555;
		text-transform: uppercase;
	}
	.np-rule {
		height: 4px;
		background: #1a1a1a;
		margin-top: 0.75rem;
		border-top: 1px solid #1a1a1a;
		border-bottom: 1px solid #1a1a1a;
		padding: 0;
		height: 6px;
		background: repeating-linear-gradient(
			to right,
			#1a1a1a 0 4px,
			transparent 4px 6px
		);
	}

	/* Lede */
	.lede {
		text-align: center;
		margin-bottom: 2rem;
		padding-bottom: 1rem;
		border-bottom: 1px solid #ccc;
	}
	.kicker {
		font-family: 'Inter Tight', sans-serif;
		font-size: 10px;
		letter-spacing: 0.25em;
		font-weight: 700;
		color: #6e1b1b;
		text-transform: uppercase;
		margin-bottom: 0.5rem;
	}
	.headline {
		font-family: 'Lora', serif;
		font-weight: 700;
		font-size: 48px;
		line-height: 1.05;
		letter-spacing: -0.02em;
		margin: 0 0 0.75rem;
	}
	.deck {
		font-family: 'Lora', serif;
		font-style: italic;
		font-size: 15px;
		color: #555;
		max-width: 38rem;
		margin: 0 auto 0.5rem;
	}
	.byline {
		font-family: 'Inter Tight', sans-serif;
		font-size: 10px;
		letter-spacing: 0.15em;
		color: #888;
		font-weight: 600;
	}

	/* 3 columns */
	.body-3col {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: 1.5rem;
		margin-bottom: 1.5rem;
	}
	.col {
		font-size: 11.5px;
	}
	.lead-block {
		border-bottom: 1px solid #ccc;
		padding-bottom: 0.75rem;
		margin-bottom: 0.75rem;
	}
	.first-p::first-letter {
		font-family: 'Lora', serif;
		font-size: 44px;
		font-weight: 700;
		float: left;
		line-height: 0.85;
		margin: 0.25rem 0.4rem -0.25rem 0;
		color: #6e1b1b;
	}
	.first-p {
		text-align: justify;
		hyphens: auto;
		margin: 0;
	}
	.ssect {
		font-family: 'Inter Tight', sans-serif;
		font-size: 10px;
		letter-spacing: 0.2em;
		text-transform: uppercase;
		font-weight: 700;
		color: #6e1b1b;
		margin: 0.75rem 0 0.5rem;
		padding-bottom: 0.25rem;
		border-bottom: 1px solid #1a1a1a;
	}
	.fact-table,
	.spec-table {
		width: 100%;
		border-collapse: collapse;
		font-family: 'Inter Tight', sans-serif;
		font-size: 11px;
	}
	.fact-table tr,
	.spec-table tr {
		border-bottom: 1px dotted #ccc;
	}
	.fact-table td {
		padding: 0.25rem 0;
	}
	.fact-table td:last-child {
		text-align: right;
		font-weight: 600;
	}
	.spec-table th {
		text-align: left;
		font-family: 'Inter Tight', sans-serif;
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: #555;
		padding: 0.3rem 0.2rem;
		border-bottom: 1px solid #1a1a1a;
	}
	.spec-table td {
		padding: 0.25rem 0.2rem;
	}
	.spec-table td.band-share {
		text-align: right;
		font-weight: 600;
	}
	.spec-table td.band-bar-cell {
		width: 50px;
	}
	.band-bar {
		display: block;
		height: 4px;
		background: #1a1a1a;
		max-width: 100%;
	}
	.caption {
		font-family: 'Lora', serif;
		font-style: italic;
		font-size: 10px;
		color: #555;
		margin: 0.5rem 0;
		text-align: center;
	}
	.quote-block {
		border-left: 3px solid #6e1b1b;
		padding-left: 0.75rem;
		margin: 0.5rem 0 0.75rem;
	}
	.quote-block blockquote {
		margin: 0;
		font-family: 'Lora', serif;
		font-style: italic;
		font-size: 13px;
		line-height: 1.45;
		color: #1a1a1a;
	}
	.col p {
		text-align: justify;
		hyphens: auto;
		margin: 0.4rem 0;
	}

	/* Big rule between sections */
	.big-rule {
		height: 12px;
		background: repeating-linear-gradient(
			to right,
			#1a1a1a 0 6px,
			transparent 6px 12px
		);
		margin: 1.5rem 0;
	}

	/* Brief paper */
	.brief-paper {
		margin-bottom: 1.5rem;
	}
	.paper-h3 {
		font-family: 'Lora', serif;
		font-style: italic;
		font-weight: 600;
		font-size: 28px;
		margin: 0 0 0.75rem;
		letter-spacing: -0.01em;
	}
	.paper-prose {
		column-count: 2;
		column-gap: 2rem;
		column-rule: 1px solid #ccc;
		column-fill: balance;
		font-size: 11.5px;
		line-height: 1.55;
	}
	/* Éléments qui débordent une colonne : on les fait s'étendre sur les 2 */
	.paper-prose :global(table),
	.paper-prose :global(h2:has(+ table)) {
		column-span: all;
	}
	.paper-prose :global(h1) {
		display: none;
	}
	.paper-prose :global(h2) {
		font-family: 'Inter Tight', sans-serif;
		font-size: 11px;
		letter-spacing: 0.2em;
		text-transform: uppercase;
		font-weight: 700;
		color: #6e1b1b;
		margin: 1rem 0 0.4rem;
		padding-bottom: 0.25rem;
		border-bottom: 1px solid #1a1a1a;
		break-after: avoid;
	}
	.paper-prose :global(h3) {
		font-family: 'Lora', serif;
		font-style: italic;
		font-size: 14px;
		font-weight: 600;
		margin: 0.75rem 0 0.25rem;
		color: #1a1a1a;
	}
	.paper-prose :global(p) {
		text-align: justify;
		hyphens: auto;
		margin: 0.35rem 0;
	}
	.paper-prose :global(strong) {
		font-weight: 700;
		color: #1a1a1a;
	}
	.paper-prose :global(em) {
		font-style: italic;
		color: #555;
	}
	.paper-prose :global(code) {
		font-family: 'JetBrains Mono', 'Menlo', 'Consolas', monospace;
		background: transparent;
		color: #6e1b1b;
		font-weight: 500;
		font-size: 0.88em;
		padding: 0;
		border-radius: 0;
		font-feature-settings: 'tnum';
	}
	.paper-prose :global(table) {
		width: 100%;
		table-layout: fixed;
		border-collapse: collapse;
		margin: 0.5rem 0;
		font-family: 'Inter Tight', sans-serif;
		font-size: 9px;
		break-inside: avoid;
	}
	.paper-prose :global(thead th) {
		font-family: 'Inter Tight', sans-serif;
		font-size: 8.5px;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		font-weight: 700;
		color: #555;
		text-align: left;
		padding: 0.25rem 0.35rem;
		border-bottom: 2px solid #1a1a1a;
		background: transparent;
		overflow-wrap: anywhere;
		word-break: break-word;
	}
	.paper-prose :global(tbody td) {
		padding: 0.2rem 0.35rem;
		border-bottom: 1px dotted #ccc;
		overflow-wrap: anywhere;
		word-break: break-word;
	}
	/* Tracks de référence (10 col) — column-span all + widths optimisés */
	.paper-prose :global(table:has(th:nth-child(10))) { column-span: all; }
	.paper-prose :global(table:has(th:nth-child(10)) td:nth-child(n+5)),
	.paper-prose :global(table:has(th:nth-child(10)) th:nth-child(n+5)) {
		white-space: nowrap;
		overflow-wrap: normal;
		word-break: normal;
	}
	.paper-prose :global(table:has(th:nth-child(10)) th:nth-child(1)),
	.paper-prose :global(table:has(th:nth-child(10)) td:nth-child(1)) { width: 24px; text-align: right; white-space: nowrap; }
	.paper-prose :global(table:has(th:nth-child(10)) th:nth-child(2)),
	.paper-prose :global(table:has(th:nth-child(10)) td:nth-child(2)) { width: 32px; text-align: right; white-space: nowrap; }
	.paper-prose :global(table:has(th:nth-child(10)) th:nth-child(5)),
	.paper-prose :global(table:has(th:nth-child(10)) td:nth-child(5)) { width: 46px; text-align: right; }
	.paper-prose :global(table:has(th:nth-child(10)) th:nth-child(6)),
	.paper-prose :global(table:has(th:nth-child(10)) td:nth-child(6)) { width: 64px; }
	.paper-prose :global(table:has(th:nth-child(10)) th:nth-child(7)),
	.paper-prose :global(table:has(th:nth-child(10)) td:nth-child(7)) { width: 40px; text-align: center; }
	.paper-prose :global(table:has(th:nth-child(10)) th:nth-child(8)),
	.paper-prose :global(table:has(th:nth-child(10)) td:nth-child(8)) { width: 54px; text-align: right; }
	.paper-prose :global(table:has(th:nth-child(10)) th:nth-child(9)),
	.paper-prose :global(table:has(th:nth-child(10)) td:nth-child(9)) { width: 60px; text-align: right; }
	.paper-prose :global(table:has(th:nth-child(10)) th:nth-child(10)),
	.paper-prose :global(table:has(th:nth-child(10)) td:nth-child(10)) { width: 54px; text-align: right; }
	/* Profil spectral (5 col) */
	.paper-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(1)),
	.paper-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(1)) { width: 50px; }
	.paper-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(2)),
	.paper-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(2)) { width: 50px; }
	.paper-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) th:nth-child(3)),
	.paper-prose :global(table:has(th:nth-child(5)):not(:has(th:nth-child(6))) td:nth-child(3)) { width: 40px; text-align: right; }
	.paper-prose :global(ul) {
		padding-left: 1rem;
		margin: 0.4rem 0;
	}
	.paper-prose :global(li) {
		margin: 0.2rem 0;
	}

	/* Footer */
	.paper-footer {
		margin-top: 2rem;
		padding-top: 0.75rem;
		border-top: 4px double #1a1a1a;
		font-family: 'Inter Tight', sans-serif;
		font-size: 10px;
		letter-spacing: 0.15em;
		text-transform: uppercase;
		color: #555;
		display: flex;
		gap: 0.5rem;
		justify-content: center;
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
		.brief-paper {
			break-before: page;
			page-break-before: always;
		}
		/* Aération entre sections principales */
		section {
			margin-top: 1rem;
		}
	}
</style>
