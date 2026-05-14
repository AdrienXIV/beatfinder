<script lang="ts">
	import { marked } from 'marked';
	import { BRIEF_HELP, findHelpKey } from '$lib/brief-help';
	import BriefHelpModal from './BriefHelpModal.svelte';

	let { markdown }: { markdown: string } = $props();

	marked.setOptions({ gfm: true, breaks: false });

	// 1. Inject un marker page-break avant "## Tracks de référence" pour les print
	// styles qui veulent forcer cette section sur une nouvelle page.
	// 2. Inject un bouton "?" inline dans chaque h2 dont le titre match une entrée
	// de BRIEF_HELP (cf. brief-help.ts). Le bouton est intercepté via event
	// delegation sur le container et ouvre BriefHelpModal.
	const processed = $derived.by(() => {
		let m = markdown;
		if (!m.includes('brief-tracks-ref-break')) {
			m = m.replace(
				/^## Tracks de référence/m,
				'<div class="brief-tracks-ref-break"></div>\n\n## Tracks de référence'
			);
		}
		m = m.replace(/^## (.+)$/gm, (match, title) => {
			const key = findHelpKey(title);
			if (!key) return match;
			return `## ${title} <button type="button" class="help-trigger" data-help-key="${key}" aria-label="Aide détaillée sur cette section">?</button>`;
		});
		return m;
	});

	let html = $derived(marked.parse(processed) as string);

	let helpOpen = $state(false);
	let helpTitle = $state('');
	let helpBody = $state('');

	function onContainerClick(e: MouseEvent) {
		const target = e.target;
		if (!(target instanceof HTMLElement)) return;
		if (!target.classList.contains('help-trigger')) return;
		const key = target.dataset.helpKey;
		if (!key) return;
		const entry = BRIEF_HELP[key];
		if (!entry) return;
		helpTitle = entry.title;
		helpBody = entry.body;
		helpOpen = true;
	}

	function closeHelp() {
		helpOpen = false;
	}
</script>

<div class="brief prose-styles" onclick={onContainerClick} role="presentation">
	{@html html}
</div>

<BriefHelpModal isOpen={helpOpen} title={helpTitle} body={helpBody} onClose={closeHelp} />

<style>
	.brief :global(h1) {
		font-size: 1.875rem;
		font-weight: 700;
		margin: 0 0 0.5rem 0;
		letter-spacing: -0.02em;
	}
	.brief :global(h2) {
		font-size: 1.25rem;
		font-weight: 600;
		margin: 2rem 0 0.75rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--color-border);
	}
	.brief :global(h3) {
		font-size: 1.05rem;
		font-weight: 600;
		margin: 1.5rem 0 0.5rem;
	}
	.brief :global(p) {
		margin: 0.5rem 0;
		line-height: 1.6;
	}
	/* Legacy : intros stockées en <div class="brief-section-intro"> dans les
	   briefs cachés générés avant la migration markdown-pur. */
	.brief :global(.brief-section-intro) {
		font-size: 0.825rem;
		color: var(--color-fg-muted);
		margin: -0.25rem 0 1rem;
		line-height: 1.55;
	}
	/* Nouveau format (markdown pur) : paragraphe entier en italique sous un
	   titre h2 → intro vulgarisée. Le `:has()` cible un <p> qui contient
	   uniquement un <em> (donc un paragraphe italique pur). */
	.brief :global(p):has(> em:only-child) {
		font-size: 0.825rem;
		margin: -0.25rem 0 1rem;
		line-height: 1.55;
	}
	.brief :global(hr) {
		border: none;
		border-top: 1px solid var(--color-border);
		margin: 1.5rem 0;
	}
	.brief :global(em) {
		color: var(--color-fg-muted);
		font-style: normal;
	}
	.brief :global(strong) {
		color: var(--color-fg);
		font-weight: 600;
	}
	.brief :global(ul) {
		margin: 0.5rem 0;
		padding-left: 1.25rem;
	}
	.brief :global(li) {
		margin: 0.25rem 0;
		line-height: 1.55;
	}
	.brief :global(code) {
		background: var(--color-surface-2);
		padding: 0.1rem 0.35rem;
		border-radius: 4px;
		font-size: 0.85em;
		font-family: var(--font-mono);
	}
	.brief :global(table) {
		width: 100%;
		border-collapse: collapse;
		margin: 0.75rem 0;
		font-size: 0.875rem;
	}
	.brief :global(thead th) {
		text-align: left;
		font-weight: 600;
		padding: 0.5rem 0.75rem;
		background: var(--color-surface-2);
		border-bottom: 1px solid var(--color-border);
		color: var(--color-fg-muted);
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.brief :global(tbody td) {
		padding: 0.5rem 0.75rem;
		border-bottom: 1px solid var(--color-border);
		font-family: var(--font-mono);
		font-size: 0.825rem;
	}
	.brief :global(a) {
		color: var(--color-accent);
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.brief :global(button.help-trigger) {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 22px;
		height: 22px;
		margin-left: 0.5rem;
		border: 1px solid var(--color-border);
		border-radius: 50%;
		background: transparent;
		color: var(--color-fg-muted);
		font-size: 0.8rem;
		font-weight: 600;
		line-height: 1;
		cursor: pointer;
		vertical-align: middle;
		transition: all 0.15s;
		padding: 0;
	}
	.brief :global(button.help-trigger:hover) {
		border-color: var(--color-accent);
		color: var(--color-accent);
		background: color-mix(in oklab, var(--color-accent) 8%, transparent);
	}
	.brief :global(button.help-trigger:focus-visible) {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
	}
	/* En print : masquer les boutons d'aide */
	@media print {
		.brief :global(button.help-trigger) {
			display: none !important;
		}
	}
</style>
