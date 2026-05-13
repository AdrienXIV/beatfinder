import type { PageLoad } from './$types';
import { api } from '$lib/api';

const VALID_STYLES = ['editorial', 'soft', 'newspaper', 'blueprint'] as const;
type StyleKey = (typeof VALID_STYLES)[number];

export const load: PageLoad = async ({ params, fetch, url }) => {
	const [detail, brief] = await Promise.all([
		api.getPlaylist(params.id, fetch),
		api.getBrief(params.id, false, fetch).catch(() => null)
	]);
	const styleParam = url.searchParams.get('style');
	const initialStyle: StyleKey = VALID_STYLES.includes(styleParam as StyleKey)
		? (styleParam as StyleKey)
		: 'editorial';
	return { detail, brief, initialStyle };
};
