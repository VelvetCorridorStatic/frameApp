#!/usr/bin/env python3
import argparse
import re
import subprocess
from pathlib import Path

PNG_RE = re.compile(r"\.png$", re.IGNORECASE)

def norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def parse_filename(name: str):
    """
    Expected patterns (examples):
      "CKT template 90x90 cropped light.png"
      "CKT template small close 60x50 dark.png"
      "CKT template small far 60x50 light.png"

    Returns dict: family, size, variant, tone
    variant in: full | crop | close
    """
    if not PNG_RE.search(name):
        return None

    base = norm_spaces(name[:-4])  # drop .png

    # Tone at end: light/dark
    m_tone = re.search(r"\s+(light|dark)$", base, flags=re.IGNORECASE)
    if not m_tone:
        return None
    tone = m_tone.group(1).lower()
    base_wo_tone = base[: m_tone.start()].strip()

    # Size like 90x90
    m_size = re.search(r"(\d{2,4}x\d{2,4})", base_wo_tone, flags=re.IGNORECASE)
    if not m_size:
        return None
    size = m_size.group(1).lower()

    # Family (extendable)
    if re.search(r"\btemplate\b", base_wo_tone, flags=re.IGNORECASE):
        family = "template"
    elif re.search(r"\baquarell\b", base_wo_tone, flags=re.IGNORECASE):
        family = "aquarell"
    else:
        # If it starts with "CKT" but doesn't declare, assume template
        if re.match(r"(?i)^ckt\b", base_wo_tone):
            family = "template"
        else:
            return None

    # Variant:
    # - "cropped" => crop
    # - "small close" => close
    # - "small far" => full (normal)
    # - otherwise => full
    variant = "full"
    if re.search(r"\bcropped\b", base_wo_tone, flags=re.IGNORECASE):
        variant = "crop"
    elif re.search(r"\bsmall close\b", base_wo_tone, flags=re.IGNORECASE):
        variant = "close"
    elif re.search(r"\bsmall far\b", base_wo_tone, flags=re.IGNORECASE):
        variant = "full"

    return {
        "original": name,
        "family": family,
        "size": size,
        "variant": variant,
        "tone": tone,
    }

def build_new_name(parsed):
    # ckt-{family}-{w}x{h}-{variant}-{tone}.png
    return f"ckt-{parsed['family']}-{parsed['size']}-{parsed['variant']}-{parsed['tone']}.png"

def main():
    ap = argparse.ArgumentParser(description="Rename frame PNGs to a toggle-friendly naming scheme.")
    ap.add_argument("--apply", action="store_true", help="Actually perform renames (default is dry-run).")
    ap.add_argument("--use-git", action="store_true", help="Use `git mv` instead of `mv` (recommended in repos).")
    args = ap.parse_args()

    cwd = Path(".").resolve()
    pngs = sorted([p for p in cwd.iterdir() if p.is_file() and PNG_RE.search(p.name)])

    mappings = []
    for p in pngs:
        parsed = parse_filename(p.name)
        if not parsed:
            continue
        new_name = build_new_name(parsed)
        if new_name == p.name:
            continue
        mappings.append((p, cwd / new_name))

    if not mappings:
        print("No matching PNGs found to rename.")
        return

    # Check collisions
    targets = [dst.name for _, dst in mappings]
    dupes = {t for t in targets if targets.count(t) > 1}
    if dupes:
        print("ERROR: Name collisions detected. These targets would be duplicated:")
        for d in sorted(dupes):
            print("  ", d)
        print("Aborting.")
        return

    # Check if any target already exists
    existing = [dst for _, dst in mappings if dst.exists()]
    if existing:
        print("ERROR: Some target filenames already exist:")
        for dst in existing:
            print("  ", dst.name)
        print("Aborting.")
        return

    print("Proposed renames:")
    for src, dst in mappings:
        print(f"  {src.name}  ->  {dst.name}")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to perform the renames.")
        return

    for src, dst in mappings:
        if args.use_git:
            subprocess.run(["git", "mv", src.name, dst.name], check=True)
        else:
            src.rename(dst)

    print("\nDone.")

if __name__ == "__main__":
    main()