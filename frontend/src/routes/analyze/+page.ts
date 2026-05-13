import type { PageLoad } from './$types';

export const load: PageLoad = async ({ url }) => {
	return {
		preselectUrl: url.searchParams.get('url') ?? ''
	};
};
