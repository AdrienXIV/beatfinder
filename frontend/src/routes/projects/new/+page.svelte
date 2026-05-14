<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, ApiError, type TrackOverride } from '$lib/api';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import { formatDurationMs } from '$lib/utils';

	type FileRow = {
		file: File;
		title: string;
		artist: string;
	};

	const ACCEPTED = '.wav,.mp3,.flac,.ogg,.m4a,.aiff';
	const ACCEPTED_LIST = ACCEPTED.split(',');

	let projectName = $state('');
	let owner = $state('Adrien');
	let rows = $state<FileRow[]>([]);
	let dragOver = $state(false);
	let submitting = $state(false);
	let error = $state<string | null>(null);
	let progressMsg = $state<string | null>(null);
	let fileInput: HTMLInputElement | null = $state(null);

	const total_bytes = $derived(rows.reduce((acc, r) => acc + r.file.size, 0));
	const total_mb = $derived(total_bytes / (1024 * 1024));

	function stemFromName(name: string): string {
		return name.replace(/\.[^.]+$/, '');
	}

	function isAccepted(name: string): boolean {
		const lower = name.toLowerCase();
		return ACCEPTED_LIST.some((ext) => lower.endsWith(ext));
	}

	function addFiles(fileList: FileList | File[] | null) {
		if (!fileList) return;
		const arr = Array.from(fileList);
		const accepted = arr.filter((f) => isAccepted(f.name));
		const rejected = arr.length - accepted.length;
		if (rejected > 0) {
			error = `${rejected} fichier(s) ignoré(s) — extensions acceptées : ${ACCEPTED}`;
		}
		rows = [
			...rows,
			...accepted.map((f) => ({
				file: f,
				title: stemFromName(f.name),
				artist: ''
			}))
		];
	}

	function removeRow(idx: number) {
		rows = rows.filter((_, i) => i !== idx);
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		if (e.dataTransfer?.files) addFiles(e.dataTransfer.files);
	}

	function onDragOver(e: DragEvent) {
		e.preventDefault();
		dragOver = true;
	}

	function onDragLeave(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
	}

	function onFileInput(e: Event) {
		const target = e.target as HTMLInputElement;
		addFiles(target.files);
		target.value = '';
	}

	async function onSubmit(e: Event) {
		e.preventDefault();
		if (!projectName.trim()) {
			error = 'Donne un nom au projet.';
			return;
		}
		if (rows.length === 0) {
			error = 'Ajoute au moins un fichier audio.';
			return;
		}
		error = null;
		submitting = true;
		try {
			progressMsg = 'Création du projet…';
			const project = await api.createProject({
				name: projectName.trim(),
				owner_display_name: owner.trim() || null
			});

			progressMsg = `Upload de ${rows.length} fichier${rows.length > 1 ? 's' : ''}…`;
			const overrides: Record<string, TrackOverride> = {};
			for (const r of rows) {
				const o: TrackOverride = {};
				if (r.title.trim()) o.title = r.title.trim();
				if (r.artist.trim()) o.artist = r.artist.trim();
				if (o.title || o.artist) overrides[r.file.name] = o;
			}
			await api.uploadTracks(
				project.spotify_id,
				rows.map((r) => r.file),
				overrides
			);

			progressMsg = "Lancement de l'analyse…";
			const job = await api.analyzeLocal(project.spotify_id);
			await goto(`/jobs/${job.id}`);
		} catch (e) {
			submitting = false;
			progressMsg = null;
			if (e instanceof ApiError) error = e.detail || e.message;
			else if (e instanceof Error) error = e.message;
			else error = String(e);
		}
	}
</script>

<div class="max-w-3xl mx-auto">
	<h1 class="text-3xl font-bold tracking-tight mb-1">Nouveau projet local</h1>
	<p class="text-sm text-[var(--color-fg-muted)] mb-8">
		Uploade des fichiers audio (WAV / MP3 / FLAC / OGG / M4A / AIFF). Le pipeline analyse
		BPM, tonalité, énergie, profil spectral. Pas de passage par Spotify ou YouTube.
	</p>

	<Card class="mb-6">
		<form onsubmit={onSubmit} class="space-y-5">
			<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
				<div class="md:col-span-2">
					<label for="name" class="block text-sm font-medium mb-1.5">
						Nom du projet <span class="text-[var(--color-err)]">*</span>
					</label>
					<input
						id="name"
						type="text"
						bind:value={projectName}
						placeholder="Ex: KyuBeats mix sessions oct"
						required
						class="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 h-10 text-sm focus:outline focus:outline-2 focus:outline-[var(--color-accent)] focus:border-transparent"
					/>
				</div>
				<div>
					<label for="owner" class="block text-sm font-medium mb-1.5">Owner</label>
					<input
						id="owner"
						type="text"
						bind:value={owner}
						class="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 h-10 text-sm focus:outline focus:outline-2 focus:outline-[var(--color-accent)] focus:border-transparent"
					/>
				</div>
			</div>

			<div>
				<label class="block text-sm font-medium mb-1.5">Fichiers audio</label>
				<button
					type="button"
					class="block w-full rounded-lg border-2 border-dashed p-8 text-center transition-colors {dragOver
						? 'border-[var(--color-accent)] bg-[var(--color-accent)]/5'
						: 'border-[var(--color-border)] hover:border-[#3a3a44] hover:bg-[var(--color-surface-2)]/40'}"
					ondrop={onDrop}
					ondragover={onDragOver}
					ondragleave={onDragLeave}
					onclick={() => fileInput?.click()}
				>
					<p class="text-sm font-medium">Drop tes fichiers ici, ou click pour parcourir</p>
					<p class="text-xs text-[var(--color-fg-muted)] mt-1.5">
						Multi-fichiers OK · extensions {ACCEPTED}
					</p>
				</button>
				<input
					bind:this={fileInput}
					type="file"
					multiple
					accept={ACCEPTED}
					onchange={onFileInput}
					class="hidden"
				/>
			</div>

			{#if rows.length > 0}
				<div class="overflow-x-auto rounded-lg border border-[var(--color-border)]">
					<table class="w-full text-sm">
						<thead
							class="bg-[var(--color-surface-2)] text-xs uppercase tracking-wider text-[var(--color-fg-muted)]"
						>
							<tr>
								<th class="px-3 py-2 text-left">Fichier</th>
								<th class="px-3 py-2 text-left w-44">Artist</th>
								<th class="px-3 py-2 text-left w-56">Title</th>
								<th class="px-3 py-2 text-right w-20">Size</th>
								<th class="px-3 py-2 w-10"></th>
							</tr>
						</thead>
						<tbody>
							{#each rows as r, i (r.file.name + i)}
								<tr class="border-t border-[var(--color-border)]">
									<td class="px-3 py-2 font-mono text-xs text-[var(--color-fg-muted)] truncate max-w-[200px]">
										{r.file.name}
									</td>
									<td class="px-2 py-1.5">
										<input
											type="text"
											bind:value={r.artist}
											placeholder="Artist (auto si ID3)"
											class="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 h-7 text-xs focus:outline focus:outline-1 focus:outline-[var(--color-accent)]"
										/>
									</td>
									<td class="px-2 py-1.5">
										<input
											type="text"
											bind:value={r.title}
											class="w-full rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 h-7 text-xs focus:outline focus:outline-1 focus:outline-[var(--color-accent)]"
										/>
									</td>
									<td class="px-3 py-2 text-right font-mono text-xs text-[var(--color-fg-muted)]">
										{(r.file.size / (1024 * 1024)).toFixed(1)} MB
									</td>
									<td class="px-2 py-2 text-center">
										<button
											type="button"
											onclick={() => removeRow(i)}
											class="text-[var(--color-fg)] hover:text-[var(--color-err)] text-lg leading-none font-bold"
											aria-label="Supprimer"
										>
											×
										</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<div class="flex items-center justify-between text-xs text-[var(--color-fg-muted)]">
					<span>{rows.length} fichier{rows.length > 1 ? 's' : ''} prêt{rows.length > 1 ? 's' : ''}</span>
					<span class="font-mono">{total_mb.toFixed(1)} MB total</span>
				</div>
				{#if rows.length < 5}
					<div class="flex items-start gap-2 rounded-md border border-[var(--color-warn)]/40 bg-[var(--color-warn)]/5 p-3 text-xs">
						<Badge variant="warn">⚠</Badge>
						<span>
							Stats limitées avec {rows.length} track{rows.length > 1 ? 's' : ''}. Recommandé : 5+ pour un pattern robuste, 8+ pour des comparaisons fiables.
						</span>
					</div>
				{/if}
			{/if}

			{#if error}
				<div
					class="rounded-md border border-[var(--color-err)]/40 bg-[var(--color-err)]/10 p-3 text-sm"
				>
					<p class="font-medium text-[var(--color-err)] mb-1">Erreur</p>
					<p>{error}</p>
				</div>
			{/if}

			{#if progressMsg}
				<div class="text-sm text-[var(--color-fg-muted)] italic">{progressMsg}</div>
			{/if}

			<div class="flex items-center gap-3 pt-2">
				<Button
					type="submit"
					variant="primary"
					loading={submitting}
					disabled={!projectName.trim() || rows.length === 0}
				>
					Créer + Analyser
				</Button>
				<span class="text-xs text-[var(--color-fg-muted)]">
					~30-90s par track (analyse librosa)
				</span>
			</div>
		</form>
	</Card>
</div>
