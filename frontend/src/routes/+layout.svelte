<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import OnboardingWizard from '$lib/components/OnboardingWizard.svelte';

	let { children } = $props();

	const links = [
		{ href: '/', label: 'Playlists' },
		{ href: '/analyze', label: 'Analyser Spotify' },
		{ href: '/projects/new', label: 'Upload local' },
		{ href: '/compare', label: 'Comparer' },
		{ href: '/settings', label: 'Paramètres' }
	];

	function isActive(href: string): boolean {
		if (href === '/') return page.url.pathname === '/';
		return page.url.pathname.startsWith(href);
	}

	// Mode print : cache la nav globale + n'enveloppe pas le contenu dans le container max-w-6xl
	const isPrintRoute = $derived(
		page.url.pathname.endsWith('/print') || page.url.pathname.endsWith('/styles')
	);
	const isSettingsRoute = $derived(page.url.pathname.startsWith('/settings'));

	let spotifyConfigured = $state<boolean | null>(null);
	async function refreshStatus() {
		try {
			const s = await api.getStatus();
			spotifyConfigured = s.spotify_configured;
		} catch {
			spotifyConfigured = null;
		}
	}

	// Onboarding 1er lancement : afficher le wizard si jamais vu ET si pas encore
	// configuré Spotify (les utilisateurs récurrents ne doivent pas le revoir).
	// Force via `?onboarding=force` pour debug/re-test.
	let showOnboarding = $state(false);
	onMount(async () => {
		await refreshStatus();
		if (page.url.searchParams.get('onboarding') === 'force') {
			showOnboarding = true;
			return;
		}
		try {
			const onboarded = localStorage.getItem('beatfinder:onboarded');
			if (!onboarded && spotifyConfigured === false && !isPrintRoute) {
				showOnboarding = true;
			}
		} catch {
			// localStorage indispo (private browsing) → skip wizard
		}
	});
	function closeOnboarding() {
		showOnboarding = false;
		refreshStatus();
	}

	// Re-fetch après chaque navigation (au cas où on vient de configurer Spotify)
	$effect(() => {
		void page.url.pathname;
		refreshStatus();
	});
</script>

{#if showOnboarding}
	<OnboardingWizard onClose={closeOnboarding} />
{/if}

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Beatfinder</title>
</svelte:head>

{#if isPrintRoute}
	{@render children()}
{:else}
	<div class="min-h-screen flex flex-col">
		<header
			class="no-print sticky top-0 z-10 border-b border-[var(--color-border)] bg-[color:color-mix(in_oklab,var(--color-bg)_92%,transparent)] backdrop-blur"
		>
			<div class="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
				<a href="/" class="flex items-center gap-2.5">
					<span class="inline-block h-2.5 w-2.5 rounded-sm bg-[var(--color-accent)]"></span>
					<span class="font-semibold tracking-tight">Beatfinder</span>
					<span
						class="ml-1 rounded bg-[var(--color-surface-2)] px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wider text-[var(--color-fg-muted)]"
						>v1.6</span
					>
				</a>
				<nav class="flex items-center gap-1">
					{#each links as link}
						<a
							href={link.href}
							class={[
								'rounded-md px-3 py-1.5 text-sm transition-colors',
								isActive(link.href)
									? 'bg-[var(--color-surface-2)] text-[var(--color-fg)]'
									: 'text-[var(--color-fg-muted)] hover:text-[var(--color-fg)]'
							].join(' ')}
						>
							{link.label}
						</a>
					{/each}
				</nav>
			</div>
		</header>

		{#if spotifyConfigured === false && !isSettingsRoute}
			<div class="no-print border-b border-[var(--color-warn)]/40 bg-[var(--color-warn)]/10">
				<div class="mx-auto max-w-6xl px-6 py-2.5 flex items-center justify-between gap-4 text-sm">
					<div class="flex items-center gap-2 text-[var(--color-warn)]">
						<span aria-hidden="true">⚠</span>
						<span class="text-[var(--color-fg)]">
							<strong>Spotify n'est pas configuré.</strong> Saisis ton CLIENT_ID + CLIENT_SECRET pour pouvoir analyser des playlists.
						</span>
					</div>
					<a
						href="/settings"
						class="rounded-md border border-[var(--color-warn)] bg-[var(--color-warn)]/20 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-warn)] hover:bg-[var(--color-warn)]/30 whitespace-nowrap"
					>
						Configurer →
					</a>
				</div>
			</div>
		{/if}

		<main class="flex-1">
			<div class="mx-auto max-w-6xl px-6 py-8">
				{@render children()}
			</div>
		</main>
	</div>
{/if}
