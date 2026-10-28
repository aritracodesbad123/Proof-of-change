# Backend selection has to sit between these imports, so the import-order rules do not apply here.
# ruff: noqa: E402, I001
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(figsize=(12, 17))
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")
W, H = 0.36, 0.052


def panel(x, y, t, c="#e8f0fe", e="#3367d6", w=W, h=H):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.006", fc=c, ec=e, lw=1.8))
    ax.text(x, y, t, ha="center", va="center", fontsize=10.5)


def arr(x1, y1, x2, y2, lab="", col="#333", rad=0):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color=col, lw=2, mutation_scale=18, connectionstyle=f"arc3,rad={rad}"),
    )
    if lab:
        ax.text((x1 + x2) / 2 + 0.01, (y1 + y2) / 2, lab, fontsize=9.5, color=col, ha="left", va="center", style="italic")


NEW = "#fff4e0"
NE = "#e08a00"
HUM = "#e6f4ea"
HE = "#188038"
ax.text(0.5, 0.985, "Proof-of-Change: how one PR check works", ha="center", fontsize=16, weight="bold")
panel(0.5, 0.94, "1. Reviewer starts a check\n(command line, web console or GitHub App)")
panel(0.5, 0.86, "2. Load the PR\nrecorded head and a base side")
panel(0.78, 0.77, "3a. Read the claims (Nemotron 3 Super)\nquotes checked against the PR text")
panel(0.78, 0.68, "4a. Draft probes (up to 4)\nfor the claims (Nemotron 3 Super)")
panel(
    0.78, 0.585,
    "5a. HUMAN REVIEW (web console only)\nkeep/drop probes, add up to 20\nnew scenarios in plain words",
    c=HUM, e=HE, h=0.065,
)
panel(
    0.22, 0.77,
    "3b. Work out setup\nproject's own setup files\n+ Tavily Crawl of its repo & docs",
    c=NEW, e=NE, h=0.065,
)
panel(
    0.30, 0.64,
    "4b. Sandbox\nGitHub App, request worker,\nhosted console: Contree only\n"
    "cannot start: could not verify\nCLI, local console, study:\nlocal bubblewrap\n"
    "no secret keys; network only for installs",
    c=NEW, e=NE, w=0.36, h=0.115,
)
panel(
    0.5, 0.49,
    "6. Run on both sides: main vs PR\nproject tests and probes\ncoverage checks whether changed lines ran",
    h=0.065,
)
panel(
    0.5, 0.395,
    "7. Verdict rules\nverdict comes from the test evidence per claim",
    h=0.065,
)
panel(0.5, 0.315, "8. Second opinion (Nemotron 3 Ultra)\nadvisory only; it does not change the verdict")
panel(0.5, 0.225, "9. VERDICT\nVerified / Needs attention / Could not verify", c="#fce8e6", e="#c5221f")
panel(0.16, 0.315, "Tavily diagnosis\nreads the real error\n+ crawled setup pages", c=NEW, e=NE, w=0.26, h=0.065)
panel(0.16, 0.41, "Fix setup in sandbox\nand retest\n(up to 3 tries)", c=NEW, e=NE, w=0.26, h=0.065)
panel(
    0.5, 0.135,
    "10. Report: HTML + Markdown + PDF\n"
    "saved with each run; emailed when the main PDF maker creates it\n"
    "shows the evidence and step timings",
    w=0.62, h=0.078,
)
panel(0.5, 0.055, "11. Human reviewer decides\nthe tool never approves or merges", c=HUM, e=HE)
arr(0.5, 0.912, 0.5, 0.888)
arr(0.55, 0.833, 0.72, 0.798)
arr(0.45, 0.833, 0.28, 0.805)
arr(0.75, 0.743, 0.75, 0.708)
arr(0.75, 0.653, 0.75, 0.62)
arr(0.24, 0.732, 0.30, 0.706)
arr(0.75, 0.551, 0.58, 0.524)
arr(0.34, 0.574, 0.42, 0.530)
arr(0.5, 0.456, 0.5, 0.423)
arr(0.5, 0.368, 0.5, 0.343)
arr(0.5, 0.288, 0.5, 0.253)
arr(0.32, 0.225, 0.20, 0.282, col=NE)
ax.text(0.04, 0.24, "Could not verify\n(setup / missing package)", fontsize=9.5, color=NE, style="italic")
arr(0.16, 0.348, 0.16, 0.376, col=NE)
arr(0.29, 0.43, 0.35, 0.475, col=NE)
ax.text(0.28, 0.458, "retest", fontsize=9.5, color=NE, ha="right", va="bottom", style="italic")
arr(0.5, 0.198, 0.5, 0.178, "final verdict")
arr(0.5, 0.092, 0.5, 0.083)
ax.text(
    0.5, 0.012,
    "The orange loop fixes setup only. It does not retry a failure the pull request caused, "
    "and it does not install operating-system packages.",
    ha="center", fontsize=9.5, color="#555",
)
plt.savefig("docs/architecture.png", dpi=130, bbox_inches="tight")
