import type { PageLoad } from './$types';
import { api } from '$lib/api';

export const load: PageLoad = async ({ params, fetch }) => {
	const [detail, brief] = await Promise.all([
		api.getPlaylist(params.id, fetch),
		api.getBrief(params.id, false, fetch).catch(() => null)
	]);
	return { detail, brief };
};
