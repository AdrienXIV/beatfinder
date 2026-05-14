<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import type { PageData } from './$types';
	import { api, ApiError, isLocalProject, type Brief, type TrackMeta } from '$lib/api';
	import ActionPlanModal from '$lib/components/ActionPlanModal.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import ScrollLock from '$lib/components/ScrollLock.svelte';
	import TrackCorrectionModal from '$lib/components/TrackCorrectionModal.svelte';
	import Card from '$lib/components/Card.svelte';
	import Stat from '$lib/components/Stat.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import BriefRenderer from '$lib/components/BriefRenderer.svelte';
	import SpectralRing from '$lib/components/charts/SpectralRing.svelte';
	import BpmHistogram from '$lib/components/charts/BpmHistogram.svelte';
	import SparkLine from '$lib/components/charts/SparkLine.svelte';
	import { cn, formatDateTime, formatDurationMs, formatNumber, formatPercent } from '$lib/utils';

	let { data }: { data: PageData } = $props();
	let { detail, playlists, comparedTargets, actionSources, stylePrediction } = $derived(data);
	const isLocal = $derived(isLocalProject(detail.spotify_id));
	const sourcesMap = $derived(
		new Map(actionSources.map((s) => [s.from_id, s.n_targets]))
	);
	const nUnanalyzed = $derived(detail.tracks.filter((t) => !t.has_analysis).length);
	let actionPlanOpen = $state(false);
	let actionPlanInitialTarget = $state<string | null>(null);
	let actionPlanSourceId = $state<string>('');
	let actionPlanSourceName = $state<string>('');

	function openActionPlan(targetId: string | null = null) {
		actionPlanSourceId = detail.spotify_id;
		actionPlanSourceName = detail.name;
		actionPlanInitialTarget = targetId;
		actionPlanOpen = true;
	}
	function openActionPlanForTrack(track: { spotify_id: string; artist: string; title: string }) {
		const display = track.artist ? `${track.artist} — ${track.title}` : track.title;
		actionPlanSourceId = track.spotify_id;
		actionPlanSourceName = display;
		actionPlanInitialTarget = null;
		actionPlanOpen = true;
	}
	function closeActionPlan() {
		actionPlanOpen = false;
		actionPlanInitialTarget = null;
	}
	async function reloadComparedTargets() {
		await invalidateAll();
	}

	type Tab = 'brief' | 'tracks' | 'patterns';
	let activeTab = $state<Tab>('brief');

	let addFileInput: HTMLInputElement | null = $state(null);
	let actionBusy = $state(false);
	let actionError = $state<string | null>(null);
	let actionMsg = $state<string | null>(null);

	let deleteDialog: HTMLDialogElement | null = $state(null);
	let deleteDialogOpen = $state(false);
	let deleting = $state(false);
	let deleteError = $state<string | null>(null);

	let correctionOpen = $state(false);
	let correctionTrack = $state<TrackMeta | null>(null);
	function openCorrection(t: TrackMeta) {
		correctionTrack = t;
		correctionOpen = true;
	}
	function closeCorrection() {
		correctionOpen = false;
	}
	async function onCorrectionSaved() {
		await invalidateAll();
	}

	function handleApiError(e: unknown): string {
		if (e instanceof ApiError) return e.detail || e.message;
		if (e instanceof Error) return e.message;
		return String(e);
	}

	async function onAddFiles(event: Event) {
		const target = event.target as HTMLInputElement;
		if (!target.files || target.files.length === 0) return;
		const files = Array.from(target.files);
		target.value = '';

		actionError = null;
		actionBusy = true;
		actionMsg = `Upload de ${files.length} fichier${files.length > 1 ? 's' : ''}…`;
		try {
			await api.uploadTracks(detail.spotify_id, files);
			actionMsg = "Lancement de l'analyse (nouveaux uniquement)…";
			const job = await api.analyzeLocal(detail.spotify_id, 'new');
			await goto(`/jobs/${job.id}`);
		} catch (e) {
			actionBusy = false;
			actionError = handleApiError(e);
			actionMsg = null;
		}
	}

	async function analyzeMode(mode: 'new' | 'full') {
		actionError = null;
		actionBusy = true;
		actionMsg =
			mode === 'new'
				? `Analyse de ${nUnanalyzed} nouvelle${nUnanalyzed > 1 ? 's' : ''} track${nUnanalyzed > 1 ? 's' : ''}…`
				: 'Re-analyse complète…';
		try {
			const job = await api.analyzeLocal(detail.spotify_id, mode);
			await goto(`/jobs/${job.id}`);
		} catch (e) {
			actionBusy = false;
			actionError = handleApiError(e);
			actionMsg = null;
		}
	}

	function openDeleteDialog() {
		deleteError = null;
		deleteDialog?.showModal();
		deleteDialogOpen = true;
	}

	function closeDeleteDialog() {
		if (deleting) return;
		deleteDialog?.close();
		deleteDialogOpen = false;
	}

	async function confirmDelete() {
		deleting = true;
		deleteError = null;
		try {
			await api.deleteProject(detail.spotify_id);
			await goto('/');
		} catch (e) {
			deleting = false;
			deleteError = handleApiError(e);
		}
	}

	let brief = $state<Brief | null>(null);
	let briefError = $state<string | null>(null);
	let briefMissing = $state(false); // pattern pas encore généré (409)
	let briefLoading = $state(false);

	async function loadBrief(regenerate = false) {
		briefError = null;
		briefMissing = false;
		briefLoading = true;
		try {
			brief = await api.getBrief(detail.spotify_id, regenerate);
		} catch (e) {
			// 409 = pas de pattern dispo (projet créé mais jamais analysé, ou
			// analyse annulée). On affiche un état vide propre au lieu d'une erreur.
			if (e instanceof ApiError && e.status === 409) {
				briefMissing = true;
			} else {
				briefError = e instanceof Error ? e.message : String(e);
			}
		} finally {
			briefLoading = false;
		}
	}

	$effect(() => {
		if (
			activeTab === 'brief' &&
			!brief &&
			!briefLoading &&
			!briefError &&
			!briefMissing
		) {
			loadBrief();
		}
	});

	const lp = $derived(detail.latest_pattern);
	const bpm = $derived(lp?.tempo?.bpm?.median);
	const lufs = $derived(lp?.energy?.lufs_integrated?.median);
	const modeDist = $derived(lp?.tonality?.mode?.distribution as Record<string, number> | undefined);
	const minor = $derived(modeDist?.minor ?? 0);
	const subPct = $derived(lp?.spectral?.band_energy?.sub?.median);
	const bassPct = $derived(lp?.spectral?.band_energy?.bass?.median);
	const drop = $derived(lp?.structure?.drop_position_ratio?.median);

	const bandsForRadar = $derived.by(() => {
		const be = lp?.spectral?.band_energy;
		if (!be) return null;
		return {
			sub: be.sub?.median,
			bass: be.bass?.median,
			low_mid: be.low_mid?.median,
			mid: be.mid?.median,
			high_mid: be.high_mid?.median,
			high: be.high?.median
		} as Record<string, number>;
	});

	const bpmRaw = $derived(((lp?.tempo?.bpm_raw as number[] | undefined) ?? []).filter(Boolean));

	const coherenceFlags = $derived(
		((lp?.coherence_flags as string[] | undefined) ?? []).filter(Boolean)
	);
	const coherenceLabels: Record<string, string> = {
		bpm: 'BPM',
		mode: 'mode mineur/majeur',
		sub: 'sub-bass'
	};
	const coherenceText = $derived(
		coherenceFlags.map((f) => coherenceLabels[f] ?? f).join(', ')
	);

	const tabClass = (tab: Tab) =>
		cn(
			'px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px',
			activeTab === tab
				? 'border-[var(--color-accent)] text-[var(--color-fg)]'
				: 'border-transparent text-[var(--color-fg-muted)] hover:text-[var(--color-fg)]'
		);
</script>

<div class="mb-6">
	<a
		href="/"
		class="no-print text-sm text-[var(--color-fg-muted)] hover:text-[var(--color-fg)] mb-3 inline-block"
	>
		← Toutes les playlists
	</a>
	<div class="flex items-end justify-between gap-4 flex-wrap">
		<div>
			<div class="flex items-center gap-x-2 gap-y-2 mb-2 flex-wrap">
				{#if isLocal}
					<Badge variant="accent">Local</Badge>
				{:else}
					<Badge variant="muted">Spotify</Badge>
				{/if}
			</div>
			<h1 class="text-3xl font-bold tracking-tight">{detail.name}</h1>
			<p class="mt-1 text-sm text-[var(--color-fg-muted)]">
				{detail.tracks.length} tracks · {detail.patterns.length} patterns
				{#if detail.owner_display_name}
					· par {detail.owner_display_name}
				{/if}
			</p>
		</div>
		<div class="no-print flex gap-2 flex-wrap">
			<Button
				variant="outline"
				href="/playlists/{encodeURIComponent(detail.spotify_id)}/styles"
			>
				Choisir un style PDF
			</Button>
			<Button
				variant="outline"
				href="/playlists/{encodeURIComponent(detail.spotify_id)}/print"
			>
				Imprimer en PDF
			</Button>
			<Button href={api.briefMdUrl(detail.spotify_id)} variant="outline">
				Download .md
			</Button>
			<Button href="/compare?a={encodeURIComponent(detail.spotify_id)}" variant="outline">
				Comparer
			</Button>
			<Button variant="primary" onclick={() => openActionPlan()} disabled={!detail.latest_pattern}>
				Plan d'action
			</Button>
		</div>
	</div>
</div>

{#if isLocal}
	<Card class="mb-6 border-[var(--color-accent)]/30">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div>
				<p class="text-sm font-medium mb-0.5 flex items-center gap-2">
					Actions locales
					{#if nUnanalyzed > 0}
						<Badge variant="warn">{nUnanalyzed} non analysé{nUnanalyzed > 1 ? 's' : ''}</Badge>
					{/if}
				</p>
				<p class="text-xs text-[var(--color-fg-muted)]">
					Uploade plus de fichiers, relance l'analyse, ou supprime le projet.
				</p>
			</div>
			<div class="flex gap-2 flex-wrap">
				<input
					bind:this={addFileInput}
					type="file"
					multiple
					accept=".wav,.mp3,.flac,.ogg,.m4a,.aiff"
					onchange={onAddFiles}
					class="hidden"
				/>
				<Button
					variant="outline"
					size="sm"
					disabled={actionBusy}
					onclick={() => addFileInput?.click()}
				>
					+ Ajouter tracks
				</Button>
				<Button
					variant="primary"
					size="sm"
					loading={actionBusy && actionMsg?.startsWith('Analyse de')}
					disabled={actionBusy || nUnanalyzed === 0}
					onclick={() => analyzeMode('new')}
				>
					{#if nUnanalyzed > 0}
						Analyser {nUnanalyzed} nouveau{nUnanalyzed > 1 ? 'x' : ''}
					{:else}
						Analyser nouveaux
					{/if}
				</Button>
				<Button
					variant="ghost"
					size="sm"
					loading={actionBusy && actionMsg === 'Re-analyse complète…'}
					disabled={actionBusy || detail.tracks.length === 0}
					onclick={() => analyzeMode('full')}
				>
					Re-analyser tout
				</Button>
			</div>
		</div>
		{#if actionMsg}
			<p class="mt-3 text-xs text-[var(--color-fg-muted)] italic">{actionMsg}</p>
		{/if}
		{#if actionError}
			<p class="mt-3 text-xs text-[var(--color-err)]">{actionError}</p>
		{/if}

		<div class="mt-4 pt-3 border-t border-[var(--color-border)] flex items-center justify-between gap-3">
			<span class="text-xs text-[var(--color-fg-muted)]">Danger zone</span>
			<Button variant="destructive" size="sm" disabled={actionBusy} onclick={openDeleteDialog}>
				Supprimer ce projet
			</Button>
		</div>
	</Card>

	<ScrollLock open={deleteDialogOpen} />

	<dialog
		bind:this={deleteDialog}
		class="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-0 backdrop:bg-black/60 max-w-md w-full"
	>
		<div class="p-6 space-y-4">
			<div>
				<h3 class="text-lg font-semibold mb-1">Supprimer ce projet ?</h3>
				<p class="text-sm text-[var(--color-fg-muted)]">
					Le projet <span class="font-semibold text-[var(--color-fg)]">{detail.name}</span>,
					ses {detail.tracks.length} track{detail.tracks.length > 1 ? 's' : ''},
					les fichiers audio uploadés et le brief seront définitivement supprimés.
				</p>
				<p class="text-xs text-[var(--color-fg-muted)] mt-2 italic">
					Cette action est irréversible.
				</p>
			</div>
			{#if deleteError}
				<div class="rounded-md border border-[var(--color-err)]/40 bg-[var(--color-err)]/10 p-2 text-xs text-[var(--color-err)]">
					{deleteError}
				</div>
			{/if}
			<div class="flex justify-end gap-2 pt-2">
				<Button variant="ghost" size="sm" disabled={deleting} onclick={closeDeleteDialog}>
					Annuler
				</Button>
				<Button variant="destructive" size="sm" loading={deleting} onclick={confirmDelete}>
					Supprimer définitivement
				</Button>
			</div>
		</div>
	</dialog>
{/if}

{#if lp}
	<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
		<Stat label="BPM médian" value={formatNumber(bpm, 0)} />
		<Stat label="LUFS" value={formatNumber(lufs, 1)} hint="dB intégré" />
		<Stat label="Mineur" value={formatPercent(minor, 0)} />
		<Stat label="Sub 20-60Hz" value={formatPercent(subPct, 0)} />
		<Stat label="Bass 60-250Hz" value={formatPercent(bassPct, 0)} />
		<Stat label="Drop pos" value={formatPercent(drop, 0)} hint="du track" />
	</div>

	{#if bandsForRadar || bpmRaw.length > 0}
		<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
			{#if bandsForRadar}
				<Card>
					<h3 class="text-sm font-semibold mb-3">Profil spectral</h3>
					<SpectralRing bands={bandsForRadar} size={220} />
				</Card>
			{/if}
			{#if bpmRaw.length > 0}
				<Card>
					<h3 class="text-sm font-semibold mb-3">
						Distribution BPM
						<span class="text-xs font-normal text-[var(--color-fg-muted)]">
							· {bpmRaw.length} tracks · médiane {formatNumber(bpm, 0)} BPM
						</span>
					</h3>
					<BpmHistogram bpms={bpmRaw} />
				</Card>
			{/if}
		</div>
	{/if}
{/if}

{#if coherenceFlags.length > 0}
	<div class="mb-6 rounded-md border border-[var(--color-warn)]/40 bg-[var(--color-warn)]/10 p-3 text-sm">
		<p class="font-medium text-[var(--color-warn)] mb-0.5">⚠ Projet hétérogène</p>
		<p class="text-[var(--color-fg)]">
			Tes tracks varient beaucoup sur <strong>{coherenceText}</strong>. Le pattern global est
			bruité et le plan d'action vs une autre playlist sera peu fiable. Considère séparer en
			projets distincts par style.
		</p>
	</div>
{/if}

{#if stylePrediction && stylePrediction.predictions.length > 0}
	{@const top = stylePrediction.predictions[0]}
	{@const conf = top.probability}
	<div class="no-print mb-6">
		<div class="flex items-center justify-between mb-2">
			<h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--color-fg-muted)]">
				Style prédit
			</h2>
			<span class="text-xs text-[var(--color-fg-muted)]">
				modèle CV {(stylePrediction.model_cv_accuracy * 100).toFixed(0)}% · {stylePrediction.model_classes.length} classes
			</span>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			{#each stylePrediction.predictions as p (p.style)}
				{@const isTop = p.style === top.style}
				<span
					class={[
						'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs',
						isTop
							? 'border-[var(--color-accent)] text-[var(--color-accent)] font-semibold'
							: 'border-[var(--color-border)] text-[var(--color-fg-muted)]'
					].join(' ')}
				>
					<span>{p.style}</span>
					<span class="font-mono">{(p.probability * 100).toFixed(0)}%</span>
				</span>
			{/each}
			{#if conf < 0.6}
				<span class="text-xs text-[var(--color-fg-muted)] italic">
					— prédiction incertaine (top &lt; 60%)
				</span>
			{/if}
		</div>
	</div>
{/if}

{#if comparedTargets.length > 0}
	<div class="no-print mb-8">
		<div class="flex items-center justify-between mb-2">
			<h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--color-fg-muted)]">
				Comparé avec
			</h2>
			<span class="text-xs text-[var(--color-fg-muted)]">
				{comparedTargets.length} cible{comparedTargets.length > 1 ? 's' : ''} en cache
			</span>
		</div>
		<div class="flex flex-wrap gap-2">
			{#each comparedTargets as ct (ct.target_id)}
				<button
					class="flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-2)] px-3 py-2 transition-colors"
					onclick={() => openActionPlan(ct.target_id)}
					title="Rouvrir le plan d'action sur {ct.target_name}"
				>
					<span class="h-2 w-2 rounded-full bg-[var(--color-ok)]" aria-hidden="true"></span>
					<span class="text-sm font-medium">{ct.target_name}</span>
					<span class="text-xs font-mono text-[var(--color-fg-muted)]">
						{ct.n_items} actions
					</span>
				</button>
			{/each}
		</div>
	</div>
{/if}

<div class="no-print border-b border-[var(--color-border)] mb-6">
	<div class="flex gap-1">
		<button class={tabClass('brief')} onclick={() => (activeTab = 'brief')}>Brief</button>
		<button class={tabClass('tracks')} onclick={() => (activeTab = 'tracks')}>
			Tracks ({detail.tracks.length})
		</button>
		<button class={tabClass('patterns')} onclick={() => (activeTab = 'patterns')}>
			Patterns ({detail.patterns.length})
		</button>
	</div>
</div>

{#if activeTab === 'brief'}
	{#if briefLoading}
		<div class="space-y-3">
			<Skeleton class="h-8 w-2/3" />
			<Skeleton class="h-4 w-full" />
			<Skeleton class="h-4 w-5/6" />
			<Skeleton class="h-4 w-3/4" />
			<Skeleton class="h-32 w-full" />
		</div>
	{:else if briefMissing}
		<div class="rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)]/40 p-6 text-center text-sm">
			<p class="font-medium mb-1">Pas encore de brief</p>
			<p class="text-[var(--color-fg-muted)] max-w-md mx-auto">
				{#if isLocal}
					Le projet a été créé mais aucune analyse n'a abouti. Uploade des tracks ou lance
					l'analyse pour générer le brief.
				{:else}
					Cette playlist n'a pas encore de pattern. Lance l'analyse depuis « Analyser Spotify ».
				{/if}
			</p>
		</div>
	{:else if briefError}
		<div class="rounded-md border border-[var(--color-err)]/40 bg-[var(--color-err)]/10 p-4 text-sm">
			<p class="font-medium mb-1">Erreur de chargement du brief</p>
			<p class="text-[var(--color-fg-muted)]">{briefError}</p>
			<Button onclick={() => loadBrief()} variant="outline" size="sm" class="mt-3">Retry</Button>
		</div>
	{:else if brief}
		<div class="mb-3 flex items-center justify-between text-xs text-[var(--color-fg-muted)]">
			<span>
				Généré le {formatDateTime(brief.generated_at)}
				{#if brief.cached}<Badge variant="muted" class="ml-2">cached</Badge>{/if}
			</span>
			<Button variant="ghost" size="sm" onclick={() => loadBrief(true)} loading={briefLoading}>
				Régénérer
			</Button>
		</div>
		<BriefRenderer markdown={brief.markdown} />
	{/if}
{:else if activeTab === 'tracks'}
	{@const formatKey = (note: string | null, mode: 'major' | 'minor' | null) => {
		if (!note || !mode) return '—';
		return `${note} ${mode}`;
	}}
	<div class="overflow-x-auto rounded-lg border border-[var(--color-border)]">
		<table class="w-full text-sm">
			<thead class="bg-[var(--color-surface-2)] text-xs uppercase tracking-wider text-[var(--color-fg-muted)]">
				<tr>
					<th class="px-3 py-2 text-left w-12">#</th>
					<th class="px-3 py-2 text-left">Artist</th>
					<th class="px-3 py-2 text-left">Title</th>
					<th class="px-3 py-2 text-right w-20">BPM</th>
					<th class="px-3 py-2 text-right w-28">Key</th>
					<th class="px-3 py-2 text-right">Duration</th>
					<th class="px-3 py-2 text-center">Analyzed</th>
					<th class="px-3 py-2 text-center w-8" title="Corriger BPM / Tonalité"></th>
					<th class="px-3 py-2 text-right w-32">Action</th>
				</tr>
			</thead>
			<tbody>
				{#each detail.tracks as t (t.spotify_id)}
					<tr class="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-2)]/50">
						<td class="px-3 py-2 font-mono text-[var(--color-fg-muted)]">
							{t.position + 1}
						</td>
						<td class="px-3 py-2 truncate max-w-[180px]">{t.artist || '—'}</td>
						<td class="px-3 py-2 truncate max-w-[280px]">{t.title}</td>
						<td class="px-3 py-2 text-right font-mono tabular-nums">
							{#if t.bpm != null}
								{formatNumber(t.bpm, 0)}
							{:else}
								<span class="text-[var(--color-fg-muted)]">—</span>
							{/if}
						</td>
						<td
							class={cn(
								'px-3 py-2 text-right font-mono',
								t.key_uncertain && 'text-[var(--color-fg-muted)] italic'
							)}
							title={t.key_uncertain ? 'Tonalité incertaine (vote 1/3 sans majorité)' : undefined}
						>
							{formatKey(t.key_note, t.key_mode)}
						</td>
						<td class="px-3 py-2 text-right font-mono text-[var(--color-fg-muted)]">
							{formatDurationMs(t.duration_ms)}
						</td>
						<td class="px-3 py-2 text-center">
							{#if t.has_analysis}
								<Badge variant="ok">OK</Badge>
							{:else}
								<Badge variant="muted">—</Badge>
							{/if}
						</td>
						<td class="px-3 py-2 text-center">
							{#if t.has_analysis}
								<button
									type="button"
									onclick={() => openCorrection(t)}
									class={cn(
										'inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold transition-colors',
										t.is_overridden
											? 'border border-[var(--color-accent)] bg-[var(--color-accent)]/15 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/25'
											: t.confidence_low
												? 'border border-[var(--color-warn)] text-[var(--color-warn)] hover:bg-[var(--color-warn)]/15'
												: 'border border-[var(--color-border)] text-[var(--color-fg-muted)] hover:text-[var(--color-fg)] hover:border-[var(--color-fg-muted)]'
									)}
									title={t.is_overridden
										? 'Valeurs corrigées manuellement (clic pour rééditer)'
										: t.confidence_low
											? 'Analyse incertaine — clic pour corriger'
											: 'Corriger BPM / Tonalité'}
									aria-label="Corriger BPM / Tonalité"
								>
									{#if t.is_overridden}
										✓
									{:else if t.confidence_low}
										⚠
									{:else}
										✎
									{/if}
								</button>
							{/if}
						</td>
						<td class="px-3 py-2 text-right">
							{#if t.has_analysis}
								{@const nTargets = sourcesMap.get(t.spotify_id) ?? 0}
								<div class="flex items-center justify-end gap-2">
									{#if nTargets > 0}
										<span
											class="flex items-center gap-1 text-xs text-[var(--color-fg-muted)]"
											title="Déjà comparé à {nTargets} cible{nTargets > 1 ? 's' : ''}"
										>
											<span class="h-2 w-2 rounded-full bg-[var(--color-ok)]" aria-hidden="true"></span>
											{nTargets}
										</span>
									{/if}
									<Button
										variant="ghost"
										size="sm"
										onclick={() => openActionPlanForTrack(t)}
									>
										Comparer
									</Button>
								</div>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{:else if activeTab === 'patterns'}
	{#if detail.patterns.length === 0}
		<p class="text-[var(--color-fg-muted)]">Aucun pattern historique.</p>
	{:else}
		{@const sortedAsc = [...detail.patterns].sort((a, b) => a.id - b.id)}
		{#if sortedAsc.length >= 2}
			{@const sparkRows = [
				{
					label: 'BPM',
					color: '#f97316',
					values: sortedAsc.map((p) => p.bpm_median ?? 0),
					fmt: (v: number) => v.toFixed(0)
				},
				{
					label: 'LUFS',
					color: '#10b981',
					values: sortedAsc.map((p) => p.lufs_median ?? 0),
					fmt: (v: number) => v.toFixed(1)
				},
				{
					label: 'Sub',
					color: '#ef4444',
					values: sortedAsc.map((p) => (p.sub_median ?? 0) * 100),
					fmt: (v: number) => `${v.toFixed(0)}%`
				},
				{
					label: 'Bass',
					color: '#facc15',
					values: sortedAsc.map((p) => (p.bass_median ?? 0) * 100),
					fmt: (v: number) => `${v.toFixed(0)}%`
				},
				{
					label: 'Mineur',
					color: '#9a9aa3',
					values: sortedAsc.map((p) => (p.minor_ratio ?? 0) * 100),
					fmt: (v: number) => `${v.toFixed(0)}%`
				}
			]}
			<div class="mb-6">
				<p class="text-xs text-[var(--color-fg-muted)] mb-3">
					Évolution sur {sortedAsc.length} patterns (du plus ancien au plus récent).
				</p>
				<div class="grid grid-cols-2 md:grid-cols-5 gap-4">
					{#each sparkRows as row (row.label)}
						<Card>
							<div class="flex items-baseline justify-between mb-1">
								<span class="text-xs uppercase tracking-wider text-[var(--color-fg-muted)]">
									{row.label}
								</span>
								<span class="font-mono text-sm">{row.fmt(row.values[row.values.length - 1])}</span>
							</div>
							<SparkLine values={row.values} color={row.color} fmt={row.fmt} height={36} />
						</Card>
					{/each}
				</div>
			</div>
		{/if}
		<div class="space-y-2">
			{#each detail.patterns as p (p.id)}
				<div
					class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3"
				>
					<div class="flex items-center justify-between mb-2">
						<div class="flex items-center gap-3">
							<Badge variant="muted">#{p.id}</Badge>
							<span class="font-mono text-sm">{p.analyzer_version}</span>
							<span class="text-sm text-[var(--color-fg-muted)]">
								{p.n_tracks_analyzed} tracks
							</span>
						</div>
						<span class="text-xs font-mono text-[var(--color-fg-muted)]">
							{formatDateTime(p.created_at)}
						</span>
					</div>
					<div class="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs font-mono">
						<div>
							<span class="text-[var(--color-fg-muted)]">BPM </span>
							<span>{formatNumber(p.bpm_median, 0)}</span>
						</div>
						<div>
							<span class="text-[var(--color-fg-muted)]">LUFS </span>
							<span>{formatNumber(p.lufs_median, 1)}</span>
						</div>
						<div>
							<span class="text-[var(--color-fg-muted)]">Sub </span>
							<span>{formatPercent(p.sub_median, 0)}</span>
						</div>
						<div>
							<span class="text-[var(--color-fg-muted)]">Bass </span>
							<span>{formatPercent(p.bass_median, 0)}</span>
						</div>
						<div>
							<span class="text-[var(--color-fg-muted)]">Mineur </span>
							<span>{formatPercent(p.minor_ratio, 0)}</span>
						</div>
					</div>
				</div>
			{/each}
		</div>
	{/if}
{/if}

<ActionPlanModal
	isOpen={actionPlanOpen}
	currentId={actionPlanSourceId}
	currentName={actionPlanSourceName}
	{playlists}
	comparedTargets={actionPlanSourceId === detail.spotify_id ? comparedTargets : []}
	initialTargetId={actionPlanInitialTarget}
	onClose={closeActionPlan}
	onPlanSaved={reloadComparedTargets}
/>

<TrackCorrectionModal
	track={correctionTrack}
	isOpen={correctionOpen}
	onClose={closeCorrection}
	onSaved={onCorrectionSaved}
/>
