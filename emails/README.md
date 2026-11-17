# Emails de La Grange

Les emails sont décrits en JSON, générés en HTML et envoyés dans Brevo par script.
Plus de copier-coller. Ce dossier n'est pas publié sur le site (`_config.yml`).

## Nouvel envoi

1. **Créer le JSON** : `evenements/AAAA-MM-JJ-nom.json` (date de l'événement).
   Partir d'un fichier existant. Un fichier peut contenir plusieurs envois
   (annonce, relance, jour J, partenaires…).
2. **Préparer les brouillons** :
   ```bash
   python3 emails/brevo_campaign.py brouillons AAAA-MM-JJ-nom             # simulation
   python3 emails/brevo_campaign.py brouillons AAAA-MM-JJ-nom --appliquer
   ```
   Le HTML est écrit dans `generes/AAAA-MM-JJ-nom/<envoi>.html` et le numéro
   de campagne Brevo est noté dans le JSON. Committer les deux.
3. **Envoyer le test** puis le vérifier dans la boîte `contact@asso-lagrange.fr` :
   ```bash
   python3 emails/brevo_campaign.py test AAAA-MM-JJ-nom --envoi relance --appliquer
   ```
4. **Envoyer ou programmer** (heure de Paris) :
   ```bash
   python3 emails/brevo_campaign.py envoyer AAAA-MM-JJ-nom --envoi relance --appliquer
   python3 emails/brevo_campaign.py envoyer AAAA-MM-JJ-nom --envoi relance --le "2026-11-25 18:00" --appliquer
   ```

`verifier` fait le point à tout moment, sans rien modifier.

## Garde-fous

- Sans `--appliquer`, **rien ne change dans Brevo** : le script montre ce qu'il ferait.
- `brouillons` ne touche jamais une campagne déjà envoyée ou programmée.
- `envoyer` refuse s'il n'y a pas eu de test **sur la version exacte**, si la config
  a changé depuis, ou si le brouillon a été retouché à la main dans Brevo.
  L'empreinte couvre le HTML, l'objet, l'aperçu, les listes et les exclusions.
  Une retouche faite dans Brevo doit être reportée dans le JSON, puis `brouillons` + `test`.

## Le JSON

| Champ | Rôle |
|---|---|
| `nom_campagne` | nom interne dans Brevo |
| `objet`, `apercu` | objet du mail et texte d'aperçu (boîte de réception) |
| `listes`, `exclusions` | numéros des listes Brevo (voir ci-dessous) |
| `contenu` | `entete` (`titre`, `surtitre`, `sous_titre`) et `blocs` |
| `contenu_de` | reprend le contenu d'un autre envoi (ex. version partenaires) |
| `brevo` | rempli par le script : numéro de campagne, test, envoi |

Blocs : `texte`, `encadre`, `liste`, `photo`, `bouton`, `signature` (détail dans
`gabarit.py`). Les textes acceptent du HTML simple : `<strong>`, `&nbsp;` avant
`! ? :`. Les images doivent être en ligne sur `https://asso-lagrange.fr/Photos/…`.

Listes Brevo (novembre 2026) : 2 « Votre première liste », 3 « Tablées #1 »,
6 « Collège solidaire », 7 « Tablées #2 » (inscrits), 8 « partenaires ».
Envoi général habituel : `[2, 3, 6]`. Version partenaires : `[8]` en excluant `[2, 3, 6, 7]`.

## Clé API

Jamais dans le code ni dans git. Le script cherche, dans l'ordre :
`BREVO_API_KEY`, puis `.env.local` à la racine (ligne `BREVO_API_KEY=…`, ignoré par git),
sinon n'envoie aucune clé : dans l'environnement cloud Claude Code, le proxy
l'ajoute pour `api.brevo.com` (secret réseau, en-tête `api-key`, sans préfixe).

## Tests

```bash
python3 emails/tests/test_rendu.py    # le générateur reproduit à l'octet les mails envoyés (campagnes 9 à 13)
python3 emails/tests/test_script.py   # le script contre un faux Brevo (aucun appel réseau)
python3 emails/generer.py --verifier  # les HTML de generes/ sont à jour
```

`archives/` contient les anciens mails écrits à la main (avant cet outillage).
