<script lang="ts">
	import type { PageData } from './$types';
	import { api, ApiError, type CompareResult } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import BriefRenderer from '$lib/components/BriefRenderer.svelte';

	let { data }: { data: PageData } = $props();

	let idA = $state(data.preselectA ?? '');
	let idB = $state(data.preselectB ?? '');
	let submitting = $state(false);
	let error = $state<string | null>(null);
	let result = $state<CompareResult | null>(null);

	const selectClass =
		'w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 h-10 text-sm focus:outline focus:outline-2 focus:outline-[var(--color-accent)] focus:border-transparent';

	async function onSubmit(e: Event) {
		e.preventDefault();
		if (!idA || !idB) return;
		if (idA === idB) {
			error = "Choisis deux playlists différentes (ou utilise --pattern-a/--pattern-b via CLI pour comparer 2 patterns d'une même playlist).";
			return;
		}
		error = null;
		submitting = true;
		result = null;
		try {
			result = await api.compare({ id_a: idA, id_b: idB });
		} catch (e) {
			if (e instanceof ApiError) {
				error = e.detail || e.message;
			} else if (e instanceof Error) {
				error = e.message;
			} else {
				error = String(e);
			}
		} finally {
			submitting = false;
		}
	}

	function downloadMd() {
		if (!result) return;
		const blob = new Blob([result.markdown], { type: 'text/markdown' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `diff-${result.id_a.slice(0, 8)}-vs-${result.id_b.slice(0, 8)}.md`;
		a.click();
		URL.revokeObjectURL(url);
	}
</script>

<div class="max-w-4xl mx-auto">
	<div class="flex items-start justify-between mb-1">
		<h1 class="text-3xl font-bold tracking-tight">Comparer 2 playlists</h1>
		<a
			href="/compare/multi"
			class="text-sm text-[var(--color-accent)] hover:underline shrink-0 mt-2"
		>
			Comparaison triangulaire (3-5 sources) →
		</a>
	</div>
	<p class="text-sm text-[var(--color-fg-muted)] mb-8">
		Diff des patterns (tempo, tonalité, énergie, profil spectral, structure) entre A et B.
		Δ = B − A.
	</p>

	<Card class="mb-6">
		<form onsubmit={onSubmit} class="space-y-5">
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				<div>
					<label for="a" class="block text-sm font-medium mb-1.5">Playlist A (référence)</label>
					<select id="a" bind:value={idA} class={selectClass} required>
						<option value="">— sélectionne —</option>
						{#each data.playlists as p (p.spotify_id)}
							<option value={p.spotify_id} disabled={p.n_patterns === 0}>
								{p.name} ({p.n_tracks} tracks{p.n_patterns === 0 ? ', no pattern' : ''})
							</option>
						{/each}
					</select>
				</div>
				<div>
					<label for="b" class="block text-sm font-medium mb-1.5">Playlist B (à comparer)</label>
					<select id="b" bind:value={idB} class={selectClass} required>
						<option value="">— sélectionne —</option>
						{#each data.playlists as p (p.spotify_id)}
							<option value={p.spotify_id} disabled={p.n_patterns === 0}>
								{p.name} ({p.n_tracks} tracks{p.n_patterns === 0 ? ', no pattern' : ''})
							</option>
						{/each}
					</select>
				</div>
			</div>

			{#if error}
				<div
					class="rounded-md border border-[var(--color-err)]/40 bg-[var(--color-err)]/10 p-3 text-sm"
				>
					<p class="font-medium text-[var(--color-err)] mb-1">Erreur</p>
					<p>{error}</p>
				</div>
			{/if}

			<div class="flex items-center gap-3">
				<Button
					type="submit"
					variant="primary"
					loading={submitting}
					disabled={!idA || !idB || idA === idB}
				>
					Comparer
				</Button>
			</div>
		</form>
	</Card>

	{#if result}
		<div class="mb-3 flex items-center justify-between">
			<span class="text-sm text-[var(--color-fg-muted)]">
				A = {result.name_a} ({result.n_tracks_a}) — B = {result.name_b} ({result.n_tracks_b})
			</span>
			<Button variant="outline" size="sm" onclick={downloadMd}>Download .md</Button>
		</div>
		<Card>
			<BriefRenderer markdown={result.markdown} />
		</Card>
	{/if}
</div>
