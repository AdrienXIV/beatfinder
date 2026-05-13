import type { PageLoad } from './$types';
import { api } from '$lib/api';

export const load: PageLoad = async ({ fetch }) => {
	const playlists = await api.listPlaylists(fetch);
	return { playlists };
};
