<script lang="ts">
	import { onDestroy, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import Chart from 'chart.js/auto';
	import type { PageData } from './$types';
	import { api, ApiError, isLocalProject, type MultiCompare } from '$lib/api';
	import Button from '$lib/components/Button.svelte';

	let { data }: { data: PageData } = $props();
	const { playlists, presets, preselectIds } = $derived(data);

	const MIN = 2;
	const MAX = 5;
	const PALETTE = ['#f97316', '#3b82f6', '#10b981', '#a855f7', '#ef4444'];

	let selectedIds = $state<string[]>([...preselectIds]);
	let result = $state<MultiCompare | null>(null);
	let busy = $state(false);
	let error = $state<string | null>(null);

	// Source items unifiés (playlists + presets) pour la sélection.
	const items = $derived.by(() => {
		const spotify = playlists
			.filter((p) => !isLocalProject(p.spotify_id))
			.map((p) => ({ id: p.spotify_id, name: p.name, n_tracks: p.n_tracks, group: 'Spotify' as const }));
		const local = playlists
			.filter((p) => isLocalProject(p.spotify_id))
			.map((p) => ({ id: p.spotify_id, name: p.name, n_tracks: p.n_tracks, group: 'Projets locaux' as const }));
		const presetItems = presets.map((p) => ({
			id: p.target_id,
			name: p.name,
			n_tracks: p.n_tracks_source,
			group: 'Standards' as const
		}));
		return [...spotify, ...local, ...presetItems];
	});

	const grouped = $derived.by(() => {
		const out = new Map<string, typeof items>();
		for (const it of items) {
			if (!out.has(it.group)) out.set(it.group, []);
			out.get(it.group)!.push(it);
		}
		return Array.from(out.entries());
	});

	function toggle(id: string) {
		if (selectedIds.includes(id)) {
			selectedIds = selectedIds.filter((s) => s !== id);
		} else if (selectedIds.length < MAX) {
			selectedIds = [...selectedIds, id];
		}
	}

	const canCompare = $derived(
		selectedIds.length >= MIN && selectedIds.length <= MAX
	);

	async function runCompare() {
		if (!canCompare) return;
		busy = true;
		error = null;
		try {
			result = await api.getMultiCompare(selectedIds);
			// Attendre que Svelte mount le canvas (suite à {#if result}) avant de dessiner.
			await tick();
			renderRadar();
		} catch (e) {
			error = e instanceof ApiError ? e.detail || e.message : String(e);
			result = null;
		} finally {
			busy = false;
		}
	}

	// Si preselectIds non vide au mount, déclencher la comparaison directement.
	let autoRan = $state(false);
	$effect(() => {
		if (!autoRan && preselectIds.length >= MIN && preselectIds.length <= MAX) {
			autoRan = true;
			runCompare();
		}
	});

	function clearAll() {
		selectedIds = [];
		result = null;
		error = null;
	}

	function nameOf(id: string): string {
		return items.find((it) => it.id === id)?.name ?? id;
	}

	// Radar Chart.js — on évite bind:this car Chart.js manipule les properties
	// du canvas et casse le Proxy $state de Svelte 5 (erreur state_descriptors_fixed).
	let radarChart: Chart | null = null;
	const RADAR_CANVAS_ID = 'multi-compare-radar';
	const isHeadless = typeof navigator !== 'undefined' && /Headless/i.test(navigator.userAgent);

	function renderRadar() {
		const canvas = document.getElementById(RADAR_CANVAS_ID) as HTMLCanvasElement | null;
		if (!result || !canvas) return;
		// Snapshot du state Svelte 5 — Chart.js mute ses options en interne,
		// ce qui casse les Proxy de $state (erreur state_descriptors_fixed).
		const snap = $state.snapshot(result);
		radarChart?.destroy();
		radarChart = new Chart(canvas, {
			type: 'radar',
			data: {
				labels: snap.spectral_radar.labels,
				datasets: snap.sources.map((src, i) => ({
					label: src.name,
					data: snap.spectral_radar.values[i],
					backgroundColor: PALETTE[i % PALETTE.length] + '33',
					borderColor: PALETTE[i % PALETTE.length],
					borderWidth: 2,
					pointBackgroundColor: PALETTE[i % PALETTE.length],
					pointRadius: 3
				}))
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: isHeadless ? false : undefined,
				scales: {
					r: {
						beginAtZero: true,
						suggestedMax: 60,
						ticks: { color: 'var(--color-fg-muted)', backdropColor: 'transparent' },
						grid: { color: 'rgba(255,255,255,0.08)' },
						angleLines: { color: 'rgba(255,255,255,0.12)' },
						pointLabels: { color: 'var(--color-fg)', font: { size: 11 } }
					}
				},
				plugins: {
					legend: {
						position: 'top',
						labels: { color: 'var(--color-fg)', boxWidth: 14 }
					},
					tooltip: {
						callbacks: {
							label: (ctx) => `${ctx.dataset.label}: ${(ctx.parsed.r as number).toFixed(1)}%`
						}
					}
				}
			}
		});
	}

	// Render initial déclenché par runCompare (après tick). Pas d'effect ici
	// pour éviter le re-render Chart.js sur chaque dep change pas vraiment liée.

	onDestroy(() => {
		radarChart?.destroy();
	});

	function formatValue(v: number | null, unit: string): string {
		if (v === null) return '—';
		if (unit === '%' || unit === 'BPM' || unit === '') return v.toFixed(unit === '%' ? 0 : 1);
		if (unit === 'Hz') return v.toFixed(0);
		if (unit === 'sec') {
			const m = Math.floor(v / 60);
			const s = Math.round(v % 60);
			return `${m}:${s.toString().padStart(2, '0')}`;
		}
		return v.toFixed(1);
	}
</script>

<svelte:head>
	<title>Compare N-way — Beatfinder</title>
</svelte:head>

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-2xl font-bold">Comparaison triangulaire</h1>
			<p class="text-sm text-[var(--color-fg-muted)] mt-1">
				Compare {MIN} à {MAX} sources simultanément. Radar spectral + stats par axe.
			</p>
		</div>
		<Button variant="ghost" onclick={() => goto('/compare')}>
			← Compare 1v1
		</Button>
	</div>

	<!-- Sélecteur sources -->
	<section class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
		<div class="flex items-center justify-between mb-3">
			<h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--color-fg-muted)]">
				Sources sélectionnées ({selectedIds.length}/{MAX})
			</h2>
			{#if selectedIds.length > 0}
				<button
					class="text-xs text-[var(--color-fg-muted)] hover:text-[var(--color-fg)]"
					onclick={clearAll}
				>
					Tout retirer
				</button>
			{/if}
		</div>

		{#if selectedIds.length > 0}
			<div class="flex flex-wrap gap-2 mb-4">
				{#each selectedIds as id, i (id)}
					<span
						class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs"
						style:border-color={PALETTE[i % PALETTE.length]}
						style:color={PALETTE[i % PALETTE.length]}
					>
						<span class="font-medium">{nameOf(id)}</span>
						<button
							onclick={() => toggle(id)}
							class="opacity-70 hover:opacity-100"
							aria-label="Retirer"
						>
							×
						</button>
					</span>
				{/each}
			</div>
		{/if}

		<div class="space-y-4">
			{#each grouped as [group, list] (group)}
				<div>
					<h3 class="text-xs uppercase tracking-wider text-[var(--color-fg-muted)] mb-2">
						{group}
					</h3>
					<div class="grid grid-cols-1 md:grid-cols-2 gap-1.5">
						{#each list as it (it.id)}
							{@const isSelected = selectedIds.includes(it.id)}
							{@const isFull = !isSelected && selectedIds.length >= MAX}
							<button
								class="flex items-center gap-2 rounded-lg border px-3 py-2 text-left transition-colors"
								class:bg-surface-2={isSelected}
								disabled={isFull}
								onclick={() => toggle(it.id)}
								style:border-color={isSelected ? 'var(--color-accent)' : 'var(--color-border)'}
							>
								<span
									class="h-4 w-4 rounded border flex items-center justify-center text-xs shrink-0"
									style:border-color={isSelected ? 'var(--color-accent)' : 'var(--color-border)'}
									style:background={isSelected ? 'var(--color-accent)' : 'transparent'}
									style:color={isSelected ? 'var(--color-accent-fg)' : 'transparent'}
								>
									{isSelected ? '✓' : ''}
								</span>
								<span class="flex-1 truncate text-sm">{it.name}</span>
								<span class="text-xs font-mono text-[var(--color-fg-muted)] shrink-0">
									{it.n_tracks}
								</span>
							</button>
						{/each}
					</div>
				</div>
			{/each}
		</div>

		<div class="mt-4 flex items-center justify-between">
			<p class="text-xs text-[var(--color-fg-muted)]">
				{#if selectedIds.length < MIN}
					Sélectionne au moins {MIN} sources.
				{:else if selectedIds.length === MAX}
					Limite atteinte ({MAX} max).
				{:else}
					{MIN}-{MAX} sources autorisées.
				{/if}
			</p>
			<Button variant="primary" onclick={runCompare} disabled={!canCompare || busy}>
				{busy ? 'Calcul…' : 'Comparer'}
			</Button>
		</div>
	</section>

	{#if error}
		<div class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-400">
			{error}
		</div>
	{/if}

	{#if result}
		<!-- Radar spectral -->
		<section class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
			<h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--color-fg-muted)] mb-3">
				Profil spectral comparé
			</h2>
			<div style:height="420px">
				<canvas id={RADAR_CANVAS_ID}></canvas>
			</div>
		</section>

		<!-- Table stats -->
		<section class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] overflow-x-auto">
			<table class="w-full text-sm">
				<thead class="bg-[var(--color-surface-2)] text-xs uppercase tracking-wider text-[var(--color-fg-muted)]">
					<tr>
						<th class="px-3 py-2 text-left">Métrique</th>
						{#each result.sources as src, i (src.id)}
							<th class="px-3 py-2 text-right">
								<span style:color={PALETTE[i % PALETTE.length]}>{src.name}</span>
								<span class="block text-[10px] font-normal text-[var(--color-fg-muted)]">
									{src.n_tracks} tracks · {src.kind}
								</span>
							</th>
						{/each}
						<th class="px-3 py-2 text-left w-12">Unité</th>
					</tr>
				</thead>
				<tbody>
					{#each result.stats_table as row (row.key)}
						<tr class="border-t border-[var(--color-border)]">
							<td class="px-3 py-2 font-medium">{row.label}</td>
							{#each row.values as v, i (i)}
								<td class="px-3 py-2 text-right font-mono">{formatValue(v, row.unit)}</td>
							{/each}
							<td class="px-3 py-2 text-xs text-[var(--color-fg-muted)]">{row.unit}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</section>
	{/if}
</div>

<style>
	.bg-surface-2 {
		background: var(--color-surface-2);
	}
</style>
