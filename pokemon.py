import requests
import time
import random

# config
DISCORD_WEBHOOK = "https://discordapp.com/api/webhooks/1495571407885832264/HFxOFnLCfste9K0D5GK5jmWDE0if9VEnDpsdAJnGV1az0Ut8ahQrwueFSUwd7Zqz3NLG"
DISCORD_ERROR_LOGS = False  # set to False to suppress error/not-found notifications on Discord

# ─────────────────────────────────────────────
# PRICE CHECKER CONFIG
# Set a max price threshold per product name.
# If the product is in stock AND at or below the
# threshold, you get a special "price drop" alert.
# Set to None to always notify regardless of price.
# ─────────────────────────────────────────────
PRICE_THRESHOLDS = {
    "Test item":                                    None,
    "Ascended Heros ETB":                           None,
    "Ascended Heros Booster Bundle":                None,
    "First collection":                             None,
    "Prismatic":                                    None,
    "Mega-Meganie-ex//Mega-Flambirex-ex//Mega-Impergator-ex": None,
    "151 Booster bundle":                           None,
}

# ─────────────────────────────────────────────
# GLOBAL PRODUCTS — edit this list to update
# all stores at once. Each store's individual
# "products" list (if set) overrides this.
# ─────────────────────────────────────────────
GLOBAL_PRODUCTS = [
    #{"name": "Test item",                                       "webcode": "13810147007"},
    {"name": "Ascended Heros ETB",                              "webcode": "13810247007"},
    {"name": "Ascended Heros Booster Bundle",                   "webcode": "13810257007"},
    {"name": "First collection",                                "webcode": "13810252007"},
    {"name": "Prismatic",                                       "webcode": "13810157007"},
    {"name": "Mega-Meganie-ex//Mega-Flambirex-ex//Mega-Impergator-ex", "webcode": "13810256007"},
    {"name": "151 Booster bundle",                              "webcode": "13810206007"},
]

# ─────────────────────────────────────────────
# STORES
# ─────────────────────────────────────────────
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


def get_price_from_data(data):
    """Extract price from top-level promotionPrice, fall back to price.bruttoPrice."""
    try:
        promo = data.get("promotionPrice") or {}
        for field in ("checkoutPrice", "afterCashbackPrice", "currentPrice"):
            val = promo.get(field)
            if val is not None:
                return float(val)
        # last resort: bruttoPrice inside price object
        return float(data["price"]["bruttoPrice"])
    except (KeyError, TypeError, ValueError):
        return None


def format_price(price):
    return f"€{price:.2f}" if price is not None else "unknown"


def send_discord_notification(store, product, stock, price=None, price_dropped=False):
    threshold = PRICE_THRESHOLDS.get(product["name"])
    under_threshold = threshold is not None and price is not None and price <= threshold

    if price_dropped:
        title = "💸 PRICE DROP + IN STOCK!"
        color = 15844367  # gold
    elif under_threshold:
        title = "🔥 GREAT PRICE + IN STOCK!"
        color = 15105570  # orange
    else:
        title = "🎉 IN STOCK!"
        color = 3066993   # green

    fields = [
        {"name": "Stock",  "value": str(stock),        "inline": True},
        {"name": "Store",  "value": store["name"],      "inline": True},
        {"name": "Price",  "value": format_price(price),"inline": True},
    ]

    if threshold is not None:
        fields.append({"name": "Your Max Price", "value": format_price(threshold), "inline": True})

    fields.append({
        "name": "Link",
        "value": "https://www.expert.de/shop/unsere-produkte/spielwaren-unterhaltung/spielfiguren-sammelkarten-fanartikel/pokemon-karten/",
        "inline": False
    })

    requests.post(DISCORD_WEBHOOK, json={
        "embeds": [{
            "title": title,
            "description": f"**{product['name']}** is available at **{store['name']}**",
            "color": color,
            "fields": fields
        }]
    })


def send_discord_price_change(store, product, old_price, new_price, stock):
    """Send a Discord alert when price changes even if already notified as in-stock."""
    requests.post(DISCORD_WEBHOOK, json={
        "embeds": [{
            "title": "📉 Price Changed!",
            "description": f"**{product['name']}** price changed at **{store['name']}**",
            "color": 3447003,  # blue
            "fields": [
                {"name": "Old Price", "value": format_price(old_price), "inline": True},
                {"name": "New Price", "value": format_price(new_price), "inline": True},
                {"name": "Stock",     "value": str(stock),              "inline": True},
                {"name": "Store",     "value": store["name"],           "inline": True},
            ]
        }]
    })


def send_discord_error(store, product, error, raw=""):
    requests.post(DISCORD_WEBHOOK, json={
        "embeds": [{
            "title": "⚠️ Error / Product Not Found",
            "description": f"**{product['name']}** at **{store['name']}** returned an error.",
            "color": 15158332,
            "fields": [
                {"name": "Error",        "value": str(error)[:500],  "inline": False},
                {"name": "Raw Response", "value": raw[:500] or "empty", "inline": False},
                {"name": "Store ID",     "value": store["storeId"],  "inline": True},
                {"name": "Webcode",      "value": product["webcode"], "inline": True},
            ]
        }]
    })


def make_session(store_id):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:149.0) Gecko/20100101 Firefox/149.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "bt-use-user-auth": "true",
        "Origin": "https://www.expert.de",
        "Referer": "https://www.expert.de/",
    }
    session.get("https://www.expert.de", headers=headers)
    session.post(
        "https://www.expert.de/api/neo/frontend/_api/user/consent",
        json={
            "IABConsentString": "",
            "preference": {
                "MARKETING": True,
                "PRODUCT_RATINGS": True,
                "REQUIRED": True,
                "STATISTICS": True
            },
            "privacyPreferenceInfo": "CookiebotRenderPostProcessor"
        },
        headers=headers
    )
    session.post(
        "https://www.expert.de/api/neo/frontend/_api/storeFinder/assignStore",
        json={"storeId": store_id},
        headers=headers
    )
    return session, headers


# ── resolve each store's product list ──────────
for store in STORES:
    if "products" not in store:
        store["products"] = GLOBAL_PRODUCTS

# ── set up sessions ─────────────────────────────
print("🔧 Setting up sessions...")
for store in STORES:
    store["session"], store["headers"] = make_session(store["storeId"])
    store["in_stock_found"] = set()
    store["error_notified"] = set()
    store["last_price"] = {}        # key → last seen price (tracks changes)
    print(f"   ✅ {store['name']} ({store['storeId']})")

print(f"\n✅ All sessions ready, starting monitor...\n")

while True:
    all_done = True

    for store in STORES:
        store_delay = random.randint(20, 30)
        print(f"waiting {store_delay}s before checking next store")
        time.sleep(store_delay)

        for product in store["products"]:
            key = f"{store['storeId']}_{product['webcode']}"
            if key in store["in_stock_found"]:
                continue

            all_done = False
            response = None

            try:
                response = store["session"].get(
                    f"https://production.brntgs.expert.de/api/pricepds?webcode={product['webcode']}&storeId={store['storeId']}",
                    headers=store["headers"]
                )

                data = response.json()
                availability = data["price"]["storeAvailability"]
                stock = data["price"]["storeStock"]
                price = get_price_from_data(data)

                threshold = PRICE_THRESHOLDS.get(product["name"])
                price_ok = threshold is None or (price is not None and price <= threshold)

                # ── price change tracking (even when out of stock) ──
                old_price = store["last_price"].get(key)
                if price is not None:
                    if old_price is not None and old_price != price:
                        price_dropped = price < old_price
                        change_str = f"↓ {format_price(old_price)} → {format_price(price)}" if price_dropped else f"↑ {format_price(old_price)} → {format_price(price)}"
                        print(f"💰 [{store['name']}] [{product['name']}] Price changed: {change_str}")
                        # only ping Discord for price changes when item is in stock
                        if availability != "SOLD_OUT" and stock > 0:
                            send_discord_price_change(store, product, old_price, price, stock)
                    store["last_price"][key] = price

                if availability == "SOLD_OUT" or stock == 0:
                    print(f"❌ [{store['name']}] [{product['name']}] OUT OF STOCK (stock: {stock}, price: {format_price(price)})")
                elif not price_ok:
                    print(f"⚠️  [{store['name']}] [{product['name']}] IN STOCK but price {format_price(price)} > threshold {format_price(threshold)} — skipping")
                else:
                    price_dropped = old_price is not None and price is not None and price < old_price
                    print(f"🎉 [{store['name']}] [{product['name']}] IN STOCK! Stock: {stock}, Price: {format_price(price)}")
                    send_discord_notification(store, product, stock, price, price_dropped)
                    store["in_stock_found"].add(key)

            except Exception as e:
                raw = response.text[:200] if response else "no response"
                print(f"❌ [{store['name']}] [{product['name']}] Error: {e}")
                print(f"   Raw response: {raw}")

                if DISCORD_ERROR_LOGS and key not in store["error_notified"]:
                    send_discord_error(store, product, e, raw)
                    store["error_notified"].add(key)

            time.sleep(2)

    if all_done:
        print("\n🎉 All products in stock! Stopping.")
        break

    delay = random.randint(900, 1100)
    print(f"\n⏳ Checking again in {delay}s...\n")
    time.sleep(delay)
