import feedparser
import time
from telegram import Bot

TOKEN = "TON_TOKEN_ICI"
CHAT_ID = "TON_CHAT_ID_ICI"

FILTRES = {
    "marque": "toyota",
    "modele": "yaris",
    "prix_max": 12000,
    "km_max": 90000,
    "annee_min": 2018,
    "annee_max": 2023,
}

annonces_vues = set()

def scraper_autoscout(filtres):
    annonces = []
    try:
        url = (
            f"https://www.autoscout24.fr/lst/{filtres['marque']}/{filtres['modele']}"
            f"?sort=age&desc=1&priceto={filtres['prix_max']}"
            f"&kmto={filtres['km_max']}&fregfrom={filtres['annee_min']}"
            f"&fregto={filtres['annee_max']}&fuel=B%2CH&ustate=N%2CU&size=20&output=rss"
        )
        feed = feedparser.parse(url)
        for entry in feed.entries:
            annonces.append({
                "source": "AutoScout24",
                "titre": entry.get("title", ""),
                "url": entry.get("link", ""),
            })
        print(f"[AutoScout24] {len(annonces)} annonces")
    except Exception as e:
        print(f"[AutoScout24] Erreur: {e}")
    return annonces

def scraper_paruvendu(filtres):
    annonces = []
    try:
        url = (
            f"https://www.paruvendu.fr/auto/rss/?"
            f"ma={filtres['marque'].upper()}&mo={filtres['modele'].upper()}"
            f"&px2={filtres['prix_max']}&km2={filtres['km_max']}"
            f"&aa1={filtres['annee_min']}&aa2={filtres['annee_max']}&carbu=1&carbu=6"
        )
        feed = feedparser.parse(url)
        for entry in feed.entries:
            annonces.append({
                "source": "ParuVendu",
                "titre": entry.get("title", ""),
                "url": entry.get("link", ""),
            })
        print(f"[ParuVendu] {len(annonces)} annonces")
    except Exception as e:
        print(f"[ParuVendu] Erreur: {e}")
    return annonces

def envoyer(bot, annonce):
    msg = (
        f"🚗 *{annonce['titre']}*\n"
        f"📌 Source: {annonce['source']}\n"
        f"🔗 {annonce['url']}"
    )
    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

def main():
    bot = Bot(token=TOKEN)
    print("✅ Bot démarré")
    while True:
        try:
            annonces = scraper_autoscout(FILTRES) + scraper_paruvendu(FILTRES)
            for a in annonces:
                if a["url"] not in annonces_vues:
                    annonces_vues.add(a["url"])
                    envoyer(bot, a)
                    time.sleep(1)
        except Exception as e:
            print(f"[ERREUR] {e}")
        time.sleep(1800)

if __name__ == "__main__":
    main()
