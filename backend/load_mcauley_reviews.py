import argparse
import os
from typing import Optional, List

from datasets import load_dataset


def download_amazon_reviews(
    output_dir: str,
    categories: Optional[List[str]] = None,
    split: str = "train",
    only_five_star: bool = False,
    streaming: bool = True,
    limit: Optional[int] = None,
) -> None:
    """
    Load local McAuley-Lab/Amazon-Reviews-2023 Parquet file directly (no remote code)
    and write JSONL under output_dir. Always uses data/full-00000-of-00002.parquet
    located under the provided output_dir.

    Notes:
    - Parquet loading via the "parquet" builder does not execute remote code.
    - only_five_star filter applies only when a numeric 'rating' field exists.
    - 'split' is kept for compatibility; parquet builder uses a single split.
    """

    os.makedirs(output_dir, exist_ok=True)

    def export_iterable_to_jsonl(ds_iter, target_path: str, limit_items: Optional[int]):
        import json

        count = 0
        with open(target_path, "w", encoding="utf-8") as f:
            for example in ds_iter:
                if only_five_star:
                    try:
                        if float(example.get("rating", 0)) != 5.0:
                            continue
                    except Exception:
                        # If no numeric rating, skip rating filter
                        pass
                f.write(json.dumps(example, ensure_ascii=False) + "\n")
                count += 1
                if limit_items is not None and count >= limit_items:
                    break

    # Always read from local parquet under output_dir
    local_parquet = os.path.join(output_dir, "full-00000-of-00002.parquet")
    if not os.path.exists(local_parquet):
        # Nothing to do; create an empty export file to signal absence
        target = os.path.join(output_dir, "amazon_reviews_2023.parquet_export.jsonl")
        open(target, "w", encoding="utf-8").close()
        return

    # Load parquet locally. For local files, prefer non-streaming to ensure iteration works.
    dataset_iterable = load_dataset(
        "parquet",
        data_files=[local_parquet],
        split="train",
        streaming=False,
    )

    target = os.path.join(output_dir, "amazon_reviews_2023.parquet_export.jsonl")
    export_iterable_to_jsonl(dataset_iterable, target, limit)


def main():
    parser = argparse.ArgumentParser(description="Download Amazon-Reviews-2023 dataset to data/")
    parser.add_argument(
        "--output-dir",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")),
        help="Directory to write JSONL files (default: project data/)",
    )
    parser.add_argument(
        "--categories",
        nargs="*",
        default=None,
        help="Optional list of category names (as in dataset card) to download individually.",
    )
    parser.add_argument(
        "--split",
        default="train",
        help="Dataset split to load (default: train)",
    )
    parser.add_argument(
        "--five-star-only",
        action="store_true",
        help="If set, keep only reviews with rating == 5.0",
    )
    parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="Disable streaming mode (may require large disk/memory)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of records per category/file (for sampling)",
    )

    args = parser.parse_args()

    download_amazon_reviews(
        output_dir=args.output_dir,
        categories=args.categories,
        split=args.split,
        only_five_star=args.five_star_only,
        streaming=not args.no_streaming,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()


