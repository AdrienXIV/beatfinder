# Beatfinder — guide pour futures sessions Claude Code

Outil desktop d'analyse de patterns audio pour beatmakers. Compare ton catalogue (Spotify playlist ou WAV/MP3 locaux) à des playlists de référence (rap FR, US, etc.) et sort un plan d'action mastering / mix / rythme / tonalité / structure actionnable.

**Owner** : Adrien (fullstack dev FR, beatmaker rap/trap/house). Voir `ROADMAP.md` pour l'historique des sprints et l'état des features.

## Stack

- **Backend** : Python 3.12 + FastAPI + SQLAlchemy 2 + SQLite. Analyseurs audio : librosa, madmom (CNN key), pyloudnorm (LUFS BS.1770), scipy, sklearn (k-means). yt-dlp pour télécharger l'audio Spotify via YouTube.
- **Frontend** : SvelteKit 2 + Svelte 5 + Vite 8 + Tailwind v4 + Chart.js. Static SPA buildée via `@sveltejs/adapter-static`, servie par FastAPI en prod (catch-all fallback sur `index.html`).
- **Packaging desktop** : PyInstaller → binaire + libs, puis squashfs AppImage (Linux). Lancement en mode fenêtre native via `chromium --app=URL --class=Beatfinder`.

## Structure dossiers

```
backend/                   # FastAPI app
  config.py                # pydantic-settings centralisé (DATA_DIR, LOG_LEVEL, Spotify creds, …)
  db.py                    # SQLAlchemy engine + session factory
  types.py                 # type aliases partagés (ProgressCallback, …)
  main.py                  # FastAPI app + lifespan + standalone launcher
  api/                     # routes & schemas Pydantic (schemas/ splitté en sous-package)
  analyzers/               # 6 analyseurs audio (tempo, tonality, energy, spectral, structure, timbre) + pipeline.py
  domain/                  # modèles SQLAlchemy ORM (entités métier)
    models.py              # Playlist, Track, PlaylistTrack, TrackAnalysis, PlaylistPattern
  services/                # logique applicative pure (pas d'I/O direct)
    action_planner.py      # règles métier source→target (4 modes)
    pattern_extractor.py   # agrégation track_features → pattern playlist
    cache_inspector.py     # GET/DELETE cache disque
  infrastructure/          # adaptateurs systèmes externes (réseau / FS / API)
    spotify_client.py      # SpotifyOAuth
    settings_store.py      # data/settings.json (Spotify credentials)
    audio_sources/         # YouTubeSource (yt-dlp) — AudioSource Protocol
  local_projects/          # Feature D : upload local MP3/WAV (split _audio_io + service)
  report_generator/        # brief markdown + CSV (split helpers/analytics/reco/brief/csv_export)
  cli/                     # entry points CLI (`python -m backend.cli.<name>`)
    pipeline.py            # ex-backend.run : pipeline d'analyse playlist Spotify
    compare.py             # diff entre 2 playlists analysées
    db_inspect.py          # ex-backend.inspect : tableau per-track + pattern global
    train_classifier.py    # entraîne ML classifier de style (RandomForest)

frontend/src/
  routes/                  # SvelteKit pages
    playlists/[id]/        # détail + print + styles + brief
    playlists/[id]/styles/ # 5 styles PDF (Editorial/Soft/Newspaper/Blueprint/Vinyl)
    settings/              # Spotify config + Cache stats/flush
    analyze/               # input URL Spotify
    compare/               # diff markdown 2 playlists
    projects/new/          # upload local
    jobs/[id]/             # SSE log + progress bar
  lib/
    components/charts/     # SpectralRing, BpmHistogram, PriorityDonut, SparkLine
    components/print-styles/  # 5 styles PDF
    api.ts                 # client typé toutes routes
    components/ActionPlanModal.svelte  # killer feature

data/                       # local (mode dev) ou ~/.beatfinder/data/ (mode binaire)
  analyses.db              # SQLite : Playlist, Track, PlaylistTrack, TrackAnalysis, PlaylistPattern
  audio/                   # MP3 YouTube cached
  audio/local/{proj}/      # uploads MP3/WAV
  reports/                 # briefs .md + .csv
  reports/actions/         # plans d'action JSON cached
  settings.json            # credentials Spotify
  .spotify_cache           # token OAuth refresh

packaging/                  # AppImage assets : .desktop, AppRun, icône
scripts/                    # build_appimage.sh, install_appimage.sh, uninstall_appimage.sh, gen_icon.py
beatfinder.spec             # PyInstaller spec
run_app.py                  # entry point binaire (appelle backend.main.main)
build.sh / build.command    # PyInstaller wrapper Linux/macOS
```

## Commandes essentielles

### Dev (2 process)

```bash
.venv/bin/uvicorn backend.main:app --reload --port 8000  # term 1
cd frontend && npm run dev -- --port 5173                 # term 2 (proxy /api → :8000)
```

Ouvre `http://localhost:5173`.

### Standalone source (un seul process)

```bash
cd frontend && npm run build && cd ..
.venv/bin/python -m backend.main
```

### Packaging desktop

```bash
./build.sh                          # PyInstaller → dist/beatfinder/ (558 MB dossier)
./scripts/build_appimage.sh         # squashfs → dist/beatfinder-x86_64.AppImage (216 MB)
./scripts/install_appimage.sh       # menu Activities GNOME + icône
./scripts/uninstall_appimage.sh             # cleanup app (garde ~/.beatfinder/)
./scripts/uninstall_appimage.sh --purge     # cleanup app + données utilisateur
```

### Tests

```bash
.venv/bin/pytest                                                 # tous les tests
cd frontend && npx svelte-check --threshold error               # type-check frontend
.venv/bin/ruff check backend/                                    # lint Python
```

## Configuration

- **Spotify** : `Paramètres` UI → CLIENT_ID + CLIENT_SECRET → stockés en `data/settings.json`. Fallback `.env` si présent (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`).
- **Redirect URI Spotify** (à ajouter dans le dashboard Spotify Developer) : `http://127.0.0.1:8888/callback`
- **DATA_DIR** : `./data` en dev, `~/.beatfinder/data` en mode binaire. Override via env `DATA_DIR=...`.

## Gotchas connus (ne pas re-trébucher dessus)

1. **PyInstaller exige `libpython3.X.so`**. `pyenv install` sans flag ne le génère pas → `Python was built without a shared library`. Rebuild avec :
   ```bash
   PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install -f 3.12.2
   ```
   Vérifier via `python -c "import sysconfig; print(sysconfig.get_config_var('Py_ENABLE_SHARED'))"` doit retourner `1`.

2. **madmom** pas dans `requirements.txt` (pas de release stable). Install séparé :
   ```bash
   pip install "madmom @ git+https://github.com/CPJKU/madmom@main"
   ```
   (Branche `master` n'existe plus depuis 2023.)

3. **`source .venv/bin/activate`** trigger un security prompt non-whitelistable dans Claude Code. **Toujours utiliser `.venv/bin/<binaire>` direct** (ex: `.venv/bin/python -m backend.main`).

4. **AppImageLauncher** auto-enregistre les AppImages → triple entrée dans Activities. Fix : flag `X-AppImage-Integrate=false` dans le `.desktop` embedded + `install_appimage.sh` nettoie les `appimagekit_*beatfinder*.desktop` orphelins.

5. **`current` de `JobProgress` est un float** (pas un int). Permet la progression fractionnelle intra-track (analyzer emit `on_step(key, label, fraction)` 14× par track = 7 étapes × 2 sub). Frontend `ProgressBar.svelte` affiche `Math.floor(current)/total` pour le compteur lisible.

6. **Pas de `redirect_uri` dans la config Spotify côté UI** : c'est obligatoire, on hardcode `http://127.0.0.1:8888/callback` (default Beatfinder). L'utilisateur doit juste l'ajouter dans son dashboard Spotify.

7. **`source .env.example` n'est pas commité avec credentials**. Le `.env` réel est gitignored.

8. **Brief 409 sur projet créé sans analyse**. Le frontend (`playlists/[id]/+page.svelte`) catch `ApiError.status === 409` sur `getBrief` et affiche un état vide "Pas encore de brief" propre.

## Architecture du Plan d'action (feature centrale)

Le **Plan d'action** est la killer feature. 4 modes possibles selon source/target :

| Source | Cible | Use case |
|---|---|---|
| Playlist | Playlist | "Mon projet (Perso/Kyu) vs FR" |
| Track | Playlist | "Cette track de moi vs FR globalement" |
| Playlist | Track | "Mon projet vs cette track de réf" |
| Track | Track | "Ce beat de PNL vs ce beat de Booba" |

- **Backend** : `backend/services/action_planner.py:generate_action_items(pattern_from, pattern_to)` retourne `list[ActionItem]` (category, priority, current, target, delta, action, rationale). Règles métier sur LUFS / crest / DR / bandes spectrales / centroid / BPM std / mode minor / drop position.
- **Endpoint unifié** : `GET /api/actions?from={id}&to={id}` (l'ID peut être un `playlist.spotify_id` ou un `track.spotify_id`, résolu via `_load_source()` qui essaie Playlist puis Track).
- **Cache fichier** : `data/reports/actions/{from_safe}__vs__{to_safe}.json` indexé sur les `pattern_id` (auto-invalidé si l'un des patterns change).
- **`/api/actions/compared-with?from={id}`** : retourne les targets déjà comparées depuis ce ID (pour les pastilles vertes UI).
- **Frontend** : `ActionPlanModal.svelte` avec tabs Playlist|Track dans le sélecteur cible, drill-down sur Track (choisis playlist → puis track), pastilles vertes si déjà comparé, checkboxes persistées en localStorage par paire `(from, to)`.

## Style de communication (préférence Adrien)

- **Tutoiement** systématique
- **Zéro emoji** dans les réponses (ASCII OK : ✓ → ▎ etc.)
- **Action concrète à chaque réponse** : pas de "je vais faire X" → faire X directement
- **Challenger** si je propose qqch qui me paraît mauvais — pas de oui-oui

## Documents associés

- `ROADMAP.md` : état des sprints, features faites/en cours/idées futures
- `README.md` : install + usage utilisateur final
- `~/.claude/projects/-home-adrien-Documents-Business-beatfinder/memory/MEMORY.md` : mémoire long-terme Claude Code, indexe les `project_beatfinder_*.md` détaillés
