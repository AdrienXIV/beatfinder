/**
 * Détecte le type d'une URL/URI Spotify (track, playlist, album, etc.).
 *
 * Supporte :
 * - Liens web : https://open.spotify.com/{type}/{id}[?si=...]
 * - URIs : spotify:{type}:{id}
 * - ID brut base62 22 chars (ambigu → 'unknown')
 *
 * Beatfinder ne supporte que `track` et `playlist` comme sources d'analyse.
 */

export type SpotifyResourceType =
	| 'track'
	| 'playlist'
	| 'album'
	| 'artist'
	| 'show'
	| 'episode'
	| 'unknown';

const URL_TYPE_RE = /(?:spotify:|open\.spotify\.com\/)(track|playlist|album|artist|show|episode)[:/]([A-Za-z0-9]{22})/i;
const BARE_ID_RE = /^[A-Za-z0-9]{22}$/;

export type SpotifyUrlInfo = {
	type: SpotifyResourceType;
	id: string | null;
	supported: boolean;
};

export function detectSpotifyUrl(input: string): SpotifyUrlInfo {
	const url = input.trim();
	if (!url) return { type: 'unknown', id: null, supported: false };

	const m = url.match(URL_TYPE_RE);
	if (m) {
		const type = m[1].toLowerCase() as SpotifyResourceType;
		return {
			type,
			id: m[2],
			supported: type === 'track' || type === 'playlist'
		};
	}

	// ID brut 22 chars : on ne peut pas deviner le type → unknown
	// (le backend tente playlist puis track, ça reste accepté en l'état)
	if (BARE_ID_RE.test(url)) {
		return { type: 'unknown', id: url, supported: true };
	}

	return { type: 'unknown', id: null, supported: false };
}

/** Label FR pour affichage utilisateur. */
export function spotifyTypeLabel(type: SpotifyResourceType): string {
	switch (type) {
		case 'track':
			return 'Track';
		case 'playlist':
			return 'Playlist';
		case 'album':
			return 'Album';
		case 'artist':
			return 'Artiste';
		case 'show':
			return 'Podcast (show)';
		case 'episode':
			return 'Épisode';
		default:
			return 'Inconnu';
	}
}
