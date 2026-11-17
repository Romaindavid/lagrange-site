"""Chargement des fichiers d'événement et calcul des empreintes."""

import hashlib
import re
import json
from pathlib import Path

import gabarit

DOSSIER = Path(__file__).resolve().parent
EVENEMENTS = DOSSIER / "evenements"
GENERES = DOSSIER / "generes"

CHAMPS_OBLIGATOIRES = ("nom_campagne", "objet", "apercu", "listes")


class ErreurConfig(ValueError):
    pass


def chemin_evenement(nom):
    """Accepte un chemin, un nom de fichier ou un nom sans extension."""
    p = Path(nom)
    for candidat in (p, EVENEMENTS / p.name, EVENEMENTS / (p.name + ".json")):
        if candidat.is_file():
            return candidat.resolve()
    raise ErreurConfig(f"événement introuvable : {nom} (cherché dans {EVENEMENTS})")


def tous_les_evenements():
    return sorted(EVENEMENTS.glob("*.json"))


def charger(chemin):
    chemin = Path(chemin)
    try:
        evt = json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErreurConfig(f"{chemin.name} : JSON invalide ({e})") from None
    envois = evt.get("envois")
    if not isinstance(envois, dict) or not envois:
        raise ErreurConfig(f"{chemin.name} : il faut un objet \"envois\" non vide")
    for cle, envoi in envois.items():
        manquants = [c for c in CHAMPS_OBLIGATOIRES if not envoi.get(c)]
        if manquants:
            raise ErreurConfig(f"{chemin.name} / {cle} : champ(s) manquant(s) : {', '.join(manquants)}")
        if "contenu_de" in envoi:
            source = envois.get(envoi["contenu_de"])
            if not source or "contenu" not in source:
                raise ErreurConfig(f"{chemin.name} / {cle} : contenu_de → envoi {envoi['contenu_de']!r} introuvable")
        elif "contenu" not in envoi:
            raise ErreurConfig(f"{chemin.name} / {cle} : il faut \"contenu\" ou \"contenu_de\"")
        for champ in ("listes", "exclusions"):
            if not all(isinstance(x, int) for x in envoi.get(champ, [])):
                raise ErreurConfig(f"{chemin.name} / {cle} : {champ} doit être une liste de numéros de listes Brevo")
    return evt


def enregistrer(chemin, evt):
    texte = json.dumps(evt, ensure_ascii=False, indent=2)
    # Listes de numéros sur une seule ligne : "listes": [2, 3, 6]
    texte = re.sub(r"\[\s*(\d+(?:,\s*\d+)*)\s*\]",
                   lambda m: "[" + ", ".join(re.split(r",\s*", m.group(1))) + "]", texte)
    Path(chemin).write_text(texte + "\n", encoding="utf-8")


def contenu(evt, cle):
    envoi = evt["envois"][cle]
    if "contenu_de" in envoi:
        return evt["envois"][envoi["contenu_de"]]["contenu"]
    return envoi["contenu"]


def rendre(evt, cle):
    envoi = dict(evt["envois"][cle])
    envoi["contenu"] = contenu(evt, cle)
    try:
        return gabarit.rendre(envoi)
    except gabarit.ErreurGabarit as e:
        raise ErreurConfig(f"{cle} : {e}") from None


def chemin_html(chemin_evt, cle):
    return GENERES / Path(chemin_evt).stem / f"{cle}.html"


def empreinte(html, objet, apercu, listes, exclusions):
    """Empreinte de ce qui part réellement : HTML, objet, aperçu, destinataires.

    Le saut de ligne final est ignoré (Brevo le retire) et l'ordre des listes aussi.
    """
    donnees = {
        "html": (html or "").rstrip(),
        "objet": objet or "",
        "apercu": apercu or "",
        "listes": sorted(listes or []),
        "exclusions": sorted(exclusions or []),
    }
    brut = json.dumps(donnees, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(brut).hexdigest()[:16]


def empreinte_locale(evt, cle):
    envoi = evt["envois"][cle]
    return empreinte(rendre(evt, cle), envoi["objet"], envoi["apercu"],
                     envoi["listes"], envoi.get("exclusions", []))
