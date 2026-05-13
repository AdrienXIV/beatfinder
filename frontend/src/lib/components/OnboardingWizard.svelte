<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import Button from './Button.svelte';

	let { onClose }: { onClose: () => void } = $props();

	type Step = 1 | 2 | 3;
	const initialStep = (() => {
		const s = page.url.searchParams.get('step');
		if (s === '2') return 2 as Step;
		if (s === '3') return 3 as Step;
		return 1 as Step;
	})();
	let step = $state<Step>(initialStep);

	// Step 2 state
	let clientId = $state('');
	let clientSecret = $state('');
	let saving = $state(false);
	let saveError = $state<string | null>(null);
	let saveOk = $state(false);

	// Step 3 state
	let suggestedUrl = $state(
		'https://open.spotify.com/playlist/0AxKYXcQKwLN04Ok73L8y6'
	);

	function next() {
		if (step < 3) step = (step + 1) as Step;
	}
	function back() {
		if (step > 1) step = (step - 1) as Step;
	}

	function dismiss() {
		try {
			localStorage.setItem('beatfinder:onboarded', '1');
		} catch {
			// ignore (private browsing)
		}
		onClose();
	}

	async function saveSpotify() {
		if (!clientId.trim() || !clientSecret.trim()) {
			saveError = 'Client ID et Client Secret sont requis.';
			return;
		}
		saving = true;
		saveError = null;
		saveOk = false;
		try {
			await api.putSpotifySettings({
				client_id: clientId.trim(),
				client_secret: clientSecret.trim()
			});
			saveOk = true;
			setTimeout(() => next(), 800);
		} catch (e) {
			saveError = e instanceof ApiError ? e.detail || e.message : String(e);
		} finally {
			saving = false;
		}
	}

	function goAnalyze() {
		dismiss();
		const u = suggestedUrl.trim();
		if (u) {
			goto(`/analyze?url=${encodeURIComponent(u)}`);
		} else {
			goto('/analyze');
		}
	}
</script>

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
	role="dialog"
	aria-modal="true"
	aria-labelledby="onboarding-title"
>
	<div class="w-full max-w-2xl rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl">
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-[var(--color-border)] px-6 py-4">
			<div class="flex items-center gap-3">
				<span class="inline-block h-2.5 w-2.5 rounded-sm bg-[var(--color-accent)]"></span>
				<h2 id="onboarding-title" class="text-base font-semibold">
					Premier lancement
				</h2>
				<span class="text-xs text-[var(--color-fg-muted)] font-mono">
					Étape {step} / 3
				</span>
			</div>
			<button
				onclick={dismiss}
				class="text-xs text-[var(--color-fg-muted)] hover:text-[var(--color-fg)]"
			>
				Plus tard
			</button>
		</div>

		<!-- Body -->
		<div class="p-6 space-y-4">
			{#if step === 1}
				<h3 class="text-2xl font-bold">Bienvenue dans Beatfinder.</h3>
				<p class="text-sm text-[var(--color-fg-muted)] leading-relaxed">
					Outil d'analyse de patterns audio pour beatmakers. Compare ton catalogue (Spotify
					ou WAV/MP3 locaux) à des playlists de référence (rap FR, US, etc.) et sort un
					plan d'action mastering / mix / rythme / tonalité / structure actionnable.
				</p>
				<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4 space-y-2">
					<h4 class="text-sm font-semibold">3 étapes pour démarrer :</h4>
					<ol class="text-sm text-[var(--color-fg-muted)] space-y-1.5 list-decimal list-inside">
						<li>Créer une app Spotify Developer (gratuit, 2 min)</li>
						<li>Coller ton Client ID + Secret dans Beatfinder</li>
						<li>Analyser ta première playlist (≈25 min pour 150 tracks)</li>
					</ol>
				</div>
				<p class="text-xs text-[var(--color-fg-muted)]">
					Tu peux passer cette étape et configurer plus tard via <strong>Paramètres</strong>.
				</p>
			{:else if step === 2}
				<h3 class="text-xl font-bold">Configurer Spotify</h3>
				<p class="text-sm text-[var(--color-fg-muted)]">
					Beatfinder a besoin d'un accès Spotify pour récupérer les tracks et leurs métadonnées.
					C'est gratuit, ça prend 2 minutes.
				</p>

				<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4 space-y-2">
					<h4 class="text-sm font-semibold">1. Crée une app Spotify Developer</h4>
					<ol class="text-sm text-[var(--color-fg-muted)] space-y-1 list-decimal list-inside ml-1">
						<li>
							Va sur
							<a
								href="https://developer.spotify.com/dashboard"
								target="_blank"
								rel="noopener noreferrer"
								class="text-[var(--color-accent)] underline hover:no-underline"
							>
								developer.spotify.com/dashboard
							</a>
							(connecte-toi avec ton compte Spotify perso).
						</li>
						<li>Clique <strong>Create app</strong>. Nom : <em>Beatfinder</em>, description : libre.</li>
						<li>
							Dans <strong>Redirect URI</strong>, colle exactement :
							<code class="block mt-1 rounded bg-[var(--color-bg)] px-2 py-1 font-mono text-xs select-all">http://127.0.0.1:8888/callback</code>
						</li>
						<li>Coche <strong>Web API</strong>, accepte les conditions, valide.</li>
						<li>
							Sur la page de l'app → <strong>Settings</strong> → copie le <strong>Client ID</strong>
							et le <strong>Client Secret</strong> (clique <em>View client secret</em>) ci-dessous.
						</li>
					</ol>
				</div>

				<div class="space-y-3">
					<h4 class="text-sm font-semibold">2. Colle tes credentials</h4>
					<div>
						<label for="onb-cid" class="block text-xs uppercase tracking-wider text-[var(--color-fg-muted)] mb-1">
							Client ID
						</label>
						<input
							id="onb-cid"
							type="text"
							bind:value={clientId}
							placeholder="32 caractères hexa"
							autocomplete="off"
							class="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 font-mono text-sm"
						/>
					</div>
					<div>
						<label for="onb-csec" class="block text-xs uppercase tracking-wider text-[var(--color-fg-muted)] mb-1">
							Client Secret
						</label>
						<input
							id="onb-csec"
							type="password"
							bind:value={clientSecret}
							placeholder="32 caractères hexa"
							autocomplete="off"
							class="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 font-mono text-sm"
						/>
					</div>
				</div>

				{#if saveError}
					<div class="rounded-md border border-red-500/40 bg-red-500/10 p-2 text-sm text-red-400">
						{saveError}
					</div>
				{/if}
				{#if saveOk}
					<div class="rounded-md border border-green-500/40 bg-green-500/10 p-2 text-sm text-green-400">
						✓ Credentials enregistrés.
					</div>
				{/if}
			{:else}
				<h3 class="text-xl font-bold">Analyse ta première playlist</h3>
				<p class="text-sm text-[var(--color-fg-muted)]">
					Lance une première analyse pour découvrir le workflow. On suggère
					<strong>Top Rap FR Beatfinder</strong> (151 tracks, ~25 min) — playlist de
					référence rap FR que tu pourras ensuite utiliser comme cible de comparaison.
				</p>
				<div>
					<label for="onb-url" class="block text-xs uppercase tracking-wider text-[var(--color-fg-muted)] mb-1">
						URL Spotify playlist
					</label>
					<input
						id="onb-url"
						type="url"
						bind:value={suggestedUrl}
						class="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 font-mono text-xs"
					/>
				</div>
				<div class="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
					<p class="text-xs text-[var(--color-fg-muted)] leading-relaxed">
						<strong class="text-[var(--color-fg)]">Astuce</strong> : l'analyse tourne en
						background. Tu peux fermer la fenêtre, elle reprendra à la prochaine ouverture.
						Compte ~10s par track (téléchargement YouTube + analyse audio).
					</p>
				</div>
			{/if}
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-between border-t border-[var(--color-border)] px-6 py-3">
			<div class="flex items-center gap-1.5">
				{#each [1, 2, 3] as s}
					<span
						class="h-1.5 w-6 rounded-full transition-colors"
						class:bg-accent={s === step}
						class:bg-muted={s !== step}
					></span>
				{/each}
			</div>
			<div class="flex items-center gap-2">
				{#if step > 1}
					<Button variant="ghost" onclick={back}>← Retour</Button>
				{/if}
				{#if step === 1}
					<Button variant="primary" onclick={next}>Configurer Spotify →</Button>
				{:else if step === 2}
					<Button variant="ghost" onclick={() => { dismiss(); }}>
						Configurer plus tard
					</Button>
					<Button variant="primary" onclick={saveSpotify} disabled={saving}>
						{saving ? 'Enregistrement…' : 'Enregistrer & continuer →'}
					</Button>
				{:else}
					<Button variant="ghost" onclick={dismiss}>Aller au dashboard</Button>
					<Button variant="primary" onclick={goAnalyze}>Lancer l'analyse →</Button>
				{/if}
			</div>
		</div>
	</div>
</div>

<style>
	.bg-accent {
		background: var(--color-accent);
	}
	.bg-muted {
		background: var(--color-border);
	}
</style>
