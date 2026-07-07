#!/usr/bin/env python3
"""Phase 2 — 전처리 + 정보량 계층화.

4개 소스 CSV를 통합·정제하고, 리뷰를 '정보량'으로 계층화한다.
핵심 판단(수집 데이터 관찰 기반):
  - 유도 문구는 소수(<300건)이고 대부분 '쿠폰 기능 칭찬'이라 대가성 리뷰 신호로 약함.
  - 진짜 노이즈는 '초저정보 리뷰'(5점+극단적 짧은 극찬)로, 예약 후 리뷰 프롬프트 유입 추정.
  → 초저정보 리뷰는 별점 통계엔 남기되 측면/토픽 분석 대상에서 제외(analyzable=False).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "CSV 데이터"
OUT = CSV_DIR / "reviews_unified.csv"

SOURCES = [
    ("reviews_michael_ios.csv", "michael", "ios"),
    ("reviews_michael_aos.csv", "michael", "android"),
    ("reviews_cardoc_ios.csv", "cardoc", "ios"),
    ("reviews_cardoc_aos.csv", "cardoc", "android"),
]

# 정보 없는 일반 극찬 사전 (이것만으로 이뤄진 리뷰 = 초저정보)
GENERIC_ONLY = re.compile(
    r"^[\s]*("
    r"좋아요|좋아용|좋음|좋네요|좋습니다|굿|good|굳|짱|최고|만족|만족합니다|"
    r"편해요|편하네요|편함|편리|감사|감사합니다|추천|사용중|잘써요|잘쓰고있어요|ㅎㅎ|ㅋㅋ|♡|❤|👍|"
    r"별로|별루|글쎄|음|ㅡㅡ|없음|괜찮아요|나쁘지않아요"
    r")[\s\.!~^ㅎㅋㅠㅜ0-9]*$"
)
COUPON = re.compile(r"쿠폰|포인트|적립|이벤트|리뷰\s?쓰|별점|사은품|기프티콘|할인")
# 한글이 거의 없는(외국어/이모지/숫자만) 리뷰 감지
HANGUL = re.compile(r"[가-힣]")


def load() -> pd.DataFrame:
    frames = []
    for fname, app, platform in SOURCES:
        p = CSV_DIR / fname
        if not p.exists():
            print(f"[skip] {fname} 없음")
            continue
        df = pd.read_csv(p)
        df["app"] = app
        df["platform"] = platform
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    df = load()
    n0 = len(df)

    # 기본 정제
    df["body"] = df["body"].fillna("").astype(str).str.strip()
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    # iOS(오프셋 포함)와 Android(naive)가 섞여 있어 format="mixed"로 파싱해야 NaT가 안 생긴다.
    df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed", utc=True).dt.tz_localize(None)
    df = df.dropna(subset=["rating"])
    df["rating"] = df["rating"].astype(int)

    # 중복 제거: review_id는 소스 내 유니크 보장 → 이것만으로 안전하게 제거.
    # username+body+rating 제거는 "좋아요/5점"을 쓴 서로 다른 실제 유저를 뭉개므로 하지 않는다.
    # 대신 페이지네이션 재수집 등으로 완전 동일 (review_id 없이) 반복된 경우만 플래그.
    df = df.drop_duplicates(subset=["app", "platform", "review_id"])
    df["exact_repeat"] = df.duplicated(subset=["app", "platform", "username", "body", "rating"], keep=False)

    # 파생 변수
    df["body_len"] = df["body"].str.len()
    df["token_est"] = df["body"].str.split().str.len()
    df["has_coupon_mention"] = df["body"].str.contains(COUPON)
    df["no_hangul"] = ~df["body"].str.contains(HANGUL)
    df["is_generic_only"] = df["body"].str.match(GENERIC_ONLY)

    # 초저정보 판정: 본문 없음 / 아주 짧고 일반 극찬만 / 한글 없음(이모지·기호·숫자만)
    df["low_info"] = (
        (df["body_len"] == 0)
        | (df["is_generic_only"])
        | ((df["body_len"] <= 4) & (df["token_est"] <= 1))
        | (df["no_hangul"] & (df["body_len"] <= 8))
    )
    # 측면/토픽 분석 대상: 정보 있는 리뷰
    df["analyzable"] = ~df["low_info"]

    # 시간 파생
    df["year"] = df["date"].dt.year
    df["ym"] = df["date"].dt.to_period("M").astype(str)

    cols = [
        "app", "platform", "review_id", "rating", "body", "date", "year", "ym",
        "version", "username", "body_len", "token_est",
        "has_coupon_mention", "is_generic_only", "no_hangul", "low_info", "analyzable", "exact_repeat",
    ]
    df = df[cols].sort_values(["app", "platform", "date"])
    df.to_csv(OUT, index=False, encoding="utf-8-sig")

    # 리포트
    print(f"입력 {n0} → 정제 후 {len(df)} (중복/무별점 제거 {n0 - len(df)})")
    print("\n[소스별 건수 / analyzable 비율]")
    g = df.groupby(["app", "platform"]).agg(
        n=("rating", "size"),
        analyzable=("analyzable", "sum"),
        mean_star=("rating", "mean"),
        low_info_pct=("low_info", "mean"),
    )
    g["analyzable_pct"] = (g["analyzable"] / g["n"] * 100).round(1)
    g["mean_star"] = g["mean_star"].round(2)
    g["low_info_pct"] = (g["low_info_pct"] * 100).round(1)
    print(g.to_string())
    print(f"\n전체 analyzable: {df['analyzable'].sum()} / {len(df)} ({df['analyzable'].mean()*100:.1f}%)")
    print(f"쿠폰/할인 언급: {df['has_coupon_mention'].sum()}건")
    print(f"저장: {OUT}")


if __name__ == "__main__":
    main()
