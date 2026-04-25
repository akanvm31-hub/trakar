import requests
import time

TOKEN = "8720932052:AAEqm7Pn6JRtHIIyZukSw19YoEo0anZ9gSM"
CHAT_ID = "8779757061"

FILTRES = {
    "marque": "toyota",
    "modele": "yaris",
    "prix_max": 12000,
    "prix_min": 0,
    "km_max": 90000,
    "annee_min": 2018,
}

annonces_vues = set()

def envoyer_telegram(annonce, score):
    emoji = "🔥" if score >= 85 else "✅"
    vendeur = "👤 Particulier" if not annonce.get("pro") else "🏢 Professionnel"
    message = (
        f"{emoji} *Nouvelle alerte Trakar !*\n\n"
        f"🚗 *{annonce['titre']}*\n"
        f"💰 Prix : *{annonce['prix']:,}€*\n"
        f"📍 Lieu : {annonce['localisation']}\n"
        f"📅 Année : {annonce.get('annee', 'N/A')} | 🛣 {annonce.get('km', 'N/A')} km\n"
        f"🌐 Source : {annonce.get('source', '')}\n"
        f"👤 Vendeur : {vendeur}\n"
        f"🎯 Score : {score}/100\n\n"
        f"🔗 [Voir l'annonce]({annonce['url']})"
    )
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        })
        if r.status_code == 200:
            print("✅ Message Telegram envoyé")
        else:
            print(f"❌ Erreur Telegram : {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Exception Telegram : {e}")

def scraper_autoscout(filtres):
    annonces = []
    try:
        url = "https://www.autoscout24.fr/lst"
        params = {
            "make": filtres["marque"],
            "model": filtres["modele"],
            "priceto": filtres["prix_max"],
            "mileageto": filtres["km_max"],
            "fregfrom": filtres.get("annee_min", 2018),
            "cy": "F",
            "atype": "C",
            "results_per_page": 20,
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=params, headers=headers, timeout=15)
        print(f"🔍 AutoScout24 status : {r.status_code}")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("[data-testid='regular-article-container']")
        print(f"📋 AutoScout24 : {len(cards)} annonces trouvées")
        for card in cards:
            try:
                titre = card.select_one("h2").text.strip()
                prix_txt = card.select_one("[data-testid='price-label']").text.strip()
                prix = int(''.join(filter(str.isdigit, prix_txt)))
                lien = "https://www.autoscout24.fr" + card.select_one("a")["href"]
                annonces.append({
                    "titre": titre,
                    "prix": prix,
                    "localisation": "France",
                    "km": filtres["km_max"],
                    "annee": filtres.get("annee_min", 2018),
                    "url": lien,
                    "source": "AutoScout24",
                    "pro": False,
                })
            except:
                continue
    except Exception as e:
        print(f"❌ AutoScout24 erreur : {e}")
    return annonces

def calculer_score(annonce, filtres):
    score = 50
    if annonce["prix"] <= filtres["prix_max"] * 0.8:
        score += 20
    elif annonce["prix"] <= filtres["prix_max"] * 0.9:
        score += 10
    if annonce.get("km", 99999) <= 50000:
        score += 20
    elif annonce.get("km", 99999) <= 70000:
        score += 10
    if not annonce.get("pro"):
        score += 10
    return min(score, 100)

def main():
    print("✅ Bot Trakar démarré")
    while True:
        try:
            annonces = scraper_autoscout(FILTRES)
            for a in annonces:
                if a["url"] not in annonces_vues:
                    annonces_vues.add(a["url"])
                    score = calculer_score(a, FILTRES)
                    envoyer_telegram(a, score)
                    time.sleep(2)
        except Exception as e:
            print(f"[ERREUR] {e}")
        print("⏳ Pause 30 min...")
        time.sleep(1800)

if __name__ == "__main__":
    main()
