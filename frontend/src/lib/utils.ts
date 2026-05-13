export function cn(...classes: (string | undefined | false | null)[]): string {
	return classes.filter(Boolean).join(' ');
}

export function formatDate(iso: string | null | undefined): string {
	if (!iso) return '—';
	const d = new Date(iso);
	if (isNaN(d.getTime())) return '—';
	return d.toLocaleDateString('fr-FR', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	});
}

export function formatDateTime(iso: string | null | undefined): string {
	if (!iso) return '—';
	const d = new Date(iso);
	if (isNaN(d.getTime())) return '—';
	return d.toLocaleString('fr-FR', {
		year: 'numeric',
		month: 'short',
		day: 'numeric',
		hour: '2-digit',
		minute: '2-digit'
	});
}

export function formatNumber(n: number | null | undefined, digits = 1): string {
	if (n === null || n === undefined || isNaN(n)) return '—';
	return n.toFixed(digits);
}

export function formatPercent(ratio: number | null | undefined, digits = 0): string {
	if (ratio === null || ratio === undefined || isNaN(ratio)) return '—';
	return `${(ratio * 100).toFixed(digits)}%`;
}

export function formatDurationMs(ms: number | null | undefined): string {
	if (ms === null || ms === undefined) return '—';
	const total = Math.round(ms / 1000);
	const m = Math.floor(total / 60);
	const s = total % 60;
	return `${m}:${s.toString().padStart(2, '0')}`;
}

export function formatBytes(bytes: number | null | undefined): string {
	if (bytes === null || bytes === undefined || isNaN(bytes)) return '—';
	if (bytes === 0) return '0 B';
	const units = ['B', 'KB', 'MB', 'GB', 'TB'];
	const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
	const value = bytes / Math.pow(1024, i);
	return `${value.toFixed(value >= 100 || i === 0 ? 0 : 1)} ${units[i]}`;
}
