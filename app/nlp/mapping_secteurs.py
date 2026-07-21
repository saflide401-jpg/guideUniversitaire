# app/nlp/mapping_secteurs.py
#
# Table de correspondance entre les secteurs réels de la base de production
# (dérivés du mot-clé de recherche, ex. "Développeur informatique") et les
# 13 catégories cibles utilisées par le classifieur secteur du notebook
# d'entraînement (`entrainement_colab.ipynb`).
#
# Construite à partir de la distribution réelle des 30 secteurs en base
# (19/07/2026). Trois catégories ont été ajoutées aux 10 initiales — Education,
# Sante, Logistique — pour refléter des secteurs réels bien représentés
# (Enseignant est le 5e secteur en volume avec 21 offres) plutôt que de les
# exclure ou de les forcer dans une catégorie qui ne leur correspond pas.
#
# Usage : sert UNIQUEMENT à pré-remplir une suggestion de catégorie pour
# accélérer l'annotation manuelle (annoter par correction plutôt qu'à blanc,
# section 5.7/7 du rapport) — ce n'est jamais une vérité terrain. Le secteur
# déjà stocké en base souffre du même biais que celui qu'on corrige
# (anomalie n°4, section 7.2) : une offre doit être relue, pas recopiée.

CATEGORIES_CIBLES = [
    "Informatique",
    "BTP_Genie_Civil",
    "Comptabilite_Finance",
    "Mines_Industrie",
    "Agriculture",
    "ONG_Social",
    "Microfinance_Banque",
    "Marketing_Commercial",
    "Juridique",
    "Ressources_Humaines",
    "Education",
    "Sante",
    "Logistique",
]

# (secteur réel en base -> (catégorie cible suggérée, confiance))
# confiance "haute" : le nom du secteur désigne sans ambiguïté la catégorie.
# confiance "a_verifier" : le nom est trop générique pour trancher sans lire
# l'offre (ex. "Technicien" peut être technicien informatique, de laboratoire...).
MAPPING_SECTEURS = {
    "Développeur informatique": ("Informatique", "haute"),
    "Comptable": ("Comptabilite_Finance", "haute"),
    "Ressources humaines": ("Ressources_Humaines", "haute"),
    "Ingénieur réseaux": ("Informatique", "haute"),
    "Enseignant": ("Education", "haute"),
    "Chef de projet marketing": ("Marketing_Commercial", "haute"),
    "Chargé de communication": ("Marketing_Commercial", "haute"),
    "Développeur python": ("Informatique", "haute"),
    "Data analyst": ("Informatique", "haute"),
    "Ingénieur génie civil": ("BTP_Genie_Civil", "haute"),
    "Ingénieur devops": ("Informatique", "haute"),
    "Développeur full stack": ("Informatique", "haute"),
    "Ingénieur logiciel": ("Informatique", "haute"),
    "Data scientist": ("Informatique", "haute"),
    "Juriste": ("Juridique", "haute"),
    "Ingénieur des mines": ("Mines_Industrie", "haute"),
    "Médecin": ("Sante", "haute"),
    "Chargé de projet ong": ("ONG_Social", "haute"),
    "Auditeur": ("Comptabilite_Finance", "haute"),
    "Assistant administratif": ("Ressources_Humaines", "a_verifier"),
    "Technicien": ("Informatique", "a_verifier"),
    "Agronome": ("Agriculture", "haute"),
    "Électricien": ("BTP_Genie_Civil", "a_verifier"),
    "Logisticien": ("Logistique", "haute"),
    "Infirmier": ("Sante", "haute"),
    "Commercial": ("Marketing_Commercial", "a_verifier"),
    "Responsable microfinance": ("Microfinance_Banque", "haute"),
    "Secrétaire": ("Ressources_Humaines", "a_verifier"),
    "Responsable qualité": ("Informatique", "a_verifier"),
    "Community manager": ("Marketing_Commercial", "haute"),

    # Mots-clés génériques utilisés par la collecte fraîche de app/nlp/collecte_corpus.py
    # (LeFaso/ICI-PE), distincts des combinaisons plus spécifiques ci-dessus issues de
    # la rotation LinkedIn (app/scheduler.py).
    "Informatique": ("Informatique", "haute"),
    "Communication": ("Marketing_Commercial", "haute"),
    "Logistique": ("Logistique", "haute"),
    "Marketing": ("Marketing_Commercial", "haute"),
    # "Ingénieur" seul est trop générique (BTP ? Mines ? Informatique ?) pour être
    # suggéré sans lecture de l'offre : laissé sans suggestion (None) plutôt que deviné.
    "Ingénieur": (None, "a_verifier"),

    # Mots-clés ajoutés pour combler les catégories sous-représentées du corpus
    # (voir RAPPORT_PROJET.md, section 5.6).
    "Microfinance": ("Microfinance_Banque", "haute"),
    "Agriculture": ("Agriculture", "haute"),
    "Ong": ("ONG_Social", "haute"),
}


def suggerer_categorie(nom_secteur):
    """
    Retourne (catégorie_suggérée, confiance) pour un secteur réel de la base,
    ou (None, "inconnu") si ce secteur n'a jamais été vu (nouveau mot-clé de
    recherche ajouté depuis la construction de cette table).
    """
    return MAPPING_SECTEURS.get(nom_secteur, (None, "inconnu"))
