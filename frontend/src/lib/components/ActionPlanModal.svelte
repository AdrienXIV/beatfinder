<script lang="ts">
	import {
		api,
		ApiError,
		isLocalProject,
		type ActionItem,
		type ActionPlan,
		type ActionPriority,
		type ActionCategory,
		type ComparedTarget,
		type PlaylistSummary,
		type ThresholdPreset,
		type TrackMeta
	} from '$lib/api';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import SpectralRing from '$lib/components/charts/SpectralRing.svelte';
	import {
		SPECTRAL_BAND_KEYS,
		SPECTRAL_BAND_COLORS,
		SPECTRAL_BAND_LABELS
	} from '$lib/components/charts/spectral-colors';
	import PriorityDonut from '$lib/components/charts/PriorityDonut.svelte';
	import { cn, formatDateTime } from '$lib/utils';

	type View = 'select' | 'loading' | 'result';
	type TargetMode = 'playlist' | 'track' | 'preset';

	let {
		isOpen,
		currentId,
		currentName,
		playlists,
		comparedTargets: comparedTargetsProp,
		initialTargetId = null,
		onClose,
		onPlanSaved
	}: {
		isOpen: boolean;
		currentId: string;
		currentName: string;
		playlists: PlaylistSummary[];
		comparedTargets: ComparedTarget[];
		initialTargetId?: string | null;
		onClose: () => void;
		onPlanSaved?: () => void;
	} = $props();

	let targetMode = $state<TargetMode>('playlist');
	let targetTrackPlaylistId = $state<string | null>(null);
	let targetTracks = $state<TrackMeta[] | null>(null);
	let loadingTracks = $state(false);
	let presets = $state<ThresholdPreset[]>([]);

	// On préfère les compared targets fetchés à la volée pour `currentId`, et on
	// retombe sur ceux passés en prop (compatibilité page playlist détail).
	let fetchedCompared = $state<ComparedTarget[] | null>(null);
	const comparedTargets = $derived(fetchedCompared ?? comparedTargetsProp);

	async function loadTracksForPlaylist(playlistId: string) {
		loadingTracks = true;
		try {
			const detail = await api.getPlaylist(playlistId);
			targetTracks = detail.tracks.filter((t) => t.has_analysis);
			targetTrackPlaylistId = playlistId;
		} catch (e) {
			error = handleApiError(e);
		} finally {
			loadingTracks = false;
		}
	}

	function backToPlaylistList() {
		targetTracks = null;
		targetTrackPlaylistId = null;
	}

	const targetTrackPlaylistName = $derived(
		playlists.find((p) => p.spotify_id === targetTrackPlaylistId)?.name ?? ''
	);

	let dialogEl: HTMLDialogElement | null = $state(null);
	let view = $state<View>('select');
	let selectedTargetId = $state<string | null>(null);
	let plan = $state<ActionPlan | null>(null);
	let error = $state<string | null>(null);
	let checked = $state<Record<string, boolean>>({});
	let busy = $state(false);

	const comparedIds = $derived(new Set(comparedTargets.map((c) => c.target_id)));

	const groups = $derived.by(() => {
		const others = playlists.filter((p) => p.spotify_id !== currentId);
		return {
			spotify: others.filter((p) => !isLocalProject(p.spotify_id)),
			local: others.filter((p) => isLocalProject(p.spotify_id))
		};
	});

	$effect(() => {
		if (isOpen) {
			dialogEl?.showModal();
		} else {
			dialogEl?.close();
		}
	});

	$effect(() => {
		if (isOpen && currentId) {
			const cid = currentId;
			api
				.listComparedTargets(cid)
				.then((cts) => {
					// Vérifier qu'on n'a pas changé de source pendant le fetch
					if (cid === currentId) fetchedCompared = cts;
				})
				.catch(() => {
					fetchedCompared = [];
				});
		} else if (!isOpen) {
			fetchedCompared = null;
		}
	});

	// Fetch presets une seule fois (au premier open).
	$effect(() => {
		if (isOpen && presets.length === 0) {
			api.listThresholdPresets()
				.then((ps) => (presets = ps))
				.catch(() => {
					// Pas critique : le tab Standards sera juste vide
				});
		}
	});

	let autoTargetHandled = $state(false);
	$effect(() => {
		if (isOpen && initialTargetId && !autoTargetHandled && view === 'select' && !busy) {
			autoTargetHandled = true;
			selectedTargetId = initialTargetId;
			validateTarget();
		}
		if (!isOpen) {
			autoTargetHandled = false;
		}
	});

	function resetState() {
		view = 'select';
		selectedTargetId = null;
		plan = null;
		error = null;
		checked = {};
		targetMode = 'playlist';
		targetTrackPlaylistId = null;
		targetTracks = null;
	}

	function handleClose() {
		if (busy) return;
		resetState();
		onClose();
	}

	function lsKey(fromId: string, toId: string): string {
		return `beatfinder:actions:${fromId}__vs__${toId}`;
	}

	function loadChecked(fromId: string, toId: string): Record<string, boolean> {
		try {
			const raw = localStorage.getItem(lsKey(fromId, toId));
			if (!raw) return {};
			const arr = JSON.parse(raw);
			if (!Array.isArray(arr)) return {};
			const obj: Record<string, boolean> = {};
			for (const k of arr) {
				if (typeof k === 'string') obj[k] = true;
			}
			return obj;
		} catch {
			return {};
		}
	}

	function saveChecked(fromId: string, toId: string, state: Record<string, boolean>) {
		try {
			const arr = Object.keys(state).filter((k) => state[k]);
			localStorage.setItem(lsKey(fromId, toId), JSON.stringify(arr));
		} catch {
			// quota or disabled, ignore
		}
	}

	function toggleCheck(key: string) {
		const next = { ...checked, [key]: !checked[key] };
		if (!next[key]) delete next[key];
		checked = next;
		if (plan) saveChecked(plan.from_id, plan.to_id, next);
	}

	function handleApiError(e: unknown): string {
		if (e instanceof ApiError) return e.detail || e.message;
		if (e instanceof Error) return e.message;
		return String(e);
	}

	async function validateTarget() {
		if (!selectedTargetId) return;
		error = null;
		view = 'loading';
		busy = true;
		try {
			const result = await api.getActionPlan(currentId, selectedTargetId);
			plan = result;
			checked = loadChecked(result.from_id, result.to_id);
			view = 'result';
			onPlanSaved?.();
		} catch (e) {
			error = handleApiError(e);
			view = 'select';
		} finally {
			busy = false;
		}
	}

	function selectAndValidate(targetId: string) {
		selectedTargetId = targetId;
		validateTarget();
	}

	async function resetPlan() {
		if (!plan) return;
		if (
			!confirm(
				'Régénérer ce plan ? Le cache sera supprimé et les actions cochées effacées.'
			)
		) {
			return;
		}
		error = null;
		busy = true;
		const fromId = plan.from_id;
		const toId = plan.to_id;
		try {
			await api.deleteActionPlan(fromId, toId);
			localStorage.removeItem(lsKey(fromId, toId));
			const result = await api.getActionPlan(fromId, toId, true);
			plan = result;
			checked = {};
			onPlanSaved?.();
		} catch (e) {
			error = handleApiError(e);
		} finally {
			busy = false;
		}
	}

	function changeTarget() {
		view = 'select';
		plan = null;
		error = null;
		checked = {};
	}

	const grouped = $derived.by(() => {
		if (!plan) return [];
		const order: ActionCategory[] = ['mastering', 'mix', 'rhythm', 'tonality', 'structure'];
		const labels: Record<ActionCategory, string> = {
			mastering: 'Mastering',
			mix: 'Mix',
			rhythm: 'Rythme',
			tonality: 'Tonalité',
			structure: 'Structure'
		};
		const map: Record<string, ActionItem[]> = {};
		for (const it of plan.items) {
			if (!map[it.category]) map[it.category] = [];
			map[it.category].push(it);
		}
		return order
			.filter((cat) => map[cat]?.length)
			.map((cat) => ({ category: cat, label: labels[cat], items: map[cat] }));
	});

	const stats = $derived.by(() => {
		if (!plan) return { total: 0, high: 0, medium: 0, low: 0, done: 0, donePct: 0 };
		const counts: Record<ActionPriority, number> = { high: 0, medium: 0, low: 0 };
		let done = 0;
		for (const it of plan.items) {
			counts[it.priority] += 1;
			if (checked[it.key]) done += 1;
		}
		const total = plan.items.length;
		const donePct = total > 0 ? Math.round((done / total) * 100) : 0;
		return { total, ...counts, done, donePct };
	});

	// Légende fixe des 6 bandes spectrales (ordre extérieur → intérieur du ring)
	const SPECTRAL_BANDS = SPECTRAL_BAND_KEYS.map((key, i) => ({
		idx: (i + 1).toString().padStart(2, '0'),
		label: SPECTRAL_BAND_LABELS[key],
		color: SPECTRAL_BAND_COLORS[key],
		key
	}));

	const priorityBadge: Record<ActionPriority, 'err' | 'warn' | 'muted'> = {
		high: 'err',
		medium: 'warn',
		low: 'muted'
	};

	const priorityLabel: Record<ActionPriority, string> = {
		high: 'High',
		medium: 'Medium',
		low: 'Low'
	};

	function formatDelta(item: ActionItem): string {
		if (item.delta === null || item.current === null || item.target === null) return '';
		const sign = item.delta > 0 ? '+' : '';
		return `${item.current} → ${item.target} (${sign}${item.delta} ${item.unit})`;
	}

	function smallSample(n: number): boolean {
		return n > 0 && n < 8;
	}
</script>

<dialog
	bind:this={dialogEl}
	class="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-0 backdrop:bg-black/60 w-2/3 max-h-[90vh] overflow-hidden"
	onclose={() => onClose()}
>
	<div class="flex flex-col h-full max-h-[90vh]">
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-3 shrink-0">
			<div>
				<h2 class="text-lg font-semibold">Plan d'action</h2>
				<p class="text-xs text-[var(--color-fg-muted)] mt-0.5 truncate max-w-md">
					{currentName}
					{#if view === 'result' && plan}
						<span class="text-[var(--color-fg-muted)]">→</span>
						<span class="text-[var(--color-fg)]">{plan.to_name}</span>
					{/if}
				</p>
			</div>
			<button
				class="rounded-md p-1.5 text-[var(--color-fg-muted)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-fg)]"
				onclick={handleClose}
				disabled={busy}
				aria-label="Fermer"
			>
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<line x1="18" y1="6" x2="6" y2="18"></line>
					<line x1="6" y1="6" x2="18" y2="18"></line>
				</svg>
			</button>
		</div>

		<!-- Body -->
		<div class="p-5 flex-1 overflow-y-auto min-h-0">
			{#if error}
				<div class="mb-4 rounded-md border border-[var(--color-err)]/40 bg-[var(--color-err)]/10 p-3 text-sm text-[var(--color-err)]">
					{error}
				</div>
			{/if}

			{#if view === 'select'}
				<p class="text-sm text-[var(--color-fg-muted)] mb-4">
					Choisis une <strong class="text-[var(--color-fg)]">cible</strong> à atteindre — playlist
					entière ou track individuelle. Beatfinder calcule les écarts mastering / mix / rythme /
					tonalité / structure et te sort une checklist actionnable.
				</p>

				<!-- Tabs : Playlist | Track | Standards -->
				<div class="mb-4 flex gap-1 border-b border-[var(--color-border)]">
					<button
						class={cn(
							'px-3 py-1.5 text-sm font-medium border-b-2 -mb-px transition-colors',
							targetMode === 'playlist'
								? 'border-[var(--color-accent)] text-[var(--color-fg)]'
								: 'border-transparent text-[var(--color-fg-muted)] hover:text-[var(--color-fg)]'
						)}
						onclick={() => {
							targetMode = 'playlist';
							targetTracks = null;
							targetTrackPlaylistId = null;
						}}
					>
						Playlist
					</button>
					<button
						class={cn(
							'px-3 py-1.5 text-sm font-medium border-b-2 -mb-px transition-colors',
							targetMode === 'track'
								? 'border-[var(--color-accent)] text-[var(--color-fg)]'
								: 'border-transparent text-[var(--color-fg-muted)] hover:text-[var(--color-fg)]'
						)}
						onclick={() => (targetMode = 'track')}
					>
						Track
					</button>
					<button
						class={cn(
							'px-3 py-1.5 text-sm font-medium border-b-2 -mb-px transition-colors',
							targetMode === 'preset'
								? 'border-[var(--color-accent)] text-[var(--color-fg)]'
								: 'border-transparent text-[var(--color-fg-muted)] hover:text-[var(--color-fg)]'
						)}
						onclick={() => (targetMode = 'preset')}
					>
						Standards
					</button>
				</div>

				{#if targetMode === 'playlist'}
					{#if groups.spotify.length === 0 && groups.local.length === 0}
						<div class="text-center text-sm text-[var(--color-fg-muted)] py-8">
							Pas d'autre playlist disponible. Analyse au moins une playlist Spotify ou crée
							un project local pour pouvoir comparer.
						</div>
					{/if}

					{#if groups.spotify.length > 0}
						<div class="mb-5">
							<h3 class="text-xs uppercase tracking-wider text-[var(--color-fg-muted)] mb-2">
								Spotify
							</h3>
							<div class="space-y-1">
								{#each groups.spotify as p (p.spotify_id)}
									{@const isCompared = comparedIds.has(p.spotify_id)}
									<button
										class="w-full flex items-center gap-3 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] hover:border-[var(--color-accent)]/50 px-3 py-2 text-left transition-colors"
										onclick={() => selectAndValidate(p.spotify_id)}
									>
										{#if isCompared}
											<span
												class="h-2 w-2 rounded-full bg-[var(--color-ok)] shrink-0"
												title="Plan déjà généré en cache"
											></span>
										{:else}
											<span class="h-2 w-2 rounded-full bg-transparent border border-[var(--color-border)] shrink-0"></span>
										{/if}
										<span class="flex-1 truncate text-sm font-medium">{p.name}</span>
										<span class="text-xs text-[var(--color-fg-muted)] font-mono shrink-0">
											{p.n_tracks} tracks
										</span>
									</button>
								{/each}
							</div>
						</div>
					{/if}

					{#if groups.local.length > 0}
						<div>
							<h3 class="text-xs uppercase tracking-wider text-[var(--color-fg-muted)] mb-2">
								Projets locaux
							</h3>
							<div class="space-y-1">
								{#each groups.local as p (p.spotify_id)}
									{@const isCompared = comparedIds.has(p.spotify_id)}
									<button
										class="w-full flex items-center gap-3 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] hover:border-[var(--color-accent)]/50 px-3 py-2 text-left transition-colors"
										onclick={() => selectAndValidate(p.spotify_id)}
									>
										{#if isCompared}
											<span
												class="h-2 w-2 rounded-full bg-[var(--color-ok)] shrink-0"
												title="Plan déjà généré en cache"
											></span>
										{:else}
											<span class="h-2 w-2 rounded-full bg-transparent border border-[var(--color-border)] shrink-0"></span>
										{/if}
										<span class="flex-1 truncate text-sm font-medium">{p.name}</span>
										<span class="text-xs text-[var(--color-fg-muted)] font-mono shrink-0">
											{p.n_tracks} tracks
										</span>
									</button>
								{/each}
							</div>
						</div>
					{/if}
				{:else if targetMode === 'track'}
					{#if targetTrackPlaylistId === null}
						<p class="text-xs text-[var(--color-fg-muted)] mb-2">
							1. Choisis d'abord la playlist où piocher la track.
						</p>
						<div class="space-y-1">
							{#each playlists.filter((p) => p.spotify_id !== currentId) as p (p.spotify_id)}
								<button
									class="w-full flex items-center gap-3 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] hover:border-[var(--color-accent)]/50 px-3 py-2 text-left transition-colors"
									onclick={() => loadTracksForPlaylist(p.spotify_id)}
								>
									<span class="text-xs text-[var(--color-fg-muted)] font-mono shrink-0">
										{isLocalProject(p.spotify_id) ? 'L' : 'S'}
									</span>
									<span class="flex-1 truncate text-sm font-medium">{p.name}</span>
									<span class="text-xs text-[var(--color-fg-muted)] font-mono shrink-0">
										{p.n_tracks} tracks ›
									</span>
								</button>
							{/each}
						</div>
					{:else}
						<div class="mb-3 flex items-center justify-between">
							<button
								class="text-xs text-[var(--color-fg-muted)] hover:text-[var(--color-fg)]"
								onclick={backToPlaylistList}
							>
								← {targetTrackPlaylistName}
							</button>
							<span class="text-xs text-[var(--color-fg-muted)]">
								{targetTracks?.length ?? 0} tracks analysées
							</span>
						</div>
						{#if loadingTracks}
							<div class="flex justify-center py-8">
								<span class="h-5 w-5 animate-spin rounded-full border-2 border-[var(--color-accent)] border-r-transparent"></span>
							</div>
						{:else if targetTracks && targetTracks.length > 0}
							<div class="space-y-1">
								{#each targetTracks as t (t.spotify_id)}
									{#if t.spotify_id !== currentId}
										<button
											class="w-full flex items-center gap-3 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] hover:border-[var(--color-accent)]/50 px-3 py-2 text-left transition-colors"
											onclick={() => selectAndValidate(t.spotify_id)}
										>
											<span class="text-xs text-[var(--color-fg-muted)] font-mono shrink-0 w-6 text-right">
												{t.position + 1}
											</span>
											<span class="flex-1 min-w-0">
												<span class="block text-sm font-medium truncate">{t.title}</span>
												{#if t.artist}
													<span class="block text-xs text-[var(--color-fg-muted)] truncate">
														{t.artist}
													</span>
												{/if}
											</span>
										</button>
									{/if}
								{/each}
							</div>
						{:else}
							<p class="text-center text-sm text-[var(--color-fg-muted)] py-8">
								Aucune track analysée dans cette playlist.
							</p>
						{/if}
					{/if}
				{:else if targetMode === 'preset'}
					<p class="text-xs text-[var(--color-fg-muted)] mb-3">
						Compare directement à un standard mainstream — pas besoin d'analyser une
						playlist de référence. Les médianes viennent de playlists réelles déjà
						analysées par Beatfinder.
					</p>
					{#if presets.length === 0}
						<p class="text-center text-sm text-[var(--color-fg-muted)] py-8">
							Aucun preset disponible.
						</p>
					{:else}
						<div class="space-y-1">
							{#each presets as preset (preset.key)}
								{@const isCompared = comparedIds.has(preset.target_id)}
								<button
									class="w-full flex items-start gap-3 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] hover:border-[var(--color-accent)]/50 px-3 py-2 text-left transition-colors"
									onclick={() => selectAndValidate(preset.target_id)}
								>
									{#if isCompared}
										<span
											class="mt-1.5 h-2 w-2 rounded-full bg-[var(--color-ok)] shrink-0"
											title="Plan déjà généré en cache"
										></span>
									{:else}
										<span class="mt-1.5 h-2 w-2 rounded-full bg-transparent border border-[var(--color-border)] shrink-0"></span>
									{/if}
									<span class="flex-1 min-w-0">
										<span class="flex items-baseline justify-between gap-2">
											<span class="text-sm font-medium">{preset.name}</span>
											<span class="text-xs font-mono text-[var(--color-fg-muted)] shrink-0">
												{preset.n_tracks_source} tracks
											</span>
										</span>
										<span class="block text-xs text-[var(--color-fg-muted)] mt-0.5">
											{preset.description}
										</span>
									</span>
								</button>
							{/each}
						</div>
					{/if}
				{/if}
			{:else if view === 'loading'}
				<div class="flex flex-col items-center justify-center py-16 gap-3">
					<span
						class="h-6 w-6 animate-spin rounded-full border-2 border-[var(--color-accent)] border-r-transparent"
						aria-hidden="true"
					></span>
					<p class="text-sm text-[var(--color-fg-muted)]">Calcul des écarts en cours…</p>
				</div>
			{:else if view === 'result' && plan}
				<!-- Stats header -->
				<div class="mb-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)]/40 p-3">
					<div class="flex flex-wrap items-center justify-between gap-3 text-xs">
						<div class="flex items-center gap-3">
							<span class="text-[var(--color-fg-muted)]">
								{plan.from_n_tracks} tracks ({currentName})
								<span class="mx-1">vs</span>
								{plan.to_n_tracks} tracks ({plan.to_name})
							</span>
							{#if smallSample(plan.from_n_tracks) || smallSample(plan.to_n_tracks)}
								<Badge variant="warn">échantillon faible</Badge>
							{/if}
						</div>
						<div class="flex items-center gap-3 text-[var(--color-fg-muted)]">
							<span>
								<span class="text-[var(--color-fg)] font-mono">{stats.done}</span>/{stats.total} fait
							</span>
							{#if plan.cached}
								<Badge variant="muted">cached</Badge>
							{/if}
						</div>
					</div>
					<div class="mt-2 flex gap-2 text-xs">
						<Badge variant="err">{stats.high} high</Badge>
						<Badge variant="warn">{stats.medium} medium</Badge>
						<Badge variant="muted">{stats.low} low</Badge>
					</div>
				</div>

				<p class="mb-5 text-xs text-[var(--color-fg-muted)] italic">
					Coche une action quand tu l'as appliquée à ton projet pour suivre ton avancement.
					L'état est mémorisé par paire (projet → cible).
				</p>

				{#if plan.from_bands && Object.keys(plan.from_bands).length > 0}
					<div class="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
						<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)]/30 p-3">
							<h4 class="text-xs font-semibold uppercase tracking-wider text-[var(--color-fg-muted)] mb-3">
								Profil spectral
								<span class="font-normal normal-case tracking-normal text-[var(--color-fg-muted)]">
									— anneaux ordonnés du plus grave au plus aigu, extérieur → intérieur
								</span>
							</h4>
							<div class="grid grid-cols-2 gap-3">
								<div class="flex flex-col items-center gap-2">
									<div class="text-xs text-center text-[var(--color-fg-muted)] truncate w-full" title={currentName}>
										{currentName}
									</div>
									<SpectralRing
										bands={plan.from_bands}
										size={150}
										showLegend={false}
									/>
								</div>
								<div class="flex flex-col items-center gap-2">
									<div class="text-xs text-center text-[var(--color-fg-muted)] truncate w-full" title={plan.to_name}>
										{plan.to_name}
									</div>
									<SpectralRing
										bands={plan.to_bands}
										size={150}
										showLegend={false}
									/>
								</div>
							</div>
							<!-- Légende partagée des 6 anneaux (ordre extérieur → intérieur).
							     Couleur du swatch = couleur de l'anneau correspondant. -->
							<ol class="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] list-none p-0">
								{#each SPECTRAL_BANDS as b (b.key)}
									{@const from = (plan.from_bands[b.key] ?? 0) * 100}
									{@const to = (plan.to_bands?.[b.key] ?? 0) * 100}
									<li class="flex items-baseline gap-2">
										<span
											class="inline-block h-2.5 w-2.5 rounded-sm shrink-0 self-center"
											style:background={b.color}
										></span>
										<span class="flex-1 truncate">{b.label}</span>
										<span class="font-mono text-[var(--color-fg)] tabular-nums">
											{from.toFixed(0)}%
										</span>
										<span class="font-mono text-[var(--color-fg-muted)] tabular-nums">
											→ {to.toFixed(0)}%
										</span>
									</li>
								{/each}
							</ol>
						</div>
						<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)]/30 p-3">
							<h4 class="flex items-baseline justify-between gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-fg-muted)] mb-2">
								<span>Avancement par priorité</span>
								<span class="font-mono normal-case tracking-normal text-[var(--color-fg)]">
									{stats.done}/{stats.total} faits
									<span class="text-[var(--color-fg-muted)]">({stats.donePct}%)</span>
								</span>
							</h4>
							<PriorityDonut
								high={stats.high}
								medium={stats.medium}
								low={stats.low}
								height={220}
							/>
						</div>
					</div>
				{/if}

				{#if plan.items.length === 0}
					<div class="text-center text-sm text-[var(--color-fg-muted)] py-8">
						Aucun écart significatif détecté. Tes médianes sont déjà alignées sur la cible.
					</div>
				{/if}

				{#each grouped as g (g.category)}
					<div class="mb-5">
						<h3 class="text-sm font-semibold mb-2 flex items-center gap-2">
							<span>{g.label}</span>
							<span class="text-xs font-normal text-[var(--color-fg-muted)]">
								{g.items.length}
							</span>
						</h3>
						<div class="space-y-2">
							{#each g.items as item (item.key)}
								{@const isChecked = !!checked[item.key]}
								<label
									class={cn(
										'flex gap-3 rounded-lg border p-3 cursor-pointer transition-colors',
										isChecked
											? 'border-[var(--color-ok)]/40 bg-[var(--color-ok)]/5'
											: 'border-[var(--color-border)] hover:bg-[var(--color-surface-2)]/40'
									)}
								>
									<input
										type="checkbox"
										class="mt-1 h-4 w-4 shrink-0 cursor-pointer accent-[var(--color-accent)]"
										checked={isChecked}
										onchange={() => toggleCheck(item.key)}
									/>
									<div class="flex-1 min-w-0">
										<div class="flex flex-wrap items-center gap-2 mb-1">
											<Badge variant={priorityBadge[item.priority]}>
												{priorityLabel[item.priority]}
											</Badge>
											<span
												class={cn(
													'text-sm font-medium',
													isChecked && 'line-through text-[var(--color-fg-muted)]'
												)}
											>
												{item.metric}
											</span>
											{#if item.delta !== null}
												<span class="text-xs font-mono text-[var(--color-fg-muted)]">
													{formatDelta(item)}
												</span>
											{/if}
										</div>
										<p
											class={cn(
												'text-sm leading-snug',
												isChecked
													? 'text-[var(--color-fg-muted)]'
													: 'text-[var(--color-fg)]'
											)}
										>
											{item.action}
										</p>
										<p class="text-xs text-[var(--color-fg-muted)] mt-1 italic">
											{item.rationale}
										</p>
									</div>
								</label>
							{/each}
						</div>
					</div>
				{/each}

				<p class="mt-6 text-xs text-[var(--color-fg-muted)] text-center">
					Plan généré le {formatDateTime(plan.generated_at)} · pattern #{plan.from_pattern_id} vs
					pattern #{plan.to_pattern_id}
				</p>
			{/if}
		</div>

		<!-- Footer -->
		<div class="border-t border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-3 flex items-center justify-between gap-2 shrink-0">
			{#if view === 'select'}
				<span class="text-xs text-[var(--color-fg-muted)]">
					<span class="inline-block h-2 w-2 rounded-full bg-[var(--color-ok)] align-middle mr-1"></span>
					= plan déjà généré
				</span>
				<Button variant="ghost" size="sm" onclick={handleClose}>Annuler</Button>
			{:else if view === 'result'}
				<Button variant="ghost" size="sm" onclick={changeTarget} disabled={busy}>
					← Changer de cible
				</Button>
				<div class="flex gap-2 items-center">
					{#if plan}
						<a
							href={api.masterChainMdUrl(plan.from_id, plan.to_id)}
							download
							class="text-xs text-[var(--color-fg-muted)] hover:text-[var(--color-fg)] underline underline-offset-2"
							title="Guide de chaîne master universel (Live/FL/Logic/Reaper)"
						>
							Export .md
						</a>
						<a
							href={api.masterChainAdgUrl(plan.from_id, plan.to_id)}
							download
							class="text-xs text-[var(--color-fg-muted)] hover:text-[var(--color-fg)] underline underline-offset-2"
							title="Rack Ableton (expérimental, à remplir manuellement)"
						>
							Export .adg
						</a>
						<span class="text-[var(--color-border)] text-xs">·</span>
					{/if}
					<Button variant="outline" size="sm" onclick={resetPlan} disabled={busy} loading={busy}>
						Régénérer
					</Button>
					<Button variant="primary" size="sm" onclick={handleClose}>Fermer</Button>
				</div>
			{:else}
				<span class="text-xs text-[var(--color-fg-muted)]">Calcul en cours…</span>
				<div></div>
			{/if}
		</div>
	</div>
</dialog>
