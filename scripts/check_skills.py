#!/usr/bin/env python3
"""
Guard for the Claude skills in .claude/skills/, which staff install as the
`appleseed-writing` plugin (Hawaii-Appleseed/claude-skills points at this
folder). A skill that only works on one laptop breaks for everyone, so this
fails CI on the mistakes that have actually happened:

  lint   machine-specific paths, repo-relative calls to the skill's own
         scripts (must be ${CLAUDE_SKILL_DIR}), a hardcoded website path that
         ignores $APPLESEED_WEBSITE, personal email addresses, and $1-style
         shell arguments in SKILL.md code blocks (Claude Code substitutes $N
         with the skill's invocation arguments before Claude sees it)
  shape  each skill has SKILL.md with name == folder name and a description
  corpus the paths the skills read from writing-bot/ still exist
  smoke  run the bundled scripts the way a colleague would: from outside the
         repo, via $APPLESEED_WEBSITE, with no LegiScan key; render a sample
         testimony to .docx using the venv setup the skill documents

    python scripts/check_skills.py            # lint + shape + corpus
    python scripts/check_skills.py --smoke    # also run the scripts (CI)
"""
from __future__ import annotations

import argparse, os, re, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / ".claude" / "skills"

# (regex, message, applies-to suffixes). A line matching `allow` is exempt.
RULES = [
    (re.compile(r"/Users/[A-Za-z]"), "absolute home path — only exists on one machine", None),
    (re.compile(r"~/\.claude/skills|\$HOME/\.claude/skills"),
     "path into one person's ~/.claude/skills — use ${CLAUDE_SKILL_DIR}", None),
    (re.compile(r"(?<![\w/])\.claude/skills/"),
     "repo-relative call to a skill file — use ${CLAUDE_SKILL_DIR}", {".md"}),
    (re.compile(r"[\w.+-]+@(hibudget\.org|gmail\.com)"), "personal email address", None),
]
# ~/HawaiiAppleseed is fine only as the $APPLESEED_WEBSITE default or the clone target.
WEBSITE = re.compile(r"HawaiiAppleseed(?!-)")
WEBSITE_OK = re.compile(r"APPLESEED_WEBSITE|gh repo clone")
SHELL_ARG = re.compile(r"\$(\d|ARGUMENTS)")

CORPUS = ["writing-bot/positions.md", "writing-bot/testimony", "writing-bot/blog-posts/2025",
          "writing-bot/blog-posts/2026", "writing-bot/requirements.txt", "assets/okina.css"]

SAMPLE = """Testimony of the Hawaiʻi Appleseed Center for Law and Economic Justice
Support for HB 1 – CI smoke test
House Committee on Finance
[DATE AND TIME]

Dear Chair [NAME], Vice Chair [NAME], and Members of the Committee:

Placeholder paragraph rendered by scripts/check_skills.py.[1]

Mahalo for the opportunity to testify.

Hawaiʻi Appleseed Center for Law and Economic Justice

________________

[1] Example, "Title," Publisher, 2026. https://example.org/
"""


def files():
    for p in sorted(SKILLS.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".md", ".py", ".sh"}:
            yield p


def lint() -> list[str]:
    errs = []
    for p in files():
        rel = p.relative_to(REPO)
        in_code = False
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip("> ").startswith("```"):
                in_code = not in_code
            for rx, msg, only in RULES:
                if (only is None or p.suffix in only) and rx.search(line):
                    errs.append(f"{rel}:{n}: {msg}\n    {line.strip()[:120]}")
            if WEBSITE.search(line) and not WEBSITE_OK.search(line):
                errs.append(f"{rel}:{n}: hardcoded website path — resolve it via "
                            f"$APPLESEED_WEBSITE (default ~/HawaiiAppleseed)\n    {line.strip()[:120]}")
            if p.name == "SKILL.md" and in_code and SHELL_ARG.search(line):
                errs.append(f"{rel}:{n}: $N / $ARGUMENTS in a code block is replaced by the "
                            f"skill's arguments — use \"$@\" or a named variable\n    {line.strip()[:120]}")
    return errs


def shape() -> list[str]:
    errs = []
    dirs = [d for d in sorted(SKILLS.iterdir()) if d.is_dir() and d.name != "__pycache__"]
    if not dirs:
        return [f"no skills found in {SKILLS}"]
    for d in dirs:
        sk = d / "SKILL.md"
        if not sk.exists():
            errs.append(f"{d.relative_to(REPO)}: missing SKILL.md")
            continue
        m = re.match(r"---\n(.*?)\n---\n", sk.read_text(encoding="utf-8"), re.S)
        fm = dict(re.findall(r"^(\w+):\s*(.+)$", m.group(1), re.M)) if m else {}
        if fm.get("name") != d.name:
            errs.append(f"{sk.relative_to(REPO)}: frontmatter name {fm.get('name')!r} != folder {d.name!r}")
        if len(fm.get("description", "")) < 20:
            errs.append(f"{sk.relative_to(REPO)}: missing or too-short description")
    return errs


def corpus() -> list[str]:
    return [f"{c}: missing — the skills read it" for c in CORPUS if not (REPO / c).exists()]


def smoke() -> list[str]:
    errs = []
    t = SKILLS / "appleseed-testimony"
    env = {k: v for k, v in os.environ.items() if k != "LEGISCAN_API_KEY"}
    env["APPLESEED_WEBSITE"] = str(REPO)
    with tempfile.TemporaryDirectory() as tmp:  # run from outside the repo, like a colleague
        def run(*cmd, expect=0):
            r = subprocess.run(cmd, cwd=tmp, env=env, capture_output=True, text=True)
            if r.returncode != expect:
                errs.append(f"{' '.join(map(str, cmd))[:140]}\n    exit {r.returncode}, expected {expect}\n"
                            f"    {(r.stderr or r.stdout).strip()[-400:]}")
            return r

        run(sys.executable, t / "bill_lookup.py", "HB1884", expect=2)  # no key -> exit 2, no guessing
        run(sys.executable, t / "reference" / "build_citations.py", "-o", f"{tmp}/citations.md")
        r = run(sys.executable, t / "reference" / "profile_testimony.py")
        if "TESTIMONY STYLE PROFILE" not in r.stdout or " 0 documents" in r.stdout:
            errs.append("profile_testimony.py found no testimony via $APPLESEED_WEBSITE")

        # The render venv exactly as SKILL.md tells a fresh clone to make it.
        venv = Path(tmp) / "venv"
        run(sys.executable, "-m", "venv", venv)
        run(venv / "bin" / "pip", "install", "-q", "python-docx")
        (Path(tmp) / "draft.txt").write_text(SAMPLE, encoding="utf-8")
        run(venv / "bin" / "python", t / "render_testimony.py", "draft.txt", "-o", "out/HB1")
        for ext in ("docx", "html"):
            if not (Path(tmp) / "out" / f"HB1.{ext}").exists():
                errs.append(f"render_testimony.py produced no HB1.{ext}")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--smoke", action="store_true", help="also run the bundled scripts")
    a = ap.parse_args()
    checks = [("lint", lint), ("shape", shape), ("corpus", corpus)] + ([("smoke", smoke)] if a.smoke else [])
    failed = 0
    for name, fn in checks:
        errs = fn()
        print(f"{'FAIL' if errs else 'ok  '} {name}")
        for e in errs:
            print(f"  {e}")
        failed += len(errs)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
