import requests
from bs4 import BeautifulSoup
import re
import os
from difflib import get_close_matches, SequenceMatcher

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_all_category_names():
    filenames = os.listdir("Data/json")
    category_names = [os.path.splitext(f)[0].lower() for f in filenames if f.endswith(".json")]
    return category_names


def extract_query_category(query, category_names, threshold=0.8):
    query_tokens = query.lower().split()
    for token in query_tokens:
        matches = get_close_matches(token, category_names, n=1, cutoff=threshold)
        if matches:
            return matches[0]
    return None


def extract_metadata_from_title(title, category_names, threshold=0.8):
    metadata = {
        "type": "Unknown",
        "brand": "Unknown"
    }

    if not isinstance(title, str):
        return metadata

    for word in title.lower().split():
        match = get_close_matches(word, category_names, n=1, cutoff=threshold)
        if match:
            metadata["type"] = match[0].capitalize()
            break
        
    words = title.split()
    metadata["brand"] = words[0] if words else "Unknown"

    return metadata


def results_contain_category(products, target_category, category_names):
    target_category = target_category.lower()
    for p in products:
        metadata = extract_metadata_from_title(p.get("title", ""), category_names)
        product_type = metadata.get("type", "").lower()
        if get_close_matches(product_type, [target_category], cutoff=0.8):
            return True
    return False

def construct_query_variants(query, target_category):
    base = target_category.replace("-", " ") if target_category else ""
    tokens = query.lower().split()

    # Remove generic filler words
    filter_words = {"best", "cheap", "top", "support", "buy", "with", "for"}
    tokens = [word for word in tokens if word not in filter_words]

    # Prioritize the category and keep relevant modifiers
    useful_modifiers = [token for token in tokens if token != target_category]
    core_query = f"{base} {' '.join(useful_modifiers)}".strip()
    
    # Variants: exact, reordered, fallback
    return [core_query, query, base]


def scrape_microcenter_listing(search_query, max_attempts=5):
    category_names = get_all_category_names()
    print('[DEBUG] Categories:',category_names)
    target_category = extract_query_category(search_query, category_names)
    print("[DEBUG] Target:",target_category)

    tried_queries = set()
    attempts = 0

    def make_url(q):
        return f"https://www.microcenter.com/search/search_results.aspx?N=&cat=&Ntt={q.replace(' ', '+')}&searchButton=search"

    search_terms = construct_query_variants(search_query, target_category)

    for query in search_terms:
        print("[DEBUG] Query:",query)
        if query in tried_queries or attempts >= max_attempts:
            break
        tried_queries.add(query)

        url = make_url(query)
        print(f"[DEBUG] Fetching: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select(".detail_wrapper")
        print(f"[DEBUG] Found {len(items)} product items")

        results = []

        for idx, item in enumerate(items):
            try:
                title_tag = item.select_one("div.h2 a")
                title = title_tag.text.strip() if title_tag else "N/A"
                product_url = "https://www.microcenter.com" + title_tag['href'] if title_tag else "N/A"

                price_block = item.find_next("div", class_="pricing")
                price_text = " ".join(price_block.stripped_strings) if price_block else ""
                price = re.search(r"Our price \$[\d,]+\.\d{2}", price_text)
                price = price.group(0).replace("Our price ", "") if price else "N/A"

                features = item.select("ul.features li")
                features_text = "; ".join(f.text.strip() for f in features)

                metadata = extract_metadata_from_title(title, category_names)
                # Only keep the product if it matches the target category or if no category was extracted
                product_type = metadata.get("type", "").lower()
                if not target_category or target_category in product_type or product_type in target_category:
                    product = {
                        "title": title,
                        "url": product_url,
                        "price": price,
                        "rating": "N/A",
                        "review_count": "N/A",
                        "shipping_info": "Check website",
                        "features": features_text,
                        "metadata": metadata
                    }
                    print("[Added]",product["title"], product["metadata"])
                    results.append(product)
                else:
                    print("[Skipped]",idx)
                
            except Exception as e:
                print(f"[WARNING] Failed to parse product at index {idx}: {e}")
                continue

        if not target_category or SequenceMatcher(None, product_type, target_category).ratio() > 0.8:
            return results

        print(f"[INFO] Output didn’t match product category, retrying... ({attempts+1})")
        attempts += 1

    print("[WARN] No relevant results found after retries.")
    return []


def clean_text(text):
    try:
        if not isinstance(text, str):
            return ""

        lines = text.strip().splitlines()
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if any(bad in line.lower() for bad in ["n/a", "unknown", "check website"]):
                continue
            line = re.sub(r'\s+', ' ', line)
            if line:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    except Exception as e:
        print(f"[WARNING] clean_text failed: {e}")
        return ""


def process_product(product):
    try:
        if not isinstance(product, dict):
            raise ValueError("Product must be a dictionary.")

        title = clean_text(product.get("title", ""))
        price = clean_text(product.get("price", ""))
        rating = clean_text(product.get("rating", ""))
        reviews = clean_text(product.get("review_count", ""))
        features = clean_text(product.get("features", ""))
        metadata = product.get("metadata", {})

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

        processed_texts = [process_product(p) for p in raw_results]
        full_text = "\n\n".join(processed_texts)
        # print(full_text)
        return full_text

    except Exception as e:
        print(f"[ERROR] text_data failed for search '{search}': {e}")
        return ""
