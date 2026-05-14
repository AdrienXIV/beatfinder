<script lang="ts">
	/**
	 * Bloque le scroll du `<body>` quand `open` est `true`.
	 * Restaure l'ancienne valeur de `overflow` à la fermeture / au démontage.
	 *
	 * Utilisable depuis n'importe quelle modale / popup :
	 *   <ScrollLock open={isOpen} />
	 *
	 * Le composant n'a pas de template — juste un side-effect. Le `<dialog>`
	 * natif HTML5 ne lock pas systématiquement le scroll sur tous les browsers
	 * (Safari notamment), d'où ce composant.
	 */
	let { open }: { open: boolean } = $props();

	$effect(() => {
		if (open) {
			const prev = document.body.style.overflow;
			document.body.style.overflow = 'hidden';
			return () => {
				document.body.style.overflow = prev;
			};
		}
	});
</script>
