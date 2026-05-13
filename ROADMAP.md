# Beatfinder — Roadmap

État actuel : **V2.0 — features étendues**. Toutes les killer features livrées :
plan d'action 4 modes, presets standards, PDF Chromium fidélité 100% (4 styles),
radar triangulaire 2-5 sources, ML classifier de style, export DAW master chain
(markdown universel + .adg Ableton expérimental), onboarding 1er lancement.
Packaging desktop AppImage Linux 177 MB. CI cross-platform GitHub Actions prêt
à être branché (workflow YAML).

## Sprints livrés

### Sprint 1-3a — V1.6 backend (2026-04-30 → 2026-05-10)

Pipeline complet Spotify URL → tracks → YouTube DL → 6 analyzers → pattern → SQLite → brief markdown + CSV.

- 6 analyseurs : `tempo` (BPM + onset + correction anti-octave), `tonality` (consensus 3 voters : KS chroma_cens, KS chroma_cqt, madmom CNN), `energy` (RMS, LUFS BS.1770, true peak 4x oversampling, crest, DR p95-p10), `spectral` (centroid, rolloff85, 6 bandes), `structure` (HPSS + novelty + drop position), `timbre` (MFCC 13)
- Détection BPM bimodal via gap analysis, sous-clusters k-means + silhouette
- Top-root filtré sur tracks vote 3/3 (filtre fiabilité)
- CLI : `python -m backend.cli.pipeline "<URL>"`, `python -m backend.cli.compare <A> <B>`, `python -m backend.cli.db_inspect <id>`
- DB SQLite avec `Playlist`, `Track`, `PlaylistTrack`, `TrackAnalysis`, `PlaylistPattern`

### Sprint 3b — V1.6 UI SvelteKit (2026-05-11)

Backend FastAPI + frontend SvelteKit SPA, glue prod (un seul process Python sert /api + le static).

- Routes API complètes (playlists, jobs, reports, projects, compare)
- JobQueue in-memory mono-user, SSE stream pour progression
- 5 pages : dashboard, détail playlist (tabs brief/tracks/patterns), analyze, jobs, compare
- Feature D (upload local MP3/WAV) avec `local:{uuid}` prefix dans `spotify_id`

### Sprint 4 — V1.7 Plan d'action + Dataviz + Cache + Settings (2026-05-12)

- **Plan d'action 4 modes** : `backend/services/action_planner.py` règles métier rap FR/trap → `ActionItem` (category, priority, current, target, delta, unit, action, rationale, key). Endpoint unifié `GET /api/actions?from={id}&to={id}` (résolution Playlist OR Track via DB lookup). `ActionPlanModal.svelte` avec tabs Playlist | Track + drill-down + pastilles "déjà comparé". localStorage par paire `(from, to)` pour checkboxes persistées. Banner cohérence si BPM std>15 / mode 50/50 / sub std>0.15.
- **Dataviz** : `SpectralRing` (anneaux concentriques SVG), `BpmHistogram`, `PriorityDonut`, `SparkLine` Chart.js
- **Page `/playlists/[id]/styles/`** : 5 styles PDF (Editorial, Soft, Newspaper, Blueprint, Vinyl)
- **Page `/settings`** : Spotify creds + Cache disque (`cache_inspector.py` 5 catégories + flush)
- Banner globale "Spotify non configuré" tant que credentials absents
- 400 propre sur `/api/playlists/analyze` si Spotify pas configuré

### Sprint 5 — V1.7 polish UX (2026-05-12)

- Progression analyse fluide : `JobProgress.current` float, analyseur emit `on_step(key, label, fraction)` 14× par track
- Logs détaillés ~30 lignes par track avec tempo `time.sleep(0.08)`
- Terminal UI : fond noir, 3 dots orange qui pulsent, colorisation par préfixe
- Timestamps heure locale, drop cap retiré Editorial, bouton destructive bordure rouge

### Sprint 6 — V1.8 Desktop packaging (2026-05-12 → 2026-05-13)

- PyInstaller `beatfinder.spec` avec `collect_all` (librosa/numba/llvmlite/madmom/sklearn/scipy/...) + `collect_submodules('backend')` + uvicorn extras + frontend/build static
- Mode binaire détecté via `sys.frozen` / `sys._MEIPASS` → `DATA_DIR=~/.beatfinder/data`
- **AppImage** : `mksquashfs` direct zstd niveau 19, `-processors 2 -mem 1G`, concat avec runtime `AppImageKit/continuous/runtime-x86_64`. 459 MB dossier → **177 MB AppImage** (-18% vs 216 MB initial)
- **Build RAM optimisé** : `nice -n 19 ionice -c3` + `strip=True` + excludes tests (numpy/scipy/sklearn/librosa/numba)
- Mesures : Pic RAM mksquashfs ~1.4 GB delta (vs 3-4 GB freeze → -60%). Durée totale ~3 min
- Icône 5 barres EQ orange (bell-curve) sur fond noir arrondi
- `.desktop` + `install_appimage.sh` (avec `--purge` pour `~/.beatfinder/`) → menu Activities GNOME
- **Fenêtre native** via `chromium --app=URL --class=Beatfinder --user-data-dir=~/.beatfinder/.browser-profile`
- Watchdog `proc.wait()` → `os._exit(0)` quand la fenêtre se ferme

### Sprint 7 — V1.9 + V2 features (2026-05-13)

Tout livré dans la journée :

**V1.9 — features Pro**
- **Compared-with pour tracks comme sources** : route `GET /actions/sources` (scan O(N) global), pastilles dot vert + count dans la colonne Action de la table Tracks
- **Mode compare vs seuils fixes (presets)** : module `services/threshold_presets/` (loader JSON + lru_cache). 2 presets `rap-fr.json` / `rap-us.json` extraits des patterns réels DB. Route `GET /actions/presets`. `_load_source` reconnaît préfixe `preset:`. 3ème tab "Standards" dans `ActionPlanModal`. E2E : Kyu→preset:rap-fr donne 19 items / 9 high identique au baseline FR
- **PDF briefs via Chromium headless** : `report_generator/pdf.py` + route `GET /playlists/{id}/brief.pdf?style={editorial|soft|newspaper|blueprint}` (4 styles, Vinyl supprimé). Fidélité 100%. Bouton "Télécharger PDF" dans sidebar des styles. Polish print : fix bg noir (cause `color-scheme: dark` → forcer `light` en print), marges @page 1.5cm 1cm, `break-inside: avoid` ciblé, `break-before: page` sur sections clés (TECHNICAL REPORT Blueprint, "Le détail" Newspaper, "Tracks de référence" Soft via marker injecté côté BriefRenderer)

**V2.0 — features étendues**
- **Radar triangulaire 2-5 sources** : refactor `_load_source` → `services/source_loader.py` partagé. `services/multi_compare.py` (radar 6 bandes spectrales + 12 stats par axe). Route `GET /compare/multi?ids=A,B,C[,D,E]`. Page `/compare/multi` avec multi-select 5 max, chips colorées, radar Chart.js (snapshot $state pour Chart.js). E2E : Kyu 60% sub vs FR 32% vs US 47% visualisé
- **Onboarding 1er lancement** : `OnboardingWizard.svelte` 3 steps (bienvenue / config Spotify / première analyse). Trigger via localStorage `beatfinder:onboarded`, affiché si Spotify non-configuré. Force-trigger via `?onboarding=force`. Auto-redirige sur `/analyze?url=...`
- **ML classifier de style** : `services/style_classifier.py` (RandomForest 200 trees + StandardScaler, balanced). 15 features track-level. CLI `python -m backend.cli.train_classifier` (mapping `LABEL_MAPPING` éditable). Modèle persisté `data/models/style_classifier.joblib` (1.3 MB). Route `GET /api/style-predict?from={id}`. Badge "Style prédit" en haut page playlist détail. CV accuracy **74%** sur 2 classes (rap-fr 151 / rap-us 99). Affiche "prédiction incertaine" si top < 60%
- **Export DAW master chain** : `services/daw_export.py` mappe ActionItems → EQ8 (6 bandes) + Compressor (cible crest) + Limiter (cible LUFS). Routes `GET /actions/master-chain.md` (universel) et `.adg` (Ableton XML gzippé expérimental). 2 liens download dans la modal Plan d'action. Heuristique : ±1 pt d'énergie ≈ ±0.3 dB en bell, cap ±6 dB
- **CI cross-platform GitHub Actions** : `.github/workflows/build.yml` matrix 4 OS (ubuntu-22.04 / macos-14 arm64 / macos-13 Intel / windows-latest). Trigger sur tag `vX.Y.Z` ou manuel. Build complet par OS (apt/brew/choco ffmpeg, pip + madmom git, npm build, PyInstaller, package par OS). Job `release` crée auto une GitHub Release avec les 4 binaries
- **README usage final** : section A étendue avec download AppImage + chmod + pré-requis système (ffmpeg + browser Chromium ou Firefox), install/uninstall scripts (`--purge`), surcharge `DATA_DIR`
- **Fallback Firefox** : `_find_firefox_browser()` dans `backend/main.py`. Si aucun Chromium-like → tente `firefox --new-window` (fenêtre dédiée). Sinon `webbrowser.open()` ultime

**Polish UI** :
- Spectral colors palette : 6 bandes en gradient grave→aigu (rouge/orange/jaune/vert/cyan/violet) dans `lib/components/charts/spectral-colors.ts`. Anneaux SpectralRing + légendes utilisent ces couleurs
- Donut "Avancement par priorité" : `%` retiré du centre, mis dans le header `X/Y faits (Z%)` mono
- Légende anneaux : swatches colorés + label + valeur source→cible dans la modal Plan d'action
- Style Vinyl supprimé (5 styles → 4)

## En attente / non-fait

### Court terme (V1.8 finalisation)

- [ ] Tester binaire AppImage sur une machine vierge (sans `.venv` ni Python dev) — valide que les libs système suffisent (notamment ffmpeg + browser)
- [ ] **Packaging macOS** : nécessite un Mac (`build.command`). PyInstaller peut générer un `.app` bundle. AppImage n'existe pas sur Mac → `.dmg` ou `.app` distribué via zip. **Le workflow CI GitHub Actions le fait automatiquement** dès qu'Adrien push le projet et tagge.

### Moyen terme (V1.9 / V2 validation)

- [ ] **Test métier réel par Adrien** : remasteriser un de ses beats Kyu selon le plan d'action FR (LUFS +6 dB, sub -28 pts, mid +9.7 pts, centroid +1026 Hz), re-uploader, vérifier que les deltas se réduisent. Boucle de validation de la value-prop, seul item bloqué par Adrien lui-même.
- [ ] **Étendre le ML classifier** : analyser des playlists drill / lo-fi / trap → ajouter à `LABEL_MAPPING` → re-run `train_classifier`. Modèle plus discriminant + couvre les styles hybrides comme Kyu (actuellement 56/44 entre rap-fr/us — vrai positif vu son côté trap français).
- [ ] **Tester / itérer .adg Ableton** : ouvrir le fichier généré dans Live, voir si Live l'accepte. Si oui → étendre pour inclure les vrais devices Ableton (EQ8 / Compressor / Limiter pré-réglés). Si non → garder uniquement le markdown export.
- [ ] **Brancher le CI cross-platform** : `git init` + commit + push GitHub + premier tag `v2.0.0`. Premier run peut révéler des bugs (madmom Windows compile, libpython.so sur Linux runners). 1-2h de debug attendus.

### Long terme (V2.1+)

- [ ] **Refactor webview natif (Tauri)** : actuellement bloqué sur Ubuntu 20.04 par un conflit PPA libxml2 (sury vs Ubuntu officiel). Sur une nouvelle install ou Ubuntu 22.04+, devrait passer sans heurts. Apport : binaire totalement autonome (zero Chrome dependency), pertinent surtout pour distribution Windows. ~4-6h.
- [ ] **Monétisation** : si l'app sort du cadre perso. Plans : licence one-time Stripe (~15-25€), freemium cloud sync, open-source GPL + Patreon. Hors-code à 90% (legal, business, support, marketing).
- [ ] **Onboarding macOS/Windows** : actuellement le wizard onboarding marche pour Linux/Spotify. À tester sur les autres plateformes une fois le CI cross-platform actif et un user non-Linux.
- [ ] **Code signing macOS + Windows** : pour éviter SmartScreen / Gatekeeper warnings. Apple Developer ~100€/an + cert Windows ~250€/an. Required si distribution publique.

## Limitations connues

- **Numpy 2.x + madmom** : madmom officiel reste à `numpy<2`, mais sa branche `main` (qu'on utilise) marche avec numpy 2.4. Si numpy bouge significativement, vérifier que madmom compile encore.
- **Python 3.13/3.14** : numba et llvmlite peuvent ne pas suivre immédiatement. Rester sur **Python 3.12**.
- **Pas de packaging cross-OS** : PyInstaller ne cross-compile pas. Pour distribuer, faire 1 build par plateforme. **Le CI GitHub Actions résout ça** (workflow YAML prêt).
- **Mode dev** : `source .venv/bin/activate` casse Claude Code (security prompt). Toujours `./.venv/bin/<binaire>`.
- **Bundle taille** : 459 MB dossier / **177 MB AppImage** après optimisations (zstd + strip + excludes). Inhérent au stack (librosa + madmom + sklearn + scipy ≈ 350 MB de libs scientifiques après strip). Réduction sous 150 MB possible mais risquée (exclure submodules scipy précis, UPX risqué avec numba).
- **Watchdog Chromium** : si l'utilisateur tue Chrome via System Monitor, uvicorn ne s'arrête pas immédiatement. Léger délai. Acceptable.
- **Tauri Linux** : bloqué sur Ubuntu 20.04 par conflit PPA libxml2-dev vs PPA externe sury (PHP). Workaround = Ubuntu 22.04+, Fedora, ou downgrade libxml2 (risque casser PHP).
- **ML classifier** : 74% CV accuracy avec seulement 2 classes (rap-fr / rap-us). Améliorable en analysant plus de playlists de styles distincts (drill, lo-fi, trap).
- **Export .adg Ableton** : expérimental. Le XML respecte la structure publique connue mais sans test dans Live, validation incertaine. Le markdown reste le fallback fiable.
