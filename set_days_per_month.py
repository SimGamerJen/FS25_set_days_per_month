#!/usr/bin/env python3
# set_days_per_month.py
#
# FS25: update days-per-month (daysPerPeriod), recompute currentDay from existing values,
# and clear cached forecast so the game rebuilds it on load.

import argparse
import os
import sys
import shutil
import datetime as dt
import xml.etree.ElementTree as ET
from xml.dom import minidom

POSSIBLE_ENV_PATHS = [
    "environment.xml",
    os.path.join("config", "environment.xml"),
]

PRIMARY_DAY_TAG = "daysPerPeriod"
DAY_TAG_SYNONYMS = ["daysPerMonth", "periodLength"]

def find_env_xml(save_dir: str) -> str:
    for rel in POSSIBLE_ENV_PATHS:
        p = os.path.join(save_dir, rel)
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(
        "Couldn't find environment.xml in the save folder. "
    )

def backup_file(path: str) -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{path}.bak.{stamp}"
    shutil.copy2(path, bak)
    return bak

def pretty_write_xml(tree: ET.ElementTree, dest_path: str):
    rough = ET.tostring(tree.getroot(), encoding="utf-8")
    parsed = minidom.parseString(rough)
    with open(dest_path, "wb") as f:
        f.write(parsed.toprettyxml(indent="  ", encoding="utf-8"))

def find_or(root: ET.Element, tag: str, default=None):
    el = root.find(f".//{tag}")
    return (el, (el.text if el is not None and el.text is not None else default))

def ensure_child(parent: ET.Element, tag: str) -> ET.Element:
    node = parent.find(tag)
    if node is None:
        node = ET.SubElement(parent, tag)
    return node

def set_days_per_period(root: ET.Element, value: int):
    env = root if root.tag == "environment" else (root.find(".//environment") or root)
    primary = ensure_child(env, PRIMARY_DAY_TAG)
    primary.text = str(value)
    for tag in DAY_TAG_SYNONYMS:
        el = root.find(f".//{tag}")
        if el is not None:
            el.text = str(value)

def clear_forecast(root: ET.Element) -> int:
    removed = 0
    def _remove_children_named(parent: ET.Element, name: str):
        nonlocal removed
        for child in list(parent):
            if child.tag.lower().endswith(name.lower()):
                parent.remove(child)
                removed += 1
            else:
                _remove_children_named(child, name)
    _remove_children_named(root, "forecast")

    for parent in root.iter():
        tag_lower = parent.tag.lower()
        if "variation" in tag_lower or "weatherpreset" in tag_lower:
            for child in list(parent):
                if child.tag.lower().endswith("object"):
                    parent.remove(child)
                    removed += 1

    for el in root.iter():
        if el.tag.lower().endswith("lastupdate"):
            el.text = "0"

    return removed

def validate_days(n: int):
    if n < 1 or n > 28:
        raise ValueError("Days per month must be between 1 and 28.")

def recompute_current_day(old_current: int, old_days: int, new_days: int, target_day: int, keep_day: bool):
    """
    Deduce how many whole months have already elapsed from the old settings,
    then recompute currentDay for the new days-per-period.
    """
    if old_days < 1:
        old_days = 1  # safety
    # Day number within the current month under the *old* system:
    old_day_in_month = ((old_current - 1) % old_days) + 1
    # Number of full months already completed:
    months_before = (old_current - old_day_in_month) // old_days
    # Decide the day to use under the *new* system:
    if keep_day:
        # keep the same ordinal day within the target month, but clamp if needed
        day_in_month = max(1, min(old_day_in_month, new_days))
    else:
        # default: day 1 (this matches your August Day 1 workflow)
        day_in_month = target_day
        if not (1 <= day_in_month <= new_days):
            raise ValueError(f"Target day must be 1..{new_days}.")
    # New linear day:
    new_current = months_before * new_days + day_in_month
    return new_current, months_before, old_day_in_month, day_in_month

# --- ADDED: update plannedDaysPerPeriod in careerSavegame.xml (only change) ---
def update_career_planned_days(save_dir: str, days_value: int, no_backup: bool, dry_run: bool):
    career_path = os.path.join(save_dir, "careerSavegame.xml")
    if not os.path.isfile(career_path):
        print("[warn] careerSavegame.xml not found; skipping plannedDaysPerPeriod update.")
        return
    print(f"[info] Updating plannedDaysPerPeriod in: {career_path}")
    tree = ET.parse(career_path)
    root = tree.getroot()
    settings = root.find(".//settings") or root
    node = settings.find("plannedDaysPerPeriod")
    if node is None:
        node = ET.SubElement(settings, "plannedDaysPerPeriod")
    node.text = str(days_value)
    if dry_run:
        print("[info] Dry-run: careerSavegame.xml not written.")
        return
    if not no_backup:
        bak = backup_file(career_path)
        print(f"[info] Backup created: {bak}")
    pretty_write_xml(tree, career_path)
    print("[ok] careerSavegame.xml updated.")

def main():
    ap = argparse.ArgumentParser(
        description="FS25: set daysPerPeriod, recompute currentDay from existing values, and clear forecast cache."
    )
    ap.add_argument("--save", required=True,
                    help="Path to the savegame folder (e.g. '.../FarmingSimulator2025/savegame1').")
    ap.add_argument("--days", type=int, required=True,
                    help="New days per month to set (1–28).")
    ap.add_argument("--target-day", type=int, default=1,
                    help="Day within the target month for the *new* system (ignored if --keep-day). Default: 1.")
    ap.add_argument("--keep-day", action="store_true",
                    help="Keep the same day-in-month as before (clamped to new days).")
    ap.add_argument("--no-backup", action="store_true",
                    help="Do not create a timestamped .bak file.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse and report what would change without writing.")
    args = ap.parse_args()

    save_dir = os.path.abspath(os.path.expanduser(args.save))
    if not os.path.isdir(save_dir):
        print(f"[error] Save folder not found: {save_dir}", file=sys.stderr)
        sys.exit(2)

    try:
        validate_days(args.days)
    except ValueError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(2)

    try:
        env_path = find_env_xml(save_dir)
    except FileNotFoundError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(2)

    print(f"[info] Using environment file: {env_path}")

    tree = ET.parse(env_path)
    root = tree.getroot()

    # Read existing values (defaults match FS25 fresh-save behavior: days=1, currentDay=6)
    _, old_days_text = find_or(root, PRIMARY_DAY_TAG, default=None)
    if old_days_text is None:
        # try synonyms
        for tag in DAY_TAG_SYNONYMS:
            _, old_days_text = find_or(root, tag, default=None)
            if old_days_text is not None:
                break
    old_days = int(old_days_text) if old_days_text not in (None, "") else 1

    _, old_current_text = find_or(root, "currentDay", default=None)
    old_current = int(old_current_text) if old_current_text not in (None, "") else 6

    print(f"[info] Detected old settings: daysPerPeriod={old_days}, currentDay={old_current}")

    # Recompute currentDay under new days-per-period
    try:
        new_current, months_before, old_dim, new_dim = recompute_current_day(
            old_current, old_days, args.days, args.target_day, args.keep_day
        )
    except ValueError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(2)

    print(f"[calc] months_before={months_before} (full months already elapsed under old system)")
    print(f"[calc] old_day_in_month={old_dim} -> new_day_in_month={new_dim}")
    print(f"[calc] new currentDay = {new_current} (months_before*{args.days} + day_in_month)")

    # 1) Force daysPerPeriod (and sync synonyms if present)
    set_days_per_period(root, args.days)
    print(f"[info] Set daysPerPeriod = {args.days} (synced any existing synonyms).")

    # 2) Set recomputed currentDay
    env = root if root.tag == "environment" else (root.find(".//environment") or root)
    node = env.find("currentDay")
    if node is None:
        node = ET.SubElement(env, "currentDay")
    node.text = str(new_current)
    print(f"[info] Set currentDay = {new_current}")

    # 3) Clear cached forecast entries so FS25 regenerates them on load
    removed = clear_forecast(root)
    print(f"[info] Cleared {removed} cached forecast entries/objects.")

    if args.dry_run:
        print("[info] Dry-run mode: no files written.")
        sys.exit(0)

    if not args.no_backup:
        bak = backup_file(env_path)
        print(f"[info] Backup created: {bak}")

    # --- ADDED: keep UI/engine in sync by updating careerSavegame.xml plannedDaysPerPeriod ---
    update_career_planned_days(save_dir, args.days, args.no_backup, args.dry_run)

    pretty_write_xml(tree, env_path)
    print("[ok] environment.xml updated. Launch the save; FS25 will regenerate the forecast on load.")

if __name__ == "__main__":
    main()
