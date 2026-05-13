<script lang="ts">
	import { marked } from 'marked';

	let { markdown }: { markdown: string } = $props();

	marked.setOptions({ gfm: true, breaks: false });

	// Inject un marker page-break avant "## Tracks de référence" pour les print
	// styles qui veulent forcer cette section sur une nouvelle page. Rétro-compatible :
	// les briefs cached sans le marker injecté côté backend bénéficient quand même.
	const processed = $derived(
		markdown.includes('brief-tracks-ref-break')
			? markdown
			: markdown.replace(
					/^## Tracks de référence/m,
					'<div class="brief-tracks-ref-break"></div>\n\n## Tracks de référence'
				)
	);

	let html = $derived(marked.parse(processed) as string);
</script>

<div class="brief prose-styles">
	{@html html}
</div>

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
</style>
