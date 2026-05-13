<script lang="ts">
	import { cn } from '$lib/utils';

	let {
		current,
		total,
		label = null,
		class: klass = ''
	}: {
		current: number;
		total: number;
		label?: string | null;
		class?: string;
	} = $props();

	const pct = $derived(total > 0 ? Math.min(100, (current / total) * 100) : 0);
	const displayCurrent = $derived(Math.floor(current));
</script>

<div class={cn('space-y-1.5', klass)}>
	<div class="flex items-center justify-between text-xs">
		<span class="font-mono text-[var(--color-fg-muted)] truncate pr-3">
			{#if label}{label}{:else}—{/if}
		</span>
		<span class="font-mono tabular-nums whitespace-nowrap">
			{displayCurrent}/{total}
			{#if total > 0}
				<span class="text-[var(--color-fg-muted)] ml-1">({pct.toFixed(0)}%)</span>
			{/if}
		</span>
	</div>
	<div class="h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-surface-2)]">
		<div
			class="h-full bg-[var(--color-accent)] transition-[width] duration-300"
			style="width: {pct}%"
		></div>
	</div>
</div>
