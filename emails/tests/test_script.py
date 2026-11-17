"""Tests de brevo_campaign.py contre un faux Brevo en mémoire (aucun appel réseau).

  python3 emails/tests/test_script.py
"""

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))

import brevo_campaign as bc  # noqa: E402
import commun  # noqa: E402

LISTES = {i: {"id": i, "name": f"liste {i}", "uniqueSubscribers": 10} for i in (2, 3, 6, 7, 8)}


class FauxBrevo:
    def __init__(self):
        self.campagnes = {}
        self.appels = []
        self.prochain_id = 100

    def __call__(self, methode, chemin, corps=None):
        if methode != "GET" and not bc.APPLIQUER:
            raise RuntimeError("écriture en simulation")
        self.appels.append((methode, chemin, corps))
        if chemin.startswith("/contacts/lists"):
            return {"lists": list(LISTES.values())}
        if chemin == "/emailCampaigns" and methode == "POST":
            cid = self.prochain_id
            self.prochain_id += 1
            self.campagnes[cid] = {"id": cid, "status": "draft"}
            self._maj(cid, corps)
            return {"id": cid}
        parts = chemin.split("/")
        cid = int(parts[2])
        if len(parts) == 3 and methode == "GET":
            return dict(self.campagnes[cid])
        if len(parts) == 3 and methode == "PUT":
            if "scheduledAt" in corps and len(corps) == 1:
                self.campagnes[cid].update(status="queued", scheduledAt=corps["scheduledAt"])
            else:
                self._maj(cid, corps)
            return None
        if parts[3] == "sendTest":
            return None
        if parts[3] == "sendNow":
            self.campagnes[cid]["status"] = "sent"
            return None
        raise AssertionError(chemin)

    def _maj(self, cid, corps):
        self.campagnes[cid].update(
            name=corps["name"], subject=corps["subject"], previewText=corps["previewText"],
            htmlContent=corps["htmlContent"].rstrip("\n"),  # comme Brevo
            recipients={"lists": corps["recipients"]["listIds"],
                        "exclusionLists": corps["recipients"]["exclusionListIds"]})

    def ecritures(self):
        return [a for a in self.appels if a[0] != "GET"]


class Script(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "evenements").mkdir()
        evt = json.loads((commun.EVENEMENTS / "2026-11-29-assemblee-generale.json").read_text(encoding="utf-8"))
        for e in evt["envois"].values():
            e.pop("brevo", None)  # un événement neuf, sans campagne
        self.chemin = self.tmp / "evenements" / "nouveau.json"
        commun.enregistrer(self.chemin, evt)
        self.brevo = FauxBrevo()
        self.patches = [mock.patch.object(commun, "EVENEMENTS", self.tmp / "evenements"),
                        mock.patch.object(commun, "GENERES", self.tmp / "generes"),
                        mock.patch.object(bc, "appel", self.brevo)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def lancer(self, *argv):
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["brevo_campaign.py", *argv]), redirect_stdout(sortie):
            try:
                code = bc.main()
            except bc.Refus as e:
                return "refus", str(e), sortie.getvalue()
        return code, None, sortie.getvalue()

    def evt(self):
        return json.loads(self.chemin.read_text(encoding="utf-8"))

    def test_simulation_ne_change_rien(self):
        code, _, out = self.lancer("brouillons", "nouveau")
        self.assertEqual(code, 0)
        self.assertIn("création d'un brouillon", out)
        self.assertEqual(self.brevo.ecritures(), [])
        self.assertNotIn("campagne_id", self.evt()["envois"]["invitation"].get("brevo", {}))

    def test_parcours_complet(self):
        self.lancer("brouillons", "nouveau", "--appliquer")
        cid = self.evt()["envois"]["invitation"]["brevo"]["campagne_id"]
        self.assertEqual(self.brevo.campagnes[cid]["status"], "draft")
        # pas de test → envoi refusé
        r, msg, _ = self.lancer("envoyer", "nouveau", "--envoi", "invitation", "--appliquer")
        self.assertEqual(r, "refus")
        self.assertIn("aucun envoi test", msg)
        # test en simulation : rien d'enregistré
        self.lancer("test", "nouveau", "--envoi", "invitation")
        self.assertNotIn("test", self.evt()["envois"]["invitation"]["brevo"])
        # test réel
        self.lancer("test", "nouveau", "--envoi", "invitation", "--appliquer")
        self.assertIn(("POST", f"/emailCampaigns/{cid}/sendTest", {"emailTo": ["contact@asso-lagrange.fr"]}),
                      self.brevo.appels)
        # brouillon retouché à la main dans Brevo → refus
        self.brevo.campagnes[cid]["subject"] = "objet retouché"
        r, msg, _ = self.lancer("envoyer", "nouveau", "--envoi", "invitation", "--appliquer")
        self.assertEqual(r, "refus")
        self.assertIn("a changé dans Brevo", msg)
        self.brevo.campagnes[cid]["subject"] = self.evt()["envois"]["invitation"]["objet"]
        # config modifiée après le test → refus
        evt = self.evt()
        evt["envois"]["invitation"]["apercu"] += " !"
        commun.enregistrer(self.chemin, evt)
        r, msg, _ = self.lancer("envoyer", "nouveau", "--envoi", "invitation", "--appliquer")
        self.assertEqual(r, "refus")
        self.assertIn("config a changé", msg)
        # brouillons ré-applique → le test est invalidé
        self.lancer("brouillons", "nouveau", "--envoi", "invitation", "--appliquer")
        self.assertNotIn("test", self.evt()["envois"]["invitation"]["brevo"])
        self.lancer("test", "nouveau", "--envoi", "invitation", "--appliquer")
        # simulation d'envoi : aucune écriture
        avant = len(self.brevo.ecritures())
        code, _, out = self.lancer("envoyer", "nouveau", "--envoi", "invitation")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.brevo.ecritures()), avant)
        # envoi réel
        code, _, _ = self.lancer("envoyer", "nouveau", "--envoi", "invitation", "--appliquer")
        self.assertEqual(code, 0)
        self.assertEqual(self.brevo.campagnes[cid]["status"], "sent")
        self.assertEqual(self.evt()["envois"]["invitation"]["brevo"]["envoi"]["mode"], "immédiat")
        # plus un brouillon : brouillons n'y touche plus, envoyer refuse
        code, _, out = self.lancer("brouillons", "nouveau", "--envoi", "invitation", "--appliquer")
        self.assertIn("je n'y touche pas", out)
        r, _, _ = self.lancer("envoyer", "nouveau", "--envoi", "invitation", "--appliquer")
        self.assertEqual(r, "refus")

    def test_programmation(self):
        self.lancer("brouillons", "nouveau", "--envoi", "partenaires", "--appliquer")
        self.lancer("test", "nouveau", "--envoi", "partenaires", "--appliquer")
        r, msg, _ = self.lancer("envoyer", "nouveau", "--envoi", "partenaires", "--le", "2020-01-01 10:00", "--appliquer")
        self.assertEqual(r, "refus")
        quand = (datetime.now(bc.PARIS) + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        code, _, _ = self.lancer("envoyer", "nouveau", "--envoi", "partenaires", "--le", quand, "--appliquer")
        self.assertEqual(code, 0)
        cid = self.evt()["envois"]["partenaires"]["brevo"]["campagne_id"]
        self.assertEqual(self.brevo.campagnes[cid]["status"], "queued")
        self.assertTrue(self.brevo.campagnes[cid]["scheduledAt"].startswith(quand.replace(" ", "T")))
        self.assertNotIn(("POST", f"/emailCampaigns/{cid}/sendNow", None), self.brevo.appels)

    def test_charge_utile(self):
        evt = commun.charger(self.chemin)
        c = bc.charge_utile(evt["envois"]["partenaires"], "<html></html>")
        self.assertEqual(c["recipients"], {"listIds": [8], "exclusionListIds": [2, 3, 6, 7]})
        self.assertEqual(c["sender"]["email"], "contact@asso-lagrange.fr")
        self.assertEqual(c["footer"], "[DEFAULT_FOOTER]")


class VraiAppel(unittest.TestCase):
    def test_garde_fou_du_vrai_appel(self):
        bc.APPLIQUER = False
        with self.assertRaises(RuntimeError):
            bc.appel("POST", "/emailCampaigns", {})

    def test_cle_jamais_sur_la_ligne_de_commande(self):
        bc.APPLIQUER = False
        with mock.patch.dict("os.environ", {"BREVO_API_KEY": "cle-bidon"}), \
             mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout='{"ok":1}\n200', stderr="")
            bc.appel("GET", "/account")
        cmd = run.call_args.args[0]
        self.assertNotIn("cle-bidon", " ".join(cmd))
        self.assertIn("api-key: cle-bidon", run.call_args.kwargs["input"])

    def test_sans_cle_aucun_entete(self):
        with mock.patch.dict("os.environ", {}, clear=False), \
             mock.patch.object(bc, "RACINE", Path(tempfile.mkdtemp())), \
             mock.patch("subprocess.run") as run:
            import os
            os.environ.pop("BREVO_API_KEY", None)
            run.return_value = mock.Mock(returncode=0, stdout='{}\n200', stderr="")
            bc.appel("GET", "/account")
        self.assertNotIn("-K", run.call_args.args[0])
        self.assertIsNone(run.call_args.kwargs["input"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
