"""Convertit un export JSON Label Studio en NER_DATA/SECTEUR_DATA/CATEGORIE_DATA
pretes a coller dans entrainement_colab.ipynb (cellules NER_DATA, SECTEUR_DATA,
CATEGORIE_DATA), a la place des petits jeux de donnees de demonstration.

Usage :
    python -m app.nlp.convertir_export_label_studio chemin/vers/export.json
"""
import argparse
import json
import re

TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def tokeniser(texte):
    return [(m.group(), m.start(), m.end()) for m in TOKEN_RE.finditer(texte)]


def convertir_ner(texte, spans):
    tokens_info = tokeniser(texte)
    tokens = [t for t, _, _ in tokens_info]
    tags = ["O"] * len(tokens)

    for span in spans:
        debut, fin, label = span["start"], span["end"], span["labels"][0]
        premier = True
        for i, (_, t_debut, t_fin) in enumerate(tokens_info):
            if t_debut >= fin:
                break
            if t_fin <= debut:
                continue
            tags[i] = f"B-{label}" if premier else f"I-{label}"
            premier = False

    return tokens, tags


def extraire_choix(resultats, nom_champ):
    for r in resultats:
        if r.get("from_name") == nom_champ:
            valeurs = r["value"].get("choices") or []
            return valeurs[0] if valeurs else None
    return None


def convertir(chemin_export):
    with open(chemin_export, encoding="utf-8") as f:
        taches = json.load(f)

    ner_data = []
    secteur_data = []
    categorie_data = []

    for tache in taches:
        annotations = tache.get("annotations") or []
        if not annotations:
            continue
        resultats = annotations[0].get("result", [])
        texte = tache["data"]["texte"]

        spans = [
            {"start": r["value"]["start"], "end": r["value"]["end"], "labels": r["value"]["labels"]}
            for r in resultats
            if r.get("type") == "labels"
        ]
        tokens, tags = convertir_ner(texte, spans)
        if any(tag != "O" for tag in tags):
            ner_data.append((tokens, tags))

        secteur = extraire_choix(resultats, "secteur_final")
        if secteur:
            secteur_data.append((texte, secteur))

        categorie = extraire_choix(resultats, "categorie_contrat_finale")
        if categorie:
            categorie_data.append((texte, categorie))

    return ner_data, secteur_data, categorie_data


def formater_python(nom, valeurs):
    lignes = [f"{nom} = ["]
    for item in valeurs:
        lignes.append(f"    {item!r},")
    lignes.append("]")
    return "\n".join(lignes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convertit un export JSON Label Studio vers NER_DATA/SECTEUR_DATA/CATEGORIE_DATA"
    )
    parser.add_argument("export_json", help="Fichier JSON exporte depuis Label Studio")
    parser.add_argument("--sortie", default="donnees_annotees.py")
    args = parser.parse_args()

    ner_data, secteur_data, categorie_data = convertir(args.export_json)

    with open(args.sortie, "w", encoding="utf-8") as f:
        f.write(formater_python("NER_DATA", ner_data) + "\n\n")
        f.write(formater_python("SECTEUR_DATA", secteur_data) + "\n\n")
        f.write(formater_python("CATEGORIE_DATA", categorie_data) + "\n")

    print(
        f"{len(ner_data)} exemples NER, {len(secteur_data)} exemples secteur, "
        f"{len(categorie_data)} exemples categorie -> {args.sortie}"
    )
