# Video Counter

Genere une video MP4 (H.264) affichant un compteur `hh:mm:ss,ms` sur fond
noir, texte blanc. Pensee pour etre posee sur une timeline de montage afin
de mesurer/illustrer une duree.

## Fonctionnement

- La duree saisie (h/m/s) correspond a la fin du compteur : la video dure
  exactement cette duree et affiche un chronometre qui part de zero.
- Le champ heure du compteur (`hh:`) n'apparait sur la video que si la
  duree totale atteint 1h ; en dessous, affichage `mm:ss[,ms]`.
- La largeur de la video est calculee automatiquement a partir de la
  police et du texte affiche (`hauteur` reste le seul parametre pixel a
  choisir, 100 a 500 px).
- Police : Consolas Bold (chasse fixe -> les chiffres ne bougent pas d'une
  image a l'autre), avec repli sur Courier New / Cascadia Mono / Arial
  Bold si Consolas est absente du poste.
- Le nom de fichier de sortie est toujours derive de la duree, par ex.
  `01h30m00s.mp4` (ou `01h30m00s.ms.mp4` si les millisecondes sont
  affichees). Deux compteurs de meme duree et meme option ms portent donc
  systematiquement le meme nom : le dossier de sortie sert de bibliotheque
  et une confirmation est demandee avant d'ecraser un fichier existant.

## Installation

Necessite Python 3.9+.

```bat
python -m pip install -r requirements.txt
```

`imageio-ffmpeg` embarque son propre binaire ffmpeg : aucune installation
systeme separee n'est necessaire.

## Utilisation

```bat
python video_counter.py
```

La fenetre tkinter permet de regler : duree (h/m/s), affichage des ms,
hauteur du texte en px, frame rate, et dossier de sortie. La generation
tourne en arriere-plan avec une barre de progression.

## Compiler en .exe

```bat
build.bat
```

Installe les dependances (dont PyInstaller) et produit
`dist\VideoCounter.exe` (executable autonome, sans console). Le dossier
`build\` et le fichier `VideoCounter.spec` sont des artefacts
intermediaires de PyInstaller, regeneres a chaque compilation.

## Fichiers

| Fichier | Role |
| --- | --- |
| `video_counter.py` | Logique de generation + interface tkinter |
| `requirements.txt` | Dependances Python (Pillow, imageio-ffmpeg) |
| `build.bat` | Compile `dist\VideoCounter.exe` via PyInstaller |
