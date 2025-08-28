# FS25 Save Utilities – Days Per Month & Farm Resets

A utility script for **Farming Simulator 25** savegames.

This script helps you:
- Change **days-per-month** (daysPerPeriod) in `environment.xml`.
- Recalculate **currentDay** to preserve elapsed months when changing day length.
- Clear cached **weather forecasts** so the game regenerates them on load.
- Sync **plannedDaysPerPeriod** in `careerSavegame.xml`.
- Reset **farm statistics** in `farms.xml` to zeros (without touching `<farmId>`).
- Reset **farm finances** in `farms.xml` by zeroing all `<stats>` values inside `<finances>`.

---

## Features

- **Days-per-month change**
  - Adjusts `<daysPerPeriod>` to your desired length.
  - Recomputes `<currentDay>` so progress stays consistent.
  - Optionally keep the old day-in-month (`--keep-day`) or pick a new target day (`--day`).
  - Clears forecast caches for consistency.
  - Updates `careerSavegame.xml`’s `<plannedDaysPerPeriod>`.

- **Statistics reset**
  - `--reset-stats` zeros all values inside `<statistics>` for each farm.
  - Preserves number style: `0` (integers) vs. `0.000000` (floats).
  - Never touches `<farmId>`.

- **Finances reset**
  - `--reset-finances` zeros all values inside `<finances><stats>` blocks for each farm.
  - Preserves number style as above.
  - Keeps the `<finances>` structure intact.

- **Safety**
  - Timestamped `.bak` backups unless `--no-backup` is set.
  - `--dry-run` mode to preview changes without touching files.
  - Verbose output with `--verbose`.

---

## Usage

```powershell
# Change to 3 days per month
py .\set_days_per_month.py --save savegame1 --days 3 --verbose

# Keep old day-in-month when changing
py .\set_days_per_month.py --save savegame1 --days 3 --keep-day --verbose

# Reset farm statistics only
py .\set_days_per_month.py --save savegame1 --reset-stats --verbose

# Reset farm finances only
py .\set_days_per_month.py --save savegame1 --reset-finances --verbose

# Reset both stats and finances
py .\set_days_per_month.py --save savegame1 --reset-stats --reset-finances --verbose

# Combine days change with resets
py .\set_days_per_month.py --save savegame1 --days 3 --reset-stats --reset-finances --verbose

# Preview (no file writes)
py .\set_days_per_month.py --save savegame1 --days 3 --reset-stats --dry-run --verbose
````

---

## Roadmap

Planned enhancements:

* **Farm reset suite**:

  * More granular reset options (e.g., per-stat, per-finance-year).
* **Save sanitization**:

  * Detect corrupted or missing XML nodes and auto-repair them.
* **Configurable starting month**:

  * Ability to change the campaign’s starting month (with a fields reset).
* **Extended resets**:

  * Optional reset of mission history, statistics for specific categories, or crop growth.

---

## Disclaimer

This script modifies your save files. Always make backups before running it on important saves.
The script attempts to back up files automatically with a timestamped `.bak` extension.
