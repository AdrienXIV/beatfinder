import type { PageLoad } from './$types';
import { api } from '$lib/api';

export const load: PageLoad = async ({ fetch }) => {
	const [cacheStats, spotify] = await Promise.all([
		api.getCacheStats(fetch),
		api.getSpotifySettings(fetch)
	]);
	return { cacheStats, spotify };
};
