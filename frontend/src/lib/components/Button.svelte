<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils';

	type Variant = 'primary' | 'ghost' | 'outline' | 'destructive';
	type Size = 'sm' | 'md' | 'lg';

	let {
		variant = 'primary',
		size = 'md',
		type = 'button',
		disabled = false,
		loading = false,
		href = null,
		onclick = undefined,
		class: klass = '',
		children
	}: {
		variant?: Variant;
		size?: Size;
		type?: 'button' | 'submit' | 'reset';
		disabled?: boolean;
		loading?: boolean;
		href?: string | null;
		onclick?: ((e: MouseEvent) => void) | undefined;
		class?: string;
		children: Snippet;
	} = $props();

	const base =
		'inline-flex items-center justify-center gap-2 font-medium rounded-md transition-colors disabled:opacity-50 disabled:pointer-events-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]';

	const sizes: Record<Size, string> = {
		sm: 'h-8 px-3 text-sm',
		md: 'h-10 px-4 text-sm',
		lg: 'h-12 px-6 text-base'
	};

	const variants: Record<Variant, string> = {
		primary:
			'bg-[var(--color-accent)] text-[var(--color-accent-fg)] hover:brightness-110',
		ghost: 'text-[var(--color-fg)] hover:bg-[var(--color-surface-2)]',
		outline:
			'border border-[var(--color-border)] text-[var(--color-fg)] hover:bg-[var(--color-surface-2)]',
		destructive:
			'border border-[var(--color-err)]/50 bg-[var(--color-err)]/10 text-[var(--color-err)] hover:bg-[var(--color-err)] hover:text-white hover:border-[var(--color-err)]'
	};
</script>

{#if href}
	<a {href} class={cn(base, sizes[size], variants[variant], klass)}>
		{@render children()}
	</a>
{:else}
	<button
		{type}
		disabled={disabled || loading}
		{onclick}
		class={cn(base, sizes[size], variants[variant], klass)}
	>
		{#if loading}
			<span
				class="h-3 w-3 animate-spin rounded-full border-2 border-current border-r-transparent"
				aria-hidden="true"
			></span>
		{/if}
		{@render children()}
	</button>
{/if}
