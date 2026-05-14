export function cn(...classes: (string | undefined | false | null)[]): string {
	return classes.filter(Boolean).join(' ');
}

/**
 * Parse une string ISO 8601 en Date. Si l'ISO n'a pas de timezone marker
 * (Z, +HH:MM ou -HH:MM), on assume **UTC** au lieu de l'heure locale.
 *
 * Workaround pour le bug récurrent backend : SQLite/SQLAlchemy stocke les
 * `datetime.now(UTC)` comme strings naïves (sans tz). Pydantic les sérialise
 * sans suffixe → `new Date()` les interprète comme heure locale et affiche
 * 2h en retard en France (UTC+2 été). Tant que le backend ne forçera pas
 * la tz à la sérialisation, ce helper compense côté frontend.
 */
function parseIsoAsUtc(iso: string): Date {
	const hasTz = /[Zz]|[+-]\d{2}:?\d{2}$/.test(iso);
	return new Date(hasTz ? iso : iso + 'Z');
}

export function formatDate(iso: string | null | undefined): string {
	if (!iso) return '—';
	const d = parseIsoAsUtc(iso);
	if (isNaN(d.getTime())) return '—';
	return d.toLocaleDateString('fr-FR', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	});
}

export function formatDateTime(iso: string | null | undefined): string {
	if (!iso) return '—';
	const d = parseIsoAsUtc(iso);
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
