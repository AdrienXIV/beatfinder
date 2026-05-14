# Beatfinder — Roadmap

État actuel : **V2.1.0 — sessions guidées + corrections track + auto-update**.
Repo passé public sur `github.com/AdrienXIV/beatfinder` (all rights reserved
sans LICENSE). Banner UI auto-détecte les nouvelles releases GitHub. Sessions
de production avec wizard 3 étapes (cible → ambiance → analyse) et état
draft/locked pour figer la référence. Modal de correction BPM/Key sur les
tracks incertaines avec propagation automatique aux playlists et sessions
actives. Migrations DB rétrocompatibles via `PENDING_COLUMN_MIGRATIONS` au
boot (zéro Alembic).

État précédent : V2.0.14 — distribution cross-platform livrée (CI GitHub
Actions actif, 3 binaires natifs Linux/Mac/Windows, validation user Quentin).

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

### Sprint 8 — V2.0.14 distribution cross-platform (2026-05-13 → 2026-05-14)

Init repo Git + push sur `github.com/AdrienXIV/beatfinder` (privé) + workflow
CI cross-platform actif. 14 tags itératifs pour debugger tous les pièges
multi-OS, version finale stable. Quentin (M4 Pro Tahoe) valide en bout-en-bout
côté Mac.

**Init repo + premier push**

- `.gitignore` durci : `data/settings.json` (Spotify creds) + `data/reports/`
  + `data/*.log` + `.claude/` (config dev perso) ajoutés
- 165 fichiers commits (sans secrets), branche `main`, remote SSH
- Cleanup historique : tous les essais ratés (v2.0.0 → v2.0.13) supprimés
  de GitHub. Seul `v2.0.14` reste comme Latest

**CI debug — bugs résolus en cascade (chacun = 1 tag)**

- **PyInstaller `strip=True`** corrompait l'alignement ELF de
  `libscipy_openblas64_*.so` → `ImportError: ELF load command address/offset
  not properly aligned` même hors AppImage. Fix : `strip=False` (+120 MB
  sur le dist/)
- **AppImage zstd + squashfuse 0.5.2 Ubuntu 20.04** : `fuse: memory
  allocation failed`. Fix : runtime `AppImageKit/continuous` (stable) +
  compression `xz` sans filtre `-Xbcj x86` (qui désalignait openblas pareil)
- **`npm ci` strict sur runners macOS/Windows** : Tailwind v4 a des
  `@tailwindcss/oxide-wasm32-wasi` optionalDeps emnapi non listées dans
  le lock généré sur Linux. Fix : `npm install` à la place (moins strict)
- **chart.js manquant des deps** : 4 fichiers Svelte l'importaient mais
  jamais ajouté à `package.json`. Marchait localement par chance. Fix :
  `npm install chart.js` proprement
- **Pool runners macOS Intel (macos-13) saturé** côté GitHub Actions :
  job queued 27+ min sans démarrer. Fix : retirer macos-13 du matrix
  (gardé macos-14 arm64 only)

**macOS — bundle .app natif + zéro friction user**

- Generate `Beatfinder.icns` à la volée dans le workflow CI via `sips`
  (multi-resolutions) + `iconutil` (compile iconset) depuis le PNG 1024px
  source. `gen_icon.py` étendu pour produire 256/512/1024
- PyInstaller `BUNDLE` block conditionnel `sys.platform == 'darwin'` →
  vrai `Beatfinder.app` avec `Info.plist` (CFBundleName, Identifier
  `com.adrienmaillard.beatfinder`, etc.), `console=False` côté Mac pour
  pas pop Terminal au lancement
- **Codesign ad-hoc** (`codesign --force --deep --sign -`) dans le workflow
  pour signer toutes les `.dylib`/`.so` + le bundle : sans ça macOS Sonoma+
  refuse de charger les libs ("library load disallowed by system policy")
- **Détection Chrome/Brave/Edge sur Mac + Windows** : `shutil.which()`
  cherchait dans `$PATH` mais Chrome est dans `/Applications/*.app/...`
  (jamais dans `$PATH`). Sans ce fix l'app fallback sur Safari avec un
  onglet URL visible. Maintenant fenêtre `--app` dédiée propre
- **Watchdog Chrome via `pgrep`** sur Mac (vs `proc.wait()` qui retournait
  130ms après le démarrage car Chrome se détache via XPC). On surveille
  un process Chrome avec notre `--user-data-dir` toutes les 2s, shutdown
  quand plus aucun
- **ffmpeg + ffprobe bundlés** dans `Contents/MacOS/` via copie depuis
  brew + `dylibbundler -of` (overwrite files only) qui bundle les dylibs
  externes (libavformat, libswscale, libcrypto, etc.) dans
  `Contents/Frameworks/` + rewrite des paths en
  `@executable_path/../Frameworks/`. **Zéro `brew install ffmpeg` côté user**.
  Détection robuste dans `youtube.py` : bundle local → `/opt/homebrew/bin`
  → `/usr/local/bin` → `$PATH`
- **DMG au lieu de zip** : `hdiutil create -format UDZO` produit une
  Disk Image qui préserve symlinks PyInstaller, permissions UNIX, xattrs,
  resource forks (que ditto ET zip standard cassaient). Inclut un alias
  `/Applications` pour drag-and-drop. UX classique macOS (Slack/VS Code)
- Pattern `*.dmg` ajouté au pattern d'upload de `softprops/action-gh-release`
  (oublié initialement, le DMG était dans les artifacts mais pas attaché
  à la Release)

**Bugs critiques évités après livraison**

- `dylibbundler -od` (overwrite-dir) WIPE le dossier `Frameworks/`
  entier avant de copier ses dylibs. PyInstaller y avait mis
  `Python.framework`, `numpy`, `sqlalchemy`, etc. → tout détruit, app
  crashait avec `Failed to load Python shared library`. Fix : `-of`
  (overwrite-files, fichier par fichier)
- Conflit avec `libcrypto.3.dylib` déjà bundlée par PyInstaller via
  `cryptography` Python → résolu par `-of`

### Sprint 9 — V2.1.0 sessions guidées + corrections track + auto-update (2026-05-14 → 2026-05-15)

Grosse session de 7 livrables coordonnés :

**Sessions de production guidées**
- Nouveau modèle `CreativeSession` (target_kind=playlist|track, target_ref, target_pattern_json, ambiance_json, plan_md, archived, **is_locked**, **locked_at**) + `SessionVersion` (audio_path, features_json, fit_score) dans `backend/domain/models.py`
- Endpoints CRUD `/sessions/*` (`backend/api/routes_sessions.py`) : POST create, GET list, GET detail (avec `target_track` ou `target_tracks` enrichis), POST `/lock` (fige la cible + régénère le pattern target), POST `/unlock`, POST `/versions` (upload + auto-analyse SSE), DELETE (cleanup tracks orphans)
- État draft/locked : tant que la session n'est pas verrouillée, la cible peut être corrigée. Au lock, `_regenerate_target_pattern()` fige le pattern (immune aux changements ultérieurs sur les tracks d'origine)
- Wizard 3 étapes côté UI (`SessionWizardModal.svelte`) : choix cible (playlist ou track) → ambiance facultative → analyse auto avec stream SSE de progression
- Page `/sessions/[id]` complète (draft : encart cible avec bouton ⚠/✎/✓ + correction inline / locked : plan_md + versions + graph fit_score à venir)
- Helper `generate_session_brief(target_pattern, target_name, ambiance)` (`backend/services/session_brief.py`) gère 2 formats top_root (playlist agrégée vs track wrapped en `{note} {mode}`)
- CLI `python -m backend.cli.track_pipeline` pour analyser une track isolée

**Corrections BPM/Key sur les tracks incertaines**
- Nouveau modèle `TrackOverride` (track_id PK FK + bpm + key_note + key_mode) dans `backend/domain/models.py`
- Module `backend/services/track_overrides.py` :
  - `apply_overrides(features, override)` : merge immuable (deepcopy) override sur les features ML
  - `bpm_alt_hypotheses(bpm)` : retourne 4 alternatives (×2, /2, ×1.5, /1.5) pour l'UI
  - `compute_confidence(features)` : retourne `(low: bool, reasons: list[str])` selon 4 critères (madmom score < 0.85, BPM out of [60,130] avec onset>4 → triplet/half-time suspect, vote tonality <3/3, etc.)
  - `regenerate_pattern_for_playlist()` + `regenerate_playlist_patterns_for_track()` : propage le correctif à TOUTES les playlists contenant cette track
  - `propagate_override_to_active_sessions()` : régénère le `target_pattern_json` des sessions non lockées qui ciblent cette track
- Modal `TrackCorrectionModal.svelte` : suggestions BPM cliquables + clavier note/mode, state `bpm: number | null` (fix Svelte 5 `bind:value` sur `<input type="number">` qui coerce string→number)
- Badge ⚠ jaune côté UI sur les tracks marquées incertaines

**Auto-update via GitHub Releases**
- Module `backend/services/update_check.py` : appel `https://api.github.com/repos/AdrienXIV/beatfinder/releases/latest` avec timeout 3s, retourne `UpdateCheck` dataclass (current, latest, update_available, release_url, release_notes, published_at). Fail silencieux (réseau down → pas de notif)
- Endpoint `GET /version/check` (séparé de `/settings/status` car appel réseau lent)
- Banner UI dans `+layout.svelte` au-dessus du contenu : cache localStorage 12h + dismiss par version (`beatfinder:update-dismissed:{vX.Y.Z}`)
- Première intégration testable après le tag v2.1.0 (sera notifié aux users sur v2.0.14)

**Single-instance guard macOS**
- Bug : double-clic sur l'icône Dock alors que l'app tourne déjà → Chrome ouvre une fenêtre régulière sur Google (Chrome refuse un `--app=URL` duplicate avec `--user-data-dir` déjà occupé)
- Fix : `_is_port_in_use(host, port)` via socket bind test + `_focus_existing_window()` via AppleScript pour focus la fenêtre Chrome existante (filtre sur titre "Beatfinder")
- `main()` exit immédiatement si port déjà bind → pas de 2e backend

**Migrations DB rétrocompatibles**
- `PENDING_COLUMN_MIGRATIONS: tuple[tuple[str, str, str], ...]` déclaratif dans `backend/db.py` (table, column, SQL)
- `_migrate_columns(engine)` : `PRAGMA table_info` → si colonne manquante → `ALTER TABLE ADD COLUMN`. Idempotent
- Appelé au boot dans `init_db()` après `create_all()`
- Cette release : ajoute `is_locked` (BOOLEAN DEFAULT 0 NOT NULL) et `locked_at` (DATETIME) sur `creative_sessions` sans casser les DB users qui auraient déjà des sessions

**Brief help modal + Action help contextuel**
- `frontend/src/lib/brief-help.ts` : 11 entrées pédagogiques (LUFS, crest, DR, sub, low-mid, ...) avec markdown rendu
- `frontend/src/lib/action-help.ts` : 7 entrées pour la modal Plan d'action
- Modal `BriefHelpModal.svelte` (60vw, scroll lock body, markdown rendu)
- Composant générique `ConfirmDialog.svelte` (520px) pour les confirms destructives (unlock, delete session)
- Composant `ScrollLock.svelte` (effect body overflow hidden) réutilisable

**Bugs résolus en cours de route**
- **Datetime UTC affiché en heure locale -2h** : SQLite perd `tzinfo` → ISO sans suffixe → `new Date()` interprète comme local. Fix dans `frontend/src/lib/utils.ts` : `parseIsoAsUtc(iso)` ajoute "Z" si pas de timezone détectée
- **204 No Content crash `res.json()`** : `SyntaxError` sur body vide → la modal se réaffichait en boucle. Fix dans `frontend/src/lib/api.ts` : check status 204 ou Content-Length 0 → return `undefined as T`
- **Heuristiques BPM/key élargies** : POPSTAR donnait bpm 108 alors qu'en vrai 163. `compute_confidence` détecte maintenant : BPM[60,130] + onset>4 = suspect triplet/half-time ; madmom score < 0.85 = suspect ; vote count <3 = suspect
- **Spotify audio-features 403** confirmé par Adrien (effective depuis nov 2024). Choix : pas de fallback Spotify API, override manuel + multi-hypothèses suffit
- **Import Spotify retries** : `ytsearch5` → `ytsearch10`, retry sans artiste, retiré "lyrics only" du blacklist
- **Compteur 0/0 progress bar** : `total=0` pendant le fetch Spotify initial → affichage placeholder "…" + barre pulse

**Versionnage**
- `_resolve_version()` dans `backend/__init__.py` : cascade `importlib.metadata` → `sys._MEIPASS/pyproject.toml` (bundle PyInstaller) → repo `pyproject.toml` → "0.0.0". Source unique = `[project].version` du pyproject

**Licensing + repo public**
- Repo passé public sur GitHub (2026-05-15) **sans fichier LICENSE** → all rights reserved par défaut. Section "Licence" ajoutée à `README.md` qui clarifie : code visible, binaires Releases libres pour usage perso, mais pas de réutilisation/redistribution du code sans accord

**Release checklist durcie**
- Mémoire `project_beatfinder_release_checklist.md` mise à jour avec règle critique : `pyproject.toml` version DOIT == tag git (sans préfixe `v`). Précédent : v2.0.14 taggé alors que pyproject était à 1.7.0 → désynchro découverte au prochain bump et corrigée

## En attente / non-fait

### Court terme — à reprendre demain

- [ ] **Import Spotify sur Mac** : Quentin a remonté quelques logs
  d'erreurs/succès partiels. À analyser pour identifier les tracks qui
  échouent encore (matching durée, encoding, edge cases yt-dlp) et
  corriger. Pas bloquant — l'app démarre, mais l'analyse ne traite pas
  100% des tracks.
- [ ] **Pydantic `field_serializer` datetime UTC** : le workaround actuel
  est côté frontend (`parseIsoAsUtc`). Plus propre : forcer côté backend
  l'émission ISO 8601 avec `Z` (UTC explicite) via un `field_serializer`
  sur tous les schemas qui exposent une datetime.
- [ ] **Phase 2 sessions** : étape ambiance dans le wizard (déjà stub),
  source upload audio + import depuis playlist Beatfinder existante (au
  lieu de Spotify URL), graph fit_score v1→vN sur la page session locked.
- [ ] **Tests UI Svelte/Playwright** : pas encore en place. Les modals
  complexes (wizard, correction) bénéficieraient d'un smoke test minimum.
- [ ] **Multi-hypothèses BPM plus poussé** : actuellement on suggère 4
  alternatives ×2/2/×1.5/1.5. À enrichir avec calcul de probabilité par
  hypothèse (autocorrelation onset enveloppe) pour proposer l'hypothèse
  la plus probable en premier.

### Moyen terme (V1.9 / V2 validation)

- [ ] **Test métier réel par Adrien** : remasteriser un de ses beats Kyu selon le plan d'action FR (LUFS +6 dB, sub -28 pts, mid +9.7 pts, centroid +1026 Hz), re-uploader, vérifier que les deltas se réduisent. Boucle de validation de la value-prop, seul item bloqué par Adrien lui-même.
- [ ] **Étendre le ML classifier** : analyser des playlists drill / lo-fi / trap → ajouter à `LABEL_MAPPING` → re-run `train_classifier`. Modèle plus discriminant + couvre les styles hybrides comme Kyu (actuellement 56/44 entre rap-fr/us — vrai positif vu son côté trap français).
- [ ] **Tester / itérer .adg Ableton** : ouvrir le fichier généré dans Live, voir si Live l'accepte. Si oui → étendre pour inclure les vrais devices Ableton (EQ8 / Compressor / Limiter pré-réglés). Si non → garder uniquement le markdown export.
- [ ] **Tester AppImage Linux sur machine vierge** (sans `.venv` ni Python dev) — valide que les libs système suffisent (ffmpeg + browser).
- [ ] **Tester binaire Windows** sur une vraie machine Windows (build CI passe mais jamais lancé).

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
- **Watchdog Chromium** : si l'utilisateur tue Chrome via System Monitor, uvicorn ne s'arrête pas immédiatement. Léger délai. Acceptable. Sur Mac, le watchdog est par `pgrep` (polling 2s) vu que Chrome se détache via XPC.
- **PyInstaller `strip=True`** corrompt `libscipy_openblas64_*.so`. Toujours `strip=False`. Coût : +120 MB sur le dist/, marginal sur le DMG/AppImage compressés.
- **dylibbundler `-od`** wipe le dossier de destination. Toujours `-of` (overwrite files) quand on bundle dans un Frameworks/ déjà rempli par PyInstaller.
- **macOS .app non-notarisé** : 1ère ouverture demande clic-droit > Ouvrir > confirmer (Gatekeeper). Inévitable sans cert Apple Developer (~100€/an + notarisation).
- **Tauri Linux** : bloqué sur Ubuntu 20.04 par conflit PPA libxml2-dev vs PPA externe sury (PHP). Workaround = Ubuntu 22.04+, Fedora, ou downgrade libxml2 (risque casser PHP).
- **ML classifier** : 74% CV accuracy avec seulement 2 classes (rap-fr / rap-us). Améliorable en analysant plus de playlists de styles distincts (drill, lo-fi, trap).
- **Export .adg Ableton** : expérimental. Le XML respecte la structure publique connue mais sans test dans Live, validation incertaine. Le markdown reste le fallback fiable.
