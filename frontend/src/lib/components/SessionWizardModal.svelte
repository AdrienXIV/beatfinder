<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, ApiError, type Job } from '$lib/api';
	import Badge from './Badge.svelte';
	import Button from './Button.svelte';
	import ProgressBar from './ProgressBar.svelte';
	import ScrollLock from './ScrollLock.svelte';

	let {
		isOpen,
		onClose
	}: {
		isOpen: boolean;
		onClose: () => void;
	} = $props();

	// Étape 1 : source URL
	// Étape 2 : preview / confirmation
	// Étape 3 : analyse en cours (uniquement si source pas encore en DB)
	type Step = 1 | 2 | 3;

	let dialog: HTMLDialogElement | null = $state(null);
	let step = $state<Step>(1);
	let sourceUrl = $state('');
	let creating = $state(false);
	let error = $state<string | null>(null);

	// État de l'étape 3 (analyse intermédiaire)
	let analyzeJob = $state<Job | null>(null);
	let analyzeStream: EventSource | null = null;

	function isTrackUrl(u: string): boolean {
		return /(?:spotify:track:|open\.spotify\.com\/track\/)/i.test(u.trim());
	}

	function closeStream() {
		if (analyzeStream) {
			analyzeStream.close();
			analyzeStream = null;
		}
	}

	function resetState() {
		step = 1;
		sourceUrl = '';
		error = null;
		creating = false;
		analyzeJob = null;
		closeStream();
	}

	$effect(() => {
		if (!dialog) return;
		if (isOpen && !dialog.open) {
			dialog.showModal();
			resetState();
		} else if (!isOpen && dialog.open) {
			dialog.close();
			closeStream();
		}
	});

	function isMissingSourceError(e: unknown): boolean {
		if (!(e instanceof ApiError)) return false;
		const msg = e.detail || e.message;
		return (
			(e.status === 404 || e.status === 409) &&
			/analyse-la|analysée|introuvable/i.test(msg)
		);
	}

	/** Stream un job d'analyse via SSE, résout quand `done`, rejette si error. */
	function waitJobDone(jobId: string): Promise<void> {
		return new Promise((resolve, reject) => {
			analyzeStream = new EventSource(api.streamJobUrl(jobId));
			analyzeStream.addEventListener('update', (e) => {
				analyzeJob = JSON.parse((e as MessageEvent).data);
			});
			analyzeStream.addEventListener('done', (e) => {
				analyzeJob = JSON.parse((e as MessageEvent).data);
				closeStream();
				if (analyzeJob?.status === 'done') {
					resolve();
				} else {
					reject(new Error(analyzeJob?.error || 'Analyse échouée'));
				}
			});
			analyzeStream.addEventListener('error', (e) => {
				const ev = e as MessageEvent;
				if (ev.data) {
					try {
						analyzeJob = JSON.parse(ev.data);
					} catch {
						// ignore
					}
				}
				closeStream();
				reject(new Error(analyzeJob?.error || 'Connexion SSE perdue'));
			});
			analyzeStream.addEventListener('cancelled', () => {
				closeStream();
				reject(new Error('Analyse annulée'));
			});
		});
	}

	async function analyzeAndRetry() {
		step = 3;
		analyzeJob = null;
		try {
			const url = sourceUrl.trim();
			const job = isTrackUrl(url)
				? await api.analyzeTrack(url)
				: await api.analyze({
						url,
						save: true,
						limit: null,
						download: true
					});
			analyzeJob = job;
			await waitJobDone(job.id);
			// Analyse terminée → re-essayer la création de session
			const sess = await api.createSession({ source_url: url });
			onClose();
			await goto(`/sessions/${encodeURIComponent(sess.spotify_id)}`);
		} catch (e) {
			creating = false;
			step = 2; // retour à la preview pour pouvoir réessayer ou modifier
			error = e instanceof ApiError ? e.detail || e.message : String(e);
		}
	}

	async function submit() {
		if (!sourceUrl.trim()) {
			error = 'Colle une URL Spotify pour continuer.';
			return;
		}
		creating = true;
		error = null;
		try {
			const sess = await api.createSession({ source_url: sourceUrl.trim() });
			onClose();
			await goto(`/sessions/${encodeURIComponent(sess.spotify_id)}`);
		} catch (e) {
			if (isMissingSourceError(e)) {
				// La source n'est pas en DB — on lance l'analyse intermédiaire
				await analyzeAndRetry();
				return;
			}
			creating = false;
			error = e instanceof ApiError ? e.detail || e.message : String(e);
		}
	}

	function onBackdropClick(e: MouseEvent) {
		// On bloque la fermeture par backdrop pendant analyse pour éviter
		// que l'utilisateur perde sa progression
		if (e.target === dialog && !creating && step !== 3) onClose();
	}

	function cancelAnalysis() {
		if (!analyzeJob) return;
		api.cancelJob(analyzeJob.id).catch(() => {});
		closeStream();
		creating = false;
		step = 2;
		error = 'Analyse annulée. Tu peux modifier l\'URL et réessayer.';
	}

	const totalSteps = 2; // affiché : 1/2 ou 2/2. L'étape 3 est une sous-étape de 2.
	const displayedStep = $derived(step === 3 ? 2 : step);
</script>

<ScrollLock open={isOpen} />

<dialog
	bind:this={dialog}
	onclose={() => !creating && onClose()}
	onclick={onBackdropClick}
	class="session-wizard"
>
	<div class="content">
		<header class="px-5 py-3 border-b border-[var(--color-border)] flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">Nouvelle session guidée</h2>
				<p class="text-xs text-[var(--color-fg-muted)] mt-0.5">
					Démarre une track à partir d'une cible d'inspiration
				</p>
			</div>
			<Badge variant="muted">Étape {displayedStep}/{totalSteps}</Badge>
		</header>

		<div class="p-5 flex-1 overflow-y-auto min-h-0">
			{#if error && step !== 3}
				<div class="mb-4 rounded-md border border-[var(--color-err)]/40 bg-[var(--color-err)]/10 p-3 text-sm">
					<p class="text-[var(--color-err)]">{error}</p>
				</div>
			{/if}

			{#if step === 1}
				<h3 class="text-sm font-semibold mb-2">Source d'inspiration</h3>
				<p class="text-sm text-[var(--color-fg-muted)] mb-4 leading-relaxed">
					Vers quel type de son tu veux aller&nbsp;? Colle l'URL d'une
					<strong>playlist Spotify</strong> ou d'un <strong>track Spotify</strong>.
					C'est ta direction stylistique : tempo, tonalité, mastering, profil spectral.
				</p>
				<p class="text-xs text-[var(--color-fg-muted)] italic mb-3">
					Si la source n'est pas encore analysée, Beatfinder lance l'analyse
					automatiquement à l'étape suivante.
				</p>
				<label for="source-url" class="block text-xs uppercase tracking-wider text-[var(--color-fg-muted)] mb-1.5">
					URL Spotify
				</label>
				<input
					id="source-url"
					type="url"
					bind:value={sourceUrl}
					placeholder="https://open.spotify.com/playlist/… ou /track/…"
					class="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 h-10 text-sm font-mono focus:outline focus:outline-2 focus:outline-[var(--color-accent)]"
					disabled={creating}
				/>
			{:else if step === 2}
				<h3 class="text-sm font-semibold mb-2">Confirmer la création</h3>
				<p class="text-sm text-[var(--color-fg-muted)] mb-4 leading-relaxed">
					Beatfinder va&nbsp;:
				</p>
				<ul class="text-sm text-[var(--color-fg)] mb-4 space-y-1.5">
					<li class="flex gap-2">
						<span class="text-[var(--color-accent)] shrink-0">1.</span>
						<span
							>Vérifier que la source est en base — sinon, lancer son analyse
							automatiquement (Spotify → YouTube → audio).</span
						>
					</li>
					<li class="flex gap-2">
						<span class="text-[var(--color-accent)] shrink-0">2.</span>
						<span>Récupérer le pattern de la cible et le figer comme référence.</span>
					</li>
					<li class="flex gap-2">
						<span class="text-[var(--color-accent)] shrink-0">3.</span>
						<span
							>Générer un <strong>plan A→Z</strong> : tempo cible, tonalité, profil
							spectral, master target, checklist pré-DAW.</span
						>
					</li>
					<li class="flex gap-2">
						<span class="text-[var(--color-accent)] shrink-0">4.</span>
						<span>Ouvrir la page de la session, prête pour ton premier upload v1.</span>
					</li>
				</ul>
				<p class="text-xs text-[var(--color-fg-muted)] italic">
					Tu pourras ensuite importer des versions successives (v1, v2, …) pour
					mesurer ta convergence vers la cible. Chaque version est analysée
					indépendamment — pas de moyennage.
				</p>
			{:else if step === 3}
				<h3 class="text-sm font-semibold mb-2">Analyse en cours…</h3>
				<p class="text-sm text-[var(--color-fg-muted)] mb-4 leading-relaxed">
					La source n'était pas encore en base. Beatfinder la télécharge via
					YouTube et l'analyse maintenant. La session sera créée
					automatiquement à la fin.
				</p>
				{#if analyzeJob}
					<ProgressBar
						current={analyzeJob.progress.current}
						total={analyzeJob.progress.total}
						label={analyzeJob.progress.label ||
							(analyzeJob.status === 'queued' ? 'En file…' : '—')}
					/>
					<details class="mt-4 text-xs text-[var(--color-fg-muted)]">
						<summary class="cursor-pointer hover:text-[var(--color-fg)]">
							Logs ({analyzeJob.log.length})
						</summary>
						<div
							class="mt-2 rounded border border-[var(--color-border)] bg-black p-3 font-mono text-[11px] leading-relaxed max-h-40 overflow-y-auto"
						>
							{#if analyzeJob.log.length === 0}
								<span class="text-[var(--color-fg-muted)]/60">(en attente…)</span>
							{:else}
								{#each analyzeJob.log.slice(-30) as line, i (i)}
									<div class="text-[var(--color-fg)]">{line}</div>
								{/each}
							{/if}
						</div>
					</details>
				{:else}
					<p class="text-xs text-[var(--color-fg-muted)] italic">
						Démarrage du job…
					</p>
				{/if}
			{/if}
		</div>

		<footer class="px-5 py-3 border-t border-[var(--color-border)] flex items-center justify-between gap-2 shrink-0">
			{#if step === 1}
				<Button variant="ghost" size="sm" onclick={onClose} disabled={creating}>
					Annuler
				</Button>
				<Button
					variant="primary"
					size="sm"
					disabled={!sourceUrl.trim() || creating}
					onclick={() => (step = 2)}
				>
					Suivant →
				</Button>
			{:else if step === 2}
				<Button variant="ghost" size="sm" onclick={() => (step = 1)} disabled={creating}>
					← Retour
				</Button>
				<Button variant="primary" size="sm" loading={creating} onclick={submit}>
					Créer la session
				</Button>
			{:else}
				<Button variant="ghost" size="sm" onclick={cancelAnalysis}>
					Annuler l'analyse
				</Button>
				<span class="text-xs text-[var(--color-fg-muted)] italic">
					Création automatique à la fin de l'analyse…
				</span>
			{/if}
		</footer>
	</div>
</dialog>

<style>
	.session-wizard {
		width: 50vw;
		min-width: 320px;
		max-height: 85vh;
		padding: 0;
		overflow: hidden;
		border: 1px solid var(--color-border);
		border-radius: 12px;
		background: var(--color-surface);
		color: var(--color-fg);
		box-shadow: 0 20px 60px -10px rgba(0, 0, 0, 0.7);
	}
	.session-wizard::backdrop {
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(2px);
	}
	@media (max-width: 768px) {
		.session-wizard {
			width: 92vw;
		}
	}
	.content {
		display: flex;
		flex-direction: column;
		max-height: 85vh;
	}
</style>
