import requests
import time
import random

# config
DISCORD_WEBHOOK = "https://discordapp.com/api/webhooks/1495571407885832264/HFxOFnLCfste9K0D5GK5jmWDE0if9VEnDpsdAJnGV1az0Ut8ahQrwueFSUwd7Zqz3NLG"
DISCORD_ERROR_LOGS = False  # set to False to suppress error/not-found notifications on Discord

# ─────────────────────────────────────────────
# GLOBAL PRODUCTS — edit this list to update
# all stores at once. Each store's individual
# "products" list (if set) overrides this.
# ─────────────────────────────────────────────
GLOBAL_PRODUCTS = [
    #{"name": "Test item", "webcode": "13810253007"},
    {"name": "Ascended Heros ETB", "webcode": "13810247007"},
    {"name": "Ascended Heros Booster Bundle", "webcode": "13810257007"},    
    {"name": "First collection", "webcode": "13810252007"},    
    {"name": "Prismatic", "webcode": "13810157007"},
    {"name": "Mega-Meganie-ex//Mega-Flambirex-ex//Mega-Impergator-ex", "webcode": "13810256007"},
    {"name": "151 Booster bundle", "webcode": "13810206007"},
]

# ─────────────────────────────────────────────
# STORES
# storeId  → look for "assignStore" in network tab
# webcode  → found in the product URL on expert.de
#
# To give a store its OWN product list (overrides
# GLOBAL_PRODUCTS for that store), add a "products"
# key as shown in the Freital example below.
# Leave "products" out to use GLOBAL_PRODUCTS.
#
# Freital        e_26051723
# Pirna          e_26051722
# Freiberg       e_13193164
# Bischofswerda  e_25254886
# Potzsch 01609  e_1906928
# Potzsch 04924  e_1907013
# Potzsch 04910  e_1907041
# Wunder         e_1907322
# Bautzen        e_25254885
# Sebnitz        e_31315790
# ─────────────────────────────────────────────
STORES = [
    {
        "storeId": "e_26051723",
        "name": "Freital",
    },
    {
        "storeId": "e_1906928",
        "name": "Potzsch 01609",
    },
    {
        "storeId": "e_1907013",
        "name": "Potzsch 04924",
    },
    {
        "storeId": "e_1907041",
        "name": "Potzsch 04910",
    },
    {
        "storeId": "e_31315790",
        "name": "Sebnitz",
    },
    {
        "storeId": "e_1907322",
        "name": "Wunder",
    },
    {
        "storeId": "e_26051722",
        "name": "Pirna",
    },
    {
        "storeId": "e_25254886",
        "name": "Bischofswerda",
    },
    {
        "storeId": "e_25254885",
        "name": "Bautzen",
    },
]


def send_discord_notification(store, product, stock):
    requests.post(DISCORD_WEBHOOK, json={
        "embeds": [{
            "title": "🎉 IN STOCK!",
            "description": f"**{product['name']}** is available at **{store['name']}**",
            "color": 3066993,
            "fields": [
                {"name": "Stock",  "value": str(stock),    "inline": True},
                {"name": "Store",  "value": store['name'], "inline": True},
                {"name": "Link",   "value": "https://www.expert.de/shop/unsere-produkte/spielwaren-unterhaltung/spielfiguren-sammelkarten-fanartikel/pokemon-karten/"}
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
                {"name": "Store ID",     "value": store['storeId'],  "inline": True},
                {"name": "Webcode",      "value": product['webcode'], "inline": True},
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

                if availability == "SOLD_OUT" or stock == 0:
                    print(f"❌ [{store['name']}] [{product['name']}] OUT OF STOCK (stock: {stock})")
                else:
                    print(f"🎉 [{store['name']}] [{product['name']}] IN STOCK! Stock: {stock}")
                    send_discord_notification(store, product, stock)
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
