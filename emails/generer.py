#!/usr/bin/env python3
"""Génère le HTML des emails à partir des fichiers d'événement.

  python3 emails/generer.py                       # tous les événements
  python3 emails/generer.py 2026-11-29-assemblee-generale
  python3 emails/generer.py --verifier            # échoue si un fichier généré n'est pas à jour

Les fichiers sont écrits dans emails/generes/<événement>/<envoi>.html (versionnés).
"""

import argparse
import sys

import commun


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("evenements", nargs="*", help="fichiers d'événement (par défaut : tous)")
    ap.add_argument("--verifier", action="store_true", help="ne rien écrire, vérifier que tout est à jour")
    args = ap.parse_args()

    chemins = [commun.chemin_evenement(e) for e in args.evenements] or commun.tous_les_evenements()
    pas_a_jour = 0
    for chemin in chemins:
        evt = commun.charger(chemin)
        for cle in evt["envois"]:
            html = commun.rendre(evt, cle)
            cible = commun.chemin_html(chemin, cle)
            actuel = cible.read_text(encoding="utf-8") if cible.exists() else None
            nom = cible.relative_to(commun.DOSSIER.parent)
            if actuel == html:
                print(f"  inchangé   {nom}")
            elif args.verifier:
                print(f"  PAS À JOUR {nom}")
                pas_a_jour += 1
            else:
                cible.parent.mkdir(parents=True, exist_ok=True)
                cible.write_text(html, encoding="utf-8")
                print(f"  écrit      {nom}")
    if pas_a_jour:
        print(f"\n{pas_a_jour} fichier(s) à régénérer : python3 emails/generer.py")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except commun.ErreurConfig as e:
        sys.exit(f"Erreur : {e}")
