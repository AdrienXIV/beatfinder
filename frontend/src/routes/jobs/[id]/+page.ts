import type { PageLoad } from './$types';
import { api } from '$lib/api';

export const load: PageLoad = async ({ params, fetch }) => {
	const job = await api.getJob(params.id, fetch);
	return { job };
};
