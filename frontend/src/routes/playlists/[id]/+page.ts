import type { PageLoad } from './$types';
import { api } from '$lib/api';

export const load: PageLoad = async ({ params, fetch }) => {
	const [detail, playlists, comparedTargets, actionSources, stylePrediction] =
		await Promise.all([
			api.getPlaylist(params.id, fetch),
			api.listPlaylists(fetch),
			api.listComparedTargets(params.id, fetch).catch(() => []),
			api.listActionSources(fetch).catch(() => []),
			// silent : si le modèle n'est pas entraîné, on ne montre juste rien
			api.predictStyle(params.id, fetch).catch(() => null)
		]);
	return { detail, playlists, comparedTargets, actionSources, stylePrediction };
};
