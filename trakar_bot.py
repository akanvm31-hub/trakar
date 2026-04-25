import requests
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime

# ============================================
# CONFIGURATION
# ============================================
TELEGRAM_TOKEN = "TON_TOKEN_ICI"
TELEGRAM_CHAT_ID = "TON_CHAT_ID_ICI"

RECHERCHES = [
    {
        "nom": "Toyota Camry pas cher LA",
        "ville": "losangeles",
        "marque": "toyota camry",
        "prix_max": 8000,
        "prix_min": 1000,
        "annee_min": 2010,
    },
    {
        "nom": "Honda Civic LA",
        "ville": "losangeles",
        "marque": "honda civic",
        "prix_max": 7000,
        "prix_min": 1000,
        "annee_min": 2010,
    },
]

INTERVALLE_SECONDES = 300

annonces_vues = set()

# ============================================
# SAUVEGARDE
# ============================================
def charger_annonces_vues():
    try:
        with open("annonces_vues.json", "r") as f:
            return set(json.load(f))
    except:
        return set()

def sauvegarder_annonces_vues():
    with open("annonces_vues.json", "w") as f:
        json.dump(list(annonces_vues), f)

# ============================================
# TELEGRAM
# ============================================
def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        requests.post(url, data=data, timeout=10)
        print("✅ Message Telegram envoyé")
    except Exception as e:
        print(f"❌ Erreur Telegram : {e}")

# ============================================
# SCRAPING
# ============================================
def scraper_craigslist(recherche):
    ville = recherche["ville"]
    url = f"https://{ville}.craigslist.org/search/cta"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    params = {
        "auto_make_model": recherche["marque"],
        "max_price": recherche["prix_max"],
        "min_price": recherche["prix_min"],
        "auto_year_min": recherche.get("annee_min", 2005),
        "sort": "date",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        print(f"📡 Status: {response.status_code} pour {recherche['nom']}")

        soup = BeautifulSoup(response.text, "html.parser")
        resultats = []

        # Méthode 1 - result-row
        annonces = soup.find_all("li", class_=lambda c: c and "result-row" in c)
        print(f"📋 Méthode 1 (result-row) : {len(annonces)}")

        # Méthode 2 - cl-search-result
        if not annonces:
            annonces = soup.select("li.cl-search-result")
            print(f"📋 Méthode 2 (cl-search-result) : {len(annonces)}")

        # Méthode 3 - cl-static-search-result
        if not annonces:
            annonces = soup.select(".cl-static-search-result")
            print(f"📋 Méthode 3 (cl-static-search-result) : {len(annonces)}")

        # Méthode 4 - liens /cto/
        if not annonces:
            liens = soup.find_all("a", href=lambda h: h and "/cto/" in h)
            print(f"📋 Méthode 4 (liens /cto/) : {len(liens)}")
            for lien_tag in liens:
                titre = lien_tag.get_text(strip=True)
                lien = lien_tag.get("href", "")
                if titre and lien:
                    resultats.append({
                        "titre": titre,
                        "prix": "Non précisé",
                        "lien": lien,
                        "lieu": "Los Angeles",
                    })
            return resultats

        # Traitement des annonces trouvées
        for annonce in annonces:
            try:
                lien_tag = annonce.find("a")
                if not lien_tag:
                    continue

                titre = lien_tag.get_text(strip=True)
                lien = lien_tag.get("href", "")

                prix_tag = annonce.find(class_=lambda c: c and "price" in str(c).lower())
                prix = prix_tag.get_text(strip=True) if prix_tag else "Non précisé"

                lieu_tag = annonce.find(class_=lambda c: c and (
                    "hood" in str(c) or "location" in str(c) or "meta" in str(c)
                ))
                lieu = lieu_tag.get_text(strip=True) if lieu_tag else "Non précisé"

                resultats.append({
                    "titre": titre,
                    "prix": prix,
                    "lien": lien,
                    "lieu": lieu,
                })

            except Exception as e:
                continue

        print(f"🔎 Total annonces extraites : {len(resultats)}")
        return resultats

    except Exception as e:
        print(f"❌ Erreur scraping : {e}")
        return []

# ============================================
# ALERTES
# ============================================
def analyser_et_alerter(annonces, recherche):
    nouvelles = 0

    for annonce in annonces:
        lien = annonce["lien"]
        if lien in annonces_vues:
            continue

        annonces_vues.add(lien)
        nouvelles += 1

        message = (
            f"🚗 <b>NOUVELLE ANNONCE</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📌 <b>{annonce['titre']}</b>\n"
            f"💰 <b>{annonce['prix']}</b>\n"
            f"📍 {annonce['lieu']}\n"
            f"🔗 <a href='{annonce['lien']}'>Voir l'annonce</a>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔎 Recherche : {recherche['nom']}"
        )

        envoyer_telegram(message)
        time.sleep(1)

    return nouvelles

# ============================================
# BOUCLE PRINCIPALE
# ============================================
def main():
    global annonces_vues
    annonces_vues = charger_annonces_vues()

    print("🚀 Bot Craigslist démarré !")
    print(f"🔍 {len(RECHERCHES)} recherche(s) configurée(s)")
    print(f"⏱️ Intervalle : {INTERVALLE_SECONDES} secondes\n")

    envoyer_telegram(
        "🚀 <b>Bot Craigslist démarré !</b>\n"
        f"🔍 {len(RECHERCHES)} recherche(s) active(s)\n"
        f"⏱️ Vérification toutes les {INTERVALLE_SECONDES // 60} minutes"
    )

    while True:
        print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] Nouvelle vérification...")
        total_nouvelles = 0

        for recherche in RECHERCHES:
            print(f"\n🔎 Recherche : {recherche['nom']}")
            annonces = scraper_craigslist(recherche)

            if annonces:
                nouvelles = analyser_et_alerter(annonces, recherche)
                total_nouvelles += nouvelles
                print(f"✅ {nouvelles} nouvelle(s) annonce(s)")
            else:
                print("⚠️ Aucune annonce récupérée")

            time.sleep(5)

        sauvegarder_annonces_vues()
        print(f"\n💾 Sauvegarde — {total_nouvelles} nouvelle(s) au total")
        print(f"⏳ Prochaine vérification dans {INTERVALLE_SECONDES // 60} minutes...")
        time.sleep(INTERVALLE_SECONDES)

if __name__ == "__main__":
    main()
