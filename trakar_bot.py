def scraper_lacentrale(filtres):
    annonces = []
    try:
        marque = filtres["marque"].lower()
        modele = filtres["modele"].lower()
        prix_max = filtres["prix_max"]
        prix_min = filtres.get("prix_min", 0)
        km_max = filtres.get("km_max", 200000)

        url = f"https://www.lacentrale.fr/api/v1/search"
        params = {
            "makesModelsCommercialNames": f"{marque}:{modele}",
            "priceMax": prix_max,
            "priceMin": prix_min,
            "mileageMax": km_max,
            "sortBy": "creationDate",
            "sortOrder": "desc",
            "pageSize": 20,
            "page": 1,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fr-FR,fr;q=0.9",
            "Referer": "https://www.lacentrale.fr/listing",
            "Origin": "https://www.lacentrale.fr",
            "x-requested-with": "XMLHttpRequest",
        }

        session = requests.Session()
        # D'abord on visite la page principale pour avoir les cookies
        session.get("https://www.lacentrale.fr", headers=headers, timeout=15)
        time.sleep(2)
        resp = session.get(url, params=params, headers=headers, timeout=20)
        print(f"[{horodatage()}] 🔍 La Centrale status : {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"[{horodatage()}] 🔑 Clés reçues La Centrale : {list(data.keys())}")

            listings = []
            for key in ["ads", "results", "listings", "data", "offers", "items"]:
                if key in data:
                    listings = data[key]
                    print(f"[{horodatage()}] ✅ Clé trouvée : {key} → {len(listings)} item(s)")
                    break

            for item in listings[:CONFIG["MAX_ANNONCES_PAR_SCAN"]]:
                try:
                    prix = int(item.get("price", item.get("prix", 0)) or 0)
                    if prix > prix_max and prix > 0:
                        continue
                    titre = item.get("title", item.get("titre", item.get("name", "Annonce La Centrale")))
                    id_annonce = str(item.get("id", item.get("adId", "")))
                    url_annonce = item.get("url", item.get("link", f"https://www.lacentrale.fr/auto-occasion-annonce-{id_annonce}.html"))
                    annonce_id = "lc_" + hashlib.md5(url_annonce.encode()).hexdigest()[:10]
                    annonces.append({
                        "id": annonce_id,
                        "titre": str(titre)[:70],
                        "prix": prix,
                        "url": url_annonce,
                        "localisation": item.get("city", item.get("ville", item.get("location", "France"))),
                        "annee": item.get("year", item.get("annee", "N/A")),
                        "km": item.get("mileage", item.get("km", "N/A")),
                        "source": "La Centrale"
                    })
                except Exception as ex:
                    print(f"[{horodatage()}] ⚠️ Item ignoré : {ex}")
                    continue

        print(f"[{horodatage()}] 📋 La Centrale : {len(annonces)} annonce(s)")
    except Exception as e:
        print(f"[{horodatage()}] ❌ La Centrale erreur : {e}")
    return annonces
