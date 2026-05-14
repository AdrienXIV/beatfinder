/**
 * Aide détaillée pour les "parties" de l'aperçu du plan d'action.
 * Affichée dans BriefHelpModal (réutilisé tel quel) au clic sur le bouton "?"
 * placé à côté des titres de partie dans ActionPlanModal.
 *
 * Mêmes conventions que brief-help.ts : langage non-jargonneux, exemples
 * concrets, avant/après quand pertinent.
 */

import type { BriefHelpEntry } from './brief-help';

export const ACTION_HELP: Record<string, BriefHelpEntry> = {
	'spectral-rings': {
		title: 'Profil spectral comparé',
		body: `
Deux anneaux côte à côte : le profil spectral de **ta source** (à gauche) et celui de **la cible** (à droite). Chaque anneau découpe le spectre audio en 6 bandes (du grave à l'aigu, de l'extérieur vers l'intérieur).

## Comment lire

Chaque couleur correspond à une bande :

- **Sub** (20-60 Hz) : sub-bass, à ressentir dans le ventre
- **Bass** (60-250 Hz) : kick, basse
- **Low-mid** (250-500 Hz) : corps des voix, low-end des snares
- **Mid** (500 Hz-2 kHz) : voix, leads
- **High-mid** (2-6 kHz) : présence, sibilance
- **High** (6-20 kHz) : air, hi-hats, cymbales

L'épaisseur de chaque anneau = le pourcentage d'énergie dans cette bande. Plus c'est épais, plus la bande est dominante.

## Ce que tu cherches

L'objectif est de **rapprocher visuellement ta forme de celle de la cible**. Si la cible a un sub très épais et ton anneau l'a fin, tu dois booster le sub. Si la cible a peu de high et toi beaucoup, tu dois réduire les aigus.

La liste d'actions en dessous donne les ajustements EQ concrets pour chaque bande qui a un écart significatif.

## Exemple

> **Avant :** ton anneau Sub fait 15%, celui de la cible 28%.
> **Action suggérée :** "Booster sub-bass : EQ shelf +2 dB autour de 50 Hz". Après application, ton anneau Sub s'épaissit et s'aligne sur la cible.
`,
	},

	'priority-donut': {
		title: 'Avancement par priorité',
		body: `
Camembert qui visualise ton **avancement** sur les 3 niveaux de priorité, en pourcentage d'actions cochées.

## Les 3 niveaux

- **High** (rouge) : actions à **fort impact** sur la cohérence avec la cible. Si tu ne fais rien d'autre, fais celles-ci. Souvent : matcher le LUFS, corriger un déséquilibre spectral majeur, choisir le bon BPM.
- **Medium** (jaune) : actions à **impact modéré**. Affinent le résultat. Ex : ajuster une bande spectrale secondaire, retoucher la durée du drop.
- **Low** (gris) : actions à **faible impact**, surtout des petits ajustements d'oreille. Optionnel.

## Comment l'utiliser

Coche les actions au fur et à mesure que tu les appliques dans ta DAW. Le donut se remplit en temps réel. L'état est **mémorisé localement par paire source→cible** : si tu rouvres ce plan plus tard, ton avancement est conservé.

## Stratégie recommandée

1. Commence par toutes les actions **High** (priorité 1)
2. Écoute en bypass A/B avec une track de la cible
3. Si ça colle, passe aux **Medium**
4. Si ça colle toujours, finis avec les **Low** au goût
`,
	},

	mastering: {
		title: 'Catégorie : Mastering',
		body: `
Les actions de cette catégorie concernent le **bus master** : le traitement final appliqué à ta track entière avant export. Influencent principalement le **volume perçu** et la **dynamique globale**.

## Métriques mesurées

- **LUFS** (*Loudness Units Full Scale*) : norme broadcast utilisée par tous les streamings (Spotify, Apple Music, YouTube). -14 LUFS = standard streaming, -10 LUFS = master poussé compétitif.
- **True peak (TP)** : niveau crête en dBFS. 0 dBFS = saturation. Au-dessus = inter-sample clipping.
- **Crest factor** : ratio peak/RMS. Élevé = peu compressé. Bas = compression marquée.
- **DR (Dynamic Range)** : contraste macro entre les sections fortes (drop) et calmes (intro).

## Outils habituels

- **Limiter** : pour pousser le LUFS sans dépasser le ceiling
- **Compressor** : pour réduire le crest factor (homogénéiser)
- **Saturator / clipper** : pour passer un peu de TP au-dessus de 0 dBFS sans audible distortion (pratique pro)

## Exemple

> **Avant :** ton master à -16 LUFS, la cible à -10 LUFS.
> **Action :** "Pousser le LUFS de -16 → -10". Tu ajoutes un limiter sur le master, gain input +6 dB, ceiling -0.5 dBFS. Ta track passe au niveau de la cible.
`,
	},

	mix: {
		title: 'Catégorie : Mix',
		body: `
Les actions de cette catégorie concernent l'**équilibre fréquentiel** de ta track : combien d'énergie dans chaque bande du spectre. Influencent le ressenti (sombre/brillant, lourd/aérien) et la lisibilité de chaque élément.

## Métriques mesurées

Les 6 bandes spectrales avec leur écart par rapport à la cible :

| Bande | Plage | Ce qu'on y trouve |
|---|---|---|
| Sub | 20-60 Hz | sub-bass long et tonal |
| Bass | 60-250 Hz | kick + basse |
| Low-mid | 250-500 Hz | corps voix, low snare |
| Mid | 500 Hz - 2 kHz | voix, leads |
| High-mid | 2-6 kHz | présence, attaques |
| High | 6-20 kHz | air, hi-hats |

## Outils habituels

EQ paramétrique 8 bandes (Ableton EQ8, FL Parametric EQ 2, FabFilter Pro-Q 3, Logic Channel EQ). Une bande EQ par déséquilibre détecté.

## Stratégie

- **Réduire** une bande dominante : EQ bell -2 à -4 dB à la fréquence centrale
- **Booster** une bande creuse : EQ bell +2 à +3 dB (ou shelf si extrémité du spectre)
- **Coupes propres** d'abord, **boosts** ensuite (la compensation par cut sonne plus naturelle)

## Exemple

> **Avant :** ton mid à 25%, la cible à 15%. Voix trop forte.
> **Action :** "Cut mid 500 Hz - 2 kHz : EQ bell -3 dB à 1 kHz". Après application, la voix prend moins de place et le low-end ressort.
`,
	},

	rhythm: {
		title: 'Catégorie : Rythme',
		body: `
Les actions de cette catégorie concernent le **tempo** et la **densité rythmique** : la vitesse de la pulsation et combien d'événements rythmiques se passent par seconde.

## Métriques mesurées

- **BPM** (*Beats Per Minute*) : vitesse de pulsation. 60 BPM = 1 battement par seconde.
- **Onset density** : nombre de débuts de notes par seconde. Mesure la densité rythmique perçue.
- **Beat consistency** : régularité de la grille (0 = très élastique, 1 = très régulière type machine).

## Outils habituels

- **Time-stretch** : pour changer le BPM d'une boucle sans changer la tonalité
- **Ajouter/retirer des hi-hats** : impacte l'onset density
- **Quantize** : impacte la beat consistency

## Stratégie

Le BPM est le plus important à matcher. Si la cible est à 90 BPM et ta source à 130 BPM, tes hi-hats à 130 sonneront frénétiques en comparaison. Soit tu fais un time-stretch global, soit tu construis le beat directement au BPM cible.

L'onset density est secondaire mais influence la "vibe" : un beat à hi-hats double-time sonne plus moderne / agressif qu'un beat avec un kick simple.

## Exemple

> **Avant :** ton BPM 130, la cible 95. Le track sonne speed.
> **Action :** "Aligner le BPM sur la cible (~95)". Soit tu refais le beat à 95 BPM, soit time-stretch -27% (en gardant la pitch).
`,
	},

	tonality: {
		title: 'Catégorie : Tonalité',
		body: `
Les actions de cette catégorie concernent la **gamme musicale** : la clé (note racine + mode) dans laquelle ta track est composée.

## Métriques mesurées

- **Note racine** : C, D, E, F, G, A, B (+ dièses/bémols). Ex : \`F#\`
- **Mode** : majeur (lumineux) ou mineur (sombre)
- **Vote 3/3** : indicateur de fiabilité — 3 algorithmes votent pour détecter la clé, 3/3 = très fiable

## Outils habituels

- **Pitch shifter** : pour transposer le mélo / le sample
- **MIDI transpose** : si la mélodie est jouée en MIDI
- **Composer directement** dans la bonne clé

## Pourquoi c'est important

Si la cible est à 85% en mineur racine F, et ta source en La majeur, ton mélo sonnera "à côté" du feel de la cible. Surtout si tu rajoutes des samples / textures issus de la cible — elles ne s'aligneront pas harmoniquement avec tes leads.

## Limites

La détection de tonalité a un plafond de fiabilité (~60-70% sur les musiques avec voix très traitée). Si le vote n'est pas 3/3, l'algorithme n'est pas sûr et l'action peut être à prendre avec précaution.

## Exemple

> **Avant :** ton mélo en La majeur, cible en Fa mineur.
> **Action :** "Transposer le mélo en Fa mineur". Avec un pitch shifter, descendre de 4 demi-tons (La → Fa) + changer le mode → ton mélo s'aligne harmoniquement avec la cible.
`,
	},

	structure: {
		title: 'Catégorie : Structure',
		body: `
Les actions de cette catégorie concernent l'**architecture temporelle** de ta track : combien de sections (intro / couplet / drop / pont / outro) et à quel moment tombe le drop principal.

## Métriques mesurées

- **Position du drop** : moment de plus haute énergie, exprimé en % du track
- **Nombre de sections** : combien de zones distinctes détectées
- **Durée médiane** : longueur typique des tracks de la cible

## Points de repère pour le drop

- **0-15%** : drop ultra-précoce, intro très courte (optimisé skip-rate streaming)
- **15-30%** : drop standard moderne
- **30-50%** : intro plus longue, narrative classique
- **> 50%** : drop tardif, build-up développé (style EDM mainstage)

## Outils habituels

- **Couper l'intro** : raccourcir une intro trop longue
- **Allonger le build-up** : pour un drop plus tardif
- **Restructurer les sections** : ajouter un pont, retirer un break

## Exemple

> **Avant :** ton track dure 4:00, drop à 1:30 (37%). La cible : drops à 25%.
> **Action :** "Coupe ton intro à 35s, drop à 25%". Ton hook arrive avant que l'auditeur skip.
`,
	},
};
