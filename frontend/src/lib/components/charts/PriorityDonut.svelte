<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';

	let {
		high,
		medium,
		low,
		height = 180
	}: {
		high: number;
		medium: number;
		low: number;
		height?: number;
	} = $props();

	let canvas: HTMLCanvasElement | null = $state(null);
	let chart: Chart | null = null;

	function buildData() {
		return {
			labels: ['High', 'Medium', 'Low'],
			datasets: [
				{
					data: [high, medium, low],
					backgroundColor: ['#ef4444', '#facc15', '#3a3a44'],
					borderColor: '#131316',
					borderWidth: 2
				}
			]
		};
	}

	onMount(() => {
		if (!canvas) return;
		chart = new Chart(canvas, {
			type: 'doughnut',
			data: buildData(),
			options: {
				responsive: true,
				maintainAspectRatio: false,
				cutout: '65%',
				plugins: {
					legend: {
						position: 'right',
						labels: {
							color: '#9a9aa3',
							font: { size: 11 },
							boxWidth: 12
						}
					},
					tooltip: {
						callbacks: {
							label: (ctx) => `${ctx.label}: ${ctx.parsed} action${ctx.parsed > 1 ? 's' : ''}`
						}
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

<div class="w-full" style="height: {height}px;">
	<canvas bind:this={canvas}></canvas>
</div>
