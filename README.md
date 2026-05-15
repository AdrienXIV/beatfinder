# Beatfinder

Outil desktop d'analyse de playlists Spotify (ou tracks audio locales) qui extrait des patterns acoustiques (BPM, tonalité, énergie, spectre, structure, timbre) et génère des briefs de production exploitables.

## Deux façons d'utiliser

### A. AppImage Linux (utilisateur final)

1. Télécharge `beatfinder-x86_64.AppImage` (~177 MB).
2. Rends-le exécutable et lance :
   ```bash
   chmod +x beatfinder-x86_64.AppImage
   ./beatfinder-x86_64.AppImage
   ```
3. Une fenêtre s'ouvre automatiquement. Première utilisation : un wizard te guide pour créer ton app Spotify Developer (3 min, gratuit). Tu peux skipper et configurer plus tard via *Paramètres*.

**Pré-requis système Linux** (toutes distros récentes ont ça par défaut) :
- `ffmpeg` pour décoder l'audio téléchargé : `sudo apt install ffmpeg` / `sudo dnf install ffmpeg` / `sudo pacman -S ffmpeg`.
- Un navigateur : Chromium/Chrome/Brave/Edge/Vivaldi → mode "app native" (fenêtre standalone). Sinon Firefox → fenêtre dédiée. Sinon onglet dans ton navigateur par défaut.

**Installer dans le menu Activities GNOME** (optionnel) :
```bash
./scripts/install_appimage.sh             # icône + .desktop dans le menu
./scripts/uninstall_appimage.sh           # retire l'app, garde ~/.beatfinder/
./scripts/uninstall_appimage.sh --purge   # retire l'app ET les données
```

**Données utilisateur** : `~/.beatfinder/data/` (DB SQLite, audio cache MP3, briefs, plans d'action). Surcharge via `DATA_DIR=/autre/chemin ./beatfinder-x86_64.AppImage`.

**Si tu lances le binaire PyInstaller direct** (sans AppImage) : `./dist/beatfinder/beatfinder` — même comportement.

#### macOS (DMG)

1. Télécharge `beatfinder-macos-arm64.dmg` (~192 MB, Apple Silicon M1/M2/M3/M4).
2. Double-clic pour monter, glisse `Beatfinder.app` dans le raccourci `Applications`.
3. **Premier lancement** : macOS Gatekeeper bloque (app non signée). Solution : clic droit sur `Beatfinder.app` dans `/Applications` → *Ouvrir* → *Ouvrir quand même*. Ou *Réglages Système → Confidentialité et sécurité → Ouvrir quand même*. Une seule fois, ensuite double-clic normal.
4. Pré-requis : Chrome ou Brave installé (l'app lance une fenêtre Chromium).

**Mise à jour propre** (si après upgrade Finder/Get Info montre encore l'ancienne version) : le DMG contient un script `uninstall_macos.command`. Double-clic dessus dans le DMG monté → il supprime `/Applications/Beatfinder.app`, démonte les volumes et reset le cache LaunchServices. Tu peux ensuite ré-installer proprement. Cause : LaunchServices cache la metadata par bundle ID, le drag-and-drop seul ne suffit pas toujours à rafraîchir Finder.

**Données utilisateur Mac** : `~/.beatfinder/data/`. Le script avec `--purge` (lance-le en CLI) supprime aussi ces données.

### B. Sources (développement)

#### Pré-requis

- Python 3.11 ou 3.12 (3.13/3.14 cassent numba/llvmlite, deps de librosa)
- ffmpeg système (yt-dlp décode en MP3)
  - Ubuntu/Debian : `sudo apt install ffmpeg`
  - macOS : `brew install ffmpeg`
- Node.js 20+ et npm (pour le frontend SvelteKit)
- Une app Spotify Developer ([dashboard](https://developer.spotify.com/dashboard))

#### Installation

```bash
# Avec pyenv (recommandé pour packager ensuite — voir build) :
PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install 3.12.2
pyenv local 3.12.2

python -m venv .venv
.venv/bin/pip install --upgrade pip wheel cython
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install "madmom @ git+https://github.com/CPJKU/madmom@main"

# Frontend
cd frontend && npm install && cd ..
```

#### Lancer en dev

Terminal 1 (backend) :
```bash
.venv/bin/uvicorn backend.main:app --reload --port 8000
```

Terminal 2 (frontend, hot reload sur :5173 avec proxy vers :8000) :
```bash
cd frontend && npm run dev -- --port 5173
```

Ouvre `http://localhost:5173`.

#### Lancer en standalone (un seul process)

```bash
cd frontend && npm run build && cd ..
.venv/bin/python -m backend.main
```

Ouvre `http://localhost:8000` (auto-open browser sauf si `BEATFINDER_NO_AUTO_OPEN=1`).

## Configurer Spotify

Crée une app sur [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard). Ajoute `http://127.0.0.1:8888/callback` dans les Redirect URIs. Récupère le Client ID + Client Secret.

Deux façons de les saisir :
- **UI** : va dans Paramètres → section Spotify, saisis-les. Stocké dans `~/.beatfinder/data/settings.json`.
- **`.env`** : copie `.env.example` → `.env`, renseigne `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET`. Pratique en dev.

Au premier accès à une playlist Spotify, ton navigateur s'ouvre sur la page d'accord OAuth, tu acceptes, le token est cached dans `data/.spotify_cache`. Les exécutions suivantes utilisent le cache (refresh auto).

## Packager en binaire desktop

```bash
./build.sh         # Linux / WSL
./build.command    # macOS (double-clic depuis Finder)
```

Le script enchaîne `npm run build` puis `pyinstaller beatfinder.spec`. Output : `dist/beatfinder/beatfinder` (~460 MB dossier avec libs).

Cross-compilation impossible : tu dois build sur la plateforme cible (Linux pour Linux, macOS pour macOS).

### Builds automatiques (GitHub Actions)

Le repo contient un workflow `.github/workflows/build.yml` qui builds les 3 plateformes (Linux AppImage / macOS .app .zip / Windows .exe .zip) à chaque tag `vX.Y.Z` pushé sur GitHub.

Setup initial (1 fois) :
```bash
# 1. Init git localement et premier commit
git init
git add .
git commit -m "Initial commit"

# 2. Créer le repo GitHub via web (https://github.com/new) ou via gh CLI
gh repo create beatfinder --private --source=. --remote=origin --push

# 3. Vérifier que le workflow Actions est activé dans Settings → Actions
```

Releaser une version :
```bash
git tag v1.0.0
git push origin v1.0.0
# → GitHub Actions builds les 4 binaries (Linux + macOS arm64 + macOS Intel + Windows)
# → crée une GitHub Release avec les artifacts attachés
```

Trigger manuel sans tag : onglet Actions → workflow `Build cross-platform binaries` → `Run workflow`.

Limitations connues :
- **Pas de code signing** macOS/Windows : SmartScreen Windows et Gatekeeper macOS afficheront un avertissement "untrusted developer". Pour distribuer largement, faut un certificat (~100€/an Apple Developer, ~250€/an CodeSign Windows).
- **madmom sur Windows** : compile depuis git, peut casser si la branche `main` change. Pin une révision si tu veux des builds reproductibles.
- **Tests E2E non lancés** : le workflow build uniquement. Les analyses audio nécessitent du temps + Spotify creds, donc skip CI.

### Gotcha pyenv

PyInstaller exige `libpython3.X.so`. `pyenv install` sans flag ne le génère pas. Rebuilde avec :
```bash
PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install -f 3.12.2
```
Puis recrée la venv. Vérifie via :
```bash
.venv/bin/python -c "import sysconfig; print(sysconfig.get_config_var('Py_ENABLE_SHARED'))"
# doit afficher 1
```

## CLI direct (sans UI)

Le pipeline tourne aussi en CLI pour scripts/tests :

```bash
# Liste les tracks d'une playlist
.venv/bin/python -m backend.cli.pipeline "https://open.spotify.com/playlist/<id>"

# Télécharge + analyse les 5 premiers tracks
.venv/bin/python -m backend.cli.pipeline "https://open.spotify.com/playlist/<id>" --analyze --limit 5

# Diff entre 2 playlists déjà en DB
.venv/bin/python -m backend.cli.compare <playlist_id_A> <playlist_id_B>

# Inspecter le contenu DB d'une playlist
.venv/bin/python -m backend.cli.db_inspect <playlist_id>
```

## Architecture

Stack : FastAPI + librosa + madmom + yt-dlp + SvelteKit + SQLite. Pattern Strategy pour les sources audio (`AudioSource` ABC + `YouTubeSource` V1). DB SQLite pour historiser les playlists analysées, leurs tracks et patterns extraits.

Le frontend SPA est servi par FastAPI en prod (catch-all qui fallback sur `index.html`) ou via Vite hot-reload en dev (proxy `/api → :8000`).

## Cadre légal

Téléchargement audio via yt-dlp utilisé uniquement pour analyse locale dans un cadre privé (étude de patterns sonores pour beatmaking). Pas de redistribution.

## Licence

Tous droits réservés © Adrien Maillard. Le code de ce dépôt est mis à
disposition pour consultation uniquement. Aucune licence d'utilisation,
modification, copie ou redistribution n'est accordée. Les binaires des
*Releases* sont librement téléchargeables pour usage personnel — mais le
code source ne peut être réutilisé, forké à des fins de publication, ou
redistribué sans autorisation écrite préalable.

Les dépendances tierces (librosa, madmom, FastAPI, SvelteKit, yt-dlp, etc.)
restent sous leurs licences respectives (majoritairement MIT/Apache/BSD).
