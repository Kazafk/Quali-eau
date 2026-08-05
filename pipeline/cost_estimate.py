# Seuils de veto sanitaire réutilisés depuis §3.1 — source unique de vérité,
# pour que le score affiché et la recommandation chiffrée restent cohérents
# sur un même dépassement (§4.1, §5.6).
VETO_THRESHOLDS = {
    "1340": 50.0,   # Nitrates, mg/L
    "1339": 0.1,    # Nitrites, mg/L
    "6276": 0.5,    # Pesticides total, µg/L
    "8847": 0.1,    # PFAS total, µg/L
}


def estimate_cost(param_code: str, value: float) -> dict | None:
    """Estimation CAPEX/OPEX par palier technologique (§4.1).
    Résultat destiné à recommandations[].estimation_cout de la fiche commune,
    calculé une fois par commune au batch — jamais interrogé en direct côté client.
    """
    if param_code == "1345":  # Titre hydrotimétrique (TH) — dureté, seuils = §3.2.1
        if value > 40:
            return {
                "materiel": "Adoucisseur haute capacité (> 25 L)",
                "achat_eur": "1600-2000",
                "entretien_annuel_eur": "70-100 (8+ sacs de sel/an)",
                "niveau_severite": "extreme",
            }
        if value > 25:
            return {
                "materiel": "Adoucisseur renforcé (20-25 L)",
                "achat_eur": "1200-1600",
                "entretien_annuel_eur": "50-70 (4-5 sacs de sel/an)",
                "niveau_severite": "eleve",
            }
        if value > 15:
            return {
                "materiel": "Adoucisseur standard (10-15 L)",
                "achat_eur": "700-900",
                "entretien_annuel_eur": "15 (2 sacs de sel/an)",
                "niveau_severite": "modere",
            }
        return None  # < 15 °fH : pas de recommandation d'adoucisseur

    seuil_veto = VETO_THRESHOLDS.get(param_code)
    if seuil_veto is None:
        return None
    ratio = value / seuil_veto
    if ratio >= 1.0:  # seuil de veto sanitaire atteint (§3.1)
        return {
            "materiel": "Osmoseur à pompe de perméat + reminéralisation",
            "achat_eur": "450-700",
            "entretien_annuel_eur": "90 (membrane 0,0001 µm saturée plus vite)",
            "niveau_severite": "extreme",
        }
    if ratio >= 0.5:  # approche du seuil de veto
        return {
            "materiel": "Osmoseur inverse basique (3 étages)",
            "achat_eur": "200-300",
            "entretien_annuel_eur": "60 (cartouches + membrane)",
            "niveau_severite": "eleve",
        }
    return {
        "materiel": "Filtre sous-évier à charbon actif",
        "achat_eur": "80-120",
        "entretien_annuel_eur": "30 (1 cartouche/an)",
        "niveau_severite": "modere",
    }
