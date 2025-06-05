import requests
from bs4 import BeautifulSoup
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def scrape_microcenter_listing(search_query):
    query = search_query.replace(" ", "+")
    url = f"https://www.microcenter.com/search/search_results.aspx?N=&cat=&Ntt={query}&searchButton=search"
    print(f"[DEBUG] Fetching: {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    items = soup.select(".detail_wrapper")
    print(f"[DEBUG] Found {len(items)} product items")

    results = []

    for idx, item in enumerate(items):
        try:
            # --- Title & URL ---
            title_tag = item.select_one("div.h2 a")
            title = title_tag.text.strip() if title_tag else "N/A"
            url = "https://www.microcenter.com" + title_tag['href'] if title_tag else "N/A"

            # --- Price block ---
            price_block = item.find_next("div", class_="pricing")
            if price_block:
                price_text = " ".join(price_block.stripped_strings)
                price = re.search(r"Our price \$[\d,]+\.\d{2}", price_text)
                price = price.group(0).replace("Our price ", "") if price else "N/A"
            else:
                price = "N/A"

            # --- Features ---
            features = item.select("ul.features li")
            features_text = "; ".join(f.text.strip() for f in features)

            # --- Rating (not available in snippet) ---
            rating = "N/A"
            review_count = "N/A"

            product = {
                "title": title,
                "url": url,
                "price": price,
                "rating": rating,
                "review_count": review_count,
                "shipping_info": "Check website",
                "features": features_text,
            }

            results.append(product)

        except Exception as e:
            print(f"[WARNING] Failed to parse product at index {idx}: {e}")
            continue

    return results


# --- Utilities ---

import re

def clean_text(text):
    try:
        if not isinstance(text, str):
            return ""

        # Split into lines to filter bad ones
        lines = text.strip().splitlines()

        cleaned_lines = []
        for line in lines:
            line = line.strip()

            # Remove lines with junk values
            if any(bad in line.lower() for bad in ["n/a", "unknown", "check website"]):
                continue

            # Collapse internal whitespace (e.g., multiple spaces)
            line = re.sub(r'\s+', ' ', line)

            if line:  # Don't keep empty lines
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    except Exception as e:
        print(f"[WARNING] clean_text failed: {e}")
        return ""


def extract_metadata_from_title(title):
    metadata = {
        "type": "Unknown",
        "brand": "Unknown"
    }

    try:
        if not isinstance(title, str):
            return metadata

        title_lower = title.lower()
        if "rtx" in title_lower or "geforce" in title_lower:
            metadata["type"] = "GPU"
        elif any(x in title_lower for x in ["motherboard", "b650", "b660", "x670"]):
            metadata["type"] = "Motherboard"
        elif any(x in title_lower for x in ["cpu", "ryzen", "intel", "i5", "i7", "i9"]):
            metadata["type"] = "Processor"

        words = title.split()
        metadata["brand"] = words[0] if words else "Unknown"

    except Exception as e:
        print(f"[WARNING] Failed to extract metadata from title '{title}': {e}")

    return metadata

def process_product(product):
    try:
        if not isinstance(product, dict):
            raise ValueError("Product must be a dictionary.")

        title = clean_text(product.get("title", ""))
        price = clean_text(product.get("price", ""))
        rating = clean_text(product.get("rating", ""))
        reviews = clean_text(product.get("review_count", ""))
        features = clean_text(product.get("features", ""))

        metadata = extract_metadata_from_title(title)

        content = f"""
        Product Title: {title}
        Price: {price}
        Rating: {rating} ({reviews} reviews)
        Features: {features}
        Type: {metadata.get('type', 'Unknown')}
        Brand: {metadata.get('brand', 'Unknown')}
        """.strip()

        return clean_text(content)

    except Exception as e:
        print(f"[ERROR] Failed to process product: {e}")
        return ""


def text_data(search):
    try:
        raw_results = scrape_microcenter_listing(search)
        if not raw_results:
            print(f"[INFO] No products found for: '{search}'")
            return ""

        # Process each product into a string, then join all with newlines
        processed_texts = [process_product(p) for p in raw_results]
        full_text = "\n\n".join(processed_texts)
        print(full_text)
        return full_text

    except Exception as e:
        print(f"[ERROR] text_data failed for search '{search}': {e}")
        return ""


# --- Main Execution ---
'''
results = scrape_microcenter_listing("RTX 4070")
if results:
    product = process_product(results[0])
    print(product)
else:
    print("No results to process.")'''
