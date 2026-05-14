<script lang="ts">
	import Button from './Button.svelte';
	import ScrollLock from './ScrollLock.svelte';

	let {
		isOpen,
		title,
		message,
		confirmLabel = 'Supprimer définitivement',
		cancelLabel = 'Annuler',
		variant = 'destructive',
		onConfirm,
		onCancel,
		busy = false
	}: {
		isOpen: boolean;
		title: string;
		message: string;
		confirmLabel?: string;
		cancelLabel?: string;
		variant?: 'destructive' | 'primary';
		onConfirm: () => void | Promise<void>;
		onCancel: () => void;
		busy?: boolean;
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

	function onBackdropClick(e: MouseEvent) {
		if (e.target === dialog && !busy) onCancel();
	}
</script>

<ScrollLock open={isOpen} />

<dialog
	bind:this={dialog}
	onclose={() => !busy && onCancel()}
	onclick={onBackdropClick}
	class="confirm-dialog"
>
	<div class="content">
		<header class="px-5 py-3 border-b border-[var(--color-border)]">
			<h2 class="text-base font-semibold">{title}</h2>
		</header>

		<div class="px-5 py-4 text-sm text-[var(--color-fg-muted)] leading-relaxed">
			{message}
		</div>

		<footer class="px-5 py-3 border-t border-[var(--color-border)] flex items-center justify-end gap-2 shrink-0">
			<Button variant="ghost" size="sm" onclick={onCancel} disabled={busy}>
				{cancelLabel}
			</Button>
			<Button {variant} size="sm" loading={busy} onclick={() => void onConfirm()}>
				{confirmLabel}
			</Button>
		</footer>
	</div>
</dialog>

<style>
	.confirm-dialog {
		width: min(520px, 92vw);
		max-height: 85vh;
		padding: 0;
		overflow: hidden;
		border: 1px solid var(--color-border);
		border-radius: 12px;
		background: var(--color-surface);
		color: var(--color-fg);
		box-shadow: 0 20px 60px -10px rgba(0, 0, 0, 0.7);
	}
	.confirm-dialog::backdrop {
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(2px);
	}
	.content {
		display: flex;
		flex-direction: column;
	}
</style>
