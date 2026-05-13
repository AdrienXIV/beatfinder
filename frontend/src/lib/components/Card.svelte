<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils';

	let {
		class: klass = '',
		href = null,
		children
	}: {
		class?: string;
		href?: string | null;
		children: Snippet;
	} = $props();

	const base =
		'block rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5';
	const hover = 'transition-colors hover:bg-[var(--color-surface-2)] hover:border-[#3a3a44]';
</script>

{#if href}
	<a {href} class={cn(base, hover, klass)}>
		{@render children()}
	</a>
{:else}
	<div class={cn(base, klass)}>
		{@render children()}
	</div>
{/if}
