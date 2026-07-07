#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pandas",
#     "app-store-scraper",
#     "google-play-scraper",
# ]
# ///

# How to run
# 1. From the project root, create/use the local venv:
#      python3 -m venv .venv
# 2. Install the requested packages:
#      .venv/bin/python -m pip install pandas app-store-scraper google-play-scraper
# 3. Run:
#      .venv/bin/python 스크립트/collect_reviews.py

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
from google_play_scraper import Sort, reviews, reviews_all, search

try:
    from app_store_scraper import AppStore
except ModuleNotFoundError:
    AppStore = None


type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

ROOT_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT_DIR / "CSV 데이터"
COMMON_COLUMNS = ["review_id", "app", "platform", "rating", "title", "body", "date", "version", "username"]
IOS_RSS_PAGES = range(1, 11)
ANDROID_SLEEP_MS, ANDROID_BATCH_SIZE = 1200, 4500
RETRY_ATTEMPTS, RETRY_SLEEP_SECONDS = 4, 3.0

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class IosSource:
    app: str; app_name: str; app_id: str; country: str; output_name: str


@dataclass(frozen=True, slots=True)
class AndroidSource:
    app: str; package_name: str; output_name: str


def retry(label: str, operation: Callable[[], T]) -> T:
    last_error: BaseException | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return operation()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt == RETRY_ATTEMPTS:
                break
            wait_seconds = RETRY_SLEEP_SECONDS * attempt
            print(f"{label}: retry {attempt}/{RETRY_ATTEMPTS} after {type(exc).__name__}; sleeping {wait_seconds:.1f}s")
            time.sleep(wait_seconds)
    raise RuntimeError(f"{label}: failed after {RETRY_ATTEMPTS} attempts") from last_error


def text_value(value: JsonValue | datetime) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ""
    return str(value)


def int_value(value: JsonValue | datetime) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def rss_label(entry: dict[str, JsonValue], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, dict):
        return ""
    label = value.get("label")
    return text_value(label)


def rss_author(entry: dict[str, JsonValue]) -> str:
    author = entry.get("author")
    if not isinstance(author, dict):
        return ""
    name = author.get("name")
    return text_value(name.get("label")) if isinstance(name, dict) else rss_label(entry, "author")


def fetch_json(url: str) -> dict[str, JsonValue]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 review-collector/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return parsed


def collect_ios_with_scraper(source: IosSource) -> list[dict[str, JsonValue]]:
    if AppStore is None:
        return []
    app = AppStore(country=source.country, app_name=source.app_name, app_id=source.app_id)
    app.review(how_many=100_000)
    rows: list[dict[str, JsonValue]] = []
    for review in app.reviews:
        rows.append(
            {
                "review_id": text_value(review.get("review_id") or review.get("id")),
                "app": source.app,
                "platform": "ios",
                "rating": int_value(review.get("rating")),
                "title": text_value(review.get("title")),
                "body": text_value(review.get("review")),
                "date": text_value(review.get("date")),
                "version": text_value(review.get("version")),
                "username": text_value(review.get("userName")),
            }
        )
    return rows


def collect_ios_with_rss(source: IosSource) -> list[dict[str, JsonValue]]:
    rows: list[dict[str, JsonValue]] = []
    for page in IOS_RSS_PAGES:
        url = f"https://itunes.apple.com/{source.country}/rss/customerreviews/id={source.app_id}/sortBy=mostRecent/page={page}/json"
        data = retry(f"{source.app} iOS RSS page {page}", lambda url=url: fetch_json(url))
        feed = data.get("feed")
        if not isinstance(feed, dict):
            continue
        raw_entries = feed.get("entry", [])
        entries = raw_entries if isinstance(raw_entries, list) else [raw_entries]
        page_rows = []
        for entry in entries:
            if not isinstance(entry, dict) or "im:rating" not in entry:
                continue
            page_rows.append(
                {
                    "review_id": rss_label(entry, "id"),
                    "app": source.app,
                    "platform": "ios",
                    "rating": int_value(rss_label(entry, "im:rating")),
                    "title": rss_label(entry, "title"),
                    "body": rss_label(entry, "content"),
                    "date": rss_label(entry, "updated"),
                    "version": rss_label(entry, "im:version"),
                    "username": rss_author(entry),
                }
            )
        rows.extend(page_rows)
        print(f"{source.app} iOS RSS page {page}: {len(page_rows)} rows")
        time.sleep(0.5)
    return rows


def collect_ios(source: IosSource) -> list[dict[str, JsonValue]]:
    try:
        scraper_rows = retry(f"{source.app} iOS app_store_scraper", lambda: collect_ios_with_scraper(source))
        if scraper_rows:
            return scraper_rows
    except RuntimeError as exc:
        print(f"{source.app} iOS: app_store_scraper failed ({exc}); using iTunes RSS")
    except Exception as exc:  # noqa: BLE001 - third-party scraper boundary must fall back to RSS
        print(f"{source.app} iOS: app_store_scraper raised {type(exc).__name__}; using iTunes RSS")
    print(f"{source.app} iOS: app_store_scraper unavailable/empty; using iTunes RSS pages 1-10")
    return collect_ios_with_rss(source)


def normalize_android_review(source: AndroidSource, review: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        "review_id": text_value(review.get("reviewId")),
        "app": source.app,
        "platform": "android",
        "rating": int_value(review.get("score")),
        "title": "",
        "body": text_value(review.get("content")),
        "date": text_value(review.get("at")),
        "version": text_value(review.get("reviewCreatedVersion")),
        "username": text_value(review.get("userName")),
    }


def collect_android(source: AndroidSource) -> list[dict[str, JsonValue]]:
    raw = retry(
        f"{source.app} Android reviews_all",
        lambda: reviews_all(
            source.package_name,
            lang="ko",
            country="kr",
            sort=Sort.NEWEST,
            sleep_milliseconds=ANDROID_SLEEP_MS,
        ),
    )
    if not raw:
        raw = collect_android_paginated(source)
    return [normalize_android_review(source, review) for review in raw]


def collect_android_paginated(source: AndroidSource) -> list[dict[str, JsonValue]]:
    token = None
    collected: list[dict[str, JsonValue]] = []
    while True:
        batch, token = retry(
            f"{source.app} Android paginated batch",
            lambda token=token: reviews(
                source.package_name,
                lang="ko",
                country="kr",
                sort=Sort.NEWEST,
                count=ANDROID_BATCH_SIZE,
                continuation_token=token,
            ),
        )
        collected.extend(batch)
        print(f"{source.app} Android pagination: +{len(batch)} rows ({len(collected)} total)")
        if not batch or getattr(token, "token", None) is None:
            return collected
        time.sleep(ANDROID_SLEEP_MS / 1000)


def find_cardoc_consumer_app() -> AndroidSource:
    results = retry("Cardoc Android search", lambda: search("카닥", n_hits=30, lang="ko", country="kr"))
    banned = ("사장", "파트너", "partner", "partners", "파트너스")
    candidates = []
    for item in results:
        title = text_value(item.get("title"))
        app_id = text_value(item.get("appId"))
        developer = text_value(item.get("developer"))
        haystack = f"{title} {app_id} {developer}".lower()
        if "카닥" in title and app_id and not any(word in haystack for word in banned):
            candidates.append(item)
    # 소비자용 카닥의 appId가 검색에서 None으로 오는 글리치가 있어, 확인된 패키지로 폴백한다.
    CARDOC_CONSUMER_PACKAGE = "kr.co.cardoc"
    chosen_package = ""
    if candidates:
        chosen = sorted(candidates, key=lambda item: 0 if text_value(item.get("title")) == "카닥" else 1)[0]
        chosen_package = text_value(chosen.get("appId"))
    package_name = chosen_package or CARDOC_CONSUMER_PACKAGE
    print(f"Cardoc Android selected package: {package_name}")
    return AndroidSource(app="Cardoc", package_name=package_name, output_name="reviews_cardoc_aos.csv")


def dedupe_rows(rows: list[dict[str, JsonValue]]) -> list[dict[str, JsonValue]]:
    seen = set()
    deduped = []
    for index, row in enumerate(rows):
        key = text_value(row.get("review_id")) or f"generated-{index}-{text_value(row.get('body'))[:80]}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def save_and_report(rows: list[dict[str, JsonValue]], output_name: str, label: str) -> int:
    rows = dedupe_rows(rows)
    if not rows:
        raise RuntimeError(f"{label}: zero rows after retries/fallbacks")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUT_DIR / output_name
    frame = pd.DataFrame(rows, columns=COMMON_COLUMNS)
    frame.to_csv(output_path, index=False, encoding="utf-8-sig")
    distribution = Counter(frame["rating"].dropna().astype(int).tolist())
    print(f"{label}: {len(frame)} rows -> {output_path}")
    print(f"{label} rating distribution: {dict(sorted(distribution.items()))}")
    return len(frame)


def main() -> None:
    ios_sources = [IosSource("Michael", "michael", "1004325731", "kr", "reviews_michael_ios.csv"), IosSource("Cardoc", "cardoc", "646336721", "kr", "reviews_cardoc_ios.csv")]
    counts: dict[str, int] = {}
    for source in ios_sources:
        counts[source.output_name] = save_and_report(collect_ios(source), source.output_name, f"{source.app} iOS")
    michael_android = AndroidSource("Michael", "com.nbdproject.macarong", "reviews_michael_aos.csv")
    counts[michael_android.output_name] = save_and_report(
        collect_android(michael_android),
        michael_android.output_name,
        "Michael Android",
    )
    cardoc_android = find_cardoc_consumer_app()
    counts[cardoc_android.output_name] = save_and_report(
        collect_android(cardoc_android),
        cardoc_android.output_name,
        "Cardoc Android",
    )
    print("Final counts:")
    for output_name, count in counts.items():
        print(f"- {output_name}: {count}")


if __name__ == "__main__":
    main()
