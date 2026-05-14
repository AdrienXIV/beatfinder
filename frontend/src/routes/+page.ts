import type { PageLoad } from './$types';
import { api } from '$lib/api';

export const load: PageLoad = async ({ fetch }) => {
	const [playlists, sessions] = await Promise.all([
		api.listPlaylists(fetch),
		api.listSessions(fetch).catch(() => [])
	]);
	return { playlists, sessions };
};
