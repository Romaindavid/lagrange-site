#!/usr/bin/env python3
"""Pilote les campagnes Brevo de La Grange depuis les fichiers d'événement.

Commandes (simulation par défaut : rien ne change dans Brevo sans --appliquer) :

  verifier   <événement>                  contrôles en lecture seule (config, listes, état Brevo)
  brouillons <événement> [--envoi CLE]    crée ou met à jour les campagnes en brouillon
  test       <événement> --envoi CLE      envoie le test (par défaut aux test_destinataires)
  envoyer    <événement> --envoi CLE [--le "AAAA-MM-JJ HH:MM"]
                                          envoie (ou programme, heure de Paris) la campagne,
                                          seulement si le test porte sur la version exacte

Exemples :
  python3 emails/brevo_campaign.py verifier 2026-11-29-assemblee-generale
  python3 emails/brevo_campaign.py brouillons 2026-11-29-assemblee-generale --appliquer
  python3 emails/brevo_campaign.py envoyer 2026-11-29-assemblee-generale --envoi relance --le "2026-11-25 18:00"

Clé API : variable BREVO_API_KEY, sinon fichier .env.local à la racine du dépôt
(ignoré par git), sinon aucune clé n'est envoyée (environnement cloud Claude Code :
le proxy ajoute l'en-tête api-key pour api.brevo.com).
Bibliothèque standard uniquement ; les appels HTTP passent par curl.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import commun

API = "https://api.brevo.com/v3"
PARIS = ZoneInfo("Europe/Paris")
RACINE = commun.DOSSIER.parent
EXPEDITEUR = {"name": "La Grange", "email": "contact@asso-lagrange.fr"}
REPONSE_A = "contact@asso-lagrange.fr"

APPLIQUER = False


class Refus(Exception):
    """Condition non remplie : on s'arrête sans rien faire."""


# --------------------------------------------------------------------------- HTTP

def cle_api():
    if os.environ.get("BREVO_API_KEY"):
        return os.environ["BREVO_API_KEY"].strip(), "variable BREVO_API_KEY"
    env_local = RACINE / ".env.local"
    if env_local.is_file():
        for ligne in env_local.read_text(encoding="utf-8").splitlines():
            nom, _, valeur = ligne.strip().partition("=")
            if nom.strip() == "BREVO_API_KEY" and valeur.strip():
                return valeur.strip().strip("'\""), ".env.local"
    return None, "aucune (ajoutée par le proxy si l'environnement la fournit)"


def appel(methode, chemin, corps=None):
    if methode != "GET" and not APPLIQUER:
        raise RuntimeError(f"garde-fou : {methode} {chemin} refusé en simulation")
    cle, _ = cle_api()
    cmd = ["curl", "-sS", "-X", methode, API + chemin,
           "-H", "accept: application/json", "-w", "\n%{http_code}"]
    config = None
    if cle:
        # La clé passe par l'entrée standard, pas par la ligne de commande (visible dans ps).
        config = f'header = "api-key: {cle}"\n'
        cmd += ["-K", "-"]
    fichier = None
    try:
        if corps is not None:
            fichier = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
            json.dump(corps, fichier, ensure_ascii=False)
            fichier.close()
            cmd += ["-H", "content-type: application/json", "--data-binary", "@" + fichier.name]
        res = subprocess.run(cmd, input=config, capture_output=True, text=True, encoding="utf-8")
    finally:
        if fichier:
            os.unlink(fichier.name)
    if res.returncode != 0:
        raise Refus(f"curl a échoué ({methode} {chemin}) : {res.stderr.strip()}")
    texte, _, code = res.stdout.rpartition("\n")
    code = int(code or 0)
    donnees = None
    if texte.strip():
        try:
            donnees = json.loads(texte)
        except json.JSONDecodeError:
            donnees = texte
    if not 200 <= code < 300:
        detail = donnees.get("message") if isinstance(donnees, dict) else donnees
        if code == 401:
            detail = f"{detail} : aucune clé valide (voir BREVO_API_KEY / .env.local / secret réseau)"
        raise Refus(f"Brevo a répondu {code} à {methode} {chemin} : {detail}")
    return donnees


# --------------------------------------------------------------------------- Brevo

def campagne(cid):
    return appel("GET", f"/emailCampaigns/{cid}")


def empreinte_distante(c):
    r = c.get("recipients") or {}
    return commun.empreinte(c.get("htmlContent"), c.get("subject"), c.get("previewText"),
                            r.get("lists"), r.get("exclusionLists"))


def listes_brevo():
    d = appel("GET", "/contacts/lists?limit=50")
    return {l["id"]: l for l in d.get("lists", [])}


def decrire_listes(ids, listes):
    if not ids:
        return "aucune"
    return ", ".join(f"{i} « {listes[i]['name']} » ({listes[i].get('uniqueSubscribers', '?')})"
                     if i in listes else f"{i} (INEXISTANTE)" for i in ids)


def differences(envoi, html, c):
    r = c.get("recipients") or {}
    diff = []
    if (c.get("htmlContent") or "").rstrip() != html.rstrip():
        diff.append("HTML")
    if c.get("subject") != envoi["objet"]:
        diff.append(f"objet (Brevo : « {c.get('subject')} »)")
    if (c.get("previewText") or "") != envoi["apercu"]:
        diff.append(f"aperçu (Brevo : « {c.get('previewText')} »)")
    if sorted(r.get("lists") or []) != sorted(envoi["listes"]):
        diff.append(f"listes (Brevo : {r.get('lists')})")
    if sorted(r.get("exclusionLists") or []) != sorted(envoi.get("exclusions", [])):
        diff.append(f"exclusions (Brevo : {r.get('exclusionLists')})")
    if c.get("name") != envoi["nom_campagne"]:
        diff.append(f"nom (Brevo : « {c.get('name')} »)")
    return diff


def charge_utile(envoi, html):
    return {
        "name": envoi["nom_campagne"],
        "subject": envoi["objet"],
        "previewText": envoi["apercu"],
        "sender": EXPEDITEUR,
        "replyTo": REPONSE_A,
        "htmlContent": html,
        "recipients": {"listIds": envoi["listes"], "exclusionListIds": envoi.get("exclusions", [])},
        "header": "[DEFAULT_HEADER]",
        "footer": "[DEFAULT_FOOTER]",
        "inlineImageActivation": False,
        "mirrorActive": False,
    }


# --------------------------------------------------------------------------- utilitaires

def rel(p):
    try:
        return Path(p).relative_to(RACINE)
    except ValueError:
        return p


def maintenant():
    return datetime.now(PARIS).isoformat(timespec="seconds")


def titre(texte):
    print(f"\n── {texte}")


def envois_vises(evt, cle):
    if cle is None:
        return list(evt["envois"])
    if cle not in evt["envois"]:
        raise Refus(f"envoi {cle!r} inconnu (disponibles : {', '.join(evt['envois'])})")
    return [cle]


def etat_brevo(envoi):
    return envoi.setdefault("brevo", {})


def ecrire_html(chemin_evt, cle, html):
    cible = commun.chemin_html(chemin_evt, cle)
    cible.parent.mkdir(parents=True, exist_ok=True)
    if not cible.exists() or cible.read_text(encoding="utf-8") != html:
        cible.write_text(html, encoding="utf-8")
        print(f"   HTML régénéré : {rel(cible)}")


def campagne_brouillon(envoi):
    cid = etat_brevo(envoi).get("campagne_id")
    if not cid:
        raise Refus("pas encore de campagne Brevo : lancer d'abord « brouillons »")
    c = campagne(cid)
    if c.get("status") != "draft":
        raise Refus(f"la campagne {cid} n'est plus un brouillon (statut Brevo : {c.get('status')})")
    return cid, c


# --------------------------------------------------------------------------- commandes

def cmd_verifier(chemin, evt, args):
    problemes = []
    print(f"Clé API : {cle_api()[1]}")
    compte = appel("GET", "/account")
    print(f"Compte Brevo : {compte.get('companyName')} ({compte.get('email')}), "
          f"plan {', '.join(p.get('type', '?') for p in compte.get('plan', []))}")
    listes = listes_brevo()
    expediteurs = appel("GET", "/senders").get("senders", [])
    if not any(s["email"] == EXPEDITEUR["email"] and s.get("active") for s in expediteurs):
        problemes.append(f"expéditeur {EXPEDITEUR['email']} absent ou inactif dans Brevo")
    if not evt.get("test_destinataires"):
        problemes.append("test_destinataires vide")

    for cle in envois_vises(evt, args.envoi):
        envoi = evt["envois"][cle]
        html = commun.rendre(evt, cle)
        local = commun.empreinte_locale(evt, cle)
        titre(f"{cle} : {envoi['nom_campagne']}")
        print(f"   objet        : {envoi['objet']}")
        print(f"   aperçu       : {envoi['apercu']}")
        print(f"   destinataires: {decrire_listes(envoi['listes'], listes)}")
        print(f"   exclusions   : {decrire_listes(envoi.get('exclusions', []), listes)}")
        print(f"   empreinte    : {local}")
        for i in envoi["listes"] + envoi.get("exclusions", []):
            if i not in listes:
                problemes.append(f"{cle} : la liste {i} n'existe pas dans Brevo")
        fichier = commun.chemin_html(chemin, cle)
        if not fichier.exists() or fichier.read_text(encoding="utf-8") != html:
            problemes.append(f"{cle} : {rel(fichier)} pas à jour (python3 emails/generer.py)")
        if "http://" in html:
            problemes.append(f"{cle} : lien ou image en http:// (préférer https://)")
        b = envoi.get("brevo", {})
        if not b.get("campagne_id"):
            print("   Brevo        : pas encore de campagne")
            continue
        c = campagne(b["campagne_id"])
        distante = empreinte_distante(c)
        print(f"   Brevo        : campagne {c['id']}, statut {c.get('status')}"
              + (f", envoyée le {c['sentDate']}" if c.get("sentDate") else "")
              + (f", programmée le {c['scheduledAt']}" if c.get("scheduledAt") and c.get("status") == "queued" else ""))
        ecarts = differences(envoi, html, c)
        print("   comparaison  : identique à la config" if not ecarts else f"   comparaison  : diffère sur {', '.join(ecarts)}")
        test = b.get("test", {})
        if c.get("status") == "draft":
            if not test:
                print("   test         : aucun")
            else:
                ok = test.get("empreinte") == local == distante
                print(f"   test         : le {test.get('le')} → "
                      + ("version exacte, envoi possible" if ok else "PÉRIMÉ (contenu changé depuis), refaire le test"))
    titre("Bilan")
    if problemes:
        for p in problemes:
            print(f"   ✗ {p}")
        return 1
    print("   ✓ aucun problème détecté")
    return 0


def cmd_brouillons(chemin, evt, args):
    listes = listes_brevo()
    modifie = False
    for cle in envois_vises(evt, args.envoi):
        envoi = evt["envois"][cle]
        html = commun.rendre(evt, cle)
        ecrire_html(chemin, cle, html)
        for i in envoi["listes"] + envoi.get("exclusions", []):
            if i not in listes:
                raise Refus(f"{cle} : la liste {i} n'existe pas dans Brevo")
        b = etat_brevo(envoi)
        titre(f"{cle} : {envoi['nom_campagne']}")
        if b.get("campagne_id"):
            c = campagne(b["campagne_id"])
            if c.get("status") != "draft":
                print(f"   campagne {c['id']} au statut « {c.get('status')} » : je n'y touche pas")
                continue
            ecarts = differences(envoi, html, c)
            if not ecarts:
                print(f"   campagne {c['id']} : brouillon déjà à jour")
                continue
            print(f"   campagne {c['id']} : mise à jour ({', '.join(ecarts)})")
            if APPLIQUER:
                appel("PUT", f"/emailCampaigns/{c['id']}", charge_utile(envoi, html))
        else:
            print(f"   création d'un brouillon : « {envoi['objet']} »")
            print(f"   vers {decrire_listes(envoi['listes'], listes)}")
            if envoi.get("exclusions"):
                print(f"   sauf {decrire_listes(envoi['exclusions'], listes)}")
            if APPLIQUER:
                b["campagne_id"] = appel("POST", "/emailCampaigns", charge_utile(envoi, html))["id"]
                modifie = True
                print(f"   → campagne {b['campagne_id']} créée")
        if APPLIQUER:
            relue = campagne(b["campagne_id"])
            restants = differences(envoi, html, relue)
            if restants:
                print(f"   ⚠ après écriture, Brevo diffère encore sur : {', '.join(restants)}")
            b["empreinte_brouillon"] = empreinte_distante(relue)
            b.pop("test", None)  # nouveau contenu : un nouveau test sera nécessaire
            modifie = True
    if modifie:
        commun.enregistrer(chemin, evt)
        print(f"\n{rel(chemin)} mis à jour (numéros de campagne, empreintes).")
    return 0


def cmd_test(chemin, evt, args):
    cle = args.envoi
    envoi = evt["envois"][envois_vises(evt, cle)[0]]
    cid, c = campagne_brouillon(envoi)
    local = commun.empreinte_locale(evt, cle)
    distante = empreinte_distante(c)
    if distante != local:
        ecarts = differences(envoi, commun.rendre(evt, cle), c)
        raise Refus(f"le brouillon {cid} ne correspond pas à la config ({', '.join(ecarts)}) : "
                    "lancer « brouillons --appliquer » ou reporter dans le JSON la retouche faite dans Brevo")
    dest = args.a or evt.get("test_destinataires") or []
    if not dest:
        raise Refus("aucun destinataire de test (test_destinataires ou --a)")
    titre(f"{cle} : envoi test de la campagne {cid} (empreinte {local})")
    print(f"   objet : [TEST] {envoi['objet']}")
    print(f"   à     : {', '.join(dest)}")
    if APPLIQUER:
        appel("POST", f"/emailCampaigns/{cid}/sendTest", {"emailTo": dest})
        etat_brevo(envoi)["test"] = {"empreinte": local, "le": maintenant(), "destinataires": dest}
        commun.enregistrer(chemin, evt)
        print("   → test envoyé. Vérifier la boîte de réception avant « envoyer ».")
    return 0


def cmd_envoyer(chemin, evt, args):
    cle = args.envoi
    envoi = evt["envois"][envois_vises(evt, cle)[0]]
    cid, c = campagne_brouillon(envoi)
    local = commun.empreinte_locale(evt, cle)
    distante = empreinte_distante(c)
    test = etat_brevo(envoi).get("test")
    if not test:
        raise Refus("aucun envoi test enregistré pour cet envoi : lancer « test » d'abord")
    if distante != test["empreinte"]:
        ecarts = differences(envoi, commun.rendre(evt, cle), c)
        raise Refus(f"le brouillon {cid} a changé dans Brevo depuis le test ({', '.join(ecarts) or 'contenu'}) : "
                    "reporter la modification dans le JSON, puis brouillons + test")
    if local != test["empreinte"]:
        raise Refus("la config a changé depuis le test : relancer brouillons puis test")

    quand = None
    if args.le:
        try:
            quand = datetime.strptime(args.le, "%Y-%m-%d %H:%M").replace(tzinfo=PARIS)
        except ValueError:
            raise Refus("--le attend le format \"AAAA-MM-JJ HH:MM\" (heure de Paris)") from None
        if quand < datetime.now(PARIS) + timedelta(minutes=5):
            raise Refus(f"{args.le} est passé ou trop proche (au moins 5 minutes)")

    listes = listes_brevo()
    titre(f"{cle} : {'PROGRAMMATION' if quand else 'ENVOI RÉEL'} de la campagne {cid}")
    print(f"   objet         : {envoi['objet']}")
    print(f"   destinataires : {decrire_listes(envoi['listes'], listes)}")
    print(f"   exclusions    : {decrire_listes(envoi.get('exclusions', []), listes)}")
    print(f"   test du {test['le']} sur la version exacte (empreinte {local})")
    print(f"   quand         : {quand.strftime('%A %d/%m/%Y à %H:%M (Paris)') if quand else 'immédiatement'}")
    if APPLIQUER:
        if quand:
            appel("PUT", f"/emailCampaigns/{cid}", {"scheduledAt": quand.isoformat(timespec="milliseconds")})
        else:
            appel("POST", f"/emailCampaigns/{cid}/sendNow")
        statut = campagne(cid).get("status")
        etat_brevo(envoi)["envoi"] = {"le": quand.isoformat() if quand else maintenant(),
                                      "mode": "programmé" if quand else "immédiat",
                                      "empreinte": local, "statut_brevo": statut}
        commun.enregistrer(chemin, evt)
        print(f"   → fait (statut Brevo : {statut}).")
    return 0


COMMANDES = {"verifier": cmd_verifier, "brouillons": cmd_brouillons, "test": cmd_test, "envoyer": cmd_envoyer}


def main():
    global APPLIQUER
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("commande", choices=COMMANDES)
    ap.add_argument("evenement", help="fichier d'événement (ex. 2026-11-29-assemblee-generale)")
    ap.add_argument("--envoi", help="clé de l'envoi dans le JSON (obligatoire pour test et envoyer)")
    ap.add_argument("--appliquer", action="store_true", help="agir réellement dans Brevo (sinon simulation)")
    ap.add_argument("--le", help="envoyer : programmer à cette date, \"AAAA-MM-JJ HH:MM\" heure de Paris")
    ap.add_argument("--a", nargs="+", metavar="EMAIL", help="test : destinataires (sinon test_destinataires)")
    args = ap.parse_args()
    if args.commande in ("test", "envoyer") and not args.envoi:
        ap.error(f"{args.commande} exige --envoi (un seul envoi à la fois)")
    if args.le and args.commande != "envoyer":
        ap.error("--le ne s'utilise qu'avec envoyer")
    APPLIQUER = args.appliquer and args.commande != "verifier"

    chemin = commun.chemin_evenement(args.evenement)
    evt = commun.charger(chemin)
    if args.commande != "verifier":
        print("MODE RÉEL : Brevo va être modifié." if APPLIQUER
              else "SIMULATION : rien ne change dans Brevo (ajouter --appliquer pour agir).")
    code = COMMANDES[args.commande](chemin, evt, args)
    if args.commande != "verifier" and not APPLIQUER:
        print("\n(simulation terminée, rien n'a été modifié)")
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Refus, commun.ErreurConfig) as e:
        sys.exit(f"\nRefusé : {e}")
