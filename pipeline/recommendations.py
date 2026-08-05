from pipeline.cost_estimate import estimate_cost


def generate_recommendations(mesures: dict, bact_actif: bool) -> list[dict]:
    """Matrice de recommandations personnalisées (§4), avec estimation
    budgétaire attachée (§4.1) pour les recommandations d'équipement.
    `mesures` : dict[code_sandre, valeur] pour le réseau principal de la commune.
    """
    recos: list[dict] = []

    if bact_actif:
        recos.append({
            "usage": "boisson",
            "type": "alerte_bacteriologique",
            "titre": "Non-conformité bactériologique active",
            "description": (
                "Relayez la consigne officielle ARS/préfecture "
                "(ébullition ou restriction) — ne jamais minimiser."
            ),
        })

    th = mesures.get("1345")
    chlore_libre = mesures.get("1398")
    chlore_total = mesures.get("1399")
    nitrates = mesures.get("1340")
    pesticide_total = mesures.get("6276", 0.0)
    pesticide_molecule_max = mesures.get("_pesticide_molecule_max", 0.0)
    pfas = mesures.get("8847", 0.0)
    fer = mesures.get("1393")
    cuivre = mesures.get("1392")

    if pesticide_total > 0.05 or pesticide_molecule_max > 0.1 or pfas > 0.02:
        pollution_ratio_pest = pesticide_total / 0.5
        pollution_ratio_pfas = pfas / 0.1
        if pollution_ratio_pest >= pollution_ratio_pfas:
            code_ref, valeur_ref = "6276", pesticide_total
        else:
            code_ref, valeur_ref = "8847", pfas
        reco = {
            "usage": "boisson",
            "type": "filtration_chimique",
            "titre": "Filtration recommandée (pesticides/PFAS)",
            "description": (
                "Filtration sous évier (bloc charbon actif haute densité "
                "ou osmose inverse selon le niveau de dépassement)."
            ),
        }
        cout = estimate_cost(code_ref, valeur_ref)
        if cout:
            reco["estimation_cout"] = cout
        recos.append(reco)

    if nitrates is not None and nitrates > 25:
        reco = {
            "usage": "boisson",
            "type": "nitrates_biberons",
            "titre": "Précaution nourrissons",
            "description": (
                "Éviter pour les biberons (< 15 mg/L conseillé). "
                "Osmoseur recommandé si > 40 mg/L."
            ),
        }
        cout = estimate_cost("1340", nitrates)
        if cout:
            reco["estimation_cout"] = cout
        recos.append(reco)

    if th is not None and th > 25:
        reco = {
            "usage": "cosmetique",
            "type": "adoucisseur",
            "titre": "Dimensionner un adoucisseur adapté",
            "description": (
                f"TH de {th:.2f} °fH : un équipement dimensionné à ce niveau "
                "de dureté limite les régénérations trop fréquentes."
            ),
        }
        cout = estimate_cost("1345", th)
        if cout:
            reco["estimation_cout"] = cout
        recos.append(reco)

    if chlore_total is not None and chlore_total > 0.15:
        recos.append({
            "usage": "cosmetique",
            "type": "pommeau_filtrant",
            "titre": "Protéger la peau du chlore",
            "description": "Pommeau de douche avec filtre KDF ou billes céramiques recommandé.",
        })

    if chlore_libre is not None and chlore_libre > 0.05:
        recos.append({
            "usage": "boisson",
            "type": "carafe",
            "titre": "Optimiser le goût de l'eau",
            "description": (
                "Laissez reposer l'eau 20 minutes au frais en carafe ouverte "
                "pour éliminer le chlore avant dégustation."
            ),
        })

    if (fer is not None and fer > 200) or (cuivre is not None and cuivre > 0.5):
        recos.append({
            "usage": "cosmetique",
            "type": "metaux_traces",
            "titre": "Fer/cuivre élevé",
            "description": (
                "Laissez couler l'eau 30 s le matin avant consommation ; "
                "masque capillaire chélatant pour cheveux clairs/décolorés."
            ),
        })

    return recos
