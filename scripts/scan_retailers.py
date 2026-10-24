#!/usr/bin/env python3
"""Best-effort product-feed adapter for the unofficial NZ retailer CLI tools.
Only publishes records containing a product name and a current price.
"""
import json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "deals.json"
STORES = {
    "Mitre 10": [["mitre10", "search", term, "--limit", "20", "--json"] for term in ["clearance", "sale", "tools", "paint"]],
    "Kmart": [["kmart", "--country", "nz", "search", term, "--json"] for term in ["clearance", "sale", "home", "storage"]],
    "The Warehouse": [["twlnz", "specials", "--limit", "40", "--json"]],
    "Farmers": [["farmers", "search", term, "--prices", "--limit", "15", "--json"] for term in ["clearance", "sale", "home", "clothing"]],
}
PRICE_KEYS = ("price", "current_price", "sale_price", "selling_price", "final_price", "price_value", "min_price")
NAME_KEYS = ("name", "title", "product_name", "display_name", "description")
ID_KEYS = ("id", "sku", "code", "keycode", "pid", "product_id", "product_code", "url")

def number(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool): return float(v)
    if isinstance(v, str):
        m = re.search(r"\d[\d,]*(?:\.\d{1,2})?", v.replace(",", ""))
        if m:
            try: return float(m.group())
            except ValueError: pass
    return None

def walk(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            if isinstance(v, (dict, list)): yield from walk(v)
    elif isinstance(x, list):
        for v in x: yield from walk(v)

def normalize(store, payload):
    rows = []
    for obj in walk(payload):
        name = next((str(obj[k]).strip() for k in NAME_KEYS if isinstance(obj.get(k), str) and obj[k].strip()), None)
        price = next((number(obj[k]) for k in PRICE_KEYS if k in obj and number(obj[k]) is not None), None)
        if not name or price is None or price <= 0: continue
        pid = next((str(obj[k]) for k in ID_KEYS if obj.get(k) not in (None, "")), name)
        old = next((number(obj[k]) for k in ("was_price", "original_price", "regular_price", "rrp", "list_price", "compare_at_price") if k in obj and number(obj[k]) is not None), None)
        url = next((str(obj[k]) for k in ("url", "product_url", "href", "link") if isinstance(obj.get(k), str) and obj[k].startswith("http")), "")
        discount = round((old-price)/old*100) if old and old > price else 0
        rows.append({"store":store,"id":pid,"name":name[:240],"price":round(price,2),"was_price":round(old,2) if old else None,"discount_percent":discount,"url":url})
    # de-duplicate by product id; prefer first useful record
    unique = {}
    for row in rows: unique.setdefault(row["id"], row)
    return list(unique.values())

def main():
    previous = {}
    if OUT.exists():
        try:
            previous = {f'{x.get("store")}::{x.get("id")}': x for x in json.loads(OUT.read_text()).get("products", [])}
        except Exception: pass
    products, status = [], {}
    for store, commands in STORES.items():
        collected, errors = [], []
        for cmd in commands:
            try:
                result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=90)
                if result.returncode != 0:
                    errors.append((result.stderr or f"exit {result.returncode}")[-500:])
                    continue
                try: payload = json.loads(result.stdout)
                except Exception:
                    errors.append("CLI output was not JSON")
                    continue
                collected.extend(normalize(store, payload))
            except Exception as exc:
                errors.append(str(exc)[:300])
        # keep the latest current price and compare against prior published snapshot
        seen = set()
        for p in collected:
            key = f'{store}::{p["id"]}'
            if key in seen: continue
            seen.add(key)
            old = previous.get(key)
            if p["discount_percent"] == 0 and old:
                prev_price = number(old.get("price"))
                if prev_price and prev_price > p["price"]:
                    p["previous_price"] = round(prev_price, 2)
                    p["discount_percent"] = round((prev_price-p["price"])/prev_price*100)
                    p["deal_type"] = "price_drop"
            elif p["discount_percent"] > 0:
                p["deal_type"] = "sale"
            else:
                p["deal_type"] = "catalogue"
            products.append(p)
        status[store] = {"products_found":len(collected),"ok":bool(collected),"message":("Feed returned product data" if collected else ("; ".join(errors[-2:]) or "No matching products returned"))}
    # Don't publish an empty/broken scan over the last good dataset.
    if not products and OUT.exists():
        print("All feeds returned no usable product records; preserving previous data.", file=sys.stderr)
        sys.exit(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),"products":products,"stores":status}, ensure_ascii=False, indent=2)+"\n")
    print(f"Published {len(products)} product records.")
    for store, state in status.items(): print(f'{store}: {state["products_found"]} products — {state["message"]}')

if __name__ == "__main__": main()
