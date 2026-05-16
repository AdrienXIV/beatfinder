/**
 * Helpers pour comparer une version de session à son target_pattern figé.
 *
 * - track features_json : dict imbriqué avec valeurs scalaires
 *   (ex: features.energy.lufs_integrated = -19.2)
 * - target_pattern : même structure mais valeurs = stats dict
 *   {n, median, mean, std, min, p25, p75, max}
 *
 * Status : 'good' si valeur ∈ p25-p75, 'warn' si ∈ [min, max], 'bad' sinon.
 */

export type FeatureStatus = 'good' | 'warn' | 'bad' | 'unknown';

export type FeatureRow = {
	key: string;
	label: string;
	unit: string; // affiché derrière la valeur, ex: ' dB', ' Hz', '%'
	path: string[]; // chemin dans features_json ET target_pattern
	/** Multiplicateur d'affichage (ex: 100 pour les bandes spectrales 0-1 → 0-100%) */
	displayScale?: number;
	/** Décimales pour formatage */
	decimals?: number;
};

/** Features clés affichées dans le tableau récap. */
export const KEY_FEATURES: FeatureRow[] = [
	// Mastering
	{ key: 'lufs', label: 'LUFS intégré', unit: ' dB', path: ['energy', 'lufs_integrated'], decimals: 1 },
	{ key: 'true_peak', label: 'True Peak', unit: ' dB', path: ['energy', 'true_peak_db'], decimals: 1 },
	// Dynamique
	{ key: 'crest', label: 'Crest factor', unit: ' dB', path: ['energy', 'crest_factor_db'], decimals: 1 },
	{ key: 'dr', label: 'Dynamic range', unit: ' dB', path: ['energy', 'dynamic_range_db'], decimals: 1 },
	// Rythme
	{ key: 'bpm', label: 'BPM', unit: '', path: ['tempo', 'bpm'], decimals: 0 },
	// Spectre
	{ key: 'centroid', label: 'Centroid', unit: ' Hz', path: ['spectral', 'centroid_hz'], decimals: 0 },
	{ key: 'sub', label: 'Sub (20-60 Hz)', unit: '%', path: ['spectral', 'band_energy', 'sub'], displayScale: 100, decimals: 1 },
	{ key: 'bass', label: 'Bass (60-250 Hz)', unit: '%', path: ['spectral', 'band_energy', 'bass'], displayScale: 100, decimals: 1 },
	{ key: 'low_mid', label: 'Low-mid (250-500)', unit: '%', path: ['spectral', 'band_energy', 'low_mid'], displayScale: 100, decimals: 1 },
	{ key: 'mid', label: 'Mid (500-2k)', unit: '%', path: ['spectral', 'band_energy', 'mid'], displayScale: 100, decimals: 1 },
	{ key: 'high_mid', label: 'High-mid (2-5k)', unit: '%', path: ['spectral', 'band_energy', 'high_mid'], displayScale: 100, decimals: 1 },
	{ key: 'high', label: 'High (5-20k)', unit: '%', path: ['spectral', 'band_energy', 'high'], displayScale: 100, decimals: 1 },
	// Structure
	{ key: 'drop', label: 'Drop position', unit: '%', path: ['structure', 'drop_position_ratio'], displayScale: 100, decimals: 0 }
];

/** Sous-ensemble suivi par les sparklines d'évolution. */
export const EVOLUTION_FEATURES: FeatureRow[] = KEY_FEATURES.filter((f) =>
	['lufs', 'sub', 'centroid', 'crest'].includes(f.key)
);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function walk(obj: any, path: string[]): unknown {
	let cur: unknown = obj;
	for (const p of path) {
		if (cur === null || typeof cur !== 'object') return undefined;
		cur = (cur as Record<string, unknown>)[p];
		if (cur === undefined) return undefined;
	}
	return cur;
}

/** Lit la valeur scalaire dans un features_json track-level. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function getFeatureValue(features: Record<string, any>, path: string[]): number | null {
	const v = walk(features, path);
	if (typeof v !== 'number' || !Number.isFinite(v)) return null;
	return v;
}

export type PatternStats = {
	n: number;
	median?: number;
	mean?: number;
	std?: number;
	min?: number;
	max?: number;
	p25?: number;
	p75?: number;
};

/** Lit le dict de stats {p25, p75, median, ...} dans un target_pattern. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function getPatternStats(pattern: Record<string, any>, path: string[]): PatternStats | null {
	const v = walk(pattern, path);
	if (!v || typeof v !== 'object') return null;
	const stats = v as Record<string, unknown>;
	if (typeof stats.n !== 'number') return null;
	return stats as PatternStats;
}

/** Vert si dans p25-p75, jaune si dans [min, max], rouge sinon. */
export function getStatus(value: number | null, stats: PatternStats | null): FeatureStatus {
	if (value === null || stats === null) return 'unknown';
	if (stats.p25 === undefined || stats.p75 === undefined) return 'unknown';
	if (value >= stats.p25 && value <= stats.p75) return 'good';
	if (stats.min !== undefined && stats.max !== undefined && value >= stats.min && value <= stats.max) {
		return 'warn';
	}
	return 'bad';
}

export function formatValue(value: number | null, row: FeatureRow): string {
	if (value === null) return '—';
	const scale = row.displayScale ?? 1;
	const decimals = row.decimals ?? 1;
	return (value * scale).toFixed(decimals);
}

export function formatTarget(stats: PatternStats | null, row: FeatureRow): string {
	if (stats === null || stats.median === undefined) return '—';
	return formatValue(stats.median, row);
}

/** Delta affiché : "+1.2", "-3.4" — valeur brute déjà mise à l'échelle. */
export function formatDelta(value: number | null, stats: PatternStats | null, row: FeatureRow): string {
	if (value === null || stats === null || stats.median === undefined) return '—';
	const scale = row.displayScale ?? 1;
	const decimals = row.decimals ?? 1;
	const delta = (value - stats.median) * scale;
	if (Math.abs(delta) < Math.pow(10, -decimals) / 2) return '0';
	const sign = delta > 0 ? '+' : '−';
	return `${sign}${Math.abs(delta).toFixed(decimals)}`;
}

export function statusColorClass(status: FeatureStatus): string {
	switch (status) {
		case 'good':
			return 'text-[var(--color-ok)]';
		case 'warn':
			return 'text-[var(--color-warn)]';
		case 'bad':
			return 'text-[var(--color-err)]';
		default:
			return 'text-[var(--color-fg-muted)]';
	}
}

export function statusBgClass(status: FeatureStatus): string {
	switch (status) {
		case 'good':
			return 'bg-[var(--color-ok)]/10';
		case 'warn':
			return 'bg-[var(--color-warn)]/10';
		case 'bad':
			return 'bg-[var(--color-err)]/10';
		default:
			return '';
	}
}
