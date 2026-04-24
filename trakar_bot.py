import requests
import feedparser
from datetime import datetime

FILTRES = {
    "marque": "toyota",
    "modele": "yaris",
    "prix_max": 12000,
    "prix_min": 0,
    "km_max": 90000,
    "annee_min": 2018,
    "annee_max": 2023,
    "carburant": ["essence", "hybride"],
}

# ─────────────────────────────────────────
# 1. LEBONCOIN
# ─────────────────────────────────────────
def scraper_leboncoin(filtres):
    annonces = []
    try:
        url = "https://api.leboncoin.fr/finder/classified/search"
        headers = {
            "User-Agent": "LeBonCoin/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "api_key": "ba0c2dad52b3565fd92a3b ced9b4a9f7aae9e64d",
        }
        payload = {
            "filters": {
                "category": {"id": "2"},
                "enums": {
                    "ad_type": ["offer"],
                    "brand": [filtres["marque"]],
                    "model": [filtres["modele"]],
                    "fuel": ["essence", "hybride"],
                },
                "ranges": {
                    "price": {"max": filtres["prix_max"]},
                    "mileage": {"max": filtres["km_max"]},
                    "regdate": {
                        "min": filtres["annee_min"],
                        "max": filtres["annee_max"]
                    },
                },
            },
            "sort_by": "time",
            "sort_order": "desc",
            "limit": 20,
        }
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        data = r.json()
        for ad in data.get("ads", []):
            attrs = {a["key"]: a.get("value_label", a.get("values", [""])[0])
                     for a in ad.get("attributes", [])}
            annonces.append({
                "source": "LeBonCoin",
                "titre": ad.get("subject", ""),
                "prix": ad.get("price", [None])[0],
                "km": attrs.get("mileage", ""),
                "annee": attrs.get("regdate", ""),
                "carburant": attrs.get("fuel", ""),
                "boite": attrs.get("gearbox", ""),
                "url": ad.get("url", ""),
                "date": ad.get("first_publication_date", ""),
            })
    except Exception as e:
        print(f"[LeBonCoin] Erreur: {e}")
    return annonces


# ─────────────────────────────────────────
# 2. AUTOSCOUT24 (RSS)
# ─────────────────────────────────────────
def scraper_autoscout(filtres):
    annonces = []
    try:
        url = (
            f"https://www.autoscout24.fr/lst/{filtres['marque']}/{filtres['modele']}"
            f"?sort=age&desc=1"
            f"&priceto={filtres['prix_max']}"
            f"&kmto={filtres['km_max']}"
            f"&fregfrom={filtres['annee_min']}"
            f"&fregto={filtres['annee_max']}"
            f"&fuel=B%2CH"
            f"&ustate=N%2CU&size=20&output=rss"
        )
        feed = feedparser.parse(url)
        for entry in feed.entries:
            annonces.append({
                "source": "AutoScout24",
                "titre": entry.get("title", ""),
                "prix": entry.get("price", ""),
                "km": "",
                "annee": "",
                "carburant": "",
                "boite": "",
                "url": entry.get("link", ""),
                "date": entry.get("published", ""),
            })
    except Exception as e:
        print(f"[AutoScout24] Erreur: {e}")
    return annonces


# ─────────────────────────────────────────
# 3. PARUVENDU (RSS)
# ─────────────────────────────────────────
def scraper_paruvendu(filtres):
    annonces = []
    try:
        url = (
            f"https://www.paruvendu.fr/auto/rss/?"
            f"ma={filtres['marque'].upper()}"
            f"&mo={filtres['modele'].upper()}"
            f"&px2={filtres['prix_max']}"
            f"&km2={filtres['km_max']}"
            f"&aa1={filtres['annee_min']}"
            f"&aa2={filtres['annee_max']}"
            f"&carbu=1&carbu=6"
        )
        feed = feedparser.parse(url)
        for entry in feed.entries:
            annonces.append({
                "source": "ParuVendu",
                "titre": entry.get("title", ""),
                "prix": entry.get("price", ""),
                "km": "",
                "annee": "",
                "carburant": "",
                "boite": "",
                "url": entry.get("link", ""),
                "date": entry.get("published", ""),
            })
    except Exception as e:
        print(f"[ParuVendu] Erreur: {e}")
    return annonces


# ─────────────────────────────────────────
# 4. LA CENTRALE (requests)
# ─────────────────────────────────────────
def scraper_lacentrale(filtres):
    annonces = []
    try:
        url = "https://www.lacentrale.fr/api/v1/search"
        params = {
            "makesModelsCommercialNames": f"TOYOTA:YARIS",
            "priceMax": filtres["prix_max"],
            "mileageMax": filtres["km_max"],
            "yearMin": filtres["annee_min"],
            "yearMax": filtres["annee_max"],
            "energies": "essence,hybride",
            "sortBy": "creationDate",
            "sortOrder": "desc",
            "pageSize": 20,
            "page": 1,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
            "Referer": "https://www.lacentrale.fr/",
        }
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        for ad in data.get("ads", []):
            annonces.append({
                "source": "LaCentrale",
                "titre": ad.get("title", ""),
                "prix": ad.get("price", ""),
                "km": ad.get("mileage", ""),
                "annee": ad.get("year", ""),
                "carburant": ad.get("energy", ""),
                "boite": ad.get("gearbox", ""),
                "url": "https://www.lacentrale.fr" + ad.get("url", ""),
                "date": ad.get("creationDate", ""),
            })
    except Exception as e:
        print(f"[LaCentrale] Erreur: {e}")
    return annonces


# ─────────────────────────────────────────
# AGRÉGATEUR
# ─────────────────────────────────────────
def scraper_all(filtres=FILTRES):
    toutes = []
    toutes += scraper_leboncoin(filtres)
    toutes += scraper_autoscout(filtres)
    toutes += scraper_paruvendu(filtres)
    toutes += scraper_lacentrale(filtres)

    # Filtrage boîte auto en priorité (tri)
    def score(a):
        boite = str(a.get("boite", "")).lower()
        return 0 if "auto" in boite else 1

    toutes.sort(key=score)
    print(f"[TOTAL] {len(toutes)} annonces trouvées")
    return toutes
