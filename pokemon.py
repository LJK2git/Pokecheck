import requests
import time
import random
import re

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DISCORD_WEBHOOK = "_webhook_here"  # rotate the one from before, it's been pasted in chat
DISCORD_ERROR_LOGS = False

# Category ID for "Pokemon Karten", found via DevTools. The script prints
# each hit's category name every cycle so you can eyeball-confirm this is
# still correct if expert.de ever reshuffles category IDs.
POKEMON_CATEGORY_ID = "e_3050"

# Optional per-product max price. Product names come from the site itself now
# (not hardcoded), so leave this empty until you've seen real names logged,
# then copy-paste them in exactly as printed.
PRICE_THRESHOLDS = {
    # "Pokémon KP09 Boosterpack (Karmesin & Purpur - Reisegefährten)": 6.00,
}

# Global floor — never post anything priced below this, no matter the product.
MIN_NOTIFY_PRICE = 10.00

# Product names containing any of these (case-insensitive) still get printed
# to console, but never sent to Discord.
BLACKLIST_KEYWORDS = [
    "Mega",
    "Kampfdeck",
    "3-Pack",
    "Battle",
    "Toolkit",
]
# Edit list based on which stores you want
STORES = [
    {"storeId": "e_26051723", "name": "Freital"},
    {"storeId": "e_1906928",  "name": "Potzsch 01609"},
    {"storeId": "e_1907013",  "name": "Potzsch 04924"},
    {"storeId": "e_1907041",  "name": "Potzsch 04910"},
    {"storeId": "e_31315790", "name": "Sebnitz"},
    {"storeId": "e_1907322",  "name": "Wunder"},
    {"storeId": "e_26051722", "name": "Pirna"},
    {"storeId": "e_25254886", "name": "Bischofswerda"},
    {"storeId": "e_25254885", "name": "Bautzen"},
]

SEARCH_URL = "https://production.brntgs.expert.de/api/search/ppm-category"
CATEGORY_PAGE_URL = "https://www.expert.de/shop/unsere-produkte/spielwaren-unterhaltung/spielfiguren-sammelkarten-fanartikel/pokemon-karten"

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
    "Origin": "https://www.expert.de",
    "Referer": "https://www.expert.de/",
}


def format_price(price):
    return f"€{price:.2f}" if price is not None else "unknown"


def is_blacklisted(name):
    name_lower = (name or "").lower()
    return any(kw.lower() in name_lower for kw in BLACKLIST_KEYWORDS)


def send_discord_notification(store, product, price, price_dropped=False):
    threshold = PRICE_THRESHOLDS.get(product["name"])
    under_threshold = threshold is not None and price is not None and price <= threshold

    if price_dropped:
        title = "💸 PRICE DROP + IN STOCK!"
        color = 15844367
    elif under_threshold:
        title = "🔥 GREAT PRICE + IN STOCK!"
        color = 15105570
    else:
        title = "🎉 IN STOCK!"
        color = 3066993

    fields = [
        {"name": "Store", "value": store["name"], "inline": True},
        {"name": "Price", "value": format_price(price), "inline": True},
    ]
    if threshold is not None:
        fields.append({"name": "Your Max Price", "value": format_price(threshold), "inline": True})
    fields.append({
        "name": "Link",
        "value": f"{CATEGORY_PAGE_URL}/{product['slug']}",
        "inline": False,
    })

    requests.post(DISCORD_WEBHOOK, json={
        "embeds": [{
            "title": title,
            "description": f"**{product['name']}** is available at **{store['name']}**",
            "color": color,
            "fields": fields,
        }]
    })


def send_discord_price_change(store, product, old_price, new_price):
    requests.post(DISCORD_WEBHOOK, json={
        "embeds": [{
            "title": "📉 Price Changed!",
            "description": f"**{product['name']}** price changed at **{store['name']}**",
            "color": 3447003,
            "fields": [
                {"name": "Old Price", "value": format_price(old_price), "inline": True},
                {"name": "New Price", "value": format_price(new_price), "inline": True},
                {"name": "Store", "value": store["name"], "inline": True},
            ],
        }]
    })


def send_discord_error(store, error):
    if not DISCORD_ERROR_LOGS:
        return
    requests.post(DISCORD_WEBHOOK, json={
        "embeds": [{
            "title": "⚠️ Error fetching category",
            "description": f"Failed to fetch Pokemon Karten listing for **{store['name']}**",
            "color": 15158332,
            "fields": [{"name": "Error", "value": str(error)[:500], "inline": False}],
        }]
    })


def make_session():
    s = requests.Session()
    s.get("https://www.expert.de", headers=BASE_HEADERS)
    s.post(
        "https://www.expert.de/api/neo/frontend/_api/user/consent",
        json={
            "IABConsentString": "",
            "preference": {"MARKETING": True, "PRODUCT_RATINGS": True, "REQUIRED": True, "STATISTICS": True},
            "privacyPreferenceInfo": "CookiebotRenderPostProcessor",
        },
        headers=BASE_HEADERS,
    )
    return s


def fetch_category_products(session, store_id, hits_per_page=100):
    """One call = every product currently in Pokemon Karten, scoped to this
    store's stock, via the fmarktheader header."""
    headers = {**BASE_HEADERS, "fmarktheader": store_id}
    body = [{
        "indexName": "expert_article_search",
        "params": {
            "filters": f"categories:{POKEMON_CATEGORY_ID}",
            "hitsPerPage": hits_per_page,
        },
    }]
    resp = session.post(SEARCH_URL, json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    result = resp.json()["results"][0]

    if result.get("nbPages", 1) > 1:
        print(f"⚠️  More results exist than fit on one page (nbHits={result.get('nbHits')}). "
              f"Bump hits_per_page if this keeps happening.")

    products = []
    for hit in result.get("hits", []):
        slug = hit.get("slug", "")
        m = re.match(r"^(\d+)-", slug)
        store_info = hit.get("storeData", {}).get(store_id, {})
        products.append({
            "articleId": hit.get("objectID"),
            "name": hit.get("name") or hit.get("headline"),
            "slug": slug,
            "webcode": m.group(1) if m else None,
            "category": hit.get("primaryCategory", {}).get("name"),
            "availability": store_info.get("combinedAvailability", "UNKNOWN"),
            "price": store_info.get("priceGross"),
        })
    return products, result.get("nbHits", 0)


def main():
    session = make_session()
    print("✅ Session ready\n")

    last_price = {}            # key -> last seen price
    in_stock_notified = set()  # key -> already alerted while currently in stock

    while True:
        for store in STORES:
            try:
                products, nb_hits = fetch_category_products(session, store["storeId"])
            except Exception as e:
                print(f"❌ [{store['name']}] Failed to fetch category: {e}")
                send_discord_error(store, e)
                time.sleep(5)
                continue

            categories_seen = sorted({p["category"] for p in products if p["category"]})
            print(f"\n📦 [{store['name']}] {nb_hits} products found (categories: {categories_seen})")

            for product in products:
                if not product["webcode"]:
                    continue

                key = f"{store['storeId']}_{product['webcode']}"
                price = product["price"]
                in_stock = product["availability"] == "AVAILABLE"
                blacklisted = is_blacklisted(product["name"])

                old_price = last_price.get(key)
                price_dropped = False
                if price is not None:
                    if old_price is not None and old_price != price:
                        price_dropped = price < old_price
                        change = f"↓ {format_price(old_price)} → {format_price(price)}" if price_dropped \
                            else f"↑ {format_price(old_price)} → {format_price(price)}"
                        print(f"💰 [{store['name']}] [{product['name']}] Price changed: {change}")
                        if in_stock and not blacklisted:
                            send_discord_price_change(store, product, old_price, price)
                    last_price[key] = price

                threshold = PRICE_THRESHOLDS.get(product["name"])
                under_max = threshold is None or (price is not None and price <= threshold)
                above_min = price is None or price >= MIN_NOTIFY_PRICE
                price_ok = under_max and above_min

                if not in_stock:
                    print(f"❌ [{store['name']}] [{product['name']}] {product['availability']} "
                          f"(price: {format_price(price)})")
                    in_stock_notified.discard(key)  # re-alert if it goes out then back in stock
                elif blacklisted:
                    print(f"🚫 [{store['name']}] [{product['name']}] IN STOCK (price: {format_price(price)}) "
                          f"— blacklisted keyword match, not sending to Discord")
                elif not above_min:
                    print(f"⚠️  [{store['name']}] [{product['name']}] IN STOCK but price "
                          f"{format_price(price)} < €{MIN_NOTIFY_PRICE:.2f} minimum — skipping")
                elif not under_max:
                    print(f"⚠️  [{store['name']}] [{product['name']}] IN STOCK but price "
                          f"{format_price(price)} > threshold {format_price(threshold)} — skipping")
                elif key not in in_stock_notified:
                    print(f"🎉 [{store['name']}] [{product['name']}] IN STOCK! Price: {format_price(price)}")
                    send_discord_notification(store, product, price, price_dropped)
                    in_stock_notified.add(key)

            store_delay = random.randint(90, 200)
            print(f"waiting {store_delay}s before next store")
            time.sleep(store_delay)

        cycle_delay = random.randint(300, 600)
        print(f"\n⏳ Full cycle done for all stores, sleeping {cycle_delay}s...\n")
        time.sleep(cycle_delay)


if __name__ == "__main__":
    main()
