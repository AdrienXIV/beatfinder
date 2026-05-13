<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils';

	let {
		label,
		value,
		hint = null,
		class: klass = '',
		valueClass = ''
	}: {
		label: string;
		value: string | number;
		hint?: string | Snippet | null;
		class?: string;
		valueClass?: string;
	} = $props();
</script>

<div class={cn('flex flex-col gap-0.5', klass)}>
	<span class="text-xs uppercase tracking-wider text-[var(--color-fg-muted)]">{label}</span>
	<span class={cn('font-mono text-lg font-medium tabular-nums', valueClass)}>{value}</span>
	{#if hint}
		{#if typeof hint === 'string'}
			<span class="text-xs text-[var(--color-fg-muted)]">{hint}</span>
		{:else}
			<span class="text-xs text-[var(--color-fg-muted)]">{@render hint()}</span>
		{/if}
	{/if}
</div>
