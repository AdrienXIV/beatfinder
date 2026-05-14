import type { PageLoad } from './$types';
import { api } from '$lib/api';

export const load: PageLoad = async ({ params, fetch }) => {
	const session = await api.getSession(params.id, fetch);
	return { session };
};
