import requests
import json
import time
import schedule
import hashlib
import os
from datetime import datetime
from bs4 import BeautifulSoup

# ══════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "")

CLIENTS = [
    {
        "nom": "Karamba (test)",
        "telegram_token": "8720932052:AAEqm7Pn6JRtHIIyZukSw19YoEo0anZ9gSM",
        "telegram_chat_id": "8779757061",
        "filtres": {
            "marque": "peugeot",
            "modele": "308",
            "prix_max": 15000,
            "prix_min": 5000,
            "km_max": 120000,
            "annee_min": 0,
        }
    },
]

CONFIG = {
    "INTERVALLE_MINUTES": 5,
    "SCORE_MIN": 0,
    "MAX_ANNONCES_PAR_SCAN": 20,
}

FICHIER_VUS = "trakar_vus.json"

MOTS_PRO = ["garage", "concessionnaire", "mandataire", "auto pro", "automobiles",
            "sas", "sarl", "sa ", "dealer", "group", "distribution"]

# ══════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════
def charger_vus():
    if os.path.exists(FICHIER_VUS):
        with open(FICHIER_VUS, "r") as f:
            return set(json.load(f))
    return set()

def sauvegarder_vus(vus):
    with open(FICHIER_VUS, "w") as f:
        json.dump(list(vus), f)

def horodatage():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def est_vendeur_pro(titre, localisation):
    texte = (titre + " " + localisation).lower()
    return any(mot in texte for mot in MOTS_PRO)

def scraper_url(url, render=False):
    try:
        resp = requests.get(
            "http://api.scraperapi.com",
            params={
                "api_key": SCRAPER_API_KEY,
                "url": url,
                "render": "true" if render else "false",
                "country_code": "fr",
            },
            timeout=60
        )
        print(f"[{horodatage()}] 🌐 ScraperAPI status : {resp.status_code} — {url[:60]}")
        return resp
    except Exception as e:
        print(f"[{horodatage()}] ❌ ScraperAPI erreur : {e}")
        return None

# ══════════════════════════════════════════════════════
# TELEGRAM
# ══════════════════════════════════════════════════════
def envoyer_telegram(annonce, score, token, chat_id):
    emoji = "🔥" if score >= 85 else "✅"
    vendeur = "👤 Particulier" if not annonce.get("pro") else "🏢 Professionnel"
    prix_affiche = f"{annonce['prix']:,}€" if annonce['prix'] > 0 else "Non renseigné"
    message = (
        f"{emoji} *Nouvelle alerte Trakar !*\n\n"
        f"🚗 *{annonce['titre']}*\n"
        f"💰 Prix : *{prix_affiche}*\n"
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
# LEBONCOIN
# ══════════════════════════════════════════════════════
def scraper_leboncoin(filtres):
    annonces = []
    try:
        marque = filtres["marque"]
        modele = filtres["modele"]
        prix_max = filtres["prix_max"]
        prix_min = filtres.get("prix_min", 0)

        url = (
            f"https://www.leboncoin.fr/recherche?"
            f"category=2&text={marque}+{modele}"
            f"&price={prix_min}-{prix_max}"
            f"&owner_type=private"
        )

        resp = scraper_url(url, render=True)
        if not resp or resp.status_code != 200:
            print(f"[{horodatage()}] ⚠️ LeBonCoin : échec scraping")
            return annonces

        soup = BeautifulSoup(resp.text, "html.parser")

        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script:
            data = json.loads(script.string)
            ads = (data.get("props", {})
                      .get("pageProps", {})
                      .get("searchData", {})
                      .get("ads", []))
            print(f"[{horodatage()}] 📋 LeBonCoin : {len(ads)} annonce(s) JSON")
            for ad in ads[:CONFIG["MAX_ANNONCES_PAR_SCAN"]]:
                try:
                    titre = ad.get("subject", "Annonce LeBonCoin")
                    prix = ad.get("price", [0])
                    prix = prix[0] if isinstance(prix, list) and prix else 0
                    url_annonce = "https://www.leboncoin.fr" + ad.get("url", "")
                    loc = ad.get("location", {})
                    localisation = f"{loc.get('city', '')} ({loc.get('zipcode', '')})"
                    annonce_id = "lbc_" + str(ad.get("list_id", hashlib.md5(url_annonce.encode()).hexdigest()[:10]))

                    attrs = {a["key"]: a.get("value_label", a.get("value", ""))
                             for a in ad.get("attributes", [])}
                    annee = attrs.get("regdate", "N/A")
                    km = attrs.get("mileage", "N/A")

                    pro = ad.get("owner", {}).get("type", "") == "pro"

                    annonces.append({
                        "id": annonce_id,
                        "titre": titre,
                        "prix": prix,
                        "url": url_annonce,
                        "localisation": localisation,
                        "annee": annee,
                        "km": km,
                        "source": "LeBonCoin",
                        "pro": pro,
                    })
                except:
                    continue
        else:
            cards = soup.select("a[href*='/voitures/offres/']")
            print(f"[{horodatage()}] 📋 LeBonCoin HTML : {len(cards)} carte(s)")
            for card in cards[:CONFIG["MAX_ANNONCES_PAR_SCAN"]]:
                try:
                    href = card.get("href", "")
                    if not href:
                        continue
                    url_annonce = "https://www.leboncoin.fr" + href
                    titre = card.get_text(separator=" ", strip=True)[:70]
                    annonce_id = "lbc_" + hashlib.md5(url_annonce.encode()).hexdigest()[:10]
                    annonces.append({
                        "id": annonce_id,
                        "titre": titre or "Annonce LeBonCoin",
                        "prix": 0,
                        "url": url_annonce,
                        "localisation": "France",
                        "annee": "N/A",
                        "km": "N/A",
                        "source": "LeBonCoin",
                        "pro": False,
                    })
                except:
                    continue

    except Exception as e:
        print(f"[{horodatage()}] ❌ LeBonCoin erreur : {e}")
    return annonces

# ══════════════════════════════════════════════════════
# LA CENTRALE
# ══════════════════════════════════════════════════════
def scraper_lacentrale(filtres):
    annonces = []
    try:
        marque = filtres["marque"].upper()
        modele = filtres["modele"].replace("+", "-plus")
        prix_max = filtres["prix_max"]
        prix_min = filtres.get("prix_min", 0)
        url = (
            f"https://www.lacentrale.fr/listing?"
            f"makesModelsCommercialNames={marque}%3A{modele}"
            f"&priceMax={prix_max}&priceMin={prix_min}"
            f"&sortBy=date&page=1"
        )

        resp = scraper_url(url, render=True)
        if not resp or resp.status_code != 200:
            print(f"[{horodatage()}] ⚠️ LaCentrale : échec scraping")
            return annonces

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("a[href*='/auto-occasion/']")
        print(f"[{horodatage()}] 📋 LaCentrale : {len(cards)} annonce(s)")

        for card in cards[:CONFIG["MAX_ANNONCES_PAR_SCAN"]]:
            try:
                href = card.get("href", "")
                if not href:
                    continue
                url_annonce = "https://www.lacentrale.fr" + href if href.startswith("/") else href
                titre = card.get_text(separator=" ", strip=True)[:70]
                annonce_id = "lc_" + hashlib.md5(url_annonce.encode()).hexdigest()[:10]

                annonces.append({
                    "id": annonce_id,
                    "titre": titre or "Annonce LaCentrale",
                    "prix": 0,
                    "url": url_annonce,
                    "localisation": "France",
                    "annee": "N/A",
                    "km": "N/A",
                    "source": "LaCentrale",
                    "pro": False,
                })
            except:
                continue

    except Exception as e:
        print(f"[{horodatage()}] ❌ LaCentrale erreur : {e}")
    return annonces

# ══════════════════════════════════════════════════════
# SCORING
# ══════════════════════════════════════════════════════
def calculer_score(annonce, filtres):
    score = 50
    prix = annonce.get("prix", 0)
    prix_max = filtres.get("prix_max", 1)

    if prix > 0:
        ratio = prix / prix_max
        if ratio < 0.7:
            score += 30
        elif ratio < 0.85:
            score += 15
        elif ratio < 0.95:
            score += 5

    if not annonce.get("pro"):
        score += 10

    km = annonce.get("km", "N/A")
    if km != "N/A":
        try:
            km_int = int(str(km).replace(" ", "").replace("km", ""))
            if km_int < 50000:
                score += 10
            elif km_int < 100000:
                score += 5
        except:
            pass

    return min(score, 100)

# ══════════════════════════════════════════════════════
# SCAN PRINCIPAL
# ══════════════════════════════════════════════════════
def scanner(vus):
    print(f"\n[{horodatage()}] 🔍 Démarrage du scan...")

    for client in CLIENTS:
        nom = client["nom"]
        token = client["telegram_token"]
        chat_id = client["telegram_chat_id"]
        filtres = client["filtres"]

        print(f"[{horodatage()}] 👤 Client : {nom}")

        toutes_annonces = []
        toutes_annonces += scraper_leboncoin(filtres)
        toutes_annonces += scraper_lacentrale(filtres)

        print(f"[{horodatage()}] 📦 Total annonces : {len(toutes_annonces)}")

        nouvelles = 0
        for annonce in toutes_annonces:
            annonce_id = annonce["id"]
            if annonce_id in vus:
                continue

            vus.add(annonce_id)
            score = calculer_score(annonce, filtres)

            if score >= CONFIG["SCORE_MIN"]:
                envoyer_telegram(annonce, score, token, chat_id)
                nouvelles += 1
                time.sleep(1)

        print(f"[{horodatage()}] ✅ {nouvelles} nouvelle(s) annonce(s) envoyée(s) pour {nom}")

    sauvegarder_vus(vus)

# ══════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════
def main():
    print(f"[{horodatage()}] 🚀 Trakar démarré")
    vus = charger_vus()

    scanner(vus)

    schedule.every(CONFIG["INTERVALLE_MINUTES"]).minutes.do(scanner, vus=vus)

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
