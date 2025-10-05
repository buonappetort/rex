import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, request, jsonify
from flask_cors import CORS

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "rex.json"
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
CORS(app)


def load_rex() -> List[Dict[str, Any]]:
    if not DATA_PATH.exists():
        DATA_PATH.write_text("[]", encoding="utf-8")
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # If corrupted, back up and reset
        backup_path = DATA_PATH.with_suffix(".bak")
        backup_path.write_text(DATA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        DATA_PATH.write_text("[]", encoding="utf-8")
        return []


def save_rex(items: List[Dict[str, Any]]) -> None:
    DATA_PATH.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def validate_rex_payload(payload: Dict[str, Any]) -> Optional[str]:
    required = ["userId", "title", "category"]
    for key in required:
        if not payload.get(key):
            return f"Missing required field: {key}"
    return None


# --- Amazon helpers ---

def _is_amazon_url(url: str) -> bool:
    url_l = (url or "").lower()
    return any(host in url_l for host in ["amazon.com"])


def _fetch_amazon_meta(url: str) -> Dict[str, Any]:
    try:
        import requests  # type: ignore
        from bs4 import BeautifulSoup  # type: ignore
        import json as _json  # reuse json name safely inside function
    except Exception:
        return {}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.amazon.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        if resp.status_code != 200:
            return {}
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        def get_meta(prop_names: List[str]) -> Optional[str]:
            for p in prop_names:
                tag = soup.find("meta", attrs={"property": p}) or soup.find("meta", attrs={"name": p})
                if tag and tag.get("content"):
                    return tag.get("content")
            return None

        # Prefer explicit product selectors when meta tags are generic
        title_text = None
        title_el = soup.select_one("#productTitle") or soup.select_one("#title #productTitle")
        if title_el and title_el.get_text(strip=True):
            title_text = title_el.get_text(strip=True)

        title = get_meta(["og:title", "twitter:title"]) or title_text or (soup.title.string.strip() if soup.title and soup.title.string else None)
        description = get_meta(["og:description", "twitter:description"]) or None
        image = get_meta(["og:image:secure_url", "og:image", "twitter:image", "twitter:image:src"]) or None

        # Fallback: try landing image attributes used by Amazon
        if not image:
            landing_img = soup.select_one("#landingImage") or soup.select_one("#imgTagWrapperId img")
            if landing_img:
                # data-old-hires sometimes contains a direct URL
                image = landing_img.get("data-old-hires") or image
                if not image:
                    dyn = landing_img.get("data-a-dynamic-image")
                    if dyn:
                        try:
                            # data-a-dynamic-image is a JSON map of url -> [w,h]
                            data = _json.loads(dyn)
                            if isinstance(data, dict) and data:
                                # choose the first key (usually the largest image first)
                                image = next(iter(data.keys()))
                        except Exception:
                            pass
                # last resort, src
                if not image:
                    image = landing_img.get("src")

        result: Dict[str, Any] = {}
        if title:
            result["title"] = title
        if description:
            result["description"] = description
        if image:
            result["image"] = image
        return result
    except Exception:
        return {}


def generate_seed_rex(user_id: str) -> List[Dict[str, Any]]:
    now = datetime.utcnow().isoformat() + "Z"
    templates = [
        {"title": "Best Sushi in Town", "category": "Restaurant", "description": "Fresh nigiri and creative rolls.", "tags": ["sushi", "japanese", "dinner"]},
        {"title": "Morning Coffee Spot", "category": "Restaurant", "description": "Fantastic espresso and pastries.", "tags": ["coffee", "breakfast"]},
        {"title": "Hydrating Face Serum", "category": "Beauty", "description": "Lightweight, absorbs quickly.", "tags": ["skincare", "serum"]},
        {"title": "Everyday Moisturizer", "category": "Beauty", "description": "Non-greasy, great under makeup.", "tags": ["moisturizer"]},
        {"title": "Classic White Sneakers", "category": "Clothing", "description": "Comfortable and versatile.", "tags": ["shoes", "casual"]},
        {"title": "Rain Jacket", "category": "Clothing", "description": "Waterproof and breathable.", "tags": ["outerwear", "travel"]},
        {"title": "Noise-Canceling Headphones", "category": "Electronics", "description": "Great sound and ANC.", "tags": ["audio", "work"]},
        {"title": "Portable Charger", "category": "Electronics", "description": "Fast charging on the go.", "tags": ["battery", "travel"]},
        {"title": "Cookbook: Weeknight Meals", "category": "Books", "description": "Simple, tasty recipes.", "tags": ["cooking", "easy"]},
        {"title": "Yoga Mat", "category": "Fitness", "description": "Non-slip, easy to clean.", "tags": ["yoga", "home-gym"]},
    ]
    seed_items: List[Dict[str, Any]] = []
    for tpl in templates:
        seed_items.append({
            "id": str(uuid.uuid4()),
            "userId": user_id,
            "title": tpl["title"],
            "category": tpl["category"],
            "description": tpl.get("description", ""),
            "mediaUrl": "",
            "tags": tpl.get("tags", []),
            "createdAt": now,
        })
    return seed_items


@app.post("/api/load-mcauley-data")
def load_mcauley_data() -> Any:
    """Download a small batch from McAuley Amazon Reviews and convert to rex.json shape.

    Request JSON (optional):
    {
      "categories": ["Books", ...],   # optional list; defaults to all
      "limit": 200,                    # optional per-file cap
      "fiveStarOnly": true             # default true
    }
    """

    body = request.get_json(silent=True) or {}
    categories = body.get("categories")
    try:
        limit = int(body.get("limit")) if body.get("limit") is not None else 200
    except Exception:
        limit = 200
    five_star_only = bool(body.get("fiveStarOnly", True))

    # Import locally to avoid hard dependency on startup if not needed
    try:
        from .load_mcauley_reviews import download_amazon_reviews  # type: ignore
    except Exception:
        # Fallback to repo path import when running without package context
        from backend.load_mcauley_reviews import download_amazon_reviews  # type: ignore

    output_dir = str(DATA_PATH.parent)
    # Trigger download (streaming) into data/
    download_amazon_reviews(
        output_dir=output_dir,
        categories=categories,
        split="train",
        only_five_star=five_star_only,
        streaming=True,
        limit=limit,
    )

    # Determine which files to read
    data_dir = Path(output_dir)
    candidates: List[Path] = []
    unified = data_dir / "amazon_reviews_2023.jsonl"
    parquet_export = data_dir / "amazon_reviews_2023.parquet_export.jsonl"
    if unified.exists():
        candidates.append(unified)
    if parquet_export.exists():
        candidates.append(parquet_export)
    if not candidates:
        for p in sorted(data_dir.glob("amazon_reviews_2023_*.jsonl")):
            candidates.append(p)

    if not candidates:
        return jsonify({"error": "No downloaded review files found"}), 500

    def pick_image_from_review(img_entry: Any) -> Optional[str]:
        if not img_entry:
            return None
        # Try common key variants
        for key in [
            "large_image_url",
            "medium_image_url",
            "small_image_url",
            "large",
            "medium",
            "small",
            "url",
        ]:
            val = img_entry.get(key) if isinstance(img_entry, dict) else None
            if isinstance(val, str) and val:
                return val
        return None

    def build_amazon_url(example: Dict[str, Any]) -> Optional[str]:
        asin = example.get("asin") or example.get("parent_asin")
        if isinstance(asin, str) and asin:
            return f"https://www.amazon.com/dp/{asin}"
        return None

    # Map into rex items
    now_iso = datetime.utcnow().isoformat() + "Z"
    new_items: List[Dict[str, Any]] = []

    for path in candidates:
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        ex = json.loads(line)
                    except Exception:
                        continue

                    user_id = str(ex.get("user_id") or "amazon-user")
                    title = (ex.get("title") or "").strip() or "Amazon Review"
                    description = (ex.get("text") or "").strip()
                    category = "Amazon"
                    amazon_url = build_amazon_url(ex)

                    image_url: Optional[str] = None
                    images = ex.get("images")
                    if isinstance(images, list) and images:
                        # pick the first usable image URL
                        for img in images:
                            image_url = pick_image_from_review(img)
                            if image_url:
                                break

                    item: Dict[str, Any] = {
                        "id": str(uuid.uuid4()),
                        "userId": user_id,
                        "title": title,
                        "category": category,
                        "description": description,
                        "mediaUrl": amazon_url or "",
                        "tags": [],
                        "createdAt": now_iso,
                    }

                    if amazon_url:
                        item["amazonUrl"] = amazon_url
                    if image_url:
                        item["amazonMeta"] = {"image": image_url}

                    new_items.append(item)
        except Exception:
            continue

    if not new_items:
        return jsonify({"error": "No items parsed from downloaded reviews"}), 500

    # Append to existing rex
    items = load_rex()
    items.extend(new_items)
    save_rex(items)

    return jsonify({
        "added": len(new_items),
        "total": len(items),
        "files": [str(p.name) for p in candidates],
    }), 201

@app.get("/api/health")
def health() -> Any:
    return {"status": "ok"}


@app.post("/api/rex")
def create_rex() -> Any:
    payload = request.get_json(silent=True) or {}
    error = validate_rex_payload(payload)
    if error:
        return jsonify({"error": error}), 400

    items = load_rex()
    new_item: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "userId": payload["userId"],
        "title": payload["title"],
        "category": payload.get("category", ""),
        "description": payload.get("description", ""),
        "mediaUrl": payload.get("mediaUrl", ""),
        "tags": payload.get("tags", []),
        "createdAt": datetime.utcnow().isoformat() + "Z",
    }

    # If mediaUrl is an Amazon URL, fetch metadata and store it
    media_url = new_item.get("mediaUrl") or ""
    if media_url and _is_amazon_url(media_url):
        meta = _fetch_amazon_meta(media_url)
        if meta:
            new_item["amazonUrl"] = media_url
            new_item["amazonMeta"] = meta
            # Backfill title/description if missing
            if not new_item.get("title") and meta.get("title"):
                new_item["title"] = meta["title"]
            if not new_item.get("description") and meta.get("description"):
                new_item["description"] = meta["description"]

    items.append(new_item)
    save_rex(items)
    return jsonify(new_item), 201


@app.post("/api/seed-user")
def seed_user() -> Any:
    body = request.get_json(silent=True) or {}
    user_id = (body.get("userId") or "").strip()
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    items = load_rex()
    # If user already has items, we still add seed data per request, but avoid duplicating exact titles
    existing_titles = { (i.get("userId"), i.get("title")) for i in items }
    new_items = []
    for seed in generate_seed_rex(user_id):
        key = (seed["userId"], seed["title"])
        if key in existing_titles:
            continue
        new_items.append(seed)

    items.extend(new_items)
    save_rex(items)
    return jsonify({"userId": user_id, "seeded": len(new_items)}), 201


@app.get("/api/rex/<item_id>")
def get_rex(item_id: str) -> Any:
    items = load_rex()
    for item in items:
        if item["id"] == item_id:
            return jsonify(item)
    return jsonify({"error": "Not found"}), 404


@app.get("/api/rex")
def list_rex() -> Any:
    user_id = request.args.get("userId")
    order = (request.args.get("order") or "").lower() or "asc"
    page_str = request.args.get("page") or ""
    limit_str = request.args.get("limit") or ""

    try:
        page = int(page_str) if page_str else None
    except ValueError:
        page = None
    try:
        limit = int(limit_str) if limit_str else None
    except ValueError:
        limit = None

    items = load_rex()
    if user_id:
        items = [i for i in items if i.get("userId") == user_id]

    # Sorting by createdAt if present
    def parse_dt(s: Optional[str]) -> float:
        if not s:
            return 0.0
        try:
            # Example: 2025-10-05T18:33:11.847191Z
            return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0

    items.sort(key=lambda x: parse_dt(x.get("createdAt")), reverse=(order == "desc"))

    total = len(items)
    if page and limit:
        start = (page - 1) * limit
        end = start + limit
        page_items = items[start:end]
        return jsonify({
            "items": page_items,
            "page": page,
            "limit": limit,
            "total": total,
            "hasMore": end < total,
        })

    return jsonify(items)


@app.post("/api/search")
def search_rex() -> Any:
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    user_id = body.get("userId")
    items = load_rex()

    # Optional: filter by user first
    if user_id:
        items = [i for i in items if i.get("userId") == user_id]

    # Optional LangChain integration
    use_llm = bool(os.getenv("OPENAI_API_KEY")) and body.get("useLLM", True)
    keywords: List[str] = []

    if use_llm and query:
        try:
            # Lazy import to avoid dependency when not needed
            from langchain_openai import ChatOpenAI  # type: ignore
            from langchain.prompts import ChatPromptTemplate  # type: ignore

            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            llm = ChatOpenAI(model=model_name, temperature=0.0)
            prompt = ChatPromptTemplate.from_template(
                """
                Extract up to 5 short search keywords from the user's question for product recommendations.
                Return as a comma-separated list only. If none, return an empty line.

                Question: {question}
                """.strip()
            )
            formatted = prompt.format_messages(question=query)
            resp = llm.invoke(formatted)
            text = (getattr(resp, "content", "") or "").strip()
            if text:
                keywords = [t.strip().lower() for t in text.split(",") if t.strip()]
        except Exception:
            keywords = []

    # Fallback: simple keyword split
    if not keywords:
        keywords = [t.lower() for t in query.split() if t]

    # Document text: Builds one lowercase string per item from title + description + category + tags.
    # Match rule: An item matches only if all keywords appear as substring matches in that combined text (logical AND).
    # Empty query: If there are no keywords, it returns all items.
    def item_matches(item: Dict[str, Any]) -> bool:
        haystack = " ".join([
            item.get("title", ""),
            item.get("description", ""),
            item.get("category", ""),
            " ".join(item.get("tags", [])),
        ]).lower()
        return all(k in haystack for k in keywords)

    results = [i for i in items if item_matches(i)] if keywords else items
    return jsonify({
        "query": query,
        "keywords": keywords,
        "results": results,
    })


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
