# 💧 Quali'eau — Évaluation de la Qualité de l'Eau du Robinet en France

> **Quali'eau** est un service web d'évaluation grand public et expert de la qualité de l'eau du robinet en France, basé sur les données officielles du contrôle sanitaire des ARS (**SISE-EAUX** / **data.gouv.fr** et API **Hub'eau**).
> 
> Il unifie les approches sanitaires et physico-chimiques en proposant une notation sous forme de **double score (Nutri-Score A à E)** adapté aux 2 grands usages de la vie quotidienne : **Boisson & Santé** 🥤 et **Cosmétique & Lavage** 🧴.

---

## 📌 Sommaire

- [🌟 Vision & Objectifs](#-vision--objectifs)
- [📊 Système de Scoring Dual (A à E)](#-système-de-scoring-dual-a-à-e)
  - [🥤 Usage 1 : Boisson & Santé](#-usage-1--boisson--santé)
  - [🧴 Usage 2 : Cosmétique, Peau & Lavage](#-usage-2--cosmétique-peau--lavage)
  - [☕ Indice Spécialisé Café / Thé (SCA)](#-indice-spécialisé-café--thé-sca)
- [💡 Recommandations & Estimation Budgétaire](#-recommandations--estimation-budgétaire)
- [🏗️ Architecture Technique](#️-architecture-technique)
  - [Pipeline de Données Batch (Python)](#pipeline-de-données-batch-python)
  - [Front-End Statique (GitHub Pages)](#front-end-statique-github-pages)
- [📁 Structure du Dépôt](#-structure-du-dépôt)
- [🚀 Guide de Démarrage & Développement](#-guide-de-démarrage--développement)
  - [Prérequis](#prérequis)
  - [Exécution du Pipeline de Données](#exécution-du-pipeline-de-données)
  - [Lancement du Serveur Web Local](#lancement-du-serveur-web-local)
- [🧪 Tests & Validation](#-tests--validation)
- [⚖️ Mentions Légales & Licence](#️-mentions-légales--licence)

---

## 🌟 Vision & Objectifs

En France, l'eau du robinet est l'aliment le plus surveillé, mais les données brutes d'analyses sanitaires restent complexes et éparpillées. **Quali'eau** traduit automatiquement ces millions de mesures brutes en indicateurs simples et actionnables :

```
                      ┌────────────────────────────────────────┐
                      │   SISE-EAUX / data.gouv (exports DIS)  │
                      │  - Prélèvements & résultats d'analyses │
                      │  - Conclusions sanitaires ARS          │
                      └──────────────────┬─────────────────────┘
                                         │ batch hebdomadaire
                                         ▼
                      ┌────────────────────────────────────────┐
                      │       Moteur de Calcul Quali'eau       │
                      │   - Agrégation temporelle & spatiale   │
                      │   - Normalisation & seuils sanitaires  │
                      └──────────────┬──────────────────┬──────┘
                                     │                  │
                ┌────────────────────┴─────┐      ┌─────┴────────────────────┐
                │                          │      │                          │
                ▼                          ▼      ▼                          ▼
   ┌──────────────────────────┐               ┌──────────────────────────┐
   │    SCORE BOISSON (🥤)     │               │ SCORE COSMÉTIQUE/LAVAGE (🧴)│
   │  - Sécurité Sanitaire    │               │  - Calcaire & Dureté TH  │
   │  - Minéralité & Équilibre│               │  - Chlore & Irritation   │
   │  - Profil Goût & Saveur  │               │  - Respect pH Cutané     │
   │  - Indice Café/Thé (SCA) │               │  - Métaux & Dépôts       │
   └──────────────────────────┘               └──────────────────────────┘
```

---

## 📊 Système de Scoring Dual (A à E)

Les deux scores sont exprimés sur une échelle de **0 à 100** avec attribution d'une lettre de **A** à **E** :

| Score Global | Classe | Niveau d'Appréciation |
| :---: | :---: | :--- |
| **80 – 100** | **A** | **Parfait** — Qualité optimale pour cet usage |
| **60 – 79** | **B** | **Bon** — Très bonne qualité générale |
| **40 – 59** | **C** | **Moyen** — Qualité passable, légers désagréments |
| **20 – 39** | **D** | **Passable** — Inconfort marqué ou paramètres dégradés |
| **0 – 19** | **E** | **Critique** — Risque sanitaire ou inconfort fort |

---

### 🥤 Usage 1 : Boisson & Santé

Formule globale :
$$\text{Score Boisson} = 0,55 \cdot S_{\text{sécurité}} + 0,25 \cdot S_{\text{minéraux}} + 0,20 \cdot S_{\text{goût}}$$

#### 🛡️ Veto Sanitaire (Facteur limitant)
En cas de dépassement sanitaire grave, le score global est immédiatement plafonné :
$$\text{Score Boisson} = \min(\text{Score Boisson}, S_{\text{sécurité}})$$

Sont concernés par le veto :
- Non-conformité bactériologique active (ex. *E. coli*, Entérocoques)
- Nitrates > 50 mg/L ou Nitrites > 0,1 mg/L
- Métaux lourd hors normes (Plomb > 10 µg/L, Arsenic > 10 µg/L, Cadmium > 5 µg/L)
- Dépassement de pesticides (molécule individuelle > 0,1 µg/L ou total > 0,5 µg/L)
- Dépassement de PFAS (somme des 20 PFAS > 0,1 µg/L)

#### Composition des Sous-Scores Boisson :
1. **Sécurité Sanitaire ($S_{\text{sécurité}}$)** : $\min(P_{\text{bact}}, P_{\text{pest}}, P_{\text{pfas}}, P_{\text{métaux}}, P_{\text{nitrates}})$
2. **Minéraux & Équilibre ($S_{\text{minéraux}}$)** : $70\% \text{ Nitrates} + 15\% \text{ Chlorures} + 15\% \text{ Sulfates}$
3. **Profil Gustatif ($S_{\text{goût}}$)** : $60\% \text{ Chlore libre} + 40\% \text{ Turbidité}$

---

### 🧴 Usage 2 : Cosmétique, Peau & Lavage

Formule globale :
$$\text{Score Cosmétique} = 0,45 \cdot S_{\text{dureté}} + 0,25 \cdot S_{\text{chlore}} + 0,15 \cdot S_{\text{pH}} + 0,15 \cdot S_{\text{métaux\_dépôts}}$$

#### Composition des Sous-Scores Cosmétique :
1. **Dureté & Calcaire ($S_{\text{dureté}}$)** : basé sur le Titre Hydrotimétrique (TH en °fH).
   - *3 à 8 °fH* : Idéal pour la peau (Score 90–100)
   - *15 à 25 °fH* : Eau moyennement dure (Score 75–100)
   - *> 35 °fH* : Eau très dure (dessèchement cutané, tartre, surconsommation de savon)
2. **Chlore & Agressivité ($S_{\text{chlore}}$)** : évaluation de l'évaporation du chlore sous la douche et de l'oxydation de la kératine/film hydrolipidique.
3. **Respect Cutané ($S_{\text{pH}}$)** : adéquation avec le pH physiologique de la peau (~4,7–5,5). Plage idéale de l'eau : 6,8–7,4.
4. **Métaux & Dépôts ($S_{\text{métaux\_dépôts}}$)** : $\min(\text{Cuivre}, \text{Fer}, \text{Manganèse})$ pour éviter les taches sur le linge et l'altération des cheveux.

---

### ☕ Indice Spécialisé Café / Thé (SCA Standard)

En complément, Quali'eau fournit un **Coffee & Tea Index** calculé selon les standards de la *Specialty Coffee Association* :
- **TDS estimé** : Cible ~150 mg/L ($0,65 \times \text{Conductivité}$)
- **Dureté calcique (GH)** : Cible ~68 mg/L $\text{CaCO}_3$ (~6,8 °fH)
- **Alcalinité totale (TAC / KH)** : Cible ~40 mg/L $\text{CaCO}_3$ (~4,0 °fH)
- **Chlore total** : Cible 0 mg/L

---

## 💡 Recommandations & Estimation Budgétaire

Pour chaque problème détecté (eau calcaire, chlore, polluants), des recommandations personnalisées et impartiales sont générées avec une **estimation budgétaire par palier technologique** (CAPEX/OPEX) :

### Dureté & Calcaire (Adoucisseurs / Douche)
- **15–25 °fH** : Adoucisseur standard 10–15 L (~700€–900€ | ~15€/an)
- **25–40 °fH** : Adoucisseur renforcé 20–25 L (~1200€–1600€ | ~50€–70€/an)
- **> 40 °fH** : Adoucisseur haute capacité > 25 L (~1600€–2000€ | ~70€–100€/an)

### Polluants Chimiques (Filtration Eau de Boisson)
- **Dépassement modéré** : Filtre sous-évier à charbon actif (~80€–120€ | ~30€/an)
- **Dépassement élevé** : Osmoseur inverse 3 étages (~200€–300€ | ~60€/an)
- **Dépassement extrême (veto)** : Osmoseur à pompe de perméat + reminéralisation (~450€–700€ | ~90€/an)

---

## 🏗️ Architecture Technique

Le projet adopte une **architecture 100 % statique hébergée sur GitHub Pages**, garantissant zéro coût d'hébergement et des performances optimales.

```
┌──────────────── GitHub Actions — cron hebdo (lundi, 6h UTC) ──────────────────┐
│  1. pipeline/download_data.py   → Téléchargement ZIPs DIS (data.gouv.fr)        │
│  2. pipeline/compute_scores.py  → Parsing TXT, agrégation & calcul des scores  │
│                                   └→ Génération des fichiers JSON dans public/  │
│  3. peaceiris/actions-gh-pages  → Publication automatique sur GitHub Pages     │
└───────────────────────────────────────────┬───────────────────────────────────┘
                                            │ push gh-pages
┌───────────────────────────────────────────▼───────────────────────────────────┐
│                          HÉBERGEMENT GITHUB PAGES                             │
│  index.html · map.js · panel.js · style.css  (Vanilla JS + MapLibre GL)       │
│  - data/national.geojson                 (Carte nationale allégée)            │
│  - data/index.json                        (Métadonnées & statistiques)        │
│  - data/communes/{code_insee}.json        (Fiches communales lazy-loaded)     │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Structure du Dépôt

```
Quali'eau/
├── .github/
│   └── workflows/
│       └── update-data.yml      # Workflow d'actualisation hebdomadaire des données
├── pipeline/
│   ├── download_data.py         # Téléchargement & extraction des données SISE-EAUX
│   ├── compute_scores.py        # Moteur d'agrégation, de scoring et d'estimation budgétaire
│   └── requirements.txt         # Dépendances Python du pipeline
├── public/                      # Site web statique servi par GitHub Pages
│   ├── index.html               # Interface utilisateur principale
│   ├── map.js                   # Cartographie interactive (MapLibre GL)
│   ├── panel.js                 # Affichage des fiches communales et graphiques
│   ├── style.css                # Style CSS Vanilla (Design moderne & responsive)
│   └── data/
│       ├── index.json           # Stats nationales & métadonnées du build
│       ├── national.geojson     # Polygones/points communaux avec scores simplifiés
│       └── communes/            # ~35 000 fiches JSON communales individuelles
├── tests/                       # Unit tests (pytest) pour le moteur de calcul
├── SPECIFICATION.md             # Spécifications techniques et algorithmiques détaillées
└── README.md                    # Documentation générale du projet
```

---

## 🚀 Guide de Démarrage & Développement

### Prérequis

- **Python 3.12+**
- **Node.js / npm** (optionnel, uniquement pour un serveur de dev local type `http-server` ou `serve`)
- **Git**

### Exécution du Pipeline de Données

1. Installez les dépendances Python :
   ```bash
   pip install -r pipeline/requirements.txt
   ```

2. Téléchargez les données officielles SISE-EAUX (data.gouv.fr) :
   ```bash
   python pipeline/download_data.py
   ```

3. Calculez les scores et générez les fichiers JSON statiques :
   ```bash
   python pipeline/compute_scores.py
   ```

### Lancement du Serveur Web Local

Pour tester le site en local, vous pouvez utiliser le serveur HTTP natif de Python :

```bash
# Se placer dans le dossier public
cd public

# Lancer le serveur local sur le port 8000
python -m http.server 8000
```

Ouvrez ensuite `http://localhost:8000` dans votre navigateur.

---

## 🧪 Tests & Validation

Les tests automatisés vérifient la précision du moteur de calcul, le respect des règles de veto et l'exactitude des équations de scoring :

```bash
pytest tests/
```

---

## ⚖️ Mentions Légales & Licence

- **Source des données** : Ministère de la Santé / ARS via [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/resultats-du-controle-sanitaire-de-leau-distribuee-commune-par-commune/) & API [Hub'eau](https://hubeau.eaufrance.fr/).
- **Licence des données** : Licence Ouverte / Open Licence (Etalab).
- **Avertissement** : Quali'eau est un outil d'information et d'évaluation indépendant. Seules les consignes et bulletins officiels émis par la Préfecture et l'ARS font foi sur le plan sanitaire réglementaire.
