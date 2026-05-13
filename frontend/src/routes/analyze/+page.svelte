<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
	let url = $state(data.preselectUrl);
	let save = $state(true);
	let download = $state(true);
	let limitStr = $state('');
	let submitting = $state(false);
	let error = $state<string | null>(null);

	async function onSubmit(e: Event) {
		e.preventDefault();
		if (!url.trim()) return;
		error = null;
		submitting = true;
		try {
			const limitNum = limitStr.trim() === '' ? null : Number.parseInt(limitStr, 10);
			if (limitNum !== null && (Number.isNaN(limitNum) || limitNum <= 0)) {
				throw new Error('Limit doit être un entier positif ou vide.');
			}
			const job = await api.analyze({
				url: url.trim(),
				save,
				limit: limitNum,
				download
			});
			await goto(`/jobs/${job.id}`);
		} catch (e) {
			submitting = false;
			if (e instanceof ApiError) {
				error = e.detail || e.message;
			} else if (e instanceof Error) {
				error = e.message;
			} else {
				error = String(e);
			}
		}
	}
</script>

<div class="max-w-2xl mx-auto">
	<h1 class="text-3xl font-bold tracking-tight mb-1">Analyser une playlist</h1>
	<p class="text-sm text-[var(--color-fg-muted)] mb-8">
		Spotify URL, URI ou ID. Le pipeline télécharge l'audio via YouTube (si manquant)
		puis extrait BPM, tonalité, énergie, profil spectral, structure.
	</p>

	<Card>
		<form onsubmit={onSubmit} class="space-y-5">
			<div>
				<label for="url" class="block text-sm font-medium mb-1.5">
					URL ou ID Spotify <span class="text-[var(--color-err)]">*</span>
				</label>
				<input
					id="url"
					type="text"
					bind:value={url}
					placeholder="https://open.spotify.com/playlist/…"
					required
					class="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 h-10 text-sm font-mono focus:outline focus:outline-2 focus:outline-[var(--color-accent)] focus:border-transparent"
				/>
			</div>

			<div>
				<label for="limit" class="block text-sm font-medium mb-1.5">
					Limit (optionnel)
				</label>
				<input
					id="limit"
					type="number"
					min="1"
					bind:value={limitStr}
					placeholder="N premières tracks"
					class="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 h-10 text-sm font-mono focus:outline focus:outline-2 focus:outline-[var(--color-accent)] focus:border-transparent"
				/>
			</div>

			<div class="space-y-2">
				<label class="flex items-center gap-2 cursor-pointer">
					<input
						type="checkbox"
						bind:checked={save}
						class="h-4 w-4 rounded border-[var(--color-border)] bg-[var(--color-bg)] accent-[var(--color-accent)]"
					/>
					<span class="text-sm">
						Persister en DB
						<span class="text-[var(--color-fg-muted)] ml-1">— ajoute un nouveau pattern, conserve l'historique</span>
					</span>
				</label>
				<label class="flex items-center gap-2 cursor-pointer">
					<input
						type="checkbox"
						bind:checked={download}
						class="h-4 w-4 rounded border-[var(--color-border)] bg-[var(--color-bg)] accent-[var(--color-accent)]"
					/>
					<span class="text-sm">
						Télécharger audio manquant via YouTube
						<span class="text-[var(--color-fg-muted)] ml-1">— skip si déjà en cache local</span>
					</span>
				</label>
			</div>

			{#if error}
				<div class="rounded-md border border-[var(--color-err)]/40 bg-[var(--color-err)]/10 p-3 text-sm">
					<p class="font-medium text-[var(--color-err)] mb-1">Erreur</p>
					<p class="text-[var(--color-fg)]">{error}</p>
				</div>
			{/if}

			<div class="flex items-center gap-3 pt-2">
				<Button type="submit" variant="primary" loading={submitting} disabled={!url.trim()}>
					Lancer l'analyse
				</Button>
				<span class="text-xs text-[var(--color-fg-muted)]">
					~1-2 min par track DL + analyse
				</span>
			</div>
		</form>
	</Card>
</div>
