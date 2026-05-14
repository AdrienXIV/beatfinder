<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import type { PageData } from './$types';
	import { api, ApiError, type TrackMeta } from '$lib/api';
	import BriefRenderer from '$lib/components/BriefRenderer.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import TrackCorrectionModal from '$lib/components/TrackCorrectionModal.svelte';
	import { cn, formatDateTime, formatDurationMs, formatNumber } from '$lib/utils';

	let { data }: { data: PageData } = $props();
	let session = $derived(data.session);

	// ─── État UI ───────────────────────────────────────────────────────
	let planOpen = $state(true);
	let uploadInput: HTMLInputElement | null = $state(null);
	let uploading = $state(false);
	let uploadError = $state<string | null>(null);

	// Modal de correction (réutilisée pour 1 track ou liste)
	let correctionTrack = $state<TrackMeta | null>(null);
	let correctionOpen = $state(false);
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

	// Filtre incertaines (draft mode, playlist target)
	let filterUncertain = $state(false);

	// Lock / unlock
	let lockBusy = $state(false);
	let lockError = $state<string | null>(null);
	let pendingLock = $state<'lock' | 'unlock' | null>(null);

	async function confirmLockAction() {
		if (!pendingLock) return;
		lockBusy = true;
		lockError = null;
		try {
			if (pendingLock === 'lock') {
				await api.lockSession(session.spotify_id);
			} else {
				await api.unlockSession(session.spotify_id);
			}
			pendingLock = null;
			await invalidateAll();
		} catch (e) {
			lockError = e instanceof ApiError ? e.detail || e.message : String(e);
		} finally {
			lockBusy = false;
		}
	}

	function cancelLockAction() {
		if (lockBusy) return;
		pendingLock = null;
		lockError = null;
	}

	// ─── Upload version (locked mode) ──────────────────────────────────
	async function onUpload(event: Event) {
		const target = event.target as HTMLInputElement;
		const file = target.files?.[0];
		if (!file) return;
		target.value = '';

		uploading = true;
		uploadError = null;
		try {
			await api.uploadSessionVersion(session.spotify_id, file);
			await invalidateAll();
		} catch (e) {
			uploadError = e instanceof ApiError ? e.detail || e.message : String(e);
		} finally {
			uploading = false;
		}
	}

	function fitColor(score: number | null): string {
		if (score === null) return 'text-[var(--color-fg-muted)]';
		if (score >= 0.7) return 'text-[var(--color-ok)]';
		if (score >= 0.4) return 'text-[var(--color-warn)]';
		return 'text-[var(--color-err)]';
	}

	function fitLabel(score: number | null): string {
		if (score === null) return '—';
		return `${(score * 100).toFixed(0)}%`;
	}

	const versionsDesc = $derived([...session.versions].reverse());

	// ─── Draft mode : stats sur les tracks ─────────────────────────────
	const targetTracks = $derived<TrackMeta[]>(
		session.target_tracks ?? (session.target_track ? [session.target_track] : [])
	);
	const nUncertain = $derived(targetTracks.filter((t) => t.confidence_low).length);
	const nOverridden = $derived(targetTracks.filter((t) => t.is_overridden).length);
	const visibleTracks = $derived(
		filterUncertain && nUncertain > 0
			? targetTracks.filter((t) => t.confidence_low || t.is_overridden)
			: targetTracks
	);

	const lockConfirmMessage = $derived(
		pendingLock === 'lock'
			? 'Verrouiller la cible va figer le pattern et le plan A→Z. Tu ne pourras plus modifier les BPM/Key des tracks après. Continuer ?'
			: pendingLock === 'unlock'
				? 'Déverrouiller te permet de modifier les tracks à nouveau. Attention : si tu modifies la cible, le fit_score de tes versions déjà uploadées sera désynchronisé tant que tu n\'auras pas re-verrouillé.'
				: ''
	);
</script>

<div class="max-w-5xl mx-auto">
	<a
		href="/"
		class="text-sm text-[var(--color-fg-muted)] hover:text-[var(--color-fg)] mb-3 inline-block"
	>
		← Tableau de bord
	</a>

	<div class="flex items-end justify-between gap-4 flex-wrap mb-6">
		<div>
			<div class="flex items-center gap-x-2 gap-y-2 mb-2 flex-wrap">
				<Badge variant="accent">Session guidée</Badge>
				{#if !session.is_locked}
					<Badge variant="warn">brouillon</Badge>
				{:else}
					<Badge variant="ok">verrouillée</Badge>
				{/if}
			</div>
			<h1 class="text-3xl font-bold tracking-tight">{session.name}</h1>
			<p class="mt-1 text-sm text-[var(--color-fg-muted)]">
				Cible : <span class="text-[var(--color-fg)]">{session.target_name}</span>
				· créée {formatDateTime(session.created_at)}
			</p>
		</div>
		<div class="flex gap-2">
			{#if session.is_locked}
				<input
					bind:this={uploadInput}
					type="file"
					accept=".wav,.mp3,.flac,.ogg,.m4a,.aiff"
					onchange={onUpload}
					class="hidden"
				/>
				<Button
					variant="primary"
					loading={uploading}
					onclick={() => uploadInput?.click()}
					disabled={uploading}
				>
					+ Importer v{session.versions.length + 1}
				</Button>
				<Button variant="outline" onclick={() => (pendingLock = 'unlock')}>
					Déverrouiller
				</Button>
			{:else}
				<Button variant="primary" onclick={() => (pendingLock = 'lock')}>
					Verrouiller la session
				</Button>
			{/if}
		</div>
	</div>

	{#if uploadError}
		<Card class="mb-4 border-[var(--color-err)]/40">
			<p class="text-sm font-medium text-[var(--color-err)]">Erreur d'upload</p>
			<p class="text-xs text-[var(--color-fg-muted)] mt-1">{uploadError}</p>
		</Card>
	{/if}

	{#if !session.is_locked}
		<!-- ═══ DRAFT MODE ═══════════════════════════════════════════════ -->
		<Card class="mb-6 border-[var(--color-warn)]/40 bg-[var(--color-warn)]/5">
			<div class="flex gap-3 items-start">
				<span class="text-[var(--color-warn)] text-xl shrink-0">⚠</span>
				<div>
					<p class="text-sm font-medium mb-1">Session en brouillon</p>
					<p class="text-xs text-[var(--color-fg-muted)] leading-relaxed">
						Vérifie le <strong>BPM</strong> et la <strong>tonalité</strong> de chaque track ci-dessous.
						Beatfinder peut se tromper sur les groove half-time (Drake-style) ou les voix très traitées.
						Corrige ce qui te paraît faux, puis clique <strong>"Verrouiller la session"</strong>
						pour figer la cible et débloquer l'import de tes versions.
					</p>
				</div>
			</div>
		</Card>

		<!-- Stats résumé -->
		<div class="flex items-center justify-between flex-wrap gap-3 mb-3">
			<h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--color-fg-muted)]">
				{targetTracks.length === 1 ? 'Cible' : `Tracks de la cible (${targetTracks.length})`}
			</h2>
			<div class="flex items-center gap-3 text-xs">
				{#if nOverridden > 0}
					<span class="text-[var(--color-accent)] font-mono">
						{nOverridden} corrigée{nOverridden > 1 ? 's' : ''}
					</span>
				{/if}
				{#if nUncertain > 0}
					{#if targetTracks.length > 1}
						<label
							class="flex items-center gap-2 cursor-pointer"
							title="Filtrer pour ne voir que les tracks incertaines / corrigées"
						>
							<input
								type="checkbox"
								bind:checked={filterUncertain}
								class="h-4 w-4 rounded border-[var(--color-border)] bg-[var(--color-bg)] accent-[var(--color-accent)]"
							/>
							<span class="text-[var(--color-warn)]">
								⚠ {nUncertain} incertaine{nUncertain > 1 ? 's' : ''}
							</span>
						</label>
					{:else}
						<span class="text-[var(--color-warn)]">⚠ analyse incertaine</span>
					{/if}
				{/if}
			</div>
		</div>

		{#if targetTracks.length === 0}
			<Card class="border-dashed">
				<p class="text-center text-sm text-[var(--color-fg-muted)] py-4">
					Aucune track à afficher pour cette cible.
				</p>
			</Card>
		{:else if targetTracks.length === 1}
			{@const t = targetTracks[0]}
			<Card>
				<div class="flex items-center justify-between gap-4 flex-wrap">
					<div class="min-w-0">
						<div class="flex items-center gap-x-2 gap-y-2 mb-3 flex-wrap">
							<Badge variant="muted">Track</Badge>
							{#if t.is_overridden}
								<Badge variant="accent">corrigée manuellement</Badge>
							{:else if t.confidence_low}
								<Badge variant="warn">analyse incertaine</Badge>
							{/if}
						</div>
						<p class="font-semibold leading-tight truncate">{t.artist} — {t.title}</p>
					</div>
					<div class="flex items-center gap-4 shrink-0">
						<div class="text-right">
							<p class="text-xs text-[var(--color-fg-muted)] uppercase tracking-wider mb-0.5">
								BPM
							</p>
							<p class="font-mono text-lg">{t.bpm != null ? Math.round(t.bpm) : '—'}</p>
						</div>
						<div class="text-right">
							<p class="text-xs text-[var(--color-fg-muted)] uppercase tracking-wider mb-0.5">
								Key
							</p>
							<p class="font-mono text-lg">
								{t.key_note && t.key_mode ? `${t.key_note} ${t.key_mode}` : '—'}
							</p>
						</div>
						<button
							type="button"
							onclick={() => openCorrection(t)}
							class={cn(
								'inline-flex items-center justify-center w-9 h-9 rounded-full text-sm font-bold transition-colors',
								t.is_overridden
									? 'border border-[var(--color-accent)] bg-[var(--color-accent)]/15 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/25'
									: t.confidence_low
										? 'border border-[var(--color-warn)] text-[var(--color-warn)] hover:bg-[var(--color-warn)]/15'
										: 'border border-[var(--color-border)] text-[var(--color-fg-muted)] hover:text-[var(--color-fg)] hover:border-[var(--color-fg-muted)]'
							)}
							title="Corriger BPM / Tonalité"
							aria-label="Corriger"
						>
							{#if t.is_overridden}✓{:else if t.confidence_low}⚠{:else}✎{/if}
						</button>
					</div>
				</div>
				{#if t.confidence_reasons && t.confidence_reasons.length > 0}
					<div class="mt-3 pt-3 border-t border-[var(--color-border)] text-xs text-[var(--color-fg-muted)]">
						<p class="font-medium mb-1">Raisons du doute :</p>
						<ul class="space-y-0.5">
							{#each t.confidence_reasons as r (r)}
								<li>· {r}</li>
							{/each}
						</ul>
					</div>
				{/if}
			</Card>
		{:else}
			<!-- Tableau tracks (cible = playlist) -->
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
							<th class="px-3 py-2 text-center w-12"></th>
						</tr>
					</thead>
					<tbody>
						{#each visibleTracks as t (t.spotify_id)}
							<tr
								class={cn(
									'border-t border-[var(--color-border)]',
									t.confidence_low && !t.is_overridden
										? 'bg-[var(--color-warn)]/8 hover:bg-[var(--color-warn)]/12'
										: t.is_overridden
											? 'bg-[var(--color-accent)]/5 hover:bg-[var(--color-accent)]/10'
											: 'hover:bg-[var(--color-surface-2)]/50'
								)}
							>
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
								<td class="px-3 py-2 text-right font-mono">
									{t.key_note && t.key_mode ? `${t.key_note} ${t.key_mode}` : '—'}
								</td>
								<td class="px-3 py-2 text-right font-mono text-[var(--color-fg-muted)]">
									{formatDurationMs(t.duration_ms)}
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
											title={t.confidence_reasons.length > 0
												? `Raison(s) du doute :\n· ${t.confidence_reasons.join('\n· ')}\n\nClic pour corriger.`
												: 'Corriger BPM / Tonalité'}
											aria-label="Corriger"
										>
											{#if t.is_overridden}✓{:else if t.confidence_low}⚠{:else}✎{/if}
										</button>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{:else}
		<!-- ═══ LOCKED MODE ═════════════════════════════════════════════ -->

		<!-- Versions -->
		<section class="mb-8">
			<h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--color-fg-muted)] mb-3">
				Versions ({session.versions.length})
			</h2>
			{#if session.versions.length === 0}
				<Card class="border-dashed">
					<div class="text-center py-6 text-sm text-[var(--color-fg-muted)]">
						<p class="mb-1">Pas encore de version uploadée.</p>
						<p class="text-xs">
							Une fois ta v1 prête, importe-la pour obtenir ton premier fit_score vs la cible.
						</p>
					</div>
				</Card>
			{:else}
				<div class="space-y-2">
					{#each versionsDesc as v (v.id)}
						{@const isLast = v.version_number === session.versions.length}
						<div
							class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 flex items-center justify-between gap-3"
						>
							<div class="flex items-center gap-3 min-w-0">
								<Badge variant={isLast ? 'accent' : 'muted'}>{v.name}</Badge>
								<span class="text-xs text-[var(--color-fg-muted)] font-mono">
									{formatDateTime(v.created_at)}
								</span>
							</div>
							<div class="flex items-baseline gap-2 shrink-0">
								<span class="text-xs text-[var(--color-fg-muted)]">fit_score</span>
								<span class={`font-mono text-lg font-semibold ${fitColor(v.fit_score)}`}>
									{fitLabel(v.fit_score)}
								</span>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</section>

		<!-- Plan A→Z -->
		<section>
			<button
				class="w-full flex items-center justify-between text-sm font-semibold uppercase tracking-wider text-[var(--color-fg-muted)] mb-3 hover:text-[var(--color-fg)] transition-colors"
				onclick={() => (planOpen = !planOpen)}
			>
				<span>Plan A→Z</span>
				<span class="font-mono text-xs">{planOpen ? '−' : '+'}</span>
			</button>
			{#if planOpen}
				<Card>
					<BriefRenderer markdown={session.plan_md} />
				</Card>
			{/if}
		</section>
	{/if}
</div>

<TrackCorrectionModal
	track={correctionTrack}
	isOpen={correctionOpen}
	onClose={closeCorrection}
	onSaved={onCorrectionSaved}
/>

<ConfirmDialog
	isOpen={pendingLock !== null}
	title={pendingLock === 'lock'
		? 'Verrouiller la session ?'
		: 'Déverrouiller la session ?'}
	message={lockConfirmMessage + (lockError ? `\n\nErreur : ${lockError}` : '')}
	confirmLabel={pendingLock === 'lock' ? 'Verrouiller' : 'Déverrouiller'}
	variant={pendingLock === 'unlock' ? 'destructive' : 'primary'}
	onConfirm={confirmLockAction}
	onCancel={cancelLockAction}
	busy={lockBusy}
/>
