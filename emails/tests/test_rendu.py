"""Non-régression : le générateur doit reproduire exactement les mails réellement
envoyés par Brevo (HTML récupéré via l'API dans tests/references/).

  python3 emails/tests/test_rendu.py
"""

import sys
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))

import commun  # noqa: E402

REFERENCES = {
    ("2026-10-03-tablee-2", "annonce"): 9,
    ("2026-10-03-tablee-2", "relance"): 10,
    ("2026-10-03-tablee-2", "jour-j"): 11,
    ("2026-11-29-assemblee-generale", "invitation"): 12,
    ("2026-11-29-assemblee-generale", "partenaires"): 13,
}


class RenduIdentique(unittest.TestCase):
    def test_references(self):
        for (nom, cle), campagne in REFERENCES.items():
            with self.subTest(evenement=nom, envoi=cle, campagne=campagne):
                evt = commun.charger(commun.chemin_evenement(nom))
                attendu = (ICI / "references" / f"campagne-{campagne}.html").read_text(encoding="utf-8")
                # Brevo retire le saut de ligne final : c'est la seule tolérance.
                self.assertEqual(commun.rendre(evt, cle).rstrip("\n"), attendu.rstrip("\n"))

    def test_empreinte_ignore_ordre_des_listes(self):
        a = commun.empreinte("<p>x</p>\n", "o", "a", [6, 3, 2], [7])
        b = commun.empreinte("<p>x</p>", "o", "a", [2, 3, 6], [7])
        self.assertEqual(a, b)
        self.assertNotEqual(a, commun.empreinte("<p>y</p>", "o", "a", [2, 3, 6], [7]))
        self.assertNotEqual(a, commun.empreinte("<p>x</p>", "o", "a", [2, 3], [7]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
