import type { PageLoad } from './$types';
import { api } from '$lib/api';

export const load: PageLoad = async ({ fetch, url }) => {
	const playlists = await api.listPlaylists(fetch);
	return {
		playlists,
		preselectA: url.searchParams.get('a'),
		preselectB: url.searchParams.get('b')
	};
};
