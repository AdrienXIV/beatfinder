<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';

	let {
		bpms,
		targetMedian = null,
		binSize = 5,
		height = 200
	}: {
		bpms: number[];
		targetMedian?: number | null;
		binSize?: number;
		height?: number;
	} = $props();

	let canvas: HTMLCanvasElement | null = $state(null);
	let chart: Chart | null = null;

	function buildData() {
		if (bpms.length === 0) {
			return { labels: [], datasets: [{ label: 'Tracks', data: [], backgroundColor: '#f97316' }] };
		}
		const min = Math.floor(Math.min(...bpms) / binSize) * binSize;
		const max = Math.ceil(Math.max(...bpms) / binSize) * binSize;
		const labels: string[] = [];
		const bins: number[] = [];
		for (let b = min; b < max + binSize; b += binSize) {
			labels.push(`${b}-${b + binSize - 1}`);
			bins.push(bpms.filter((v) => v >= b && v < b + binSize).length);
		}
		return {
			labels,
			datasets: [
				{
					label: 'Tracks',
					data: bins,
					backgroundColor: 'rgba(249, 115, 22, 0.7)',
					borderRadius: 3
				}
			]
		};
	}

	function resolveColors() {
		if (typeof window === 'undefined' || !canvas) {
			return { text: '#9a9aa3', grid: 'rgba(154, 154, 163, 0.12)' };
		}
		const style = getComputedStyle(canvas);
		return {
			text: style.getPropertyValue('--color-fg-muted').trim() || '#9a9aa3',
			grid: style.getPropertyValue('--color-border').trim() || 'rgba(154, 154, 163, 0.12)'
		};
	}

	onMount(() => {
		if (!canvas) return;
		const { text, grid } = resolveColors();
		chart = new Chart(canvas, {
			type: 'bar',
			data: buildData(),
			options: {
				responsive: true,
				maintainAspectRatio: false,
				layout: { padding: { top: 8, right: 4, bottom: 0, left: 4 } },
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: {
							label: (ctx) => {
								const n = (ctx.parsed.y ?? 0) as number;
								return `${n} track${n > 1 ? 's' : ''}`;
							}
						}
					}
				},
				scales: {
					x: {
						grid: { display: false },
						border: { color: grid },
						ticks: { color: text, font: { size: 11 }, maxRotation: 45, minRotation: 45 },
						title: {
							display: true,
							text: 'BPM',
							color: text,
							font: { size: 12, weight: 500 },
							padding: { top: 6 }
						}
					},
					y: {
						beginAtZero: true,
						border: { display: false },
						ticks: {
							color: text,
							font: { size: 11 },
							precision: 0,
							padding: 4
						},
						grid: { color: grid, lineWidth: 1 }
					}
				}
			}
		});
	});

	$effect(() => {
		if (!chart) return;
		chart.data = buildData();
		chart.update();
	});

	onDestroy(() => {
		chart?.destroy();
	});
</script>

<div style="height: {height}px;" class="w-full">
	<canvas bind:this={canvas}></canvas>
</div>
