<script lang="ts">
	import { cn } from '$lib/utils';
	let { class: klass = '' }: { class?: string } = $props();
</script>

<div
	class={cn(
		'animate-pulse rounded bg-[var(--color-surface-2)]',
		klass
	)}
></div>
