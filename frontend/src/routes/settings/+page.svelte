<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import type { PageData } from './$types';
	import { api, ApiError, type CacheKind } from '$lib/api';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import Stat from '$lib/components/Stat.svelte';
	import { cn, formatBytes } from '$lib/utils';

	let { data }: { data: PageData } = $props();

	const cacheStats = $derived(data.cacheStats);
	const spotify = $derived(data.spotify);

	let spClientId = $state(data.spotify.client_id);
	let spClientSecret = $state('');
	let spSaving = $state(false);
	let spSaveError = $state<string | null>(null);
	let spSaveOk = $state(false);

	async function saveSpotify() {
		spSaveError = null;
		spSaveOk = false;
		if (!spClientId.trim()) {
			spSaveError = 'client_id requis';
			return;
		}
		if (!spClientSecret.trim() && !spotify.has_secret) {
			spSaveError = 'client_secret requis (jamais affiché en clair, mais doit être saisi pour la 1ère config)';
			return;
		}
		spSaving = true;
		try {
			await api.putSpotifySettings({
				client_id: spClientId.trim(),
				client_secret: spClientSecret.trim()
			});
			spClientSecret = '';
			spSaveOk = true;
			await invalidateAll();
		} catch (e) {
			spSaveError = e instanceof ApiError ? e.detail : String(e);
		} finally {
			spSaving = false;
		}
	}

	async function clearSpotify() {
		if (
			!confirm(
				'Effacer les credentials Spotify ? Tu ne pourras plus analyser de playlists tant que tu ne les ressaisis pas.'
			)
		) {
			return;
		}
		spSaving = true;
		spSaveError = null;
		try {
			await api.deleteSpotifySettings();
			spClientId = '';
			spClientSecret = '';
			spSaveOk = false;
			await invalidateAll();
		} catch (e) {
			spSaveError = e instanceof ApiError ? e.detail : String(e);
		} finally {
			spSaving = false;
		}
	}

	let flushBusy = $state<CacheKind | null>(null);
	let flushError = $state<string | null>(null);
	let flushMsg = $state<string | null>(null);

	function handleApiError(e: unknown): string {
		if (e instanceof ApiError) return e.detail || e.message;
		if (e instanceof Error) return e.message;
		return String(e);
	}

	async function flush(kind: CacheKind, label: string) {
		const cat = cacheStats[kind as keyof typeof cacheStats];
		if (!cat || cat.n_files === 0) return;
		if (
			!confirm(
				`Supprimer ${cat.n_files} fichier${cat.n_files > 1 ? 's' : ''} dans "${label}" ` +
					`(${formatBytes(cat.size_bytes)}) ?\nIrréversible.`
			)
		) {
			return;
		}
		flushBusy = kind;
		flushError = null;
		flushMsg = null;
		try {
			const r = await api.flushCache(kind);
			flushMsg = `${label} : ${r.n_files_deleted} fichier${r.n_files_deleted > 1 ? 's' : ''} supprimé${r.n_files_deleted > 1 ? 's' : ''} (${formatBytes(r.bytes_freed)} libéré${r.bytes_freed > 1 ? 's' : ''})`;
			await invalidateAll();
		} catch (e) {
			flushError = handleApiError(e);
		} finally {
			flushBusy = null;
		}
	}

	const totalDiskUsed = $derived(
		cacheStats.youtube.size_bytes +
			cacheStats['local-audio'].size_bytes +
			cacheStats.reports.size_bytes +
			cacheStats.actions.size_bytes +
			cacheStats.db.size_bytes
	);

	const cacheItems = $derived([
		{ key: 'youtube' as CacheKind, cat: cacheStats.youtube },
		{ key: 'local-audio' as CacheKind, cat: cacheStats['local-audio'] },
		{ key: 'reports' as CacheKind, cat: cacheStats.reports },
		{ key: 'actions' as CacheKind, cat: cacheStats.actions }
	]);
</script>

<div class="mb-6">
	<h1 class="text-3xl font-bold tracking-tight">Paramètres</h1>
	<p class="mt-1 text-sm text-[var(--color-fg-muted)]">
		Configuration Spotify et gestion du cache disque.
	</p>
</div>

<!-- Section Spotify -->
<section class="mb-10">
	<div class="mb-3 flex items-center justify-between flex-wrap gap-3">
		<div class="flex items-center gap-3">
			<h2 class="text-lg font-semibold">Spotify</h2>
			{#if spotify.is_configured}
				<Badge variant="ok">configuré</Badge>
			{:else}
				<Badge variant="warn">non configuré</Badge>
			{/if}
		</div>
		<a
			href="https://developer.spotify.com/dashboard"
			target="_blank"
			rel="noopener noreferrer"
			class="text-xs text-[var(--color-accent)] hover:underline"
		>
			↗ Créer une app Spotify Developer
		</a>
	</div>

	<Card>
		<p class="text-sm text-[var(--color-fg-muted)] mb-4">
			Beatfinder utilise l'API Spotify pour lister les tracks d'une playlist. Crée une app sur
			<a href="https://developer.spotify.com/dashboard" target="_blank" rel="noopener noreferrer" class="text-[var(--color-accent)] hover:underline">
				developer.spotify.com/dashboard
			</a>, récupère le <code class="px-1 bg-[var(--color-surface-2)] rounded">Client ID</code> et
			<code class="px-1 bg-[var(--color-surface-2)] rounded">Client Secret</code>, puis ajoute
			<code class="px-1 bg-[var(--color-surface-2)] rounded">http://127.0.0.1:8888/callback</code>
			dans les <strong>Redirect URIs</strong> de ton app Spotify.
		</p>

		<div class="space-y-3">
			<div>
				<label for="sp-client-id" class="text-xs font-medium uppercase tracking-wider text-[var(--color-fg-muted)] block mb-1">
					Client ID
				</label>
				<input
					id="sp-client-id"
					type="text"
					bind:value={spClientId}
					placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
					autocomplete="off"
					spellcheck="false"
					class="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-sm font-mono focus:outline-none focus:border-[var(--color-accent)]"
				/>
			</div>
			<div>
				<label for="sp-client-secret" class="text-xs font-medium uppercase tracking-wider text-[var(--color-fg-muted)] block mb-1">
					Client Secret
					{#if spotify.has_secret}
						<span class="ml-2 text-[var(--color-ok)] normal-case tracking-normal">· déjà configuré (laisse vide pour ne pas changer)</span>
					{/if}
				</label>
				<input
					id="sp-client-secret"
					type="password"
					bind:value={spClientSecret}
					placeholder={spotify.has_secret ? '••••••••••••••••' : 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}
					autocomplete="off"
					spellcheck="false"
					class="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-sm font-mono focus:outline-none focus:border-[var(--color-accent)]"
				/>
			</div>
		</div>

		{#if spSaveError}
			<div class="mt-3 rounded-md border border-[var(--color-err)]/40 bg-[var(--color-err)]/10 p-2.5 text-sm text-[var(--color-err)]">
				{spSaveError}
			</div>
		{/if}
		{#if spSaveOk}
			<div class="mt-3 rounded-md border border-[var(--color-ok)]/40 bg-[var(--color-ok)]/10 p-2.5 text-sm">
				Spotify configuré. Tu peux maintenant analyser des playlists.
			</div>
		{/if}

		<div class="mt-4 flex items-center justify-between gap-2">
			{#if spotify.is_configured}
				<Button variant="destructive" size="sm" onclick={clearSpotify} disabled={spSaving}>
					Effacer les credentials
				</Button>
			{:else}
				<span></span>
			{/if}
			<Button variant="primary" size="sm" onclick={saveSpotify} loading={spSaving} disabled={spSaving}>
				Enregistrer
			</Button>
		</div>
	</Card>
</section>

<!-- Section Cache -->
<div class="mb-6 flex items-end justify-between gap-4 flex-wrap">
	<div>
		<h2 class="text-lg font-semibold">Cache disque</h2>
		<p class="mt-1 text-sm text-[var(--color-fg-muted)]">
			Inspection et nettoyage des fichiers temporaires (audio, briefs, plans d'action).
		</p>
	</div>
	<span class="text-sm text-[var(--color-fg-muted)]">
		Total : <span class="font-mono text-[var(--color-fg)]">{formatBytes(totalDiskUsed)}</span>
	</span>
</div>

{#if flushMsg}
	<div class="mb-3 rounded-md border border-[var(--color-ok)]/40 bg-[var(--color-ok)]/10 p-3 text-sm">
		{flushMsg}
	</div>
{/if}
{#if flushError}
	<div class="mb-3 rounded-md border border-[var(--color-err)]/40 bg-[var(--color-err)]/10 p-3 text-sm text-[var(--color-err)]">
		{flushError}
	</div>
{/if}

<div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
	{#each cacheItems as item (item.key)}
		<Card>
			<div class="flex items-start justify-between gap-3 mb-2">
				<div>
					<h3 class="text-sm font-semibold">{item.cat.label}</h3>
					<p class="text-xs font-mono text-[var(--color-fg-muted)] mt-0.5">
						{item.cat.description}
					</p>
				</div>
				<Badge variant="muted">{formatBytes(item.cat.size_bytes)}</Badge>
			</div>
			<div class="flex items-center justify-between mt-3">
				<span class="text-xs text-[var(--color-fg-muted)]">
					{item.cat.n_files} fichier{item.cat.n_files > 1 ? 's' : ''}
				</span>
				<Button
					variant="destructive"
					size="sm"
					disabled={item.cat.n_files === 0 || flushBusy !== null}
					loading={flushBusy === item.key}
					onclick={() => flush(item.key, item.cat.label)}
				>
					Vider
				</Button>
			</div>
		</Card>
	{/each}
</div>

<Card class={cn('border-[var(--color-warn)]/30')}>
	<div class="flex flex-wrap items-start justify-between gap-3 mb-3">
		<div>
			<h3 class="text-sm font-semibold flex items-center gap-2">
				{cacheStats.db.label}
				<Badge variant="warn">protégée</Badge>
			</h3>
			<p class="text-xs font-mono text-[var(--color-fg-muted)] mt-0.5">
				{cacheStats.db.description}
			</p>
		</div>
		<Badge variant="muted">{formatBytes(cacheStats.db.size_bytes)}</Badge>
	</div>
	{#if cacheStats.db.counts}
		<div class="grid grid-cols-3 md:grid-cols-5 gap-3">
			<Stat label="Playlists" value={cacheStats.db.counts.playlists} />
			<Stat label="Tracks" value={cacheStats.db.counts.tracks} />
			<Stat label="PL tracks" value={cacheStats.db.counts.playlist_tracks} />
			<Stat label="Analyses" value={cacheStats.db.counts.analyses} />
			<Stat label="Patterns" value={cacheStats.db.counts.patterns} />
		</div>
	{/if}
	<p class="text-xs text-[var(--color-fg-muted)] mt-3 italic">
		La DB n'est pas flushable depuis l'UI (risque de perte permanente). Pour repartir à zéro,
		supprime manuellement <span class="font-mono">data/analyses.db</span> et relance.
	</p>
</Card>
