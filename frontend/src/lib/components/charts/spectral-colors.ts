/**
 * Palette des 6 bandes spectrales (gradient grave → aigu).
 * Utilisée par SpectralRing pour différencier les anneaux, et par les légendes.
 *
 * Mapping mnémonique : chaud (grave / sub) → froid (aigu / high)
 */
export const SPECTRAL_BAND_KEYS = [
	'sub',
	'bass',
	'low_mid',
	'mid',
	'high_mid',
	'high'
] as const;

export type SpectralBandKey = (typeof SPECTRAL_BAND_KEYS)[number];

export const SPECTRAL_BAND_COLORS: Record<SpectralBandKey, string> = {
	sub: '#ef4444', // rouge
	bass: '#f97316', // orange (accent)
	low_mid: '#eab308', // jaune
	mid: '#22c55e', // vert
	high_mid: '#06b6d4', // cyan
	high: '#a855f7' // violet
};

export const SPECTRAL_BAND_LABELS: Record<SpectralBandKey, string> = {
	sub: 'Sub 20-60 Hz',
	bass: 'Bass 60-250 Hz',
	low_mid: 'Low-mid 250-500 Hz',
	mid: 'Mid 500 Hz - 2 kHz',
	high_mid: 'High-mid 2-6 kHz',
	high: 'High 6-20 kHz'
};
