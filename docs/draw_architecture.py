"""导出架构图 PNG（离线，无外部网络依赖）。
运行：python3 docs/draw_architecture.py  ->  生成 docs/architecture.png
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# 注册系统中文字体（macOS PingFang），保证中文不乱码
for _fp in ("/System/Library/Fonts/PingFang.ttc", "/Library/Fonts/Arial Unicode.ttf"):
    if Path(_fp).exists():
        try:
            fm.fontManager.addfont(_fp)
        except Exception:
            pass
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

OUT = Path(__file__).resolve().parent / "architecture.png"

NAVY = "#1f3a5f"
BLUE = "#1a6fd4"
TEAL = "#1f9e8f"
AMBER = "#d98a00"
GREY = "#e9eef5"
DARK = "#22303f"

fig, ax = plt.subplots(figsize=(13, 7.2))
ax.set_xlim(0, 13)
ax.set_ylim(1.6, 7.2)
ax.axis("off")


def box(x, y, w, h, title, sub=None, color=BLUE, fc=GREY, txt=DARK, fs=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12",
                                linewidth=1.6, edgecolor=color, facecolor=fc))
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", fontsize=fs,
            fontweight="bold", color=txt)
    if sub:
        ax.text(x + w / 2, y + h * 0.26, sub, ha="center", va="center", fontsize=8.5, color="#556")


def arrow(x1, y1, x2, y2, color="#888"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13,
                                linewidth=1.4, color=color))


def label(x, y, t, color=DARK, fs=9, ha="center"):
    ax.text(x, y, t, ha=ha, va="center", fontsize=fs, color=color, style="italic")


# 标题
ax.text(6.5, 6.9, "金融+科技 · 流程重写者 作品集架构", ha="center", fontsize=15,
        fontweight="bold", color=NAVY)

# 左轨 v0.1
box(0.4, 5.4, 1.7, 0.9, "RSS 信源 ×3", "金融资讯", BLUE)
box(2.5, 5.4, 1.7, 0.9, "抓取+清洗", "去重·新鲜度", BLUE)
box(4.6, 5.4, 1.7, 0.9, "GLM 摘要打标", "利好/中性/风险", BLUE)
box(6.7, 5.4, 1.9, 0.9, "投研情报简报", "brief_YYYYMMDD.md", NAVY, "#dce8f7")
arrow(2.1, 5.85, 2.5, 5.85)
arrow(4.2, 5.85, 4.6, 5.85)
arrow(6.3, 5.85, 6.7, 5.85)

# 右轨 v0.1 报表
box(0.4, 3.6, 1.7, 0.9, "业务 CSV", "date/cat/rev/cost", TEAL)
box(2.5, 3.6, 1.7, 0.9, "pandas 算数", "环比/同比/占比", TEAL)
box(4.6, 3.6, 1.7, 0.9, "GLM 仅解读", "不自己算数", TEAL)
box(6.7, 3.6, 1.9, 0.9, "经营月报+异常", "report_YYYYMM.md", NAVY, "#dce8f7")
arrow(2.1, 4.05, 2.5, 4.05)
arrow(4.2, 4.05, 4.6, 4.05)
arrow(6.3, 4.05, 6.7, 4.05)

# 共用护栏
box(4.4, 2.2, 2.5, 0.85, "共用合规护栏", "高危词打码·免责声明·对账", AMBER, "#fbeed2", fs=10)
arrow(6.7, 3.6, 5.65, 3.05, AMBER)
arrow(6.7, 5.4, 5.65, 3.05, AMBER)

# 分发
box(9.0, 5.4, 3.0, 0.9, "发布为应用 - 在线链接", "v0.1 获客/演示", BLUE, "#dce8f7")
box(9.0, 3.6, 3.0, 0.9, "GitHub + 录屏 + 截图", "v1.0 私有化交付背书", TEAL, "#d6efe9")
arrow(8.6, 5.85, 9.0, 5.85)
arrow(8.6, 4.05, 9.0, 4.05)

# 轨道标签
ax.text(0.3, 6.7, "v0.1 验证体（Python+FastAPI，可一键发布）", fontsize=10, color=BLUE, fontweight="bold")
ax.text(0.3, 2.75, "v1.0 交付体（Java 17+Spring Boot，私有化）", fontsize=10, color=TEAL, fontweight="bold")
label(10.5, 5.95, "WorkBuddy 发布为应用", fs=8)
label(5.65, 1.85, "两个 Demo 共用 _shared/ 与 check_compliance.sh", fs=8, color="#a06b00")

fig.tight_layout()
fig.savefig(OUT, dpi=160, bbox_inches="tight", facecolor="white")
print("written", OUT)
