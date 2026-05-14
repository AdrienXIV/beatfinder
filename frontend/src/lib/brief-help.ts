/**
 * Aide détaillée par section du brief — affichée dans BriefHelpModal au clic
 * sur le bouton "?" inséré à côté de chaque titre `h2` du brief.
 *
 * Le langage est volontairement non-jargonneux (cible : beatmaker non-initié)
 * et inclut des exemples + avant/après quand pertinents.
 *
 * Le matching titre → clé d'aide se fait via H2_TO_HELP_KEY (slug lowercase).
 */

export type BriefHelpEntry = {
	title: string;
	body: string;
};

export const BRIEF_HELP: Record<string, BriefHelpEntry> = {
	tldr: {
		title: 'TL;DR — session DAW',
		body: `
Le TL;DR (*Too Long; Didn't Read* = "trop long, j'ai pas lu") est un résumé express qui synthétise les chiffres clés en 5 lignes. Tu le lis en 30 secondes et tu sais par où commencer ta session de prod.

## Comment l'utiliser

Avant d'ouvrir ta DAW, lis ces 5 bullets dans l'ordre :

1. **BPM** : le tempo cible. Configure-le dans ton projet dès l'ouverture.
2. **Tonalité** : la clé majoritaire. Détermine ton mélo et tes basses.
3. **Master** : le volume LUFS à viser sur ton master final.
4. **Profil low-end** : combien d'énergie totale dans les graves (sub + bass).
5. **Drop** : à quel pourcentage du track placer le drop principal.

## Exemple

Si le TL;DR dit :
- BPM 92
- 70% minor, racine F
- Master -10 LUFS
- 65% sous 250 Hz
- Drop à 25%

→ Tu sais que tu produis à 92 BPM, en Fa mineur, avec un master limiter poussé, des basses très en avant, et un drop placé tôt (1ère minute si le track fait 3:30).
`,
	},

	tempo: {
		title: 'Tempo & rythme',
		body: `
Cette section quantifie la **vitesse** et la **densité rythmique** des tracks de la playlist.

## BPM (battements par minute)

Le BPM est la fréquence des pulsations rythmiques. Plus c'est haut, plus c'est rapide.

**Repères par genre :**
- 60-90 BPM : hip-hop classique, R&B
- 90-110 BPM : trap, soul moderne
- 110-140 BPM : house, drill, drum'n'bass lent
- 140-180 BPM : techno, hardstyle, breakcore

**Chiffres affichés :**
- **Médian** : la valeur centrale (50% des tracks au-dessus, 50% en-dessous). Plus fiable que la moyenne car insensible aux extrêmes.
- **Cluster 50% (IQR)** : la plage qui contient les 50% du milieu. Utile pour choisir un BPM "consensuel".
- **Range min-max** : si très large (ex. 70-180), la playlist mélange plusieurs vitesses.

## Onset density

Le nombre de "débuts de notes" par seconde — autrement dit, à quel point la grille rythmique est remplie.

- < 2 onsets/s : rythme lâche (ambient, lo-fi)
- 2-4 onsets/s : rythme standard
- 4-6 onsets/s : rythme dense (hi-hats actifs, percussions chargées)
- > 6 onsets/s : très dense (rolls, percussions rapides)

## Beat consistency

Indicateur de 0 à 1 qui mesure si la grille rythmique est régulière (machine, sampler) ou élastique (musique jouée live).

- 0.9+ : grille très régulière (productions électroniques)
- 0.7-0.9 : grille majoritaire avec quelques variations (groove humain léger)
- < 0.7 : grille très élastique (jeu live, jazz)

## Avant / après

> **Avant :** tu fais un beat à 140 BPM, mais la playlist tape à 95 BPM médian. Ton beat sonnera "speed" comparé aux références.
> **Après :** tu baisses à 95 BPM, le beat colle au feel de la playlist.
`,
	},

	tonality: {
		title: 'Tonalité',
		body: `
Cette section identifie la **gamme musicale** (clé + mode) dominante dans la playlist.

## Clé musicale : c'est quoi

Une clé est composée de deux éléments :
- **Une note racine** : Do, Ré, Mi, Fa, Sol, La, Si (ou notation anglaise C, D, E, F, G, A, B + dièses/bémols).
- **Un mode** : majeur ou mineur.

Exemples : "Do mineur" (\`C minor\`), "La majeur" (\`A major\`), "Fa# mineur" (\`F# minor\`).

## Mineur vs majeur — la différence à l'oreille

- **Mineur** : ambiance sombre, mélancolique, dramatique. 90%+ du rap, drill, trap, R&B sombre.
- **Majeur** : ambiance lumineuse, joyeuse, "uplifting". Pop, gospel, plein de morceaux d'été.

Si la playlist est à 85% en mineur, ton mélo en majeur sonnera décalé.

## Racine dominante

C'est la note la plus fréquente comme tonique. Si "F" domine à 30%, beaucoup de tracks sont en Fa mineur ou Fa majeur.

Écrire dans la même clé permet de mixer facilement les samples / textures issus de plusieurs tracks de référence sans qu'elles se battent harmoniquement.

## Fiabilité / vote 3/3

Beatfinder utilise 3 algorithmes différents pour détecter la clé (Krumhansl-Schmuckler chroma_cens + chroma_cqt + madmom CNN). Quand les 3 sont d'accord, c'est "vote 3/3" = très fiable. Sinon (vote 2/3 ou 1/3), la clé est incertaine.

Pourquoi cette incertitude ? Sur les musiques avec voix très traitée (autotune), basses très saturées, ou pas de progression d'accords claire, les algos ont du mal. Le plafond observé en pratique est ~60-70% de tracks "vote 3/3" même sur des playlists pros.

## Avant / après

> **Avant :** tu composes un mélo en La majeur. La playlist est à 85% en Fa mineur, racine F dominante. Au mixdown, ton mélo dans la mauvaise clé sonne "à côté" des références.
> **Après :** tu transposes en Fa mineur. Le mélo se fond avec le feel de la playlist.
`,
	},

	energy: {
		title: 'Énergie & mastering',
		body: `
Cette section mesure deux choses : le **volume perçu** de ta musique et sa **dynamique** (le contraste entre les passages calmes et forts).

## LUFS, c'est quoi

LUFS = "Loudness Units Full Scale". C'est la mesure officielle utilisée par toutes les plateformes de streaming (Spotify, Apple Music, YouTube, Tidal) pour comparer le volume entre les tracks. Plus le chiffre est proche de 0, plus c'est fort.

**Repères :**
- \`-23 LUFS\` : très calme (norme broadcast TV)
- \`-14 LUFS\` : standard streaming Spotify
- \`-10 LUFS\` : master agressif, productions modernes compétitives
- \`-7 LUFS\` ou plus : extrêmement compressé (limiteur poussé à fond)

## Pourquoi c'est important

Si ton master est à -20 LUFS et la playlist de référence à -10 LUFS, ta track sonnera **deux fois moins forte** quand elle passera juste après dans une queue Spotify. Le streaming normalise mais ramène vers -14 LUFS — ta track devient plate, sans punch, comparée aux autres.

## True peak (TP)

Le niveau maximum atteint par le signal, mesuré en dBFS (dB Full Scale). 0 dBFS = saturation théorique.

- TP < -1 dBFS : headroom propre, pas de clipping
- TP entre -1 et 0 dBFS : à la limite, inter-sample clipping possible
- TP > 0 dBFS : clipping confirmé (signature des masters poussés modernes)

## Crest factor & dynamic range

- **Crest factor** : écart entre les pics et la moyenne RMS. Élevé (>14 dB) = peu compressé, respire ; bas (<8 dB) = compression molle, "écrasé".
- **DR (p95-p10)** : contraste macro entre les sections fortes (drop) et calmes (intro). DR=20 dB → breaks marqués ; DR=8 dB → dense en permanence.

## Avant / après

> **Avant :** mix propre, dynamique large (DR=14 dB), master à -18 LUFS.
> **Après :** ajout d'un limiter, push à -11 LUFS (accepte un peu de pumping), la track tient face aux références.
`,
	},

	spectral: {
		title: 'Profil spectral',
		body: `
Le profil spectral, c'est comment l'**énergie sonore se répartit** entre les graves et les aigus. On découpe le spectre audio en 6 bandes pour analyser fin.

## Les 6 bandes

| Bande | Plage | Ce qu'on y trouve |
|---|---|---|
| **Sub** | 20-60 Hz | Sub-bass (basses synthétiques longues). Ressenti dans le ventre. |
| **Bass** | 60-250 Hz | Kick, basse, contre-basse. Le "poids" de la prod. |
| **Low-mid** | 250-500 Hz | Corps des voix, low-end des snares, premiers harmoniques des basses. |
| **Mid** | 500 Hz - 2 kHz | Voix, leads, mélodies principales. |
| **High-mid** | 2-6 kHz | Présence, attaques, sibilance des voix. |
| **High** | 6-20 kHz | Air, cymbales, hi-hats brillants. |

## Lire les pourcentages

Chaque bande affiche son pourcentage de l'énergie totale (la somme des 6 ≈ 100%).

- Bande > 30% : **dominante**
- Bande < 5% : **discrète**

## Profils typiques

- **Low-end dominant** : sub + bass > 60%. Mix orienté basses, top retenu.
- **Mid-centric** : mid > 25%. Voix très exposée, mix "frontal". Pop, R&B.
- **Bright / aéré** : high > 8%. Hi-hats et cymbales généreux. EDM, drum'n'bass.
- **Équilibré** : aucune bande ne dépasse 25%. Mastering audiophile, jazz, classique.

## Centroid et flatness

- **Centroid** (en Hz) : "centre de gravité" du spectre. Bas = sombre ; haut = brillant.
- **Flatness** (0 à 1) : ratio bruit vs tonal. Bas = très tonal (production léchée) ; haut = bruit (hats, ambiance, percussions).

## Action mix par bande

À droite du tableau spectral, tu vois une suggestion EQ par bande. Exemple si ta mid est à 25% : "voix très exposée, mix sec et frontal" → si tu veux ce résultat, n'étouffe pas la voix au mix.

## Avant / après

> **Avant :** ta prod a sub à 15% et high à 12%. Le ton est plutôt brillant, sans poids.
> **Après :** tu boost le sub à 25% (sub-bass long, sidechain marqué) et tu shelf down le top à 6%. La track gagne en chaleur et colle au profil de la playlist.
`,
	},

	structure: {
		title: 'Structure',
		body: `
Cette section analyse l'**architecture temporelle** des tracks : combien de sections (intro / couplet / drop / pont / outro) et à quel moment tombe le drop principal.

## Nombre de sections

Beatfinder détecte automatiquement les frontières entre sections via une analyse de similarité (chaque seconde du track est comparée aux autres, et un "changement" est détecté quand le timbre / l'énergie change brutalement).

- **4-6 sections** : structure simple (intro / drop / break / drop / outro)
- **7-10 sections** : structure standard (intro / couplet / drop / pont / 2e couplet / drop / outro)
- **10+ sections** : structure très découpée (breaks fréquents, transitions multiples)

## Position du drop

Le drop principal est le moment de plus haute énergie. Sa position est exprimée en % du track.

- **0-15%** : drop ultra-précoce. Optimise le "skip-rate" streaming (les listeners zappent dans les 30 premières secondes).
- **15-30%** : drop standard moderne. Intro courte, on entre dans le vif vite.
- **30-50%** : intro plus longue, narrative classique.
- **> 50%** : drop tardif. Build-up développé (style EDM mainstage).

## Durée

La durée médiane des tracks. Varie selon le genre :
- 2:00-2:30 : tracks courts (productions optimisées streaming)
- 3:00-3:30 : standard radio
- 4:00+ : tracks longs (rock, électronique, ambient)

## Avant / après

> **Avant :** ton beat dure 4:00, drop à 1:30 (37%). La playlist de référence est à 2:45 médian avec drop à 25%.
> **Après :** tu coupes ton intro à 35s, drop à 25% (= 40s sur 2:45). Le hook arrive avant que l'auditeur skip.
`,
	},

	'to-copy': {
		title: 'À copier',
		body: `
Cette section liste les **patterns que tu peux directement reproduire** dans ta prod pour rester dans le style de la playlist. Ce sont des règles dérivées des médianes et des dispersions des features.

## Lecture

Chaque bullet est de la forme : **"Métrique cible — valeur — interprétation"**.

Exemple :
> **BPM cible 92, cluster typique 88-98**

→ Lance ton projet à 92 BPM. Si tu veux varier, reste entre 88 et 98 (cluster du milieu de la playlist).

## Types de règles

- **Tempo / clé** : valeurs centrales à viser (BPM, mode majeur ou mineur, racine).
- **Master** : niveau LUFS à atteindre + comportement TP (clipping accepté ou pas).
- **Spectral** : pourcentages de sub / bass à reproduire pour matcher le profil.
- **Structure** : position du drop, densité rythmique.

## À quoi ça sert concrètement

Quand tu attaques un nouveau projet, garde cet onglet ouvert dans un coin. Chaque décision peut être validée par référence à la liste :

> "Je mets le drop à 1:00 sur un track de 3:00, donc 33%. Hors zone 15-30%, mais 33% reste raisonnable."
> "Je vais master à -14 LUFS. La playlist tape à -10 LUFS, donc je perds en compétitivité. Je dois pousser à -11 LUFS minimum."

## Limites

Les règles sont des **moyennes statistiques**, pas des lois absolues. Si la playlist est très hétérogène (gros écart-type), une règle "BPM 92 médian" peut cacher 2 sous-clusters (ex. 70 + 110). Regarde la section "Sous-clusters détectés" pour ça.
`,
	},

	'to-avoid': {
		title: 'À éviter',
		body: `
Cette section est le miroir de "À copier" : ce sont les patterns **incompatibles** avec le style de la playlist. Ils sortiraient ta track du registre.

## Lecture

Chaque bullet est de la forme : **"Métrique hors-zone — valeur seuil — conséquence"**.

Exemple :
> **Master < -16 LUFS sera perçu comme calme à côté de cette playlist (qui tape à -10)**

→ Si tu masters à -18 LUFS, ta track sonnera deux fois moins fort que les autres. Le streaming normalise, mais la sensation de "punch" sera plus faible.

## Types de pièges

- **BPM hors zone** : tempo très éloigné du cluster central → sortira du flow.
- **Mode majeur si playlist mineure** (ou inverse) : sonnera "joyeux" dans un univers sombre, ou vice versa.
- **Sur-représentation du mid** : voix qui masque les basses → mix daté ou amateur.
- **Top-end discret / brillant** : aigus pas alignés avec le style (rare ou trop forts).
- **LUFS trop bas / DR trop large** : master pas assez compétitif sur les plateformes streaming.
- **Crest trop bas** : compression molle, manque de punch.

## À quoi ça sert concrètement

Avant de finaliser, balaye cette liste pour identifier les drapeaux rouges :

> "Mon master est à -16 LUFS. La liste dit '< -14 perçu comme calme'. Je dois remaster en poussant 2-3 dB de plus."

## Limites

Les seuils sont contextualisés à la playlist analysée. Si tu compares à une playlist très "hot" (style competitive), les seuils LUFS seront stricts. Si tu compares à une playlist audiophile ou jazz, ils seront plus laxes.
`,
	},

	subclusters: {
		title: 'Sous-clusters détectés',
		body: `
Cette section apparaît uniquement quand Beatfinder détecte que ta playlist **mélange plusieurs sous-styles distincts**. Si elle est absente, la playlist est jugée homogène (un seul style dominant).

## C'est quoi un sous-cluster

Imagine que ta playlist "Top hits 2026" contient :
- 80 tracks de trap à 90 BPM, master -10 LUFS
- 60 tracks de house à 125 BPM, master -8 LUFS

Si on prend la médiane brute, on obtient BPM=107 (au milieu : inutile, aucune track ne tape vraiment à ce tempo). Et un mélange aberrant des autres features.

Le sous-clustering sépare automatiquement ces 2 sous-groupes via *k-means* + *silhouette score*. Tu vois alors 2 clusters distincts, chacun avec ses propres médianes et ses propres tracks.

## Quand cette section apparaît

- Silhouette score > 0.10 (= les sous-groupes sont assez distincts pour être pertinents)
- Variance suffisante sur les features clés (BPM, LUFS, DR, bandes spectrales, drop, centroid)

Si silhouette < 0.10 : la playlist est jugée continue stylistiquement → section absente.

## Comment l'utiliser

Quand tu vois plusieurs clusters, **choisis ton cluster cible avant de produire**. Sinon tu vises une moyenne qui ne correspond à aucune track.

## Avant / après

> **Avant :** tu prends le BPM médian 107 (mélange trap + house) → ton beat ne ressemble à rien.
> **Après :** tu choisis le cluster "trap 90 BPM" → tu copies les médianes spécifiques à ce cluster.

## Top artistes par cluster

Beatfinder liste aussi les artistes les plus représentés de chaque cluster. Utile pour identifier le sous-style ("ah OK, cluster 1 = PNL/Booba/Damso = drill FR sombre").
`,
	},

	'tracks-ref': {
		title: 'Tracks de référence (fit_score)',
		body: `
Cette table liste les tracks de la playlist triées par leur **fit_score** — un indicateur de représentativité.

## Le fit_score, c'est quoi

Pour chaque track, on compare ses features (BPM, LUFS, bandes spectrales, drop, etc.) au pattern global. Le fit_score = **% de features qui tombent dans le cluster central (p25-p75) de la playlist**.

- **fit = 100%** : la track est au cœur du pattern, dans chaque feature.
- **fit = 50%** : moitié des features collent, moitié sont en périphérie.
- **fit = 0%** : la track est un outlier total (style très différent du reste).

Les features ne sont pas toutes pondérées pareil :
- BPM : poids 1.5 (très important)
- LUFS, bandes spectrales : poids 1.0
- DR, centroid : poids 0.5-0.7

## À quoi ça sert

**Écoute les top 3-5** comme références principales. Ce sont les tracks qui incarnent le mieux ce que la playlist "est en moyenne". Tes meilleurs étalons quand tu mixe ta prod.

**Ignore le bottom 5** pour t'inspirer du style — ce sont les outliers, ils ne représentent pas le centre de la playlist.

## Limites

Le fit_score est une statistique, pas un jugement de qualité. Une track avec fit=30% peut être excellente — elle est juste atypique dans cette playlist.

## Exemple

> Playlist "Top Rap FR" :
> - **fit 95%** : track avec BPM 92, LUFS -10, sub 25%, drop 22% (= moyenne quasi exacte de la playlist)
> - **fit 40%** : track avec BPM 145 (= dérapage drill rapide), reste dans la moyenne sur les autres features

Tu vas écouter les fit 95% pour caler ton beat, et oublier les fit 40% pour cette session.
`,
	},

	methodology: {
		title: 'Méthodologie',
		body: `
Cette section documente les **outils et choix techniques** que Beatfinder utilise pour calculer les chiffres affichés. Utile pour comprendre les limites et la fiabilité des résultats.

## Pipeline complet

1. **Spotify Web API** : récupère la liste des tracks (titres, durées, artistes).
2. **YouTube (yt-dlp)** : télécharge l'audio (la version officielle quand elle existe — chaîne "Topic", Vevo, lyrics video).
3. **librosa** : analyse du signal audio (BPM, onset detection, spectre, structure).
4. **pyloudnorm** : mesure des LUFS selon la norme broadcast ITU BS.1770-4.
5. **madmom CNN** : réseau de neurones convolutif pour détecter la tonalité (entraîné sur le dataset GiantSteps).

## Tonalité — consensus 3 voters

Pour la clé, Beatfinder ne fait pas confiance à un seul algorithme. Trois méthodes votent :

- **KS chroma_cens** : Krumhansl-Schmuckler appliqué sur le chroma_cens (chroma normalisé à long terme).
- **KS chroma_cqt** : même algo mais sur chroma_cqt (transformée Q-constant, plus précise sur les aigus).
- **madmom CNN** : modèle deep learning.

Si les 3 méthodes sont d'accord (vote 3/3), on a très haute confiance. Sinon la clé est marquée "uncertain". Le top-root affiché dans le brief est calculé sur les tracks vote 3/3 uniquement.

**Plafond pratique :** ~60% de tracks vote 3/3 sur les musiques avec voix très traitée (autotune) et basses synthétiques tonales. Les algos ne peuvent pas trancher correctement quand la fondamentale du sub concurrence la mélodie.

## BPM — correction anti-octave-error

\`librosa.beat.beat_track\` peut se tromper d'une octave (annoncer 70 BPM au lieu de 140, ou vice versa). Beatfinder applique une correction : si le BPM tombe hors d'une zone "musicale" (~50-200), on multiplie/divise par 2 jusqu'à rentrer.

La détection bimodale (2 BPM dominants distincts dans la playlist) utilise une analyse de gap (≥ 20 BPM entre 2 modes, vallée ≤ 30% du pic).

## fit_score

Le fit_score d'une track = % de features dans le cluster central (p25-p75) du pattern. Pondéré ainsi :

- BPM : 1.5
- LUFS, sub, bass, low_mid : 1.0
- DR, mid, centroid : 0.5-0.7
- TP, crest, high_mid, high, drop_position : 0.5

## Sous-clusters

k-means + silhouette score > 0.10. Seuil bas car les playlists varient souvent en continuum stylistique plutôt qu'en groupes nets. None = playlist homogène.

## DR vs crest_factor

- **DR (p95-p10)** : contraste macro entre les sections fortes (drop) et calmes (intro). Évalue la dynamique structurelle.
- **Crest factor** : ratio peak/RMS local. Évalue la compression réelle du master.

Les deux sont complémentaires : un master peut être très compressé localement (crest bas) tout en gardant un grand contraste intro/drop (DR élevé), ou l'inverse.
`,
	},
};

/**
 * Mapping du titre `h2` normalisé → clé dans BRIEF_HELP.
 * Le matching se fait sur lowercase + trim. Les titres dans le brief markdown
 * peuvent contenir des préfixes/suffixes (ex. "Tracks de référence (triées par
 * fit_score)") qu'on capture via `startsWith`.
 */
export const H2_TO_HELP_KEY: { match: string; key: string }[] = [
	{ match: 'tl;dr', key: 'tldr' },
	{ match: 'tempo', key: 'tempo' },
	{ match: 'tonalité', key: 'tonality' },
	{ match: 'énergie', key: 'energy' },
	{ match: 'profil spectral', key: 'spectral' },
	{ match: 'structure', key: 'structure' },
	{ match: 'à copier', key: 'to-copy' },
	{ match: 'à éviter', key: 'to-avoid' },
	{ match: 'sous-clusters', key: 'subclusters' },
	{ match: 'tracks de référence', key: 'tracks-ref' },
	{ match: 'méthodologie', key: 'methodology' },
];

export function findHelpKey(h2Title: string): string | null {
	const normalized = h2Title.toLowerCase().trim();
	for (const { match, key } of H2_TO_HELP_KEY) {
		if (normalized.startsWith(match)) return key;
	}
	return null;
}
