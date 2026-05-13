<script lang="ts">
	import { goto } from '$app/navigation';
	import type { PageData } from './$types';
	import { api } from '$lib/api';
	import Editorial from '$lib/components/print-styles/Editorial.svelte';
	import Soft from '$lib/components/print-styles/Soft.svelte';
	import Newspaper from '$lib/components/print-styles/Newspaper.svelte';
	import Blueprint from '$lib/components/print-styles/Blueprint.svelte';

	let { data }: { data: PageData } = $props();
	const { detail, brief, initialStyle } = $derived(data);

	type StyleKey = 'editorial' | 'soft' | 'newspaper' | 'blueprint';

	const styles: Array<{ key: StyleKey; label: string; tagline: string }> = [
		{ key: 'editorial', label: 'Editorial', tagline: 'magazine serif · 2 colonnes · ring chart' },
		{ key: 'soft', label: 'Soft', tagline: 'pastel · rounded cards · donut' },
		{ key: 'newspaper', label: 'Newspaper', tagline: 'serif sobre · 3 colonnes · sans charts' },
		{ key: 'blueprint', label: 'Blueprint', tagline: 'plan technique · wireframe · grille' }
	];

	let active = $state<StyleKey>(initialStyle);

	let downloadingPdf = $state(false);
	async function downloadPdf() {
		downloadingPdf = true;
		try {
			const blob = await api.downloadBriefPdf(detail.spotify_id, active);
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${detail.name}-${active}.pdf`;
			document.body.appendChild(a);
			a.click();
			a.remove();
			URL.revokeObjectURL(url);
		} catch (e) {
			alert(`Erreur génération PDF: ${e instanceof Error ? e.message : String(e)}`);
		} finally {
			downloadingPdf = false;
		}
	}

	function back() {
		goto(`/playlists/${encodeURIComponent(detail.spotify_id)}`);
	}
</script>

<div class="styles-page">
	<aside class="no-print sidebar">
		<button class="back-btn" onclick={back}>← Retour à la playlist</button>
		<div class="sb-title">
			<div class="sb-eyebrow">CHOIX DE STYLE PDF</div>
			<h2>4 styles, 4 personnalités</h2>
			<p>Chaque style change <em>tout</em> : police, layout, graphiques, tableaux. Choisis lequel te parle pour ton brief.</p>
		</div>

		<nav class="style-tabs">
			{#each styles as s (s.key)}
				<button
					class="tab"
					class:active={active === s.key}
					onclick={() => (active = s.key)}
				>
					<span class="tab-label">{s.label}</span>
					<span class="tab-tagline">{s.tagline}</span>
				</button>
			{/each}
		</nav>

		<button class="print-btn" onclick={downloadPdf} disabled={downloadingPdf}>
			{downloadingPdf ? 'Génération…' : 'Télécharger PDF'}
		</button>
		<button class="print-btn print-btn-secondary" onclick={() => window.print()}>
			Imprimer (Cmd+P)
		</button>
		<p class="hint">
			<strong>Télécharger PDF</strong> = fichier prêt à partager (~1-3 MB, fidélité 100%).
			<strong>Imprimer</strong> = boîte de dialogue navigateur classique.
		</p>
	</aside>

	<main class="preview">
		{#if active === 'editorial'}
			<Editorial {detail} {brief} />
		{:else if active === 'soft'}
			<Soft {detail} {brief} />
		{:else if active === 'newspaper'}
			<Newspaper {detail} {brief} />
		{:else if active === 'blueprint'}
			<Blueprint {detail} {brief} />
		{/if}
	</main>
</div>

<style>
	.styles-page {
		display: grid;
		grid-template-columns: 280px 1fr;
		min-height: 100vh;
		background: var(--color-bg);
	}

	/* Sidebar */
	.sidebar {
		position: sticky;
		top: 0;
		height: 100vh;
		overflow-y: auto;
		padding: 1.5rem 1.25rem;
		background: var(--color-surface);
		border-right: 1px solid var(--color-border);
		color: var(--color-fg);
		font-family: 'Inter', sans-serif;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	.back-btn {
		appearance: none;
		background: transparent;
		border: 1px solid var(--color-border);
		color: var(--color-fg-muted);
		font: 500 13px/1 inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 6px;
		text-align: left;
		cursor: pointer;
	}
	.back-btn:hover {
		background: var(--color-surface-2);
		color: var(--color-fg);
	}

	.sb-title {
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--color-border);
	}
	.sb-eyebrow {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.15em;
		color: var(--color-accent);
		font-weight: 600;
		margin-bottom: 0.4rem;
	}
	.sb-title h2 {
		font-size: 17px;
		font-weight: 700;
		margin: 0 0 0.5rem;
		letter-spacing: -0.01em;
	}
	.sb-title p {
		font-size: 12px;
		color: var(--color-fg-muted);
		margin: 0;
		line-height: 1.4;
	}
	.sb-title em {
		color: var(--color-accent);
		font-style: italic;
	}

	.style-tabs {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		flex: 1;
	}
	.tab {
		appearance: none;
		background: transparent;
		border: 1px solid var(--color-border);
		border-radius: 8px;
		padding: 0.7rem 0.85rem;
		color: var(--color-fg);
		text-align: left;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		cursor: pointer;
		transition: all 0.15s;
		font-family: inherit;
	}
	.tab:hover {
		background: var(--color-surface-2);
		border-color: var(--color-accent);
	}
	.tab.active {
		background: var(--color-accent);
		border-color: var(--color-accent);
		color: var(--color-accent-fg);
	}
	.tab-label {
		font-size: 14px;
		font-weight: 700;
		letter-spacing: -0.005em;
	}
	.tab-tagline {
		font-size: 10.5px;
		opacity: 0.75;
	}

	.print-btn {
		appearance: none;
		background: var(--color-accent);
		border: 1px solid var(--color-accent);
		color: var(--color-accent-fg);
		font: 600 13px/1 inherit;
		padding: 0.75rem 1rem;
		border-radius: 8px;
		cursor: pointer;
	}
	.print-btn:hover {
		filter: brightness(1.08);
	}
	.print-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.print-btn-secondary {
		background: transparent;
		color: var(--color-fg);
		border-color: var(--color-border);
		margin-top: 0.5rem;
	}
	.print-btn-secondary:hover {
		background: var(--color-surface-2);
		filter: none;
	}
	.hint {
		font-size: 11px;
		color: var(--color-fg-muted);
		margin: 0;
		line-height: 1.4;
	}

	/* Preview */
	.preview {
		overflow-y: auto;
		max-height: 100vh;
	}

	/* Print : cache la sidebar, le preview prend toute la page,
	   et on neutralise le fond noir du dark theme global (bande noire dans le PDF). */
	@media print {
		:global(html),
		:global(body) {
			background: white !important;
		}
		.styles-page {
			grid-template-columns: 1fr;
			background: white !important;
		}
		.sidebar {
			display: none;
		}
		.preview {
			overflow: visible;
			max-height: none;
			background: white !important;
		}
	}
</style>
