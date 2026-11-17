"""Gabarit HTML des emails de La Grange.

Reproduit à l'identique la charte des mails envoyés jusqu'ici (carte 600 px,
fond crème, accent terracotta, pied de page de l'association).

Un email = un en-tête + une suite de blocs, décrits dans le JSON de l'événement.
Les textes peuvent contenir du HTML en ligne (<strong>, &nbsp;, <br />…) : ils
sont insérés tels quels.

Blocs disponibles (champ "type") :
  texte      paragraphes, avec un intertitre facultatif
  encadre    encadré beige (lignes séparées par des retours), bordure facultative
  liste      liste « À ne pas oublier » (éléments + sous-lignes facultatives)
  photo      image pleine largeur
  bouton     bouton terracotta, avec texte avant / après facultatif
  signature  message final + « L'équipe de La Grange »
Chaque bloc accepte "commentaire" (commentaire HTML) et "espace" (marge haute en px).
"""

LOGO = "https://asso-lagrange.fr/Photos/logo.png"

INTERTITRE = ('<p style="margin:0 0 14px; font-family:Arial,sans-serif; font-size:13px; '
              'color:#C4622D; font-weight:bold; text-transform:uppercase; letter-spacing:.06em;">{}</p>')

PAR_DEFAUT = {
    "texte": {"commentaire": "Texte", "espace": 28},
    "encadre": {"commentaire": "Infos pratiques", "espace": 24},
    "liste": {"commentaire": "À ne pas oublier", "espace": 28},
    "photo": {"commentaire": "Photo", "espace": 28},
    "bouton": {"commentaire": "Bouton", "espace": 28},
    "signature": {"commentaire": "Message final"},
}


class ErreurGabarit(ValueError):
    pass


def _lignes(*lignes):
    return "\n".join(lignes)


def _entete(e):
    titre = e["titre"]
    taille = e.get("taille_titre", 28)
    interligne = e.get("interligne_titre", 1.25)
    sous_titre = e.get("sous_titre")
    marge = "6px 0" if sous_titre else "6px 0 0"
    out = [
        "          <!-- Header -->",
        "          <tr>",
        '            <td style="background:#F5F0E8; padding: 40px 40px 32px; text-align:center; border-bottom: 3px solid #C4622D;">',
        f'              <img src="{LOGO}" alt="Logo La Grange" width="150" style="display:block; margin:0 auto 20px; height:auto;" />',
    ]
    if e.get("surtitre"):
        out.append('              <p style="margin:0 0 8px; color:#555; font-family:Arial,sans-serif; font-size:13px; '
                   f'font-weight:bold; text-transform:uppercase; letter-spacing:.06em;">{e["surtitre"]}</p>')
    out.append(f'              <h1 style="margin:{marge}; color:#C4622D; font-size:{taille}px; font-weight:normal; '
               f'line-height:{interligne}; font-family: Georgia, serif;">{titre}</h1>')
    if sous_titre:
        out.append(f'              <p style="margin:8px 0 0; color:#555; font-family:Arial,sans-serif; font-size:14px;">{sous_titre}</p>')
    out += ["            </td>", "          </tr>"]
    return _lignes(*out)


def _bloc_texte(b):
    taille = b.get("taille", 16)
    out = []
    if b.get("intertitre"):
        out.append("              " + INTERTITRE.format(b["intertitre"]))
    for i, par in enumerate(b["paragraphes"]):
        marge = "0" if i == 0 else "14px 0 0"
        out += [
            f'              <p style="margin:{marge}; font-size:{taille}px; color:#333; font-family:Arial,sans-serif; line-height:1.75;">',
            f"                {par}",
            "              </p>",
        ]
    return out


def _bloc_encadre(b):
    if b.get("bordure", False):
        style = "background:#FFF8F3; border-left:4px solid #C4622D; border-radius:0 8px 8px 0; padding:18px 20px;"
    else:
        style = "background:#FFF8F3; border-radius:8px; padding:18px 20px;"
    out = []
    if b.get("intertitre"):
        out.append("              " + INTERTITRE.format(b["intertitre"]))
    out += [
        f'              <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="{style}">',
        "                <tr>",
        "                  <td>",
        f'                    <p style="margin:0; font-size:15px; color:#333; font-family:Arial,sans-serif; line-height:{b.get("interligne", 1.9)};">',
        "<br />\n".join("                      " + l for l in b["lignes"]),
        "                    </p>",
        "                  </td>",
        "                </tr>",
        "              </table>",
    ]
    return out


def _bloc_liste(b):
    out = []
    if b.get("intertitre"):
        out.append("              " + INTERTITRE.format(b["intertitre"]))
    out.append('              <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">')
    elements = b["elements"]
    for i, el in enumerate(elements):
        dernier = i == len(elements) - 1
        out += [
            "                <tr>",
            "                  <td>" if dernier else '                  <td style="padding-bottom:14px;">',
            '                    <p style="margin:0; font-size:15px; color:#333; font-family:Arial,sans-serif; line-height:1.7;">',
            f"                      {el['texte']}",
            "                    </p>",
        ]
        if el.get("sous_lignes"):
            out += [
                '                    <p style="margin:10px 0 0; padding-left:22px; font-size:15px; color:#333; font-family:Arial,sans-serif; line-height:1.9;">',
                "<br />\n".join("                      " + l for l in el["sous_lignes"]),
                "                    </p>",
            ]
        out += ["                  </td>", "                </tr>"]
    out.append("              </table>")
    return out


def _bloc_photo(b):
    return [f'              <img src="{b["src"]}" alt="{b["alt"]}" width="520" '
            'style="display:block; width:100%; max-width:520px; height:auto; border-radius:8px;" />']


def _bloc_bouton(b):
    out = []
    if b.get("texte_avant"):
        out.append('              <p style="margin:0 0 20px; font-size:15px; color:#333; font-family:Arial,sans-serif; '
                   f'line-height:1.75;">{b["texte_avant"]}</p>')
    out.append(f'              <a href="{b["url"]}" style="display:inline-block; background:#C4622D; color:#ffffff; '
               'font-family:Arial,sans-serif; font-size:15px; font-weight:bold; text-decoration:none; '
               f'padding:14px 32px; border-radius:6px;">{b["libelle"]}</a>')
    if b.get("texte_apres"):
        out.append('              <p style="margin:14px 0 0; font-size:13px; color:#777; font-family:Arial,sans-serif;">'
                   f'{b["texte_apres"]}</p>')
    return out


def _bloc_signature(b):
    return [
        '              <p style="margin:0; font-size:17px; color:#1E3A2F; line-height:1.7; font-family:Georgia,serif;">',
        f'                {b["texte"]}<br />',
        '                <span style="font-size:14px; color:#777; font-family:Arial,sans-serif;">L\'équipe de La Grange</span>',
        "              </p>",
    ]


RENDUS = {
    "texte": _bloc_texte,
    "encadre": _bloc_encadre,
    "liste": _bloc_liste,
    "photo": _bloc_photo,
    "bouton": _bloc_bouton,
    "signature": _bloc_signature,
}


def _bloc(b):
    t = b.get("type")
    if t not in RENDUS:
        raise ErreurGabarit(f"type de bloc inconnu : {t!r} (attendu : {', '.join(RENDUS)})")
    b = {**PAR_DEFAUT[t], **b}
    if t == "signature":
        td = '            <td style="padding: 36px 40px; text-align:center;">'
    elif t == "bouton":
        td = f'            <td style="padding: {b["espace"]}px 40px 0; text-align:center;">'
    else:
        td = f'            <td style="padding: {b["espace"]}px 40px 0;">'
    try:
        corps = RENDUS[t](b)
    except KeyError as e:
        raise ErreurGabarit(f"bloc {t!r} : champ obligatoire manquant {e}") from None
    return _lignes(f"          <!-- {b['commentaire']} -->", "          <tr>", td, *corps, "            </td>", "          </tr>")


PIED = """          <!-- Footer -->
          <tr>
            <td style="border-top:1px solid #E8E2D8; padding: 20px 40px; text-align:center;">
              <p style="margin:0; font-size:12px; color:#999; font-family:Arial,sans-serif; line-height:1.6;">
                Association La Grange, La Rochelle · RNA W173011277<br />
                <a href="mailto:contact@asso-lagrange.fr" style="color:#999;">contact@asso-lagrange.fr</a>
              </p>
            </td>
          </tr>"""


def rendre(envoi):
    """Retourne le HTML complet d'un envoi (dict issu du JSON)."""
    titre_page = envoi.get("titre_html", envoi["objet"])
    preheader = envoi.get("preheader_html", envoi["apercu"])
    contenu = envoi["contenu"]
    sections = [_entete(contenu["entete"])] + [_bloc(b) for b in contenu["blocs"]] + [PIED]
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{titre_page}</title>
</head>
<body style="margin:0; padding:0; background:#F5F0E8; font-family: Georgia, 'Times New Roman', serif;">

  <!-- Preheader (aperçu boîte de réception) -->
  <span style="display:none; max-height:0; overflow:hidden; mso-hide:all;">
    {preheader}
    &nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
  </span>

  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#F5F0E8;">
    <tr>
      <td align="center" style="padding: 32px 16px;">

        <!-- Carte principale -->
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width:600px; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow: 0 2px 12px rgba(0,0,0,.08);">

{chr(10).join(s + chr(10) for s in sections)}
        </table>

      </td>
    </tr>
  </table>

</body>
</html>
"""
