import requests
import json
import time
import schedule
import hashlib
import os
from datetime import datetime

CONFIG = {
    "TELEGRAM_TOKEN": "8720932052:AAEqm7Pn6JRtHIIyZukSw19YoEo0anZ9gSM",
    "TELEGRAM_CHAT_ID": "8779757061",
    "FILTRES": {
        "marque": "toyota",
        "modele": "prius+",
        "prix_max": 15000,
        "prix_min": 0,
        "km_max": 999999,
        "annee_min": 0,
    },
    "INTERVALLE_MINUTES": 5,
    "SCORE_MIN": 60,
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

def envoyer_telegram(annonce, score):
    token = CONFIG["TELEGRAM_TOKEN"]
    chat_id = CONFIG["TELEGRAM_CHAT_ID"]
    emoji = "🔥" if score >= 85 else "✅"
    message = (
        f"{emoji} *Nouvelle alerte Trakar !*\n\n"
        f"🚗 *{annonce['titre']}*\n"
        f"💰 Prix : *{annonce['prix']:,}€*\n"
        f"📍 Lieu : {annonce['localisation']}\n"
        f"📅 Année : {annonce.get('annee', 'N/A')} | 🛣 {annonce.get('km', 'N/A')} km\n"
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

def rechercher_annonces(filtres):
    url = "https://api.leboncoin.fr/finder/search"
    headers = {
        "User-Agent": "LeBonCoin/5.0 (Android)",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "api_key": "ba0c2dad52b3565fd92a83e3599e9312",
    }
    payload = {
        "filters": {
            "category": {"id": "2"},
            "enums": {
                "fuel": ["hybrid"],
            },
            "keywords": {
                "text": f"{filtres['marque']} {filtres['modele']}"
            },
            "ranges": {
                "price": {
                    "min": filtres["prix_min"],
                    "max": filtres["prix_max"]
                },
                "mileage": {
                    "max": filtres["km_max"]
                }
            }
        },
        "limit": filtres.get("MAX_ANNONCES_PAR_SCAN", 20),
        "sort_by": "time",
        "sort_order": "desc",
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("ads", [])
        else:
            print(f"[{horodatage()}] ❌ API LBC erreur {resp.status_code}")
            return []
    except Exception as e:
        print(f"[{horodatage()}] ❌ API LBC exception : {e}")
        return []

def parser_annonce(ad):
    try:
        titre = ad.get("subject", "")
        prix = ad.get("price", [0])[0] if ad.get("price") else 0
        url = ad.get("url", "")
        localisation = ad.get("location", {}).get("city", "")
        annonce_id = str(ad.get("list_id", hashlib.md5(url.encode()).hexdigest()[:12]))

        # Attributs
        attrs = {a["key"]: a.get("value_label", a.get("values_label", [""])[0]) 
                 for a in ad.get("attributes", [])}
        annee = attrs.get("regdate", "N/A")
        km = attrs.get("mileage", "N/A")

        return {
            "id": annonce_id,
            "titre": titre,
            "prix": prix,
            "url": url,
            "localisation": localisation,
            "annee": annee,
            "km": km,
        }
    except Exception as e:
        print(f"[{horodatage()}] ❌ Parse erreur : {e}")
        return None

def calculer_score(annonce, filtres):
    score = 50
    prix = annonce["prix"]
    if prix > 0:
        if prix < filtres["prix_max"] * 0.7:
            score += 35
        elif prix < filtres["prix_max"] * 0.85:
            score += 20
        elif prix < filtres["prix_max"] * 0.95:
            score += 10
    if annonce["localisation"]:
        score += 10
    if annonce["titre"]:
        score += 5
    return min(max(score, 0), 100)

def lancer_scan():
    print(f"\n[{horodatage()}] ━━━ Nouveau scan ━━━")
    filtres = CONFIG["FILTRES"]
    vus = charger_vus()
    nouvelles = 0

    ads = rechercher_annonces(filtres)
    print(f"[{horodatage()}] 📋 {len(ads)} annonce(s) trouvée(s)")

    for ad in ads[:CONFIG["MAX_ANNONCES_PAR_SCAN"]]:
        annonce = parser_annonce(ad)
        if not annonce:
            continue

        if annonce["id"] in vus:
            continue

        score = calculer_score(annonce, filtres)
        print(f"[{horodatage()}] 🎯 Score {score}/100 — {annonce['titre']} — {annonce['prix']}€")

        if score >= CONFIG["SCORE_MIN"]:
            envoyer_telegram(annonce, score)
            nouvelles += 1

        vus.add(annonce["id"])

    sauvegarder_vus(vus)
    print(f"[{horodatage()}] ✅ Scan terminé — {nouvelles} alerte(s) envoyée(s)")

def demarrer():
    print("🚗 TRAKAR — Bot démarré")
    lancer_scan()
    schedule.every(CONFIG["INTERVALLE_MINUTES"]).minutes.do(lancer_scan)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    demarrer()
