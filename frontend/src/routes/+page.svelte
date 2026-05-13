<script lang="ts">
	import type { PageData } from './$types';
	import Card from '$lib/components/Card.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import { formatDateTime } from '$lib/utils';
	import { isLocalProject } from '$lib/api';

	let { data }: { data: PageData } = $props();
</script>

<div class="flex items-end justify-between mb-8 gap-4 flex-wrap">
	<div>
		<h1 class="text-3xl font-bold tracking-tight">Playlists & projets</h1>
		<p class="mt-1 text-sm text-[var(--color-fg-muted)]">
			{data.playlists.length} au total
		</p>
	</div>
	<div class="flex gap-2">
		<Button href="/projects/new" variant="outline">+ Upload local</Button>
		<Button href="/analyze" variant="primary">+ Spotify</Button>
	</div>
</div>

{#if data.playlists.length === 0}
	<Card>
		<div class="text-center py-8 text-[var(--color-fg-muted)]">
			<p class="mb-4">Aucune playlist en base.</p>
			<Button href="/analyze" variant="primary">Lancer une première analyse</Button>
		</div>
	</Card>
{:else}
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
		{#each data.playlists as p (p.spotify_id)}
			<Card href="/playlists/{encodeURIComponent(p.spotify_id)}">
				<div class="flex items-start justify-between gap-3 mb-3">
					<h2 class="font-semibold leading-tight line-clamp-2">{p.name}</h2>
					<div class="flex flex-col items-end gap-1 shrink-0">
						{#if isLocalProject(p.spotify_id)}
							<Badge variant="accent">Local</Badge>
						{:else}
							<Badge variant="muted">Spotify</Badge>
						{/if}
						{#if p.n_patterns > 0}
							<Badge variant="ok">{p.n_patterns} pat.</Badge>
						{/if}
					</div>
				</div>

				<div class="flex items-center gap-4 text-sm text-[var(--color-fg-muted)]">
					<span class="flex items-baseline gap-1">
						<span class="font-mono text-[var(--color-fg)]">{p.n_tracks}</span>
						<span>tracks</span>
					</span>
					{#if p.owner_display_name}
						<span class="truncate">par {p.owner_display_name}</span>
					{/if}
				</div>

				<div class="mt-4 pt-3 border-t border-[var(--color-border)] text-xs text-[var(--color-fg-muted)] flex justify-between">
					<span>Dernier scan</span>
					<span class="font-mono">{formatDateTime(p.last_analyzed_at)}</span>
				</div>
			</Card>
		{/each}
	</div>
{/if}
