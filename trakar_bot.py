import requests
import json
import time
import schedule
import hashlib
import os
from datetime import datetime
from bs4 import BeautifulSoup
from collections import defaultdict

# ══════════════════════════════════════════════════════
# CLIENTS
# ══════════════════════════════════════════════════════
CLIENTS = [
    {
        "nom": "Karamba (test)",
        "telegram_token": "8720932052:AAEqm7Pn6JRtHIIyZukSw19YoEo0anZ9gSM",
        "telegram_chat_id": "8779757061",
        "filtres": {
            "marque": "",       # Vide = toutes marques
            "modele": "",       # Vide = tous modèles
            "prix_max": 15000,
            "prix_min": 3000,
            "km_max": 150000,
            "annee_min": 2015,
            "ecart_marche_min": 15,  # Alerte si -15% sous la moyenne
        }
    },
]

CONFIG = {
    "INTERVALLE_MINUTES": 5,
    "SCORE_MIN": 0,
    "MAX_ANNONCES_PAR_SCAN": 50,
}

FICHIER_VUS = "trakar_vus.json"
FICHIER_PRIX = "trakar_prix_marche.json"

MOTS_PRO = ["garage", "concessionnaire", "mandataire", "auto pro", "automobiles",
            "sas", "sarl", "sa ", "dealer", "group", "distribution", "automotion"]

def charger_vus():
    if os.path.exists(FICHIER_VUS):
        with open(FICHIER_VUS, "r") as f:
            return set(json.load(f))
    return set()

def sauvegarder_vus(vus):
    with open(FICHIER_VUS, "w") as f:
        json.dump(list(vus), f)

def charger_prix_marche():
    if os.path.exists(FICHIER_PRIX):
        with open(FICHIER_PRIX, "r") as f:
            return json.load(f)
    return {}

def sauvegarder_prix_marche(prix):
    with open(FICHIER_PRIX, "w") as f:
        json.dump(prix, f)

def horodatage():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def est_vendeur_pro(titre, localisation):
    texte = (titre + " " + localisation).lower()
    return any(mot in texte for mot in MOTS_PRO)

def extraire_modele_cle(titre):
    """Extrait une clé modèle depuis le titre pour comparer les prix."""
    titre = titre.lower()
    modeles_connus = [
        "308", "3008", "2008", "208", "508", "clio", "megane", "kadjar",
        "captur", "golf", "polo", "passat", "tiguan", "serie 1", "serie 3",
        "serie 5", "a3", "a4", "a6", "c3", "c4", "c5", "yaris", "corolla",
        "focus", "fiesta", "kuga", "tucson", "i30", "qashqai", "juke",
        "zoe", "leaf", "scenic", "laguna", "twingo", "sandero", "duster"
    ]
    for modele in modeles_connus:
        if modele in titre:
            return modele
    # Fallback : premiers mots du titre
    mots = titre.split()
    return " ".join(mots[:2]) if len(mots) >= 2 else titre[:10]

def calculer_prix_marche(annonces):
    """Calcule le prix moyen par modèle depuis toutes les annonces collectées."""
    prix_par_modele = defaultdict(list)
    for annonce in annonces:
        if annonce["prix"] > 0:
            cle = extraire_modele_cle(annonce["titre"])
            prix_par_modele[cle].append(annonce["prix"])

    prix_marche = {}
    for modele, prix_list in prix_par_modele.items():
        if len(prix_list) >= 2:
            # Moyenne en excluant les valeurs extrêmes
            prix_list.sort()
            trim = max(1, len(prix_list) // 5)
            prix_trimmed = prix_list[trim:-trim] if len(prix_list) > 4 else prix_list
            prix_marche[modele] = sum(prix_trimmed) / len(prix_trimmed)

    return prix_marche

def envoyer_telegram(annonce, score, token, chat_id, prix_marche_ref=None, ecart_pct=None):
    emoji = "🔥" if score >= 85 else "✅"
    vendeur = "👤 Particulier" if not annonce.get("pro") else "🏢 Professionnel"

    ecart_str = ""
    if ecart_pct and ecart_pct > 0:
        economie = int(prix_marche_ref - annonce["prix"]) if prix_marche_ref else 0
        ecart_str = f"📉 Sous le marché : *-{ecart_pct:.0f}%* (≈ -{economie:,}€)\n"

    message = (
        f"{emoji} *Nouvelle alerte Trakar !*\n\n"
        f"🚗 *{annonce['titre']}*\n"
        f"💰 Prix : *{annonce['prix']:,}€*\n"
        f"{ecart_str}"
        f"📍 Lieu : {annonce['localisation']}\n"
        f"📅 Année : {annonce.get('annee', 'N/A')} | 🛣 {annonce.get('km', 'N/A')} km\n"
        f"🌐 Source : {annonce.get('source', '')}\n"
        f"👤 Vendeur : {vendeur}\n"
        f"🎯 Score : {score}/100\n\n"
        f"🔗 [Voir l'annonce]({annonce['url']})"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=10)
        if resp.status_code == 200:
            print(f"[{horodatage()}] ✈️ Telegram envoyé : {annonce['titre']}")
        else:
            print(f"[{horodatage()}] ❌ Telegram erreur : {resp.text}")
    except Exception as e:
        print(f"[{horodatage()}] ❌ Telegram exception : {e}")

# ══════════════════════════════════════════════════════
# AUTOSCOUT24 — toutes marques
# ══════════════════════════════════════════════════════
def scraper_autoscout(filtres):
    annonces = []
    try:
        prix_max = filtres["prix_max"]
        prix_min = filtres.get("prix_min", 0)
        annee_min = filtres.get("annee_min", 0)
        km_max = filtres.get("km_max", 999999)

        # Toutes marques — pas de marque dans l'URL
        url = (
            f"https://www.autoscout24.fr/lst?"
            f"sort=age&desc=1"
            f"&priceto={prix_max}&pricefrom={prix_min}"
            f"&mileageto={km_max}"
            f"&fregfrom={annee_min}"
            f"&ustate=N%2CU&size=20&page=1&atype=C"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=20)
        print(f"[{horodatage()}] 🔍 AutoScout24 status : {resp.status_code}")
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("article[class*='cldt-summary']") or \
                soup.select("div[class*='ListItem']") or \
                soup.select("article") or \
                soup.select("a[href*='/annonces/']")
        print(f"[{horodatage()}] 📋 AutoScout24 : {len(cards)} carte(s)")

        for card in cards[:CONFIG["MAX_ANNONCES_PAR_SCAN"]]:
            try:
                titre_el = card.select_one("h2") or card.select_one("h1") or card.select_one("[class*='title']")
                titre = titre_el.get_text(strip=True) if titre_el else card.get_text(separator=" ", strip=True)[:60]
                prix_el = card.select_one("[class*='price']") or card.select_one("[data-testid*='price']")
                prix_txt = prix_el.get_text(strip=True) if prix_el else "0"
                prix = int("".join(filter(str.isdigit, prix_txt))) if any(c.isdigit() for c in prix_txt) else 0
                href = card.get("href", "") or (card.select_one("a") or {}).get("href", "")
                if not href:
                    continue
                url_annonce = href if href.startswith("http") else "https://www.autoscout24.fr" + href
                loc_el = card.select_one("[class*='location']") or card.select_one("[class*='seller']")
                loc = loc_el.get_text(strip=True) if loc_el else "France"
                annonce_id = "as_" + hashlib.md5(url_annonce.encode()).hexdigest()[:10]
                if prix > filtres["prix_max"] and prix > 0:
                    continue
                if prix > 0 and prix < filtres["prix_min"]:
                    continue
                pro = est_vendeur_pro(titre, loc)
                annonces.append({
                    "id": annonce_id,
                    "titre": titre or "Annonce AutoScout24",
                    "prix": prix,
                    "url": url_annonce,
                    "localisation": loc[:40],
                    "annee": "N/A",
                    "km": "N/A",
                    "source": "AutoScout24",
                    "pro": pro,
                })
            except:
                continue
    except Exception as e:
        print(f"[{horodatage()}] ❌ AutoScout24 erreur : {e}")
    return annonces

# ══════════════════════════════════════════════════════
# LA CENTRALE — toutes marques
# ══════════════════════════════════════════════════════
def scraper_lacentrale(filtres):
    annonces = []
    try:
        prix_max = filtres["prix_max"]
        prix_min = filtres.get("prix_min", 0)

        url = (
            f"https://www.lacentrale.fr/listing?"
            f"priceMax={prix_max}&priceMin={prix_min}"
            f"&sortBy=date&sortOrder=desc&sellerType=private&page=1"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=20)
        print(f"[{horodatage()}] 🔍 La Centrale status : {resp.status_code}")
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("div[class*='searchCard']") or \
                soup.select("article[class*='vehicle']") or \
                soup.select("div[class*='vehicleCard']") or \
                soup.select("a[href*='/voiture-occasion']")
        print(f"[{horodatage()}] 📋 La Centrale : {len(cards)} carte(s)")

        for card in cards[:CONFIG["MAX_ANNONCES_PAR_SCAN"]]:
            try:
                titre = card.get_text(separator=" ", strip=True)[:80]
                href = card.get("href", "") or (card.select_one("a") or {}).get("href", "")
                if not href:
                    continue
                url_annonce = href if href.startswith("http") else "https://www.lacentrale.fr" + href
                annonce_id = "lc_" + hashlib.md5(url_annonce.encode()).hexdigest()[:10]
                prix_el = card.select_one("[class*='price']") or card.select_one("[class*='Price']")
                prix_txt = prix_el.get_text(strip=True) if prix_el else "0"
                prix = int("".join(filter(str.isdigit, prix_txt))) if any(c.isdigit() for c in prix_txt) else 0
                loc_el = card.select_one("[class*='location']") or card.select_one("[class*='Location']")
                loc = loc_el.get_text(strip=True) if loc_el else "France"
                pro = est_vendeur_pro(titre, loc)
                annonces.append({
                    "id": annonce_id,
                    "titre": titre or "Annonce La Centrale",
                    "prix": prix,
                    "url": url_annonce,
                    "localisation": loc,
                    "annee": "N/A",
                    "km": "N/A",
                    "source": "La Centrale",
                    "pro": pro,
                })
            except:
                continue
    except Exception as e:
        print(f"[{horodatage()}] ❌ La Centrale erreur : {e}")
    return annonces

# ══════════════════════════════════════════════════════
# SCORE INTELLIGENT — basé sur l'écart au prix marché
# ══════════════════════════════════════════════════════
def calculer_score_intelligent(annonce, filtres, prix_marche):
    score = 50
    prix = annonce["prix"]
    ecart_pct = 0
    prix_marche_ref = None

    if prix > 0:
        cle = extraire_modele_cle(annonce["titre"])
        prix_marche_ref = prix_marche.get(cle)

        if prix_marche_ref and prix_marche_ref > 0:
            ecart_pct = ((prix_marche_ref - prix) / prix_marche_ref) * 100
            if ecart_pct >= 25:
                score += 45   # Très grosse affaire
            elif ecart_pct >= 20:
                score += 35
            elif ecart_pct >= 15:
                score += 25
            elif ecart_pct >= 10:
                score += 15
            elif ecart_pct >= 5:
                score += 5
            elif ecart_pct < 0:
                score -= 20   # Plus cher que la moyenne
        else:
            # Pas de référence → score basique sur le prix max
            if prix < filtres["prix_max"] * 0.7:
                score += 20
            elif prix < filtres["prix_max"] * 0.85:
                score += 10

    # Bonus particulier
    if annonce.get("pro"):
        score -= 20
    else:
        score += 15

    # Bonus localisation
    if annonce["localisation"] and annonce["localisation"] != "France":
        score += 5

    return min(max(score, 0), 100), ecart_pct, prix_marche_ref

# ══════════════════════════════════════════════════════
# SCAN PAR CLIENT
# ══════════════════════════════════════════════════════
def scanner_client(client, vus):
    nom = client["nom"]
    filtres = client["filtres"]
    token = client["telegram_token"]
    chat_id = client["telegram_chat_id"]
    ecart_min = filtres.get("ecart_marche_min", 15)
    nouvelles = 0

    print(f"\n[{horodatage()}] 👤 Scan pour : {nom}")

    # Collecte toutes les annonces
    toutes_annonces = []
    toutes_annonces += scraper_autoscout(filtres)
    toutes_annonces += scraper_lacentrale(filtres)

    print(f"[{horodatage()}] 📊 {nom} : {len(toutes_annonces)} annonces collectées")

    # Calcul du prix marché par modèle
    prix_marche = calculer_prix_marche(toutes_annonces)
    print(f"[{horodatage()}] 📈 Prix marché calculés pour {len(prix_marche)} modèles")

    # Sauvegarder pour référence future
    ancien_prix = charger_prix_marche()
    ancien_prix.update(prix_marche)
    sauvegarder_prix_marche(ancien_prix)

    # Analyser chaque annonce
    for annonce in toutes_annonces:
        cle = f"{nom}_{annonce['id']}"
        if cle in vus:
            continue

        score, ecart_pct, prix_ref = calculer_score_intelligent(annonce, filtres, prix_marche)
        vendeur = "PARTICULIER" if not annonce.get("pro") else "pro"

        print(f"[{horodatage()}] 🎯 {score}/100 [{vendeur}] écart:{ecart_pct:.0f}% — {annonce['titre'][:30]} — {annonce['prix']}€")

        # Alerte si sous le marché ET score suffisant
        if ecart_pct >= ecart_min and score >= CONFIG["SCORE_MIN"]:
            envoyer_telegram(annonce, score, token, chat_id, prix_ref, ecart_pct)
            nouvelles += 1
        elif annonce["prix"] == 0 and not annonce.get("pro"):
            # Prix inconnu mais particulier → on alerte quand même
            envoyer_telegram(annonce, score, token, chat_id)
            nouvelles += 1

        vus.add(cle)

    return nouvelles

def lancer_scan():
    print(f"\n[{horodatage()}] ━━━ Nouveau scan — {len(CLIENTS)} client(s) ━━━")
    vus = charger_vus()
    total_nouvelles = 0
    for client in CLIENTS:
        try:
            nouvelles = scanner_client(client, vus)
            total_nouvelles += nouvelles
        except Exception as e:
            print(f"[{horodatage()}] ❌ Erreur client {client['nom']} : {e}")
    sauvegarder_vus(vus)
    print(f"[{horodatage()}] ✅ Scan terminé — {total_nouvelles} alerte(s) envoyée(s)")

def demarrer():
    print(f"🚗 TRAKAR PRO — Bot intelligent démarré ({len(CLIENTS)} client(s))")
    if os.path.exists(FICHIER_VUS):
        os.remove(FICHIER_VUS)
        print(f"[{horodatage()}] 🗑️ Cache vidé")
    lancer_scan()
    schedule.every(CONFIG["INTERVALLE_MINUTES"]).minutes.do(lancer_scan)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    demarrer()
