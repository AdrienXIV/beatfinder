import type { PlaylistDetail, Brief } from '$lib/api';

export type StyleProps = {
	detail: PlaylistDetail;
	brief: Brief | null;
};

export function pickBands(lp: Record<string, unknown> | undefined | null) {
	const be = (lp as any)?.spectral?.band_energy;
	if (!be) return null;
	return {
		sub: be.sub?.median ?? 0,
		bass: be.bass?.median ?? 0,
		low_mid: be.low_mid?.median ?? 0,
		mid: be.mid?.median ?? 0,
		high_mid: be.high_mid?.median ?? 0,
		high: be.high?.median ?? 0
	} as Record<string, number>;
}

export const BAND_LABELS: Record<string, string> = {
	sub: 'Sub 20–60Hz',
	bass: 'Bass 60–250Hz',
	low_mid: 'Low-mid 250–500Hz',
	mid: 'Mid 500Hz–2kHz',
	high_mid: 'High-mid 2–6kHz',
	high: 'High 6–20kHz'
};
