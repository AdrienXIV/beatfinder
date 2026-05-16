<script lang="ts">
	import type { SessionVersion } from '$lib/api';
	import ScrollLock from './ScrollLock.svelte';
	import {
		KEY_FEATURES,
		type FeatureRow,
		getFeatureValue,
		getPatternStats,
		getStatus,
		formatValue,
		formatTarget,
		formatDelta,
		statusBgClass,
		statusColorClass
	} from '$lib/session-comparison';
	import { cn, formatDateTime } from '$lib/utils';

	let {
		version,
		targetPattern,
		isOpen,
		onClose
	}: {
		version: SessionVersion | null;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		targetPattern: Record<string, any>;
		isOpen: boolean;
		onClose: () => void;
	} = $props();

	let dialog: HTMLDialogElement | null = $state(null);

	$effect(() => {
		if (!dialog) return;
		if (isOpen && !dialog.open) {
			dialog.showModal();
		} else if (!isOpen && dialog.open) {
			dialog.close();
		}
	});

	function onBackdropClick(e: MouseEvent) {
		if (e.target === dialog) onClose();
	}

	// ─── Group features by section ──────────────────────────────────────
	type Section = { title: string; keys: string[] };
	const SECTIONS: Section[] = [
		{ title: 'Mastering', keys: ['lufs', 'true_peak'] },
		{ title: 'Dynamique', keys: ['crest', 'dr'] },
		{ title: 'Rythme', keys: ['bpm'] },
		{ title: 'Spectre', keys: ['centroid', 'sub', 'bass', 'low_mid', 'mid', 'high_mid', 'high'] },
		{ title: 'Structure', keys: ['drop'] }
	];

	function rowsForSection(section: Section): FeatureRow[] {
		return KEY_FEATURES.filter((r) => section.keys.includes(r.key));
	}

	// ─── Tonalité (catégoriel) ──────────────────────────────────────────
	type Tonality = { note: string | null; mode: string | null };
	const versionTonality = $derived.by<Tonality>(() => {
		if (!version) return { note: null, mode: null };
		const t = version.features_json?.tonality;
		return { note: t?.note ?? null, mode: t?.mode ?? null };
	});
	const targetTonality = $derived.by<Tonality>(() => {
		const note = targetPattern?.tonality?.note?.most_common ?? null;
		const mode = targetPattern?.tonality?.mode?.most_common ?? null;
		return { note, mode };
	});

	function fitColorClass(score: number | null): string {
		if (score === null) return 'text-[var(--color-fg-muted)]';
		if (score >= 0.7) return 'text-[var(--color-ok)]';
		if (score >= 0.4) return 'text-[var(--color-warn)]';
		return 'text-[var(--color-err)]';
	}
</script>

<ScrollLock open={isOpen} />

<dialog bind:this={dialog} onclose={onClose} onclick={onBackdropClick} class="detail-dialog">
	{#if version}
		{@const tv = versionTonality}
		{@const tt = targetTonality}
		<div class="detail-content" role="document">
			<header class="detail-header">
				<div class="min-w-0">
					<div class="text-[10px] uppercase tracking-wider text-[var(--color-fg-muted)]">
						Détail version
					</div>
					<h2 class="detail-title">{version.name}</h2>
					<div class="text-xs text-[var(--color-fg-muted)] mt-0.5 font-mono">
						{formatDateTime(version.created_at)}
					</div>
				</div>
				<div class="flex items-center gap-4">
					<div class="text-right">
						<div class="text-[10px] uppercase tracking-wider text-[var(--color-fg-muted)]">
							Fit score
						</div>
						<div class={cn('text-2xl font-mono font-bold', fitColorClass(version.fit_score))}>
							{version.fit_score !== null ? `${Math.round(version.fit_score * 100)}%` : '—'}
						</div>
					</div>
					<button type="button" class="detail-close" onclick={onClose} aria-label="Fermer">×</button>
				</div>
			</header>

			<div class="detail-body">
				<!-- Tonalité -->
				<section class="detail-section">
					<h3 class="detail-section-title">Tonalité</h3>
					<div class="grid grid-cols-3 gap-3 text-sm">
						<div class="rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2">
							<div class="text-[10px] uppercase tracking-wider text-[var(--color-fg-muted)]">
								Version
							</div>
							<div class="font-mono font-semibold text-base">
								{tv.note ?? '—'} {tv.mode ?? ''}
							</div>
						</div>
						<div class="rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2">
							<div class="text-[10px] uppercase tracking-wider text-[var(--color-fg-muted)]">
								Cible
							</div>
							<div class="font-mono font-semibold text-base">
								{tt.note ?? '—'} {tt.mode ?? ''}
							</div>
						</div>
						<div
							class={cn(
								'rounded-md border px-3 py-2',
								tv.note && tt.note && tv.note === tt.note && tv.mode === tt.mode
									? 'border-[var(--color-ok)]/40 bg-[var(--color-ok)]/10'
									: 'border-[var(--color-warn)]/40 bg-[var(--color-warn)]/10'
							)}
						>
							<div class="text-[10px] uppercase tracking-wider text-[var(--color-fg-muted)]">
								Match
							</div>
							<div class="font-mono font-semibold text-base">
								{tv.note && tt.note && tv.note === tt.note && tv.mode === tt.mode ? 'oui' : 'non'}
							</div>
						</div>
					</div>
				</section>

				<!-- Numerical sections -->
				{#each SECTIONS as section (section.title)}
					{@const rows = rowsForSection(section)}
					<section class="detail-section">
						<h3 class="detail-section-title">{section.title}</h3>
						<div class="overflow-hidden rounded-md border border-[var(--color-border)]">
							<table class="w-full text-sm">
								<thead class="bg-[var(--color-surface-2)] text-[10px] uppercase tracking-wider text-[var(--color-fg-muted)]">
									<tr>
										<th class="px-3 py-1.5 text-left">Feature</th>
										<th class="px-3 py-1.5 text-right w-28">Version</th>
										<th class="px-3 py-1.5 text-right w-24">Cible</th>
										<th class="px-3 py-1.5 text-right w-24">Delta</th>
										<th class="px-3 py-1.5 text-right w-36">Range cible</th>
									</tr>
								</thead>
								<tbody>
									{#each rows as row (row.key)}
										{@const stats = getPatternStats(targetPattern, row.path)}
										{@const value = getFeatureValue(version.features_json, row.path)}
										{@const status = getStatus(value, stats)}
										<tr class={cn('border-t border-[var(--color-border)]', statusBgClass(status))}>
											<td class="px-3 py-1.5 font-medium">{row.label}</td>
											<td class={cn('px-3 py-1.5 text-right font-mono font-semibold tabular-nums', statusColorClass(status))}>
												{formatValue(value, row)}<span class="text-xs opacity-75">{row.unit}</span>
											</td>
											<td class="px-3 py-1.5 text-right font-mono tabular-nums text-[var(--color-fg-muted)]">
												{formatTarget(stats, row)}<span class="text-xs">{row.unit}</span>
											</td>
											<td class={cn('px-3 py-1.5 text-right font-mono tabular-nums text-xs', statusColorClass(status))}>
												{formatDelta(value, stats, row)}
											</td>
											<td class="px-3 py-1.5 text-right font-mono text-[10px] text-[var(--color-fg-muted)] tabular-nums">
												{stats && stats.p25 !== undefined && stats.p75 !== undefined
													? `${formatValue(stats.p25, row)}–${formatValue(stats.p75, row)}`
													: '—'}
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</section>
				{/each}
			</div>
		</div>
	{/if}
</dialog>

<style>
	.detail-dialog {
		width: 75vw;
		max-width: 1080px;
		min-width: 320px;
		max-height: 88vh;
		padding: 0;
		overflow: hidden;
		border: 1px solid var(--color-border);
		border-radius: 12px;
		background: var(--color-surface);
		color: var(--color-fg);
		box-shadow: 0 20px 60px -10px rgba(0, 0, 0, 0.7);
	}
	@media (max-width: 768px) {
		.detail-dialog {
			width: 94vw;
		}
	}
	.detail-dialog::backdrop {
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(2px);
	}
	.detail-content {
		display: flex;
		flex-direction: column;
		max-height: 88vh;
	}
	.detail-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		padding: 1rem 1.5rem;
		border-bottom: 1px solid var(--color-border);
		background: var(--color-surface-2);
	}
	.detail-title {
		font-size: 1.4rem;
		font-weight: 700;
		margin: 0;
		letter-spacing: -0.01em;
	}
	.detail-close {
		flex-shrink: 0;
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		border: 1px solid var(--color-border);
		border-radius: 6px;
		background: transparent;
		color: var(--color-fg);
		font-size: 1.4rem;
		line-height: 1;
		font-weight: bold;
		cursor: pointer;
		transition: background 0.15s;
	}
	.detail-close:hover {
		background: var(--color-bg);
	}
	.detail-body {
		overflow-y: auto;
		padding: 1.25rem 1.5rem 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}
	.detail-section-title {
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-fg-muted);
		margin: 0 0 0.5rem;
	}
</style>
