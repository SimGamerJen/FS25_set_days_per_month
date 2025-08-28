#!/usr/bin/env python3
# set_days_per_month.py
#
# FS25 utility:
# - Update days-per-month (daysPerPeriod) in environment.xml
# - Recompute currentDay to preserve progress across a days-per-month change
# - Clear cached forecast so the game rebuilds it on load
# - Sync plannedDaysPerPeriod in careerSavegame.xml
# - Reset farms.xml <statistics> values to 0 / 0.000000 (skipping <farmId>)
# - Remove all <stats> entries inside <finances> (per farm) in farms.xml
#
# Example usages:
#   py .\set_days_per_month.py --save savegame1 --days 3 --verbose
#   py .\set_days_per_month.py --save savegame1 --days 3 --keep-day --verbose
#   py .\set_days_per_month.py --save savegame1 --reset-stats --verbose
#   py .\set_days_per_month.py --save savegame1 --reset-finances --verbose
#   py .\set_days_per_month.py --save savegame1 --days 3 --reset-stats --reset-finances --dry-run --verbose
#
import argparse
import os
import sys
import shutil
import datetime as dt
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

POSSIBLE_ENV_PATHS = [
    "environment.xml",
    os.path.join("config", "environment.xml"),
]

PRIMARY_DAY_TAG = "daysPerPeriod"
DAY_TAG_SYNONYMS = ["daysPerMonth", "plannedDaysPerPeriod"]

# -------------------------
# Pretty XML write / backup
# -------------------------
def pretty_write_xml(tree: ET.ElementTree, path: Path, dry_run: bool = False):
    xml_bytes = ET.tostring(tree.getroot(), encoding="utf-8")
    reparsed = minidom.parseString(xml_bytes)
    pretty = reparsed.toprettyxml(indent="  ", encoding="utf-8")
    if dry_run:
        return
    with open(path, "wb") as f:
        f.write(pretty)

def timestamped_backup(path: Path) -> Path:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".{ts}.bak")
    path.replace(bak)
    return bak

def ensure_exists(path: Path, label: str):
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")

# -------------------------
# XML helpers
# -------------------------
def find_environment_xml(save_dir: Path) -> Path:
    for rel in POSSIBLE_ENV_PATHS:
        candidate = save_dir / rel
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"environment.xml not found in {save_dir} (tried {POSSIBLE_ENV_PATHS})")

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
    def _remove_children_named(parent_xpath: str, child_tag: str):
        nonlocal removed
        for parent in root.findall(parent_xpath):
            for child in list(parent.findall(child_tag)):
                parent.remove(child)
                removed += 1
    _remove_children_named(".//weatherForecast", "period")
    _remove_children_named(".//weather", "object")
    _remove_children_named(".//weatherObjects", "object")
    return removed

# -------------------------
# Current day recompute
# -------------------------
def compute_new_current_day(old_current: int, old_days: int, new_days: int, keep_day: bool, target_day: int) -> int:
    if old_days <= 0 or new_days <= 0:
        raise ValueError("days-per-period must be positive")
    old_day_in_month = ((old_current - 1) % old_days) + 1
    months_before = (old_current - old_day_in_month) // old_days
    if keep_day:
        day_in_month = max(1, min(old_day_in_month, new_days))
    else:
        day_in_month = target_day
        if not (1 <= day_in_month <= new_days):
            raise ValueError(f"Target day must be 1..{new_days}.")
    new_current = months_before * new_days + day_in_month
    return new_current

# -------------------------
# careerSavegame.xml update
# -------------------------
def update_career_planned_days(save_dir: Path, days: int, no_backup: bool, dry_run: bool, verbose: bool = False):
    career_path = save_dir / "careerSavegame.xml"
    ensure_exists(career_path, "careerSavegame.xml")
    if verbose:
        print(f"[info] Opening {career_path}")
    tree = ET.parse(career_path)
    root = tree.getroot()
    settings = root.find("./settings")
    if settings is None:
        settings = ET.SubElement(root, "settings")
    node = settings.find("plannedDaysPerPeriod")
    if node is None:
        node = ET.SubElement(settings, "plannedDaysPerPeriod")
    current = (node.text or "").strip()
    if current == str(days):
        if verbose:
            print(f"[info] plannedDaysPerPeriod already {current}; no change.")
    else:
        if verbose:
            print(f"[info] plannedDaysPerPeriod: '{current}' -> '{days}'")
        node.text = str(days)
        if not dry_run and not no_backup:
            bak = timestamped_backup(career_path)
            if verbose:
                print(f"[info] Backup created: {bak}")
        if not dry_run:
            tree.write(career_path, encoding="utf-8", xml_declaration=True)
            if verbose:
                print(f"[ok] careerSavegame.xml updated")

# -------------------------
# farms.xml statistics reset
# -------------------------
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")
_INT_RE   = re.compile(r"^-?\d+$")

def _zero_like(value: str) -> str:
    val = (value or "").strip()
    if _FLOAT_RE.match(val):
        return "0.000000"
    if _INT_RE.match(val):
        return "0"
    return "0"

def reset_farm_statistics(farms_xml_path: Path, verbose: bool = False, dry_run: bool = False, no_backup: bool = False) -> int:
    ensure_exists(farms_xml_path, "farms.xml")
    if verbose:
        print(f"[info] Opening {farms_xml_path}")
    tree = ET.parse(farms_xml_path)
    root = tree.getroot()
    changed = 0
    for farm in root.findall("./farm"):
        stats = farm.find("statistics")
        if stats is None:
            continue
        for node in list(stats):
            if node.tag == "farmId":
                continue
            old = (node.text or "").strip()
            new = _zero_like(old)
            if old != new:
                node.text = new
                changed += 1
                if verbose:
                    print(f"[info]  {node.tag}: '{old}' -> '{new}'")
    if changed > 0:
        if not dry_run and not no_backup:
            bak = timestamped_backup(farms_xml_path)
            if verbose:
                print(f"[info] Backup created: {bak}")
        if not dry_run:
            tree.write(farms_xml_path, encoding="utf-8", xml_declaration=True)
            if verbose:
                print(f"[ok] farms.xml statistics updated")
    elif verbose:
        print("[info] No statistic fields required changes.")
    return changed

# -------------------------
# farms.xml finances reset
# -------------------------

def reset_farm_finances(farms_xml_path: Path, verbose: bool = False, dry_run: bool = False, no_backup: bool = False) -> int:
    """
    Zero out numeric values inside each <finances>/<stats> block for every <farm> in farms.xml.
    Preserves numeric style (ints -> '0', floats -> '0.000000').
    Returns the number of fields changed.
    """
    ensure_exists(farms_xml_path, "farms.xml")
    if verbose:
        print(f"[info] Opening {farms_xml_path}")
    tree = ET.parse(farms_xml_path)
    root = tree.getroot()
    changed = 0

    for farm in root.findall("./farm"):
        finances = farm.find("finances")
        if finances is None:
            continue

        for stats in finances.findall("stats"):
            # Iterate all direct children under <stats> (and nested ones, to be safe).
            for node in stats.iter():
                if node is stats:
                    continue  # skip the container element itself
                # Only attempt to zero leaf nodes that have text content
                text = (node.text or "").strip()
                if text == "":
                    continue
                new_text = _zero_like(text)
                if text != new_text:
                    node.text = new_text
                    changed += 1
                    if verbose:
                        print(f"[info]  finances.stats/{node.tag}: '{text}' -> '{new_text}'")

    if changed > 0:
        if not dry_run and not no_backup:
            bak = timestamped_backup(farms_xml_path)
            if verbose:
                print(f"[info] Backup created: {bak}")
        if not dry_run:
            tree.write(farms_xml_path, encoding="utf-8", xml_declaration=True)
            if verbose:
                print(f"[ok] farms.xml finances values zeroed")
    elif verbose:
        print("[info] No finance values required changes.")
    return changed

# -------------------------
# Main workflow
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="FS25: adjust days-per-month; optional farms.xml stats/finances resets.")
    parser.add_argument("--save", required=True,
                        help="Save folder name (e.g., savegame1) or full path to a save folder.")
    parser.add_argument("--days", type=int,
                        help="Set days per month (daysPerPeriod). If omitted, no day change is applied.")
    parser.add_argument("--day", type=int, default=1,
                        help="Target day within current month after change (default: 1). Ignored with --keep-day.")
    parser.add_argument("--keep-day", action="store_true",
                        help="Keep the old day-in-month when changing days-per-month (clamped if needed).")
    parser.add_argument("--reset-stats", action="store_true",
                        help="Reset farms.xml <statistics> values to 0/0.000000 (keeps <farmId>).")
    parser.add_argument("--reset-finances", action="store_true",
                        help="Remove all <stats> entries inside <finances> for each farm in farms.xml.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing files.")
    parser.add_argument("--no-backup", action="store_true",
                        help="Do not create .bak backups before writing.")
    parser.add_argument("--verbose", action="store_true",
                        help="Verbose output.")
    args = parser.parse_args()

    save_dir = Path(args.save)
    if not save_dir.exists():
        common = Path.home() / "Documents" / "My Games" / "FarmingSimulator2025" / args.save
        if common.exists():
            save_dir = common
        else:
            rel = Path.cwd() / args.save
            if rel.exists():
                save_dir = rel
            else:
                raise FileNotFoundError(f"Could not resolve save directory from '{args.save}'.")
    if args.verbose:
        print(f"[info] Save directory: {save_dir}")

    # Independent operations on farms.xml
    if args.reset_stats or args.reset_finances:
        farms_xml = save_dir / "farms.xml"
        if args.reset_stats:
            reset_farm_statistics(farms_xml, verbose=args.verbose, dry_run=args.dry_run, no_backup=args.no_backup)
        if args.reset_finances:
            reset_farm_finances(farms_xml, verbose=args.verbose, dry_run=args.dry_run, no_backup=args.no_backup)

    # If no days change requested, stop here
    if args.days is None:
        if args.verbose:
            print("[info] No --days provided; skipping days-per-month adjustments.")
        return

    # environment.xml
    env_path = find_environment_xml(save_dir)
    ensure_exists(env_path, "environment.xml")
    if args.verbose:
        print(f"[info] Using environment.xml: {env_path}")

    tree = ET.parse(env_path)
    root = tree.getroot()

    # read old daysPerPeriod (default 3)
    current_days_node = root.find(f".//{PRIMARY_DAY_TAG}")
    if current_days_node is None:
        old_days = 3
    else:
        try:
            old_days = int((current_days_node.text or "3").strip())
        except Exception:
            old_days = 3

    new_days = args.days
    if args.verbose:
        print(f"[info] daysPerPeriod: old={old_days}, new={new_days}")

    # read currentDay (default 1)
    current_day_node = root.find(".//currentDay")
    if current_day_node is None:
        old_current = 1
    else:
        try:
            old_current = int((current_day_node.text or "1").strip())
        except Exception:
            old_current = 1
    if args.verbose:
        print(f"[info] currentDay (before): {old_current}")

    new_current = compute_new_current_day(
        old_current=old_current,
        old_days=old_days,
        new_days=new_days,
        keep_day=args.keep_day,
        target_day=args.day
    )
    if args.verbose:
        print(f"[info] currentDay (after):  {new_current}")

    set_days_per_period(root, new_days)

    current_day_node = root.find(".//currentDay")
    if current_day_node is None:
        parent = root.find(".//environment") or root
        current_day_node = ET.SubElement(parent, "currentDay")
    current_day_node.text = str(new_current)

    removed = clear_forecast(root)
    if args.verbose:
        print(f"[info] Cleared forecast entries: {removed}")

    if not args.dry_run and not args.no_backup:
        bak = timestamped_backup(env_path)
        if args.verbose:
            print(f"[info] Backup created: {bak}")
    if not args.dry_run:
        pretty_write_xml(tree, env_path)
        if args.verbose:
            print("[ok] environment.xml updated]")

    update_career_planned_days(save_dir, new_days, args.no_backup, args.dry_run, verbose=args.verbose)

    if args.verbose:
        print("[done] All requested operations completed.")

if __name__ == "__main__":
    main()
