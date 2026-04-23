import requests
import json
import time
import schedule
import smtplib
import hashlib
import os
from datetime import datetime
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

CONFIG = {
    "TELEGRAM_TOKEN": "8720932052:AAEqm7Pn6JRtHIIyZukSw19YoEo0anZ9gSM",
    "TELEGRAM_CHAT_ID": "8779757061",
    "EMAIL_FROM": "tonemail@gmail.com",
    "EMAIL_PASSWORD": "ton_app_password",
    "EMAIL_TO": "destination@email.com",
    "FILTRES": {
        "marque": "toyota",
        "modele": "prius+",
        "prix_max": 15000,
        "prix_min": 0,
        "km_max": 999999,
        "annee_min": 0,
        "carburant": "hybride",
        "localisation": "",
        "rayon_km": 999,
    },
    "INTERVALLE_MINUTES": 5,
    "SCORE_MIN": 70,
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

SCRAPER_API_KEY = "3107bbb62b2150daf9b4a47336bbb939"

def construire_url(filtres):
    base = "https://www.leboncoin.fr/recherche"
    params = {
        "category": "2",
        "text": f"{filtres['marque']} {filtres['modele']}".strip(),
        "price": f"{filtres['prix_min']}-{filtres['prix_max']}",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items() if v)
    lbc_url = f"{base}?{query}"
    return f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={lbc_url}&render=true"

def extraire_prix(valeur):
    if isinstance(valeur, (int, float)):
        return int(valeur)
    try:
        return int("".join(filter(str.isdigit, str(valeur))))
    except:
        return 0

def horodatage():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def envoyer_telegram(annonce, score):
    token = CONFIG["TELEGRAM_TOKEN"]
    chat_id = CONFIG["TELEGRAM_CHAT_ID"]
    emoji = "🔥" if score >= 85 else "✅"
    message = (
        f"{emoji} *Nouvelle alerte Trakar !*\n\n"
        f"🚗 *{annonce['titre']}*\n"
        f"💰 Prix : *{annonce['prix']:,}€*\n"
        f"📍 Lieu : {annonce['localisation']}\n"
        f"🎯 Score : {score}/100\n\n"
        f"🔗 [Voir l'annonce]({annonce['url']})"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=10)
        print(f"[{horodatage()}] ✈️ Telegram envoyé : {annonce['titre']}")
    except Exception as e:
        print(f"[{horodatage()}] ❌ Telegram erreur : {e}")

def lancer_scan():
    print(f"\n[{horodatage()}] ━━━ Nouveau scan ━━━")
    filtres = CONFIG["FILTRES"]
    vus = charger_vus()
    url = construire_url(filtres)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("article[data-qa-id='aditem_container']")
        print(f"[{horodatage()}] 📋 {len(cards)} annonce(s) trouvée(s)")
        for card in cards[:CONFIG["MAX_ANNONCES_PAR_SCAN"]]:
            try:
                titre_el = card.select_one("[data-qa-id='aditem_title']")
                prix_el = card.select_one("[data-qa-id='aditem_price']")
                loc_el = card.select_one("[data-qa-id='aditem_location']")
                link_el = card.select_one("a")
                titre = titre_el.text.strip() if titre_el else ""
                prix = extraire_prix(prix_el.text if prix_el else "0")
                loc = loc_el.text.strip() if loc_el else ""
                url_annonce = "https://www.leboncoin.fr" + link_el["href"] if link_el else ""
                annonce_id = hashlib.md5(url_annonce.encode()).hexdigest()[:12]
                if annonce_id in vus:
                    continue
                annonce = {"titre": titre, "prix": prix, "localisation": loc, "url": url_annonce}
                score = min(max(50 + (30 if prix < 12000 else 0) + (10 if loc else 0), 0), 100)
                if score >= CONFIG["SCORE_MIN"]:
                    envoyer_telegram(annonce, score)
                vus.add(annonce_id)
            except:
                continue
    except Exception as e:
        print(f"[{horodatage()}] ❌ Erreur : {e}")
    sauvegarder_vus(vus)

def demarrer():
    print("🚗 TRAKAR — Bot démarré")
    lancer_scan()
    schedule.every(CONFIG["INTERVALLE_MINUTES"]).minutes.do(lancer_scan)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    demarrer()
