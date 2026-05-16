<script lang="ts">
	import { api, type Job } from '$lib/api';
	import Button from './Button.svelte';
	import ProgressBar from './ProgressBar.svelte';
	import ScrollLock from './ScrollLock.svelte';

	let {
		jobId,
		isOpen,
		onClose,
		onDone
	}: {
		jobId: string | null;
		isOpen: boolean;
		onClose: () => void;
		onDone: (job: Job) => void;
	} = $props();

	let dialog: HTMLDialogElement | null = $state(null);
	let job = $state<Job | null>(null);
	let stream: EventSource | null = null;
	let logsBox: HTMLDivElement | null = $state(null);

	const running = $derived(
		job !== null && (job.status === 'queued' || job.status === 'running')
	);

	function closeStream() {
		if (stream) {
			stream.close();
			stream = null;
		}
	}

	function startStream(id: string) {
		closeStream();
		job = null;
		stream = new EventSource(api.streamJobUrl(id));
		stream.addEventListener('update', (e) => {
			job = JSON.parse((e as MessageEvent).data);
		});
		stream.addEventListener('done', (e) => {
			const finalJob: Job = JSON.parse((e as MessageEvent).data);
			job = finalJob;
			closeStream();
			if (finalJob.status === 'done') {
				onDone(finalJob);
			}
		});
		stream.addEventListener('error', (e) => {
			const ev = e as MessageEvent;
			if (ev.data) {
				try {
					job = JSON.parse(ev.data);
				} catch {
					// ignore
				}
			}
			closeStream();
		});
		stream.addEventListener('cancelled', (e) => {
			job = JSON.parse((e as MessageEvent).data);
			closeStream();
		});
	}

	$effect(() => {
		if (!dialog) return;
		if (isOpen && jobId) {
			if (!dialog.open) dialog.showModal();
			startStream(jobId);
		} else if (!isOpen && dialog.open) {
			dialog.close();
			closeStream();
			job = null;
		}
	});

	// Auto-scroll des logs vers le bas à chaque nouvel ajout
	$effect(() => {
		void job?.log.length;
		if (logsBox) {
			logsBox.scrollTop = logsBox.scrollHeight;
		}
	});

	async function cancel() {
		if (!job) return;
		try {
			await api.cancelJob(job.id);
		} catch {
			// ignore — le stream va recevoir l'event cancelled
		}
	}

	function tryClose() {
		// Bloque le close pendant le running pour éviter de perdre le suivi
		if (running) return;
		onClose();
	}

	function onBackdropClick(e: MouseEvent) {
		if (e.target === dialog) tryClose();
	}

	function statusBadge(s: Job['status']): { label: string; cls: string } {
		switch (s) {
			case 'queued':
				return { label: 'En file', cls: 'text-[var(--color-fg-muted)]' };
			case 'running':
				return { label: 'Analyse en cours', cls: 'text-[var(--color-accent)]' };
			case 'done':
				return { label: 'Terminé', cls: 'text-[var(--color-ok)]' };
			case 'error':
				return { label: 'Erreur', cls: 'text-[var(--color-err)]' };
			case 'cancelled':
				return { label: 'Annulé', cls: 'text-[var(--color-warn)]' };
		}
	}
</script>

<ScrollLock open={isOpen} />

<dialog bind:this={dialog} onclose={tryClose} onclick={onBackdropClick} class="upload-dialog">
	<div class="upload-content" role="document">
		<header class="upload-header">
			<div>
				<div class="text-[10px] uppercase tracking-wider text-[var(--color-fg-muted)]">
					Import version
				</div>
				<h2 class="upload-title">Analyse audio en cours</h2>
				{#if job}
					{@const sb = statusBadge(job.status)}
					<div class="text-xs mt-1 {sb.cls}">{sb.label}</div>
				{/if}
			</div>
			<button
				type="button"
				class="upload-close"
				onclick={tryClose}
				disabled={running}
				title={running ? 'Annule d\'abord ou attends la fin' : 'Fermer'}
				aria-label="Fermer"
			>
				×
			</button>
		</header>

		<div class="upload-body">
			{#if !job}
				<p class="text-sm text-[var(--color-fg-muted)] italic">Connexion au job…</p>
			{:else}
				<ProgressBar
					current={job.progress.current}
					total={job.progress.total}
					label={job.progress.label ||
						(job.status === 'queued' ? 'En file d\'attente…' : '—')}
				/>

				<p class="mt-3 text-xs text-[var(--color-fg-muted)] leading-relaxed">
					Beatfinder fait passer ton audio dans 6 analyseurs (tempo, tonalité, énergie,
					profil spectral, structure, timbre) puis calcule le fit_score vs la cible figée.
					Compte 10 à 30 secondes pour une track de 3 minutes.
				</p>

				<div class="mt-4">
					<div class="flex items-baseline justify-between mb-1">
						<span class="text-[10px] uppercase tracking-wider text-[var(--color-fg-muted)]">
							Logs ({job.log.length})
						</span>
					</div>
					<div
						bind:this={logsBox}
						class="rounded border border-[var(--color-border)] bg-black p-3 font-mono text-[11px] leading-relaxed max-h-64 overflow-y-auto"
					>
						{#if job.log.length === 0}
							<span class="text-[var(--color-fg-muted)]/60">(en attente…)</span>
						{:else}
							{#each job.log as line, i (i)}
								<div
									class={line.includes('✓')
										? 'text-[var(--color-ok)]'
										: line.includes('→')
											? 'text-[var(--color-fg-muted)]'
											: 'text-[var(--color-fg)]'}
								>
									{line}
								</div>
							{/each}
						{/if}
					</div>
				</div>

				{#if job.status === 'error' && job.error}
					<div class="mt-3 rounded-md border border-[var(--color-err)]/40 bg-[var(--color-err)]/10 p-3 text-sm">
						<p class="text-[var(--color-err)] font-medium">Échec de l'analyse</p>
						<p class="text-xs text-[var(--color-fg-muted)] mt-1 font-mono">{job.error}</p>
					</div>
				{:else if job.status === 'done' && job.result}
					<div class="mt-3 rounded-md border border-[var(--color-ok)]/40 bg-[var(--color-ok)]/10 p-3 text-sm">
						<p class="text-[var(--color-ok)] font-medium">
							✓ v{job.result.version_number} ajoutée à la session
						</p>
						{#if job.result.fit_score !== null && job.result.fit_score !== undefined}
							<p class="text-xs text-[var(--color-fg-muted)] mt-1">
								Fit score : <span class="font-mono">{Math.round((job.result.fit_score as number) * 100)}%</span>
							</p>
						{/if}
					</div>
				{/if}
			{/if}
		</div>

		<footer class="upload-footer">
			{#if running}
				<Button variant="ghost" size="sm" onclick={cancel}>Annuler l'analyse</Button>
				<span class="text-xs text-[var(--color-fg-muted)] italic">
					La session se rafraîchira automatiquement à la fin.
				</span>
			{:else}
				<span></span>
				<Button variant="primary" size="sm" onclick={onClose}>Fermer</Button>
			{/if}
		</footer>
	</div>
</dialog>

<style>
	.upload-dialog {
		width: 65vw;
		max-width: 720px;
		min-width: 320px;
		max-height: 88vh;
		padding: 0;
		overflow: hidden;
		border: 1px solid var(--color-border);
		border-radius: 12px;
		background: var(--color-surface);
		color: var(--color-fg);
		box-shadow: 0 20px 60px -10px rgba(0, 0, 0, 0.7);
	}
	@media (max-width: 768px) {
		.upload-dialog {
			width: 94vw;
		}
	}
	.upload-dialog::backdrop {
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(2px);
	}
	.upload-content {
		display: flex;
		flex-direction: column;
		max-height: 88vh;
	}
	.upload-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		padding: 1rem 1.5rem;
		border-bottom: 1px solid var(--color-border);
		background: var(--color-surface-2);
	}
	.upload-title {
		font-size: 1.2rem;
		font-weight: 700;
		margin: 0;
		letter-spacing: -0.01em;
	}
	.upload-close {
		flex-shrink: 0;
		width: 30px;
		height: 30px;
		display: flex;
		align-items: center;
		justify-content: center;
		border: 1px solid var(--color-border);
		border-radius: 6px;
		background: transparent;
		color: var(--color-fg);
		font-size: 1.3rem;
		line-height: 1;
		font-weight: bold;
		cursor: pointer;
		transition: background 0.15s;
	}
	.upload-close:hover:not(:disabled) {
		background: var(--color-bg);
	}
	.upload-close:disabled {
		opacity: 0.35;
		cursor: not-allowed;
	}
	.upload-body {
		overflow-y: auto;
		padding: 1.25rem 1.5rem 1rem;
	}
	.upload-footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.75rem 1.5rem;
		border-top: 1px solid var(--color-border);
		background: var(--color-surface-2);
	}
</style>
