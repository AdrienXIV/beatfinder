<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import type { PageData } from './$types';
	import { api, type Job } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import ProgressBar from '$lib/components/ProgressBar.svelte';
	import { formatDateTime } from '$lib/utils';

	let { data }: { data: PageData } = $props();

	let job = $state<Job>(data.job);
	let connectionError = $state<string | null>(null);
	let cancelling = $state(false);
	let logEl: HTMLDivElement | null = $state(null);
	let es: EventSource | null = null;

	function statusBadge(status: Job['status']) {
		switch (status) {
			case 'queued':
				return { variant: 'muted' as const, label: 'En attente' };
			case 'running':
				return { variant: 'accent' as const, label: 'En cours' };
			case 'done':
				return { variant: 'ok' as const, label: 'Terminé' };
			case 'error':
				return { variant: 'err' as const, label: 'Erreur' };
			case 'cancelled':
				return { variant: 'warn' as const, label: 'Annulé' };
		}
	}

	async function scrollLogToBottom() {
		await tick();
		if (logEl) {
			logEl.scrollTop = logEl.scrollHeight;
		}
	}

	function updateJob(next: Job) {
		const grew = next.log.length > job.log.length;
		job = next;
		if (grew) {
			scrollLogToBottom();
		}
	}

	function startStream() {
		if (job.status !== 'queued' && job.status !== 'running') {
			return;
		}
		es = new EventSource(api.streamJobUrl(job.id));
		es.addEventListener('update', (e) => {
			updateJob(JSON.parse((e as MessageEvent).data));
		});
		es.addEventListener('done', (e) => {
			updateJob(JSON.parse((e as MessageEvent).data));
			es?.close();
			es = null;
		});
		es.addEventListener('error', (e) => {
			const ev = e as MessageEvent;
			if (ev.data) {
				updateJob(JSON.parse(ev.data));
				es?.close();
				es = null;
			} else {
				connectionError = 'Connexion SSE perdue. Recharge la page pour reprendre.';
			}
		});
		es.addEventListener('cancelled', (e) => {
			updateJob(JSON.parse((e as MessageEvent).data));
			es?.close();
			es = null;
		});
	}

	async function cancel() {
		if (job.status !== 'running' && job.status !== 'queued') return;
		cancelling = true;
		try {
			const updated = await api.cancelJob(job.id);
			updateJob(updated);
		} catch (e) {
			connectionError = e instanceof Error ? e.message : String(e);
		} finally {
			cancelling = false;
		}
	}

	onMount(() => {
		scrollLogToBottom();
		startStream();
	});

	onDestroy(() => {
		es?.close();
	});

	const badge = $derived(statusBadge(job.status));
	const playlistId = $derived(job.result?.playlist_spotify_id as string | undefined);

	function lineClass(line: string): string {
		// Strip timestamp [HH:MM:SS] avant matching
		const m = line.match(/^\[\d{2}:\d{2}:\d{2}\]\s*(.*)$/);
		const body = m ? m[1] : line;

		// Erreurs : préfixe `!` ou mots déclencheurs en début
		if (/^\s*!\s/.test(body) || /^(Erreur|Error\b|Échec|Failed\b)/i.test(body)) {
			return 'text-[var(--color-err)]';
		}
		// Succès : commence par ✓
		if (/^\s*✓/.test(body)) {
			return 'text-[var(--color-ok)]';
		}
		// Étapes en cours : commence par → ou "Starting"/"Analyzing"
		if (/^\s*→/.test(body) || /^(Starting|Analyzing|Extracting|Fetching)/i.test(body)) {
			return 'text-[var(--color-accent)]';
		}
		// Sous-marqueur · ou cache
		if (/^\s*·/.test(body) || /\bcache(d)?\b/i.test(body)) {
			return 'text-[var(--color-fg-muted)]';
		}
		return 'text-[var(--color-fg)]';
	}
</script>

<div class="max-w-3xl mx-auto">
	<a
		href="/"
		class="text-sm text-[var(--color-fg-muted)] hover:text-[var(--color-fg)] mb-3 inline-block"
	>
		← Toutes les playlists
	</a>

	<div class="flex items-end justify-between gap-4 mb-6">
		<div>
			<h1 class="text-2xl font-bold tracking-tight">Job {job.id.slice(0, 8)}</h1>
			<p class="text-sm text-[var(--color-fg-muted)] mt-1">
				{job.kind} · démarré {formatDateTime(job.created_at)}
			</p>
		</div>
		<div class="flex items-center gap-2">
			<Badge variant={badge.variant}>{badge.label}</Badge>
			{#if job.status === 'running' || job.status === 'queued'}
				<Button variant="destructive" size="sm" loading={cancelling} onclick={cancel}>
					Annuler
				</Button>
			{/if}
			{#if job.status === 'done' && playlistId}
				<Button variant="primary" size="sm" href="/playlists/{playlistId}">
					Voir la playlist
				</Button>
			{/if}
		</div>
	</div>

	<Card class="mb-6">
		<ProgressBar
			current={job.progress.current}
			total={job.progress.total}
			label={job.progress.label || (job.status === 'queued' ? 'En file…' : '—')}
		/>
	</Card>

	{#if job.error}
		<Card class="mb-6 border-[var(--color-err)]/40">
			<p class="font-medium text-[var(--color-err)] mb-1">Erreur</p>
			<p class="font-mono text-sm whitespace-pre-wrap">{job.error}</p>
		</Card>
	{/if}

	{#if connectionError}
		<Card class="mb-6 border-[var(--color-warn)]/40">
			<p class="text-sm">{connectionError}</p>
		</Card>
	{/if}

	{#if job.status === 'done' && job.result}
		<Card class="mb-6">
			<p class="font-medium mb-2">Résultat</p>
			<div class="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm font-mono">
				{#each Object.entries(job.result) as [k, v] (k)}
					<span class="text-[var(--color-fg-muted)]">{k}</span>
					<span class="truncate">{v ?? '—'}</span>
				{/each}
			</div>
		</Card>
	{/if}

	<div>
		<div class="mb-2 flex items-center justify-between">
			<h2 class="text-sm font-medium text-[var(--color-fg-muted)]">Terminal</h2>
			<span class="text-xs text-[var(--color-fg-muted)] font-mono">
				{job.log.length} ligne{job.log.length > 1 ? 's' : ''}
			</span>
		</div>
		<div
			bind:this={logEl}
			class="rounded-lg border border-[var(--color-border)] bg-black p-4 font-mono text-[13px] leading-relaxed text-[var(--color-fg)] max-h-[500px] min-h-[200px] overflow-y-auto"
		>
			{#if job.log.length === 0}
				<span class="text-[var(--color-fg-muted)]/60">(aucun log)</span>
			{:else}
				{#each job.log as line, i (i)}
					{@const cls = lineClass(line)}
					<div class={cls}>{line}</div>
				{/each}
			{/if}
			{#if job.status === 'running' || job.status === 'queued'}
				<div class="loader-row">
					<span class="dot d1">·</span>
					<span class="dot d2">·</span>
					<span class="dot d3">·</span>
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	.loader-row {
		display: inline-flex;
		gap: 4px;
		align-items: center;
		color: var(--color-accent);
		font-family: 'JetBrains Mono', ui-monospace, monospace;
		font-size: 22px;
		line-height: 1;
		margin-top: 4px;
	}
	.dot {
		opacity: 0.2;
		animation: term-blink 1.4s infinite ease-in-out;
	}
	.dot.d1 {
		animation-delay: 0s;
	}
	.dot.d2 {
		animation-delay: 0.25s;
	}
	.dot.d3 {
		animation-delay: 0.5s;
	}
	@keyframes term-blink {
		0%,
		80%,
		100% {
			opacity: 0.2;
		}
		40% {
			opacity: 1;
		}
	}
</style>
