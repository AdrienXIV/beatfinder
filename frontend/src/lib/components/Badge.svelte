<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils';

	type Variant = 'default' | 'accent' | 'warn' | 'ok' | 'err' | 'muted';

	let {
		variant = 'default',
		class: klass = '',
		children
	}: {
		variant?: Variant;
		class?: string;
		children: Snippet;
	} = $props();

	const variants: Record<Variant, string> = {
		default: 'bg-[var(--color-surface-2)] text-[var(--color-fg)]',
		accent: 'bg-[var(--color-accent)] text-[var(--color-accent-fg)]',
		warn: 'bg-[var(--color-warn)] text-black',
		ok: 'bg-[var(--color-ok)]/15 text-[var(--color-ok)] border border-[var(--color-ok)]/30',
		err: 'bg-[var(--color-err)]/15 text-[var(--color-err)] border border-[var(--color-err)]/30',
		muted:
			'bg-transparent text-[var(--color-fg-muted)] border border-[var(--color-border)]'
	};
</script>

<span
	class={cn(
		'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium',
		variants[variant],
		klass
	)}
>
	{@render children()}
</span>
