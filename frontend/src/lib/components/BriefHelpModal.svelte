<script lang="ts">
	import { marked } from 'marked';
	import ScrollLock from './ScrollLock.svelte';

	let {
		isOpen,
		title,
		body,
		onClose
	}: {
		isOpen: boolean;
		title: string;
		body: string;
		onClose: () => void;
	} = $props();

	let dialog: HTMLDialogElement | null = $state(null);

	$effect(() => {
		if (!dialog) return;
		if (isOpen && !dialog.open) {
			dialog.showModal();
		} else if (!isOpen && dialog.open) {
			dialog.close();
		}
	});

	const html = $derived(body ? (marked.parse(body) as string) : '');

	// Click sur la backdrop = clic sur le dialog lui-même (pas sur son contenu)
	function onBackdropClick(e: MouseEvent) {
		if (e.target === dialog) onClose();
	}
</script>

<ScrollLock open={isOpen} />

<dialog
	bind:this={dialog}
	onclose={onClose}
	onclick={onBackdropClick}
	class="help-dialog"
>
	<div class="help-content" role="document">
		<header class="help-header">
			<h2 class="help-title">{title}</h2>
			<button type="button" class="help-close" onclick={onClose} aria-label="Fermer">
				×
			</button>
		</header>
		<div class="help-body">
			{@html html}
		</div>
	</div>
</dialog>

<style>
	.help-dialog {
		width: 60vw;
		min-width: 320px;
		max-height: 85vh;
		padding: 0;
		overflow: hidden;
		border: 1px solid var(--color-border);
		border-radius: 12px;
		background: var(--color-surface);
		color: var(--color-fg);
		box-shadow: 0 20px 60px -10px rgba(0, 0, 0, 0.7);
	}
	@media (max-width: 768px) {
		.help-dialog {
			width: 92vw;
		}
	}
	.help-dialog::backdrop {
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(2px);
	}
	.help-content {
		display: flex;
		flex-direction: column;
		max-height: 85vh;
	}
	.help-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 1rem 1.5rem;
		border-bottom: 1px solid var(--color-border);
		background: var(--color-surface-2);
	}
	.help-title {
		font-size: 1.05rem;
		font-weight: 600;
		margin: 0;
		letter-spacing: -0.01em;
	}
	.help-close {
		flex-shrink: 0;
		width: 28px;
		height: 28px;
		display: flex;
		align-items: center;
		justify-content: center;
		border: 1px solid var(--color-border);
		border-radius: 6px;
		background: transparent;
		color: var(--color-fg);
		font-size: 1.25rem;
		line-height: 1;
		font-weight: bold;
		cursor: pointer;
		transition: background 0.15s;
	}
	.help-close:hover {
		background: var(--color-bg);
	}
	.help-body {
		overflow-y: auto;
		padding: 1.25rem 1.5rem 1.5rem;
		font-size: 0.9rem;
		line-height: 1.6;
	}
	.help-body :global(h2) {
		font-size: 1rem;
		font-weight: 600;
		margin: 1.25rem 0 0.4rem;
		color: var(--color-fg);
	}
	.help-body :global(h2:first-child) {
		margin-top: 0;
	}
	.help-body :global(p) {
		margin: 0.5rem 0;
	}
	.help-body :global(ul) {
		margin: 0.5rem 0;
		padding-left: 1.25rem;
	}
	.help-body :global(li) {
		margin: 0.2rem 0;
	}
	.help-body :global(blockquote) {
		margin: 0.75rem 0;
		padding: 0.6rem 0.9rem;
		border-left: 3px solid var(--color-accent);
		background: var(--color-surface-2);
		border-radius: 0 6px 6px 0;
		color: var(--color-fg);
		font-size: 0.85rem;
		line-height: 1.55;
	}
	.help-body :global(blockquote p) {
		margin: 0.3rem 0;
	}
	.help-body :global(strong) {
		color: var(--color-fg);
		font-weight: 600;
	}
	.help-body :global(em) {
		color: var(--color-fg-muted);
	}
	.help-body :global(code) {
		background: var(--color-surface-2);
		padding: 0.1rem 0.35rem;
		border-radius: 4px;
		font-size: 0.85em;
		font-family: var(--font-mono);
	}
	.help-body :global(table) {
		width: 100%;
		border-collapse: collapse;
		margin: 0.75rem 0;
		font-size: 0.85rem;
	}
	.help-body :global(thead th) {
		text-align: left;
		font-weight: 600;
		padding: 0.4rem 0.6rem;
		background: var(--color-surface-2);
		border-bottom: 1px solid var(--color-border);
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-fg-muted);
	}
	.help-body :global(tbody td) {
		padding: 0.4rem 0.6rem;
		border-bottom: 1px solid var(--color-border);
	}
</style>
