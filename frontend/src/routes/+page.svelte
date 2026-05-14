<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import type { PageData } from './$types';
	import Card from '$lib/components/Card.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import SessionWizardModal from '$lib/components/SessionWizardModal.svelte';
	import { formatDateTime } from '$lib/utils';
	import { api, ApiError, isLocalProject } from '$lib/api';

	let { data }: { data: PageData } = $props();
	let wizardOpen = $state(false);

	// État du confirm de suppression
	type DeleteTarget =
		| { kind: 'session'; spotifyId: string; name: string }
		| { kind: 'project'; spotifyId: string; name: string }
		| { kind: 'playlist'; spotifyId: string; name: string };

	let pendingDelete = $state<DeleteTarget | null>(null);
	let deleting = $state(false);
	let deleteError = $state<string | null>(null);

	function askDelete(target: DeleteTarget, e: MouseEvent) {
		e.preventDefault();
		e.stopPropagation();
		pendingDelete = target;
		deleteError = null;
	}

	function cancelDelete() {
		if (deleting) return;
		pendingDelete = null;
		deleteError = null;
	}

	async function confirmDelete() {
		if (!pendingDelete) return;
		deleting = true;
		deleteError = null;
		try {
			if (pendingDelete.kind === 'session') {
				await api.archiveSession(pendingDelete.spotifyId);
			} else if (pendingDelete.kind === 'project') {
				await api.deleteProject(pendingDelete.spotifyId);
			} else {
				await api.deletePlaylist(pendingDelete.spotifyId);
			}
			pendingDelete = null;
			await invalidateAll();
		} catch (e) {
			deleteError = e instanceof ApiError ? e.detail || e.message : String(e);
		} finally {
			deleting = false;
		}
	}

	const confirmMessage = $derived.by(() => {
		if (!pendingDelete) return '';
		if (pendingDelete.kind === 'session') {
			return `La session "${pendingDelete.name}" sera supprimée définitivement (versions audio comprises). La playlist/track de référence n'est pas touchée.`;
		}
		if (pendingDelete.kind === 'project') {
			return `Le projet local "${pendingDelete.name}" sera supprimé : ses fichiers audio uploadés, ses analyses, ses patterns et son brief. Cette action est irréversible.`;
		}
		return `La playlist "${pendingDelete.name}" sera supprimée du dashboard, avec ses analyses agrégées et son brief. Les tracks individuelles restent en base (peuvent être référencées par d'autres playlists / sessions).`;
	});
</script>

<div class="flex items-end justify-between mb-8 gap-4 flex-wrap">
	<div>
		<h1 class="text-3xl font-bold tracking-tight">Dashboard</h1>
		<p class="mt-1 text-sm text-[var(--color-fg-muted)]">
			Sessions créatives, playlists analysées et projets locaux.
		</p>
	</div>
</div>

<!-- ─── Sessions créatives ─────────────────────────────────────────── -->
<section class="mb-10">
	<div class="flex items-end justify-between mb-4 gap-4 flex-wrap">
		<div>
			<h2 class="text-xl font-bold tracking-tight flex items-center gap-2">
				<span class="inline-block h-2 w-2 rounded-full bg-[var(--color-accent)]"></span>
				Sessions créatives
			</h2>
			<p class="mt-1 text-xs text-[var(--color-fg-muted)]">
				Démarrer une track depuis zéro avec une cible d'inspiration
				· {data.sessions.length} session{data.sessions.length > 1 ? 's' : ''} active{data.sessions.length > 1 ? 's' : ''}
			</p>
		</div>
		<Button variant="primary" onclick={() => (wizardOpen = true)}>
			+ Session guidée
		</Button>
	</div>

	{#if data.sessions.length === 0}
		<Card class="border-dashed">
			<div class="text-center py-6 text-sm text-[var(--color-fg-muted)]">
				<p class="mb-2">Pas de session en cours.</p>
				<p class="text-xs">
					Tu peux démarrer une track guidée par une cible d'inspiration
					(playlist ou track Spotify déjà analysée).
				</p>
			</div>
		</Card>
	{:else}
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
			{#each data.sessions as s (s.spotify_id)}
				<div class="card-with-delete">
					<Card href="/sessions/{encodeURIComponent(s.spotify_id)}">
						<div class="flex items-start justify-between gap-3 mb-2">
							<h3 class="font-semibold leading-tight line-clamp-2 text-sm">{s.name}</h3>
							<Badge variant="accent">Session</Badge>
						</div>
						<p class="text-xs text-[var(--color-fg-muted)] truncate mb-3">
							Cible : <span class="text-[var(--color-fg)]">{s.target_name}</span>
						</p>
						<div class="flex items-center justify-between text-xs">
							<span class="text-[var(--color-fg-muted)]">
								<span class="font-mono text-[var(--color-fg)]">{s.n_versions}</span>
								version{s.n_versions > 1 ? 's' : ''}
							</span>
							{#if s.last_fit_score !== null}
								<span class="font-mono">
									fit
									<span class="text-[var(--color-accent)]">
										{(s.last_fit_score * 100).toFixed(0)}%
									</span>
								</span>
							{/if}
						</div>
						<div class="mt-3 pt-3 border-t border-[var(--color-border)] text-xs text-[var(--color-fg-muted)] flex justify-between">
							<span>Dernier upload</span>
							<span class="font-mono">{formatDateTime(s.updated_at)}</span>
						</div>
					</Card>
					<button
						type="button"
						class="delete-btn"
						onclick={(e) => askDelete({ kind: 'session', spotifyId: s.spotify_id, name: s.name }, e)}
						aria-label="Supprimer la session"
						title="Supprimer la session"
					>
						🗑
					</button>
				</div>
			{/each}
		</div>
	{/if}
</section>

<!-- ─── Playlists & projets ────────────────────────────────────────── -->
<section>
	<div class="flex items-end justify-between mb-4 gap-4 flex-wrap">
		<div>
			<h2 class="text-xl font-bold tracking-tight">Playlists & projets</h2>
			<p class="mt-1 text-xs text-[var(--color-fg-muted)]">
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
				{@const local = isLocalProject(p.spotify_id)}
				<div class="card-with-delete">
					<Card href="/playlists/{encodeURIComponent(p.spotify_id)}">
						<div class="flex items-start justify-between gap-3 mb-3">
							<h2 class="font-semibold leading-tight line-clamp-2">{p.name}</h2>
							<div class="flex flex-col items-end gap-1.5 shrink-0">
								{#if local}
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
					<button
						type="button"
						class="delete-btn"
						onclick={(e) =>
							askDelete(
								{
									kind: local ? 'project' : 'playlist',
									spotifyId: p.spotify_id,
									name: p.name
								},
								e
							)}
						aria-label={local ? 'Supprimer le projet' : 'Supprimer la playlist'}
						title={local ? 'Supprimer le projet' : 'Supprimer la playlist'}
					>
						🗑
					</button>
				</div>
			{/each}
		</div>
	{/if}
</section>

<SessionWizardModal isOpen={wizardOpen} onClose={() => (wizardOpen = false)} />

<ConfirmDialog
	isOpen={pendingDelete !== null}
	title={pendingDelete?.kind === 'session'
		? 'Supprimer cette session ?'
		: pendingDelete?.kind === 'project'
			? 'Supprimer ce projet local ?'
			: 'Supprimer cette playlist ?'}
	message={confirmMessage + (deleteError ? `\n\nErreur : ${deleteError}` : '')}
	confirmLabel="Supprimer définitivement"
	onConfirm={confirmDelete}
	onCancel={cancelDelete}
	busy={deleting}
/>

<style>
	.card-with-delete {
		position: relative;
	}
	.delete-btn {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border-radius: 6px;
		background: color-mix(in oklab, var(--color-surface) 80%, transparent);
		border: 1px solid var(--color-border);
		color: var(--color-fg-muted);
		font-size: 0.95rem;
		line-height: 1;
		cursor: pointer;
		opacity: 0;
		transition: opacity 0.15s, color 0.15s, background 0.15s;
	}
	.card-with-delete:hover .delete-btn,
	.delete-btn:focus-visible {
		opacity: 1;
	}
	.delete-btn:hover {
		color: var(--color-err);
		background: var(--color-surface);
	}
</style>
