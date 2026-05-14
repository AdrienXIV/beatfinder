export type PlaylistSummary = {
	spotify_id: string;
	name: string;
	owner_display_name: string | null;
	description: string | null;
	n_tracks: number;
	n_patterns: number;
	last_analyzed_at: string | null;
	created_at: string;
	updated_at: string;
};

export type TrackMeta = {
	spotify_id: string;
	title: string;
	artist: string;
	duration_ms: number;
	release_date: string | null;
	position: number;
	has_analysis: boolean;
	audio_path: string | null;
	bpm: number | null;
	key_note: string | null;
	key_mode: 'major' | 'minor' | null;
	key_uncertain: boolean | null;
	is_overridden: boolean;
	confidence_low: boolean;
	confidence_reasons: string[];
	bpm_alt_hypotheses: number[];
};

export type TrackOverridePayload = {
	bpm?: number | null;
	key_note?: string | null;
	key_mode?: 'major' | 'minor' | null;
};

export type PatternSummary = {
	id: number;
	n_tracks_analyzed: number;
	analyzer_version: string;
	created_at: string;
	bpm_median: number | null;
	lufs_median: number | null;
	sub_median: number | null;
	bass_median: number | null;
	minor_ratio: number | null;
};

export type PlaylistDetail = {
	spotify_id: string;
	name: string;
	owner_display_name: string | null;
	description: string | null;
	tracks: TrackMeta[];
	patterns: PatternSummary[];
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	latest_pattern: Record<string, any> | null;
	created_at: string;
	updated_at: string;
};

export type Pattern = {
	id: number;
	playlist_spotify_id: string;
	n_tracks_analyzed: number;
	analyzer_version: string;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	pattern: Record<string, any>;
	created_at: string;
};

export type Brief = {
	spotify_id: string;
	playlist_name: string;
	markdown: string;
	generated_at: string;
	cached: boolean;
};

export type JobProgress = {
	current: number;
	total: number;
	label: string;
};

export type Job = {
	id: string;
	kind: string;
	status: 'queued' | 'running' | 'done' | 'error' | 'cancelled';
	progress: JobProgress;
	log: string[];
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	result: Record<string, any> | null;
	error: string | null;
	revision: number;
	created_at: string;
	updated_at: string;
};

export type AnalyzeRequest = {
	url: string;
	save?: boolean;
	limit?: number | null;
	download?: boolean;
};

export type CompareRequest = {
	id_a: string;
	id_b: string;
	pattern_a?: number | null;
	pattern_b?: number | null;
};

export type CompareResult = {
	id_a: string;
	id_b: string;
	name_a: string;
	name_b: string;
	n_tracks_a: number;
	n_tracks_b: number;
	markdown: string;
	generated_at: string;
};

export type TrackAnalysis = {
	spotify_id: string;
	title: string;
	artist: string;
	duration_ms: number;
	release_date: string | null;
	audio_path: string | null;
	analyzer_version: string;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	features: Record<string, any>;
	analyzed_at: string;
};

export type ActionPriority = 'high' | 'medium' | 'low';
export type ActionCategory = 'mastering' | 'mix' | 'rhythm' | 'tonality' | 'structure';

export type ActionItem = {
	key: string;
	category: ActionCategory;
	metric: string;
	priority: ActionPriority;
	current: number | null;
	target: number | null;
	delta: number | null;
	unit: string;
	action: string;
	rationale: string;
};

export type ActionPlan = {
	from_id: string;
	from_name: string;
	from_n_tracks: number;
	to_id: string;
	to_name: string;
	to_n_tracks: number;
	from_pattern_id: number | null;
	to_pattern_id: number | null;
	from_bands: Record<string, number>;
	to_bands: Record<string, number>;
	items: ActionItem[];
	generated_at: string;
	cached: boolean;
};

export type ComparedTarget = {
	target_id: string;
	target_name: string;
	target_n_tracks: number;
	n_items: number;
	generated_at: string;
};

export type ComparedSource = {
	from_id: string;
	n_targets: number;
};

export type ThresholdPreset = {
	key: string;
	target_id: string;  // e.g. "preset:rap-fr" — utilisable comme `to` dans getActionPlan
	name: string;
	description: string;
	n_tracks_source: number;
	source_playlist_name: string;
};

export type MultiCompareSource = {
	id: string;
	name: string;
	n_tracks: number;
	kind: 'playlist' | 'track' | 'preset';
};

export type SpectralRadar = {
	labels: string[];
	values: number[][];  // [source_idx][band_idx]
};

export type MultiStatRow = {
	key: string;
	label: string;
	unit: string;
	values: (number | null)[];
};

export type MultiCompare = {
	sources: MultiCompareSource[];
	spectral_radar: SpectralRadar;
	stats_table: MultiStatRow[];
};

export type StylePredictionItem = {
	style: string;
	probability: number;
};

export type StylePrediction = {
	source_id: string;
	source_name: string;
	predictions: StylePredictionItem[];
	model_classes: string[];
	model_cv_accuracy: number;
};

export type CacheCategory = {
	kind: string;
	label: string;
	description: string;
	n_files: number;
	size_bytes: number;
	flushable: boolean;
	counts?: {
		playlists: number;
		tracks: number;
		playlist_tracks: number;
		analyses: number;
		patterns: number;
	} | null;
};

export type CacheStats = {
	youtube: CacheCategory;
	'local-audio': CacheCategory;
	reports: CacheCategory;
	actions: CacheCategory;
	db: CacheCategory;
};

export type CacheFlushResult = {
	kind: string;
	n_files_deleted: number;
	bytes_freed: number;
};

export type CacheKind = 'youtube' | 'local-audio' | 'reports' | 'actions';

export type AppStatus = {
	spotify_configured: boolean;
	version: string;
};

export type UpdateCheck = {
	current: string;
	latest: string | null;
	update_available: boolean;
	release_url: string | null;
	release_notes: string | null;
	published_at: string | null;
};

export type SpotifySettings = {
	client_id: string;
	redirect_uri: string;
	has_secret: boolean;
	is_configured: boolean;
};

export type SpotifySettingsInput = {
	client_id: string;
	client_secret: string;
	redirect_uri?: string;
};

const API_BASE = '/api';

export class ApiError extends Error {
	status: number;
	detail: string;
	constructor(status: number, detail: string) {
		super(`HTTP ${status}: ${detail}`);
		this.status = status;
		this.detail = detail;
	}
}

async function request<T>(
	path: string,
	init?: RequestInit,
	fetchImpl: typeof fetch = fetch
): Promise<T> {
	const res = await fetchImpl(`${API_BASE}${path}`, {
		...init,
		headers: {
			'Content-Type': 'application/json',
			...(init?.headers ?? {})
		}
	});
	if (!res.ok) {
		let detail = res.statusText;
		try {
			const body = await res.json();
			detail = body.detail ?? detail;
		} catch {
			// ignore
		}
		throw new ApiError(res.status, String(detail));
	}
	// 204 No Content + Content-Length: 0 → pas de body à parser, sinon
	// `res.json()` throw `SyntaxError: Unexpected end of JSON input`.
	if (res.status === 204 || res.headers.get('Content-Length') === '0') {
		return undefined as T;
	}
	return res.json() as Promise<T>;
}

export const LOCAL_PREFIX = 'local:';

export function isLocalProject(spotifyId: string): boolean {
	return spotifyId.startsWith(LOCAL_PREFIX);
}

export type CreateProjectRequest = {
	name: string;
	owner_display_name?: string | null;
};

export type CreateProjectOut = {
	spotify_id: string;
	name: string;
	owner_display_name: string | null;
};

export type AddedTrack = {
	spotify_id: string;
	title: string;
	artist: string;
	duration_ms: number;
	audio_path: string;
	filename: string;
};

export type TrackOverride = {
	title?: string;
	artist?: string;
};

async function multipartRequest<T>(
	path: string,
	formData: FormData,
	fetchImpl: typeof fetch = fetch
): Promise<T> {
	const res = await fetchImpl(`${API_BASE}${path}`, {
		method: 'POST',
		body: formData
		// NB: no Content-Type — browser sets multipart/form-data with boundary automatically
	});
	if (!res.ok) {
		let detail = res.statusText;
		try {
			const body = await res.json();
			detail = body.detail ?? detail;
		} catch {
			// ignore
		}
		throw new ApiError(res.status, String(detail));
	}
	return res.json() as Promise<T>;
}

export const api = {
	listPlaylists: (f?: typeof fetch) => request<PlaylistSummary[]>('/playlists', undefined, f),

	createProject: (payload: CreateProjectRequest, f?: typeof fetch) =>
		request<CreateProjectOut>(
			'/projects',
			{ method: 'POST', body: JSON.stringify(payload) },
			f
		),

	uploadTracks: (
		projectId: string,
		files: File[],
		overrides: Record<string, TrackOverride> = {},
		f?: typeof fetch
	) => {
		const fd = new FormData();
		for (const file of files) fd.append('files', file);
		if (Object.keys(overrides).length > 0) {
			fd.append('overrides_json', JSON.stringify(overrides));
		}
		return multipartRequest<AddedTrack[]>(
			`/projects/${encodeURIComponent(projectId)}/tracks`,
			fd,
			f
		);
	},

	analyzeLocal: (
		projectId: string,
		mode: 'new' | 'full' = 'new',
		f?: typeof fetch
	) =>
		request<Job>(
			`/projects/${encodeURIComponent(projectId)}/analyze?mode=${mode}`,
			{ method: 'POST' },
			f
		),

	deleteProject: async (projectId: string, f: typeof fetch = fetch): Promise<void> => {
		const res = await f(`${API_BASE}/projects/${encodeURIComponent(projectId)}`, {
			method: 'DELETE'
		});
		if (!res.ok) {
			let detail = res.statusText;
			try {
				const body = await res.json();
				detail = body.detail ?? detail;
			} catch {
				// ignore
			}
			throw new ApiError(res.status, String(detail));
		}
	},


	getPlaylist: (id: string, f?: typeof fetch) =>
		request<PlaylistDetail>(`/playlists/${id}`, undefined, f),

	listPatterns: (id: string, f?: typeof fetch) =>
		request<PatternSummary[]>(`/playlists/${id}/patterns`, undefined, f),

	getPattern: (id: string, patternId: number, f?: typeof fetch) =>
		request<Pattern>(`/playlists/${id}/patterns/${patternId}`, undefined, f),

	getBrief: (id: string, regenerate = false, f?: typeof fetch) =>
		request<Brief>(`/playlists/${id}/brief${regenerate ? '?regenerate=true' : ''}`, undefined, f),

	briefMdUrl: (id: string) => `${API_BASE}/playlists/${id}/brief.md`,

	downloadBriefPdf: async (id: string, style: string = 'editorial'): Promise<Blob> => {
		const res = await fetch(
			`${API_BASE}/playlists/${encodeURIComponent(id)}/brief.pdf?style=${encodeURIComponent(style)}`
		);
		if (!res.ok) {
			let detail = res.statusText;
			try {
				const body = await res.json();
				detail = body.detail ?? detail;
			} catch {
				// ignore
			}
			throw new ApiError(res.status, String(detail));
		}
		return res.blob();
	},

	analyze: (payload: AnalyzeRequest, f?: typeof fetch) =>
		request<Job>('/playlists/analyze', { method: 'POST', body: JSON.stringify(payload) }, f),

	analyzeTrack: (url: string, f?: typeof fetch) =>
		request<Job>('/tracks/analyze', { method: 'POST', body: JSON.stringify({ url }) }, f),

	patchTrackOverride: (spotifyId: string, payload: TrackOverridePayload, f?: typeof fetch) =>
		request<{ bpm: number | null; key_note: string | null; key_mode: string | null }>(
			`/tracks/${encodeURIComponent(spotifyId)}/overrides`,
			{ method: 'PATCH', body: JSON.stringify(payload) },
			f
		),

	deleteTrackOverride: (spotifyId: string, f?: typeof fetch) =>
		request<void>(
			`/tracks/${encodeURIComponent(spotifyId)}/overrides`,
			{ method: 'DELETE' },
			f
		),

	listJobs: (f?: typeof fetch) => request<Job[]>('/jobs', undefined, f),

	getJob: (id: string, f?: typeof fetch) => request<Job>(`/jobs/${id}`, undefined, f),

	cancelJob: (id: string, f?: typeof fetch) =>
		request<Job>(`/jobs/${id}/cancel`, { method: 'POST' }, f),

	streamJobUrl: (id: string) => `${API_BASE}/jobs/${id}/stream`,

	compare: (payload: CompareRequest, f?: typeof fetch) =>
		request<CompareResult>('/compare', { method: 'POST', body: JSON.stringify(payload) }, f),

	getTrackAnalysis: (id: string, f?: typeof fetch) =>
		request<TrackAnalysis>(`/tracks/${id}/analysis`, undefined, f),

	getActionPlan: (
		fromId: string,
		toId: string,
		regenerate = false,
		f?: typeof fetch
	) => {
		const qs = new URLSearchParams({ from: fromId, to: toId });
		if (regenerate) qs.set('regenerate', 'true');
		return request<ActionPlan>(`/actions?${qs.toString()}`, undefined, f);
	},

	deleteActionPlan: async (
		fromId: string,
		toId: string,
		f: typeof fetch = fetch
	): Promise<void> => {
		const qs = new URLSearchParams({ from: fromId, to: toId });
		const res = await f(`${API_BASE}/actions?${qs.toString()}`, { method: 'DELETE' });
		if (!res.ok && res.status !== 204) {
			let detail = res.statusText;
			try {
				const body = await res.json();
				detail = body.detail ?? detail;
			} catch {
				// ignore
			}
			throw new ApiError(res.status, String(detail));
		}
	},

	listComparedTargets: (fromId: string, f?: typeof fetch) =>
		request<ComparedTarget[]>(
			`/actions/compared-with?from=${encodeURIComponent(fromId)}`,
			undefined,
			f
		),

	listActionSources: (f?: typeof fetch) =>
		request<ComparedSource[]>('/actions/sources', undefined, f),

	listThresholdPresets: (f?: typeof fetch) =>
		request<ThresholdPreset[]>('/actions/presets', undefined, f),

	getMultiCompare: (ids: string[], f?: typeof fetch) =>
		request<MultiCompare>(
			`/compare/multi?ids=${encodeURIComponent(ids.join(','))}`,
			undefined,
			f
		),

	predictStyle: (fromId: string, f?: typeof fetch) =>
		request<StylePrediction>(
			`/style-predict?from=${encodeURIComponent(fromId)}`,
			undefined,
			f
		),

	masterChainMdUrl: (fromId: string, toId: string) =>
		`${API_BASE}/actions/master-chain.md?from=${encodeURIComponent(fromId)}&to=${encodeURIComponent(toId)}`,

	getCacheStats: (f?: typeof fetch) => request<CacheStats>('/cache/stats', undefined, f),

	flushCache: async (kind: CacheKind, f: typeof fetch = fetch): Promise<CacheFlushResult> => {
		const res = await f(`${API_BASE}/cache/${kind}`, { method: 'DELETE' });
		if (!res.ok) {
			let detail = res.statusText;
			try {
				const body = await res.json();
				detail = body.detail ?? detail;
			} catch {
				// ignore
			}
			throw new ApiError(res.status, String(detail));
		}
		return res.json() as Promise<CacheFlushResult>;
	},

	getStatus: (f?: typeof fetch) => request<AppStatus>('/settings/status', undefined, f),

	checkUpdate: (f?: typeof fetch) =>
		request<UpdateCheck>('/version/check', undefined, f),

	getSpotifySettings: (f?: typeof fetch) =>
		request<SpotifySettings>('/settings/spotify', undefined, f),

	putSpotifySettings: (payload: SpotifySettingsInput, f?: typeof fetch) =>
		request<SpotifySettings>(
			'/settings/spotify',
			{ method: 'PUT', body: JSON.stringify(payload) },
			f
		),

	deleteSpotifySettings: (f?: typeof fetch) =>
		request<SpotifySettings>('/settings/spotify', { method: 'DELETE' }, f),

	// ─── Sessions créatives ──────────────────────────────────────────
	listSessions: (f?: typeof fetch) =>
		request<CreativeSessionSummary[]>('/sessions', undefined, f),

	getSession: (id: string, f?: typeof fetch) =>
		request<CreativeSessionDetail>(`/sessions/${encodeURIComponent(id)}`, undefined, f),

	createSession: (payload: { source_url: string; ambiance?: Record<string, string> }, f?: typeof fetch) =>
		request<CreativeSessionDetail>(
			'/sessions',
			{ method: 'POST', body: JSON.stringify(payload) },
			f
		),

	lockSession: (id: string, f?: typeof fetch) =>
		request<CreativeSessionDetail>(
			`/sessions/${encodeURIComponent(id)}/lock`,
			{ method: 'POST' },
			f
		),

	unlockSession: (id: string, f?: typeof fetch) =>
		request<CreativeSessionDetail>(
			`/sessions/${encodeURIComponent(id)}/unlock`,
			{ method: 'POST' },
			f
		),

	uploadSessionVersion: (sessionId: string, file: File, f?: typeof fetch) => {
		const fd = new FormData();
		fd.append('file', file);
		return multipartRequest<SessionVersion>(
			`/sessions/${encodeURIComponent(sessionId)}/versions`,
			fd,
			f
		);
	},

	archiveSession: (id: string, f?: typeof fetch) =>
		request<void>(`/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' }, f),

	deletePlaylist: (spotifyId: string, f?: typeof fetch) =>
		request<void>(`/playlists/${encodeURIComponent(spotifyId)}`, { method: 'DELETE' }, f)
};

export type CreativeSessionSummary = {
	spotify_id: string;
	name: string;
	target_kind: 'spotify_playlist' | 'spotify_track' | 'upload' | 'local_playlist';
	target_name: string;
	n_versions: number;
	last_fit_score: number | null;
	is_locked: boolean;
	created_at: string;
	updated_at: string;
};

export type SessionVersion = {
	id: number;
	version_number: number;
	name: string;
	fit_score: number | null;
	created_at: string;
};

export type CreativeSessionDetail = {
	spotify_id: string;
	name: string;
	target_kind: 'spotify_playlist' | 'spotify_track' | 'upload' | 'local_playlist';
	target_ref: string;
	target_name: string;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	target_pattern: Record<string, any>;
	target_track: TrackMeta | null;
	target_tracks: TrackMeta[] | null;
	ambiance: Record<string, string> | null;
	plan_md: string;
	versions: SessionVersion[];
	is_locked: boolean;
	locked_at: string | null;
	created_at: string;
	updated_at: string;
};
