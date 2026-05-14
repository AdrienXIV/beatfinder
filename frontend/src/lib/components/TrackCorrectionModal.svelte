<script lang="ts">
	import { api, ApiError, type TrackMeta } from '$lib/api';
	import Badge from './Badge.svelte';
	import Button from './Button.svelte';
	import ScrollLock from './ScrollLock.svelte';

	let {
		track,
		isOpen,
		onClose,
		onSaved
	}: {
		track: TrackMeta | null;
		isOpen: boolean;
		onClose: () => void;
		onSaved: () => void; // appelé après save/reset → parent reload
	} = $props();

	const NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
	const MODES = ['major', 'minor'] as const;

	let dialog: HTMLDialogElement | null = $state(null);
	// bind:value sur <input type="number"> coerce en `number | null` côté Svelte 5
	let bpm = $state<number | null>(null);
	let keyNote = $state<string>('');
	let keyMode = $state<'major' | 'minor' | ''>('');
	let saving = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		if (!dialog) return;
		if (isOpen && !dialog.open) {
			dialog.showModal();
			// Pré-remplir avec les valeurs actuelles
			bpm = track?.bpm != null ? Math.round(track.bpm) : null;
			keyNote = track?.key_note ?? '';
			keyMode = (track?.key_mode as 'major' | 'minor') ?? '';
			error = null;
			saving = false;
		} else if (!isOpen && dialog.open) {
			dialog.close();
		}
	});

	async function save() {
		if (!track) return;
		saving = true;
		error = null;
		try {
			const payload: {
				bpm?: number;
				key_note?: string;
				key_mode?: 'major' | 'minor';
			} = {};
			if (bpm != null) {
				if (Number.isNaN(bpm) || bpm < 20 || bpm > 300) {
					throw new Error('BPM doit être un nombre entre 20 et 300.');
				}
				payload.bpm = bpm;
			}
			if (keyNote) payload.key_note = keyNote;
			if (keyMode) payload.key_mode = keyMode;
			if (Object.keys(payload).length === 0) {
				throw new Error('Aucune modification à enregistrer.');
			}
			await api.patchTrackOverride(track.spotify_id, payload);
			onSaved();
			onClose();
		} catch (e) {
			saving = false;
			error = e instanceof ApiError ? e.detail || e.message : String(e);
		}
	}

	async function reset() {
		if (!track) return;
		saving = true;
		error = null;
		try {
			await api.deleteTrackOverride(track.spotify_id);
			onSaved();
			onClose();
		} catch (e) {
			saving = false;
			error = e instanceof ApiError ? e.detail || e.message : String(e);
		}
	}

	function pickBpm(v: number) {
		bpm = Math.round(v);
	}

	function onBackdropClick(e: MouseEvent) {
		if (e.target === dialog && !saving) onClose();
	}
</script>

<ScrollLock open={isOpen} />

<dialog
	bind:this={dialog}
	onclose={() => !saving && onClose()}
	onclick={onBackdropClick}
	class="correction-modal"
>
	<div class="content">
		<header class="px-5 py-3 border-b border-[var(--color-border)] flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">Corriger BPM / tonalité</h2>
				<p class="text-xs text-[var(--color-fg-muted)] mt-0.5 truncate max-w-md">
					{track?.artist} — {track?.title}
				</p>
			</div>
			{#if track?.is_overridden}
				<Badge variant="accent">déjà corrigé</Badge>
			{:else if track?.confidence_low}
				<Badge variant="warn">analyse incertaine</Badge>
			{/if}
		</header>

		<div class="p-5 space-y-5 flex-1 overflow-y-auto min-h-0">
			{#if error}
				<div class="rounded-md border border-[var(--color-err)]/40 bg-[var(--color-err)]/10 p-3 text-sm text-[var(--color-err)]">
					{error}
				</div>
			{/if}

			<p class="text-sm text-[var(--color-fg-muted)] leading-relaxed">
				Beatfinder peut se tromper sur les tracks à autotune fort, sub
				dominant ou groove half-time / triplet. Si tu sais que les valeurs
				ci-dessous sont fausses, corrige-les manuellement — l'override sera
				utilisé partout (plans d'action, briefs, sessions).
			</p>

			<!-- BPM -->
			<div>
				<label for="bpm-input" class="block text-xs uppercase tracking-wider text-[var(--color-fg-muted)] mb-1.5">
					BPM
				</label>
				<input
					id="bpm-input"
					type="number"
					min="20"
					max="300"
					step="0.1"
					bind:value={bpm}
					class="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 h-10 text-sm font-mono focus:outline focus:outline-2 focus:outline-[var(--color-accent)]"
					disabled={saving}
				/>
				{#if track?.bpm_alt_hypotheses && track.bpm_alt_hypotheses.length > 0}
					<p class="text-[11px] text-[var(--color-fg-muted)] mt-2 mb-1">
						Alternatives plausibles (×2, /2, ×1.5, /1.5) :
					</p>
					<div class="flex flex-wrap gap-1.5">
						{#each track.bpm_alt_hypotheses as alt (alt)}
							<button
								type="button"
								onclick={() => pickBpm(alt)}
								class="rounded-md border border-[var(--color-border)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] px-2.5 py-1 text-xs font-mono transition-colors"
								disabled={saving}
							>
								{Math.round(alt)}
							</button>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Note racine -->
			<div>
				<label for="note-select" class="block text-xs uppercase tracking-wider text-[var(--color-fg-muted)] mb-1.5">
					Note racine
				</label>
				<div class="grid grid-cols-6 gap-1.5">
					{#each NOTES as n (n)}
						<button
							type="button"
							onclick={() => (keyNote = keyNote === n ? '' : n)}
							class={[
								'rounded-md border px-2 py-1.5 text-sm font-mono transition-colors',
								keyNote === n
									? 'border-[var(--color-accent)] bg-[var(--color-accent)]/15 text-[var(--color-accent)]'
									: 'border-[var(--color-border)] hover:border-[var(--color-accent)]/50'
							].join(' ')}
							disabled={saving}
						>
							{n}
						</button>
					{/each}
				</div>
			</div>

			<!-- Mode -->
			<div>
				<label class="block text-xs uppercase tracking-wider text-[var(--color-fg-muted)] mb-1.5">
					Mode
				</label>
				<div class="grid grid-cols-2 gap-1.5">
					{#each MODES as m (m)}
						<button
							type="button"
							onclick={() => (keyMode = keyMode === m ? '' : m)}
							class={[
								'rounded-md border px-3 py-1.5 text-sm transition-colors',
								keyMode === m
									? 'border-[var(--color-accent)] bg-[var(--color-accent)]/15 text-[var(--color-accent)]'
									: 'border-[var(--color-border)] hover:border-[var(--color-accent)]/50'
							].join(' ')}
							disabled={saving}
						>
							{m}
						</button>
					{/each}
				</div>
			</div>
		</div>

		<footer class="px-5 py-3 border-t border-[var(--color-border)] flex items-center justify-between gap-2 shrink-0">
			{#if track?.is_overridden}
				<Button variant="ghost" size="sm" onclick={reset} disabled={saving}>
					Réinitialiser
				</Button>
			{:else}
				<span></span>
			{/if}
			<div class="flex gap-2">
				<Button variant="ghost" size="sm" onclick={onClose} disabled={saving}>
					Annuler
				</Button>
				<Button variant="primary" size="sm" loading={saving} onclick={save}>
					Appliquer
				</Button>
			</div>
		</footer>
	</div>
</dialog>

<style>
	.correction-modal {
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
	.correction-modal::backdrop {
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(2px);
	}
	@media (max-width: 768px) {
		.correction-modal {
			width: 92vw;
		}
	}
	.content {
		display: flex;
		flex-direction: column;
		max-height: 85vh;
	}
</style>
