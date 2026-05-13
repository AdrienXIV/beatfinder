import type { PageLoad } from './$types';
import { api } from '$lib/api';

export const load: PageLoad = async ({ fetch, url }) => {
	const [playlists, presets] = await Promise.all([
		api.listPlaylists(fetch),
		api.listThresholdPresets(fetch).catch(() => [])
	]);
	const preselectIds = url.searchParams
		.getAll('ids')
		.flatMap((s) => s.split(','))
		.map((s) => s.trim())
		.filter(Boolean);
	return { playlists, presets, preselectIds };
};
