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

INTERVALLE_SECONDES = 300  # Vérifie toutes les 5 minutes

# ============================================
# STOCKAGE DES ANNONCES DÉJÀ VUES
# ============================================
annonces_vues = set()

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
        print(f"✅ Message Telegram envoyé")
    except Exception as e:
        print(f"❌ Erreur Telegram : {e}")

# ============================================
# SCRAPING CRAIGSLIST
# ============================================
def scraper_craigslist(recherche):
    ville = recherche["ville"]
    url = f"https://{ville}.craigslist.org/search/cta"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }

    params = {
        "auto_make_model": recherche["marque"],
        "max_price": recherche["prix_max"],
        "min_price": recherche["prix_min"],
        "auto_year_min": recherche.get("annee_min", 2005),
        "sort": "date",  # Les plus récentes en premier
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        print(f"📡 Status: {response.status_code} pour {recherche['nom']}")

        if response.status_code != 200:
            print(f"❌ Erreur HTTP {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        annonces = soup.find_all("li", class_="cl-search-result")
        print(f"🔍 {len(annonces)} annonces trouvées pour {recherche['nom']}")

        resultats = []

        for annonce in annonces:
            try:
                # Titre et lien
                lien_tag = annonce.find("a", class_="cl-app-anchor")
                if not lien_tag:
                    continue

                titre = lien_tag.get_text(strip=True)
                lien = lien_tag.get("href", "")

                # Prix
                prix_tag = annonce.find("span", class_="priceinfo")
                if not prix_tag:
                    continue
                prix_texte = prix_tag.get_text(strip=True)
                prix = int(prix_texte.replace("$", "").replace(",", "").strip())

                # Localisation
                lieu_tag = annonce.find("div", class_="supertitle")
                lieu = lieu_tag.get_text(strip=True) if lieu_tag else "Non précisé"

                # Date
                date_tag = annonce.find("div", class_="meta")
                date = date_tag.get_text(strip=True) if date_tag else ""

                resultats.append({
                    "titre": titre,
                    "prix": prix,
                    "lien": lien,
                    "lieu": lieu,
                    "date": date,
                })

            except Exception as e:
                continue

        return resultats

    except Exception as e:
        print(f"❌ Erreur scraping : {e}")
        return []

# ============================================
# ANALYSE ET ALERTE
# ============================================
def analyser_et_alerter(annonces, recherche):
    nouvelles = 0

    for annonce in annonces:
        lien = annonce["lien"]

        # Déjà vue ?
        if lien in annonces_vues:
            continue

        annonces_vues.add(lien)
        nouvelles += 1

        # Construire le message Telegram
        message = (
            f"🚗 <b>NOUVELLE ANNONCE</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📌 <b>{annonce['titre']}</b>\n"
            f"💰 <b>{annonce['prix']}$</b>\n"
            f"📍 {annonce['lieu']}\n"
            f"🕐 {annonce['date']}\n"
            f"🔗 <a href='{annonce['lien']}'>Voir l'annonce</a>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🔎 Recherche : {recherche['nom']}"
        )

        envoyer_telegram(message)
        time.sleep(1)  # Pause entre chaque message

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
        f"⏱️ Vérification toutes les {INTERVALLE_SECONDES//60} minutes"
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
                print(f"⚠️ Aucune annonce récupérée")

            time.sleep(5)  # Pause entre chaque recherche

        sauvegarder_annonces_vues()
        print(f"\n💾 Sauvegarde effectuée — {total_nouvelles} nouvelle(s) au total")
        print(f"⏳ Prochaine vérification dans {INTERVALLE_SECONDES//60} minutes...")
        time.sleep(INTERVALLE_SECONDES)

if __name__ == "__main__":
    main()
