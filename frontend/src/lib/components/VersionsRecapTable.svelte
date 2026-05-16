<script lang="ts">
	import type { SessionVersion } from '$lib/api';
	import {
		KEY_FEATURES,
		getFeatureValue,
		getPatternStats,
		getStatus,
		formatValue,
		formatTarget,
		formatDelta,
		statusBgClass,
		statusColorClass
	} from '$lib/session-comparison';
	import { cn } from '$lib/utils';

	let {
		versions,
		targetPattern,
		onVersionClick
	}: {
		versions: SessionVersion[];
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		targetPattern: Record<string, any>;
		onVersionClick?: (v: SessionVersion) => void;
	} = $props();

	const lastVersionNumber = $derived(
		versions.length > 0 ? versions[versions.length - 1].version_number : -1
	);

	// Auto-scroll vers la droite (dernière version) au mount + à chaque ajout.
	// Sans ça, à >10 versions l'utilisateur ne voit que v1...v_k et doit scroller
	// manuellement pour atteindre la version qui l'intéresse (la dernière).
	let scrollWrapper: HTMLDivElement | null = $state(null);
	$effect(() => {
		void versions.length;
		if (!scrollWrapper) return;
		requestAnimationFrame(() => {
			if (scrollWrapper) {
				scrollWrapper.scrollLeft = scrollWrapper.scrollWidth;
			}
		});
	});
</script>

<div
	bind:this={scrollWrapper}
	class="overflow-x-auto rounded-lg border border-[var(--color-border)]"
>
	<table class="w-full text-sm border-collapse">
		<thead class="bg-[var(--color-surface-2)] text-xs uppercase tracking-wider text-[var(--color-fg-muted)]">
			<tr>
				<th
					class="px-3 py-2 text-left font-semibold sticky left-0 bg-[var(--color-surface-2)] z-20 w-[170px]"
				>
					Feature
				</th>
				<th
					class="px-3 py-2 text-right font-semibold w-28 sticky left-[170px] bg-[var(--color-surface-2)] z-20 border-l border-[var(--color-border)] shadow-[2px_0_3px_-1px_rgba(0,0,0,0.25)]"
				>
					Cible
				</th>
				{#each versions as v (v.id)}
					<th
						class={cn(
							'px-3 py-2 text-right font-semibold w-28 border-l border-[var(--color-border)]',
							onVersionClick ? 'cursor-pointer hover:bg-[var(--color-bg)] transition-colors' : ''
						)}
						onclick={() => onVersionClick?.(v)}
						title={onVersionClick ? `Détails ${v.name}` : undefined}
					>
						<span
							class={v.version_number === lastVersionNumber ? 'text-[var(--color-accent)]' : ''}
						>
							{v.name}
						</span>
						{#if onVersionClick}
							<span class="ml-1 text-[var(--color-fg-muted)] text-[10px]">▸</span>
						{/if}
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each KEY_FEATURES as row (row.key)}
				{@const stats = getPatternStats(targetPattern, row.path)}
				<tr class="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-2)]/30">
					<td
						class="px-3 py-2 sticky left-0 bg-[var(--color-surface)] z-10 w-[170px]"
					>
						<div class="font-medium text-[var(--color-fg)]">{row.label}</div>
						{#if stats && stats.p25 !== undefined && stats.p75 !== undefined}
							<div class="text-[10px] text-[var(--color-fg-muted)] font-mono mt-0.5">
								p25-p75 : {formatValue(stats.p25, row)}–{formatValue(stats.p75, row)}{row.unit}
							</div>
						{/if}
					</td>
					<td
						class="px-3 py-2 text-right font-mono tabular-nums text-[var(--color-fg)] w-28 sticky left-[170px] bg-[var(--color-surface)] z-10 border-l border-[var(--color-border)] shadow-[2px_0_3px_-1px_rgba(0,0,0,0.25)]"
					>
						<span class="font-semibold">{formatTarget(stats, row)}</span>
						<span class="text-xs text-[var(--color-fg-muted)] ml-0.5">{row.unit}</span>
					</td>
					{#each versions as v (v.id)}
						{@const value = getFeatureValue(v.features_json, row.path)}
						{@const status = getStatus(value, stats)}
						<td
							class={cn(
								'px-3 py-2 text-right font-mono tabular-nums border-l border-[var(--color-border)]',
								statusBgClass(status)
							)}
						>
							<div class={cn('font-semibold', statusColorClass(status))}>
								{formatValue(value, row)}<span class="text-xs opacity-75 ml-0.5">{row.unit}</span>
							</div>
							{#if value !== null && stats}
								<div class="text-[10px] text-[var(--color-fg-muted)] mt-0.5">
									{formatDelta(value, stats, row)}
								</div>
							{/if}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<div class="mt-2 flex items-center gap-4 text-[10px] text-[var(--color-fg-muted)] flex-wrap">
	<span class="flex items-center gap-1.5">
		<span class="w-2.5 h-2.5 rounded bg-[var(--color-ok)]/30 border border-[var(--color-ok)]/60"></span>
		dans p25-p75 (bonne fit)
	</span>
	<span class="flex items-center gap-1.5">
		<span class="w-2.5 h-2.5 rounded bg-[var(--color-warn)]/30 border border-[var(--color-warn)]/60"></span>
		dans [min, max]
	</span>
	<span class="flex items-center gap-1.5">
		<span class="w-2.5 h-2.5 rounded bg-[var(--color-err)]/30 border border-[var(--color-err)]/60"></span>
		hors range
	</span>
	{#if versions.length > 8}
		<span class="ml-auto text-[var(--color-fg-muted)] italic">
			Scroll horizontal → {versions.length} versions ; Feature + Cible figées à gauche
		</span>
	{/if}
</div>
