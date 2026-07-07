#!/usr/bin/env python3
"""제안서용 PNG 차트 3종. dataviz 원칙: 폼 우선, 하이라이트-원 패턴, 얇은 마크, 직접 라벨, 레세시브 그리드."""
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

OUT = Path(__file__).resolve().parents[1] / "분석 이미지 파일"
OUT.mkdir(exist_ok=True)

rcParams["font.family"] = "Apple SD Gothic Neo"
rcParams["axes.unicode_minus"] = False
rcParams["figure.facecolor"] = "white"
rcParams["savefig.facecolor"] = "white"
rcParams["axes.facecolor"] = "white"

INK = "#2b2f36"; MUTED = "#6b7280"; GRID = "#e6e8eb"
HILITE = "#c0443b"        # 문제/타이어
CTX = "#9aa3ad"           # 중립 맥락
MICHAEL = "#2e6e9e"; CARDOC = "#d98a2b"


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=11, length=0)
    ax.title.set_color(INK)


# ── 차트 1: 측면별 관여도 × 만족도 (버블) ──
def chart1():
    # 기준: 마이클 Android analyzable N=19,556 (락). 세부 카운트는 패턴 민감 → 순서·위치 해석용.
    data = [  # (측면, 언급 점유율%, 평균별점, 언급수)
        ("가격/견적", 4.7, 4.51, 913), ("예약/대기", 4.2, 4.33, 823),
        ("엔진오일", 2.2, 3.82, 440), ("알림", 1.2, 3.73, 237),
        ("교체주기 알림", 1.1, 4.35, 212), ("타이어", 1.0, 3.41, 188),
        ("세차", 0.4, 4.41, 86),
    ]
    app_avg = 4.50
    fig, ax = plt.subplots(figsize=(7.6, 4.8), dpi=150)
    ax.axhline(app_avg, ls="--", lw=1.3, color=MUTED, zorder=1)
    ax.text(0.08, app_avg + 0.02, "앱 평균 4.5", color=MUTED, fontsize=10, ha="left", va="bottom")
    # 라벨 위치 커스텀(겹침 방지): (offx, offy, ha)
    label_pos = {
        "가격/견적": (0, 14, "center"), "예약/대기": (0, -22, "center"),
        "엔진오일": (0, 15, "center"), "알림": (0, 15, "center"),
        "교체주기 알림": (0, 15, "center"), "세차": (11, -4, "left"),
        "타이어": (0, -22, "center"),
    }
    for name, x, y, n in data:
        hot = name == "타이어"
        ax.scatter(x, y, s=n * 1.1, color=HILITE if hot else CTX,
                   alpha=0.9 if hot else 0.6, edgecolor="white", linewidth=1.5, zorder=3)
        offx, offy, ha = label_pos[name]
        ax.annotate(name, (x, y), xytext=(offx, offy), textcoords="offset points",
                    ha=ha, fontsize=11.5 if hot else 10.5,
                    color=HILITE if hot else INK, fontweight="bold" if hot else "normal")
    ax.annotate("전 측면 중\n만족도 최저 (3.41)",
                (1.0, 3.41), xytext=(2.4, 3.30), fontsize=10.5, color=HILITE,
                arrowprops=dict(arrowstyle="->", color=HILITE, lw=1.3))
    ax.set_xlim(0, 5.3); ax.set_ylim(3.2, 4.65)
    ax.set_xlabel("리뷰 언급 점유율 (%)  →  관여도", color=MUTED, fontsize=11)
    ax.set_ylabel("평균 별점  →  만족도", color=MUTED, fontsize=11)
    ax.set_title("마이클 서비스 측면별 관여도 × 만족도", fontsize=14, fontweight="bold", pad=12, loc="left")
    ax.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
    style(ax)
    fig.text(0.125, 0.005, "마이클 Android 분석가능 리뷰 19,556건 · 버블 크기=언급 수", color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "차트1_관여도x만족도.png", bbox_inches="tight")
    plt.close(fig)


# ── 차트 2: 마이클 vs 카닥 가격 언급 점유율 ──
def chart2():
    fig, ax = plt.subplots(figsize=(7.0, 3.2), dpi=150)
    labels = ["마이클", "카닥"]; vals = [4.7, 36.5]; colors = [MICHAEL, CARDOC]
    bars = ax.barh(labels, vals, color=colors, height=0.55, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(v + 0.7, b.get_y() + b.get_height() / 2, f"{v}%", va="center",
                fontsize=13, fontweight="bold", color=INK)
    ax.set_xlim(0, 42)
    ax.invert_yaxis()
    ax.set_title("‘가격/견적’ 언급 점유율 — 마이클은 가격경쟁 앱이 아니다", fontsize=13.5,
                 fontweight="bold", pad=12, loc="left")
    ax.set_xlabel("리뷰 언급 점유율 (%)", color=MUTED, fontsize=11)
    ax.tick_params(axis="y", labelsize=12.5)
    ax.get_xaxis().set_visible(False)
    style(ax)
    fig.text(0.125, 0.02, "카닥은 견적비교 앱이라 가격 언급이 8배 — 마이클 사용자는 편의·관리로 온다", color=MUTED, fontsize=9.5)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(OUT / "차트2_마이클vs카닥_가격언급.png", bbox_inches="tight")
    plt.close(fig)


# ── 차트 3: 타이어 부정, 마찰이 일어나는 단계 ──
def chart3():
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=150)
    rows = [("진입·결정·예약 단계", 50, HILITE),
            ("불명", 42, CTX),
            ("둘 다 언급", 3, CTX),
            ("정비소 시공·방문 후", 5, MICHAEL)]
    labels = [r[0] for r in rows]; vals = [r[1] for r in rows]; colors = [r[2] for r in rows]
    y = range(len(rows))
    bars = ax.barh(list(y), vals, color=colors, height=0.6, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(v + 0.8, b.get_y() + b.get_height() / 2, f"{v}%", va="center",
                fontsize=12, fontweight="bold", color=INK)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=11.5)
    ax.invert_yaxis(); ax.set_xlim(0, 58)
    ax.get_xaxis().set_visible(False)
    ax.set_title("타이어 부정 리뷰 — 마찰은 앱 ‘결정·예약 여정’에 집중", fontsize=13.5,
                 fontweight="bold", pad=12, loc="left")
    style(ax)
    fig.text(0.125, 0.02, "타이어 부정 76건 · 정비소 시공 후 불만은 5%뿐 → 정비사 손끝이 아니라 앱 안에서 새고 있다", color=MUTED, fontsize=9.5)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(OUT / "차트3_타이어_마찰단계.png", bbox_inches="tight")
    plt.close(fig)


# ── 차트 4: 측면별 부정률 (건당 불만 — 급소1 재프레임의 견고한 근거) ──
def chart4():
    # 마이클 Android analyzable 부정률(별점<=3, %). 전체 기준 11.2%.
    rows = [("타이어", 40.4, True), ("알림", 32.5, False), ("엔진오일", 31.4, False),
            ("예약/대기", 17.4, False), ("교체주기 알림", 16.0, False),
            ("가격/견적", 11.7, False), ("세차", 9.3, False)]
    base = 11.2
    labels = [r[0] for r in rows]; vals = [r[1] for r in rows]
    colors = [HILITE if r[2] else CTX for r in rows]
    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=150)
    y = range(len(rows))
    bars = ax.barh(list(y), vals, color=colors, height=0.62, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(v + 0.8, b.get_y() + b.get_height() / 2, f"{v}%", va="center",
                fontsize=11.5, fontweight="bold", color=INK)
    ax.axvline(base, ls="--", lw=1.3, color=MUTED, zorder=2)
    ax.text(base + 0.3, len(rows) - 0.4, f"전체 평균 {base}%", color=MUTED, fontsize=9.5, va="center")
    ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=11.5)
    ax.invert_yaxis(); ax.set_xlim(0, 46)
    ax.get_xaxis().set_visible(False)
    ax.set_title("측면별 부정 리뷰 비율 — 타이어가 전체 평균의 3.6배", fontsize=13.5,
                 fontweight="bold", pad=12, loc="left")
    style(ax)
    fig.text(0.125, 0.02, "마이클 Android 분석가능 19,556건 · 별점 3점 이하 비율 · 타이어 40.4% = 전체 11.2%의 3.6배", color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "차트4_측면별_부정률.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    chart1(); chart2(); chart3(); chart4()
    print("saved to", OUT)
    for p in sorted(OUT.glob("*.png")):
        print(" -", p.name)
