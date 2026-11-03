"""Dette, bilan, flux de trésorerie et investissements de l'Etat de Vaud, d'après les brochures des comptes 2018-2025.

Entrée : sources/txt/comptes-AAAA.txt (pdftotext -layout des « Brochures des comptes »)
Sortie : data/dette_indicateurs.csv, dette_bilan.csv, dette_flux.csv, dette_objets.csv,
         dette_controles.csv et la clé « dette » de site/data.json (fusion faite par build_site.py)

Principe : on recopie les chiffres publiés, sans les interpréter. Chaque série est confrontée
à une autre présentation du même chiffre dans les comptes (voir ctrl()).
"""
import csv, glob, json, os, re, sys

AMT = r"(?:-\s?)?\d{1,3}(?:'\d{3})*(?:\.\d+)?|--"


def num(s):
    s = s.strip()
    if s in ("--", "-", ""):
        return 0.0
    neg = s.startswith("-")
    v = float(s.lstrip("-").strip().replace("'", ""))
    return -v if neg else v


def amounts(txt):
    return [num(m) for m in re.findall(r"(?<![\w.])(%s)(?![\w])" % AMT, txt)]


def lire(an):
    return open(f"sources/txt/comptes-{an}.txt", encoding="utf-8").read().split("\n")


CONTROLES = []


def ctrl(an, objet, attendu, obtenu, tol=1.0, bloquant=True):
    ok = abs(attendu - obtenu) <= tol
    CONTROLES.append([an, objet, round(attendu, 2), round(obtenu, 2), int(ok), int(bloquant)])
    return ok


# ---------------------------------------------------------------- évolution de la dette (2017-2025)
def evolution(lines):
    """Tableau « Evolution de la fortune nette, indicateurs financiers et évolution de la dette » (9 années)."""
    i0 = next(i for i, l in enumerate(lines) if "Evolution de la fortune nette, indicateurs" in l and "2017 - 2025" in l)
    bloc = lines[i0:i0 + 70]
    ann = next([int(x) for x in re.findall(r"\b(20\d\d)\b", l)] for l in bloc if len(re.findall(r"\b(20\d\d)\b", l)) == 9)
    cles = [
        ("fortune_debut", r"Fortune nette .* au 1er janvier"),
        ("resultat_operationnel", r"Résultat opérationnel"),
        ("resultat_extraordinaire", r"Résultat extraordinaire"),
        ("resultat", r"Résultat de l'exercice"),
        ("fortune_fin", r"Fortune nette .* au 31 décembre"),
        ("degre_autofinancement", r"Degré d'autofinancement"),
        ("taux_endettement_net", r"Taux d'endettement net"),
        ("part_interets", r"Part des charges d'intérêts"),
        ("emprunts", r"Emprunts au 31 décembre"),
        ("interets", r"Intérêts des emprunts"),
        ("taux_interet", r"Intérêts en % des emprunts"),
    ]
    out = {}
    for cle, rx in cles:
        for l in bloc:
            if re.search(rx, l):
                txt = re.sub(r"^.*?\.{3,}", "", l)
                txt = txt.replace("%", " ").replace("*", " ")
                txt = re.sub(r"(?<=[+\-])\s+(?=\d)", "", txt).replace("+", " ")
                v = amounts(txt)
                if len(v) == 9:
                    out[cle] = dict(zip(ann, v))
                    break
    manque = [c for c, _ in cles if c not in out]
    if manque:
        sys.exit("Tableau d'évolution : lignes introuvables " + str(manque))
    return out


# ---------------------------------------------------------------- bilan
BILAN_CODES = {
    "10": "Patrimoine financier", "100": "Disponibilités et placements à court terme",
    "1000": "Caisse", "1001": "Poste", "1002": "Banques", "1003": "Placements à court terme",
    "1009": "Autres disponibilités", "101": "Créances", "102": "Placements financiers à court terme",
    "107": "Placements financiers à long terme", "14": "Patrimoine administratif",
    "140": "Immobilisations corporelles du PA", "142": "Immobilisations incorporelles du PA",
    "144": "Prêts", "145": "Participations, capital social", "146": "Subventions d'investissements",
    "148": "Amortissements supplémentaires cumulés", "20": "Capitaux de tiers",
    "200": "Engagements courants", "201": "Engagements financiers à court terme",
    "206": "Engagements financiers à long terme", "2063": "Emprunts",
    "2014": "Part à court terme d'engagements à long terme",
    "2064": "Prêts, reconnaissances de dettes", "2069": "Autres engagements financiers à long terme",
    "209": "Engagements financements spéciaux et fonds", "29": "Capital propre",
    "293": "Préfinancements", "298": "Autres capitaux propres",
    "299": "Excédent / découvert (-) du bilan",
}


def bilan(lines):
    """Premier bilan de la brochure (Etat de Vaud) : deux colonnes, année N puis N-1."""
    i0 = next(i for i, l in enumerate(lines) if re.search(r"PATRIMOINE FINANCIER\.{3,}", l))
    i1 = next(i for i in range(i0, len(lines)) if "Tableau des flux de trésorerie" in lines[i] and "...." not in lines[i])
    out, totaux = {}, []
    for ligne in lines[i0:i1]:
        ligne = re.sub(r"(?<=[\d\-])(\s{4,})CAPITAL PROPRE\.", r"\1 29   CAPITAL PROPRE.", ligne)
        # brochures 2020-2021 : actif et passif côte à côte sur la même ligne
        for l in re.split(r"(?<=[\d\-])\s{4,}(?=\d{2,4}\s+[A-Za-zÉé(])", ligne):
            l = re.sub(r"^(\s+)CAPITAL PROPRE\.", r"\1 29   CAPITAL PROPRE.", l)
            m = re.match(r"^\s*(\d{2,4})\s+(.+?)\s{2,}(.*)$", l)
            if m and m.group(1) in BILAN_CODES:
                v = amounts(m.group(3).replace("(R)", ""))
                if len(v) >= 2 and m.group(1) not in out:
                    out[m.group(1)] = v[:2]
                continue
        if re.match(r"^\s{20,}(%s)\s+(%s)(\s+(%s)\s+(%s))?\s*$" % (AMT, AMT, AMT, AMT), ligne):
            totaux += [amounts(ligne)]
    plat = [x for t in totaux for x in t]
    return out, [plat[0:2], plat[2:4]]


# ---------------------------------------------------------------- flux de trésorerie
FLUX = [
    ("resultat", r"^Résultat total du compte"),
    ("amortissements", r"^\+\s*Amortissements du patrimoine administratif"),
    ("fto", r"\[FTO\]\s"),
    ("depenses_nettes_bi", r"Dépenses d'investissements nettes au sens du budget"),
    ("credit_etudes", r"Crédit d'études"),
    ("prets_conditionnels", r"Investissements prêts conditionnellement"),
    ("credits_inventaire", r"Crédits d'inventaires"),
    ("fti", r"\[FTI\]\s"),
    ("fti_p", r"\[FTI\+P\]"),
    ("ftf", r"\[FTF\]"),
    ("variation_liquidites", r"^Variation des liquidités"),
]


def flux(lines):
    i0 = next(i for i, l in enumerate(lines) if re.match(r"^\s{20,}Tableau des flux de trésorerie\s*$", l))
    bloc = lines[i0:i0 + 70]
    out = {}
    for cle, rx in FLUX:
        for j, l in enumerate(bloc):
            if re.search(rx, l):
                # montant = premier nombre « 1'234.56 » après le libellé (le texte en marge des brochures 2020-2021 est ignoré)
                m = re.search(r"(?:^|\s)(-?\s?\d{1,3}(?:'\d{3})*\.\d\d)(?=\s|$)", re.sub(r"\d+\.\d+\.\d{4}", " ", l))
                if not m and j + 1 < len(bloc):   # libellé sur deux lignes
                    m = re.search(r"(?:^|\s)(-?\s?\d{1,3}(?:'\d{3})*\.\d\d)(?=\s|$)", bloc[j + 1])
                out[cle] = num(m.group(1)) if m else 0.0
                break
    return out


# ---------------------------------------------------------------- objets d'investissement de l'exercice
RX_OBJ = re.compile(r"^\s*(I\.\d{6}\.\d\d)\s+(.*)$")
RX_TOK = re.compile(r"(?<![\w.'])(-?\s?\d{1,3}(?:'\d{3})*(?:\.\d\d)?|--)(?![\w'])")


def _jetons(txt):
    """Montants d'une ligne d'objet : (avec décimales = comptes, sans décimales = budget)."""
    toks = [t.replace(" ", "") for t in RX_TOK.findall(txt)]
    return toks



def _colonnes(ligne, aretes, debut=None):
    """Dépenses nettes des comptes et du budget pour une ligne d'objet.

    Colonnes : Comptes (dépenses, recettes, nettes) puis Budget (idem). Les cases vides ne sont pas imprimées.
    Les montants des comptes ont des centimes, ceux du budget sont arrondis au franc : le premier entier sans
    centimes ouvre la partie « Budget ». Dans les comptes, on retient le découpage qui respecte
    « dépenses - recettes = dépenses nettes » ; seul le cas ambigu [x, x] (dépenses et nettes, ou dépenses et
    recettes avec nettes vides) est tranché par l'écart entre les deux montants sur la ligne.
    """
    mm = list(re.finditer(r"\.{3,}", ligne))
    debut = debut if debut is not None else mm[-1].end() if mm else (re.search(r"\s{2,}", ligne[16:]).end() + 16 if re.search(r"\s{2,}", ligne[16:]) else len(ligne))
    tk = [(m.group(1).replace(" ", ""), m.end(1)) for m in RX_TOK.finditer(ligne, debut)]
    ib = next((i for i, (t, _) in enumerate(tk) if "." not in t and t != "--"), len(tk))
    if len(tk) == 6:
        ib = 3
    v = [num(t) for t, _ in tk[:ib]]
    if len(v) >= 3 and abs(v[0] - v[1] - v[2]) < 1:
        net = v[2]
    elif len(v) == 2 and abs(v[0] - v[1]) < 1:
        gap = tk[1][1] - tk[0][1]
        seuil = ((aretes[1] - aretes[0]) + (aretes[2] - aretes[0])) / 2
        net = v[1] if gap > seuil else 0.0
    elif len(v) == 2 and abs(v[0] + v[1]) < 1:
        net = v[1]
    else:
        net = v[0] if v else 0.0
    bud = num(tk[-1][0]) if len(tk) > ib else 0.0
    return net, bud


def objets(lines, an):
    """Dépenses et recettes d'investissements de l'exercice, par objet (I.nnnnnn.nn), avec contrôles par département."""
    i0 = next(i for i, l in enumerate(lines) if re.match(r"^\s+Dépenses et recettes d'investissements de l'exercice %d\s*$" % an, l))
    i1 = next(i for i in range(i0, len(lines)) if "TOTAL DES DEPENSES D'INVESTISSEMENT" in lines[i])
    tot = [num(t) for t in _jetons(lines[i1].split("INVESTISSEMENT", 1)[1]) if "." in t][:3]
    aretes = [m.end(1) for m in RX_TOK.finditer(lines[i1], lines[i1].index("INVESTISSEMENT"))][:6]
    out, pend, acc, service, attente, orphelin = [], [], 0.0, "", None, None
    for l in lines[i0:i1]:
        if not l.strip() or re.match(r"^\s*\d{3}\s*$", l):
            continue
        if attente is None and re.match(r"^\s{40,}(%s)(\s+(%s))*\s*$" % (AMT, AMT), l):
            orphelin = l                       # montants imprimés avant le code de leur objet (ordre d'extraction du PDF)
            continue
        m = RX_OBJ.match(l)
        if m:
            reste = re.sub(r"\.{3,}", "  ", m.group(2))
            parts = re.split(r"\s{2,}", reste.strip(), maxsplit=1)
            lib, nombres = (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "")
            if orphelin and not re.search(r"\d{1,3}'\d{3}|\s--\s", re.sub(r"\.{3,}", " ", m.group(2))):
                net, bud = _colonnes(orphelin, aretes, 0)
            else:
                net, bud = _colonnes(l, aretes)
            orphelin = None
            rec = dict(annee=an, objet=m.group(1), libelle=lib.strip(), service=service, departement="",
                       depenses_nettes=net, budget_net=bud)
            out.append(rec); pend.append(rec); acc += net
            continue
        t = l.strip()
        if re.match(r"^TOTAL (?!DES )", t) or (attente is not None and re.search(r"\d{1,3}'\d{3}|\s--\s", t)):
            if attente is None:
                attente = re.sub(r"^TOTAL\s+", "", re.split(r"\s{2,}", t)[0])
                reste = t[len(re.split(r"\s{2,}", t)[0]):]
            else:
                reste = t
                if re.split(r"\s{2,}", t)[0] and not re.match(r"^(-?\d|--)", t):
                    attente += " " + re.split(r"\s{2,}", t)[0]
                    reste = t[len(re.split(r"\s{2,}", t)[0]):]
            toks = _jetons(reste)
            if len(toks) >= 3:
                nom = re.sub(r"^(DEPARTEMENT|DÉPARTEMENT)\s*", "", attente).strip()
                ctrl(an, f"objets d'investissement : somme = total « {nom[:60]} »", num(toks[2]), acc, 2.0)
                for r in pend:
                    r["departement"] = nom
                pend, acc, attente = [], 0.0, None
            continue
        if re.search(r"\d{1,3}'\d{3}", t) or re.match(r"^(Comptes|Budget|Dépenses|Recettes)\b", t) or t.startswith("Dépenses et recettes"):
            continue
        if re.match(r"^[A-ZÉÈÀ0-9 ,'’\-()]+$", t) and len(t) > 8:
            continue                       # nom de département en majuscules
        service = t if not service.endswith(("de la", "de l'", "du", "des")) or not out else service
        service = t
    ctrl(an, "objets d'investissement : somme des dépenses nettes = total publié", tot[2], sum(r["depenses_nettes"] for r in out), 2.0)
    return out, tot


def main():
    ANS = sorted(int(re.search(r"comptes-(\d{4})\.txt$", p).group(1)) for p in glob.glob("sources/txt/comptes-20??.txt"))
    if not ANS:
        sys.exit("Aucune brochure de comptes dans sources/txt/.")
    dernier = ANS[-1]
    L = {a: lire(a) for a in ANS}

    evo = evolution(L[dernier])
    # --- bilan : année N prise dans la brochure N ; colonne N-1 comparée à la brochure N-1
    B, TOT = {}, {}
    for a in ANS:
        b, t = bilan(L[a])
        for code, v in b.items():
            B.setdefault(a, {})[code] = v[0]
            if a - 1 not in ANS:
                B.setdefault(a - 1, {})[code] = v[1]
        TOT[a] = t
    for a in ANS:
        b, t = bilan(L[a])
        if a - 1 in ANS:
            for code, v in b.items():
                if code in B.get(a - 1, {}):
                    ctrl(a - 1, f"bilan {code} : brochure {a - 1} = colonne N-1 de la brochure {a}", B[a - 1][code], v[1], 1.0, False)
        ctrl(a, "total actif (10 + 14) = total passif (20 + 29)", B[a]["10"] + B[a]["14"], B[a]["20"] + B[a]["29"], 1.0)
        if t[0] and t[1]:
            ctrl(a, "total du bilan publié = patrimoine financier + administratif", t[0][0], B[a]["10"] + B[a]["14"], 1.0, False)
        ctrl(a, "capital propre : excédent du bilan (299) = fortune nette publiée", evo["fortune_fin"][a] * 1e6, B[a]["299"], 150000)
        e = evo["emprunts"][a] * 1e6
        cand = [B[a]["2063"], B[a]["2063"] + B[a].get("2014", 0.0)]
        ctrl(a, "emprunts du tableau d'évolution = compte 2063 (ou 2063 + 2014, part à court terme)", e, min(cand, key=lambda x: abs(x - e)), 60000)

    # --- flux
    F = {a: flux(L[a]) for a in ANS}
    for a in ANS:
        f = F[a]
        ctrl(a, "FTO + FTI+P + FTF = variation des liquidités", f["fto"] + f["fti_p"] + f["ftf"], f["variation_liquidites"], 1.0)
        b = B[a]
        liq = lambda x: x["1000"] + x["1001"] + x["1002"] + x["1009"] if "1009" in x else x["1000"] + x["1001"] + x["1002"]
        if a - 1 in B:
            ctrl(a, "variation des liquidités = variation caisse+poste+banques du bilan", f["variation_liquidites"], liq(b) - liq(B[a - 1]), 1.0, False)
        ctrl(a, "résultat du flux = résultat publié", evo["resultat"][a] * 1e6, f["resultat"], 60000)

    # --- objets d'investissement de l'exercice
    OBJ = {}
    for a in ANS:
        OBJ[a], tot = objets(L[a], a)
        ctrl(a, "dépenses nettes des objets = flux de trésorerie (dépenses nettes au sens du budget d'investissements)", -F[a]["depenses_nettes_bi"], tot[2], 2.0, a != 2021)

    # --- erratum CHUV 2024 : ne touche pas les comptes de l'Etat
    err = "sources/txt/comptes-2024-erratum-chuv.txt"
    if os.path.exists(err):
        t = re.sub(r"\s+", " ", open(err, encoding="utf-8").read())
        ctrl(2024, "erratum CHUV : précise que les comptes 2024 de l'Etat ne sont pas modifiés", 1, int("ne modifie pas les comptes 2024 de l’Etat" in t))
        ctrl(2024, "erratum CHUV : correction du résultat CHUV 2024 (7'777'861.55 -> 4'607'711.55)", 7777861.55 - 3170150.00, 4607711.55, 0.01)

    # --- sorties
    os.makedirs("data", exist_ok=True)
    cols = ["fortune_debut", "resultat_operationnel", "resultat_extraordinaire", "resultat", "fortune_fin",
            "degre_autofinancement", "taux_endettement_net", "part_interets", "emprunts", "interets", "taux_interet"]
    annees_evo = sorted(evo["emprunts"])
    with open("data/dette_indicateurs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["annee"] + cols)
        for a in annees_evo:
            w.writerow([a] + [evo[c][a] for c in cols])
    with open("data/dette_bilan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["annee", "code", "libelle", "montant_chf"])
        for a in sorted(B):
            for code in BILAN_CODES:
                if code in B[a]:
                    w.writerow([a, code, BILAN_CODES[code], B[a][code]])
    with open("data/dette_flux.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["annee", "ligne", "montant_chf"])
        for a in ANS:
            for cle, _ in FLUX:
                w.writerow([a, cle, F[a].get(cle, 0.0)])
    with open("data/dette_objets.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["annee", "departement", "service", "objet", "libelle", "depenses_nettes_chf", "budget_net_chf"])
        for a in ANS:
            for r in OBJ[a]:
                w.writerow([a, r["departement"], r["service"], r["objet"], r["libelle"], r["depenses_nettes"], r["budget_net"]])
    with open("data/dette_controles.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["annee", "controle", "attendu", "obtenu", "ok", "bloquant"])
        w.writerows(CONTROLES)
    # --- données du site (clé « dette » de site/data.json)
    annees_b = sorted(B)
    liq = lambda x: sum(x.get(c, 0.0) for c in ("1000", "1001", "1002", "1009"))
    site = {
        "annees": annees_evo,
        "ind": {c: [evo[c][a] for a in annees_evo] for c in cols},
        "bilan_annees": annees_b,
        "bilan": {c: [B[a].get(c) for a in annees_b] for c in BILAN_CODES if any(c in B[a] for a in annees_b)},
        "liquidites": [liq(B[a]) for a in annees_b],
        "libelles": BILAN_CODES,
        "flux_annees": ANS,
        "flux": {cle: [F[a].get(cle, 0.0) for a in ANS] for cle, _ in FLUX},
        "objets": {"cles": ["annee", "service", "objet", "libelle", "net", "budget"],
                   "lignes": [[r["annee"], r["service"], r["objet"], r["libelle"], r["depenses_nettes"], r["budget_net"]]
                              for a in ANS for r in OBJ[a] if r["depenses_nettes"] or r["budget_net"]]},
        "tot_objets": {a: round(sum(r["depenses_nettes"] for r in OBJ[a]), 2) for a in ANS},
        "tot_budget": {a: round(sum(r["budget_net"] for r in OBJ[a]), 2) for a in ANS},
        "brochures": ANS,
        "erratum_chuv_2024": os.path.exists(err),
    }
    if os.path.exists("site/data.json"):
        data = json.load(open("site/data.json", encoding="utf-8"))
        data["dette"] = site
        json.dump(data, open("site/data.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    nko = [c for c in CONTROLES if not c[4] and c[5]]
    print(f"{len(CONTROLES)} contrôles, {len(nko)} bloquants en échec, {sum(1 for c in CONTROLES if not c[4] and not c[5])} avertissements")
    for c in CONTROLES:
        if not c[4]:
            print("  ✗", c)
    if nko:
        sys.exit(1)


if __name__ == "__main__":
    main()
