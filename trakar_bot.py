import requests
import json
import time
import schedule
import hashlib
import os
from datetime import datetime
from bs4 import BeautifulSoup

# ══════════════════════════════════════════════════════
# CLIENTS — Ajoute chaque nouveau client ici
# ══════════════════════════════════════════════════════
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
    # ── Ajoute tes clients ici ──
    # {
    #     "nom": "Garage Dupont",
    #     "telegram_token": "8720932052:AAEqm7Pn6JRtHIIyZukSw19YoEo0anZ9gSM",
    #     "telegram_chat_id": "CHAT_ID_CLIENT",
    #     "filtres": {
    #         "marque": "peugeot",
    #         "modele": "3008",
    #         "prix_max": 20000,
    #         "prix_min": 5000,
    #         "km_max": 100000,
    #         "annee_min": 2018,
    #     }
    # },
]

CONFIG = {
    "INTERVALLE_MINUTES": 5,
    "SCORE_MIN": 0,
    "MAX_ANNONCES_PAR_SCAN": 20,
}

FICHIER_VUS = "trakar_vus.json"

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

def envoyer_telegram(annonce, score, token, chat_id):
    emoji = "🔥" if score >= 85 else "✅"
    message = (
        f"{emoji} *Nouvelle alerte Trakar !*\n\n"
        f"🚗 *{annonce['titre']}*\n"
        f"💰 Prix : *{annonce['prix']:,}€*\n"
        f"📍 Lieu : {annonce['localisation']}\n"
        f"📅 Année : {annonce.get('annee', 'N/A')} | 🛣 {annonce.get('km', 'N/A')} km\n"
        f"🌐 Source : {annonce.get('source', '')}\n"
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

def scraper_lacentrale(filtres):
    annonces = []
    try:
        marque = filtres["marque"].upper()
        modele = filtres["modele"].replace("+", "-plus")
        prix_max = filtres["prix_max"]
        url = f"https://www.lacentrale.fr/listing?makesModelsCommercialNames={marque}%3A{modele}&priceMax={prix_max}&options=&page=1"
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
                annonces.append({
                    "id": annonce_id,
                    "titre": titre or "Annonce La Centrale",
                    "prix": 0,
                    "url": url_annonce,
                    "localisation": "France",
                    "annee": "N/A",
                    "km": "N/A",
                    "source": "La Centrale"
                })
            except:
                continue
    except Exception as e:
        print(f"[{horodatage()}] ❌ La Centrale erreur : {e}")
    return annonces

def scraper_autoscout(filtres):
    annonces = []
    try:
        marque = filtres["marque"].lower()
        modele = filtres["modele"].lower().replace("+", "%2B")
        prix_max = filtres["prix_max"]
        url = f"https://www.autoscout24.fr/lst/{marque}/{modele}?sort=age&desc=1&priceto={prix_max}&ustate=N%2CU&size=20&page=1"
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
                annonces.append({
                    "id": annonce_id,
                    "titre": titre or "Annonce AutoScout24",
                    "prix": prix,
                    "url": url_annonce,
                    "localisation": loc[:40],
                    "annee": "N/A",
                    "km": "N/A",
                    "source": "AutoScout24"
                })
            except:
                continue
    except Exception as e:
        print(f"[{horodatage()}] ❌ AutoScout24 erreur : {e}")
    return annonces

def scraper_paruvendu(filtres):
    annonces = []
    try:
        marque = filtres["marque"].lower()
        modele = filtres["modele"].lower().replace("+", "-plus")
        prix_max = filtres["prix_max"]
        url = f"https://www.paruvendu.fr/auto-moto-bateau/voiture/{marque}/{modele}/?px2={prix_max}"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=20)
        print(f"[{horodatage()}] 🔍 ParuVendu status : {resp.status_code}")
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("div[class*='annonce']") or \
                soup.select("article") or \
                soup.select("a[href*='/voiture/']")
        print(f"[{horodatage()}] 📋 ParuVendu : {len(cards)} carte(s)")
        for card in cards[:10]:
            try:
                href = card.get("href", "") or (card.select_one("a") or {}).get("href", "")
                if not href or "voiture" not in href:
                    continue
                url_annonce = href if href.startswith("http") else "https://www.paruvendu.fr" + href
                titre = card.get_text(separator=" ", strip=True)[:70]
                annonce_id = "pv_" + hashlib.md5(url_annonce.encode()).hexdigest()[:10]
                annonces.append({
                    "id": annonce_id,
                    "titre": titre or "Annonce ParuVendu",
                    "prix": 0,
                    "url": url_annonce,
                    "localisation": "France",
                    "annee": "N/A",
                    "km": "N/A",
                    "source": "ParuVendu"
                })
            except:
                continue
    except Exception as e:
        print(f"[{horodatage()}] ❌ ParuVendu erreur : {e}")
    return annonces

def calculer_score(annonce, filtres):
    score = 55
    prix = annonce["prix"]
    if prix > 0:
        if prix < filtres["prix_max"] * 0.7:
            score += 35
        elif prix < filtres["prix_max"] * 0.85:
            score += 20
        elif prix < filtres["prix_max"] * 0.95:
            score += 10
    else:
        score += 15
    if annonce["localisation"] and annonce["localisation"] != "France":
        score += 5
    if annonce["titre"] and len(annonce["titre"]) > 10:
        score += 5
    return min(max(score, 0), 100)

def scanner_client(client, vus):
    nom = client["nom"]
    filtres = client["filtres"]
    token = client["telegram_token"]
    chat_id = client["telegram_chat_id"]
    nouvelles = 0
    print(f"\n[{horodatage()}] 👤 Scan pour : {nom}")
    toutes_annonces = []
    toutes_annonces += scraper_lacentrale(filtres)
    toutes_annonces += scraper_autoscout(filtres)
    toutes_annonces += scraper_paruvendu(filtres)
    print(f"[{horodatage()}] 📊 {nom} : {len(toutes_annonces)} annonce(s) trouvée(s)")
    for annonce in toutes_annonces:
        cle = f"{nom}_{annonce['id']}"
        if cle in vus:
            continue
        score = calculer_score(annonce, filtres)
        print(f"[{horodatage()}] 🎯 {score}/100 — {annonce['titre'][:40]} — {annonce['source']}")
        if score >= CONFIG["SCORE_MIN"]:
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
    print(f"🚗 TRAKAR PRO — Bot multi-clients démarré ({len(CLIENTS)} client(s))")
    lancer_scan()
    schedule.every(CONFIG["INTERVALLE_MINUTES"]).minutes.do(lancer_scan)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    demarrer()
