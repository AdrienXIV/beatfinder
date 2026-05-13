<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';

	let {
		values,
		labels = null,
		color = '#f97316',
		height = 40,
		fmt = (v: number) => v.toFixed(1)
	}: {
		values: number[];
		labels?: string[] | null;
		color?: string;
		height?: number;
		fmt?: (v: number) => string;
	} = $props();

	let canvas: HTMLCanvasElement | null = $state(null);
	let chart: Chart | null = null;

	function buildData() {
		return {
			labels: labels ?? values.map((_, i) => `#${i + 1}`),
			datasets: [
				{
					data: values,
					borderColor: color,
					backgroundColor: color + '22',
					fill: true,
					borderWidth: 2,
					pointRadius: 2,
					pointBackgroundColor: color,
					tension: 0.3
				}
			]
		};
	}

	onMount(() => {
		if (!canvas) return;
		chart = new Chart(canvas, {
			type: 'line',
			data: buildData(),
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: {
							label: (ctx) => fmt(ctx.parsed.y as number)
						}
					}
				},
				scales: {
					x: { display: false },
					y: { display: false }
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
