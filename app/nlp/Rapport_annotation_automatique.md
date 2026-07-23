# Rapport d'annotation automatique des offres d'emploi

## RÃ©sumÃ©

Les **264 offres d'emploi** du corpus Burkina Faso ont Ã©tÃ© annotÃ©es automatiquement Ã  l'aide d'un modÃ¨le LLM (gpt-5-mini), en combinant les signaux prÃ©-annotÃ©s (zero-shot) avec une analyse contextuelle du texte complet. Chaque offre dispose dÃ©sormais d'entitÃ©s NER Ã©tiquetÃ©es et de classifications sectorielles/contractuelles.

## Fichiers produits

| Fichier | Description | Taille |
|---------|-------------|--------|
| `annotated_offres_label_studio.json` | Export Label Studio (JSON) prÃªt Ã  importer | ~1.9 MB |
| `annotated_offres_label_studio_summary.csv` | Tableau rÃ©capitulatif des classifications | ~30 KB |

## RÃ©partition des entitÃ©s NER extraites

| CatÃ©gorie | Nombre d'entitÃ©s |
|-----------|-----------------|
| **COMPETENCE** | 493 |
| **METIER** | 184 |
| **ENTREPRISE** | 144 |
| **DIPLOME** | 102 |
| **LOCALISATION** | 62 |
| **TYPE_CONTRAT** | 50 |

## Distribution du secteur_final

| Secteur | Nombre d'offres |
|---------|----------------|
| Informatique | 53 |
| Education | 34 |
| Ressources Humaines | 31 |
| Marketing Commercial | 30 |
| ONG Social | 20 |
| ComptabilitÃ© Finance | 18 |
| Mines Industrie | 15 |
| Agriculture | 15 |
| SantÃ© | 12 |
| BTP GÃ©nie Civil | 12 |
| Logistique | 11 |
| Microfinance Banque | 7 |
| Juridique | 6 |

## Distribution de la catÃ©gorie_contrat_finale

| CatÃ©gorie | Nombre d'offres |
|-----------|----------------|
| non_precise | 100 |
| CDI | 42 |
| Freelance | 37 |
| CDD | 28 |
| Temps Partiel | 20 |
| Stage | 19 |
| Alternance | 18 |

## Points d'attention

**Offres non-pertinentes dÃ©tectÃ©es** : 26 offres liÃ©es Ã  des articles de blog sur les Ã©checs (Chessiverse) ont Ã©tÃ© dÃ©tectÃ©es et classÃ©es en Education. Ces offres ne sont pas de vraies annonces d'emploi et peuvent Ãªtre exclues avant le fine-tuning.

**Contrats non prÃ©cisÃ©s** : 100 offres sur 264 n'indiquent pas de type de contrat dans le texte. Le LLM a correctement retournÃ© "non_precise" pour ces cas, ce qui est le comportement attendu.

**Type contrat avec slash** : 3 valeurs de TYPE_CONTRAT contenaient un slash (ex: "CDD / CDI") et ont Ã©tÃ© nettoyÃ©es en post-traitement (premiÃ¨re valeur retenue).

## Format Label Studio

Le fichier JSON d'export suit la structure Label Studio avec :

- **id** : identifiant unique de l'offre (id_externe du CSV)
- **data.text** : texte complet de l'offre pour l'affichage
- **data.titre_poste / data.nom_entreprise / data.localisation** : mÃ©tadonnÃ©es contextuelles
- **annotations[0].result** : liste des annotations NER (labels avec span start/end) + choix sectoriel et contractuel
- **meta** : champs de rÃ©fÃ©rence (zero-shot, accord_secteur) pour le suivi

## Utilisation

1. **Importer dans Label Studio** : Menu du projet > Import > sÃ©lectionner `annotated_offres_label_studio.json`
2. **VÃ©rifier** : Le script `convertir_export_label_studio.py` peut Ãªtre lancÃ© sur ce fichier pour valider la conversion vers NER_DATA/SECTEUR_DATA/CATEGORIE_DATA
3. **Corriger manuellement** : Les ~100 contrats "non_precise" et les offres Chessiverse peuvent Ãªtre ajustÃ©s dans l'interface Label Studio si nÃ©cessaire
