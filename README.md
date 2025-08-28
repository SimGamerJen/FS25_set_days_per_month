````markdown
# FS25 Days Per Month Utility

This Python script updates **Farming Simulator 25** savegames to change the number of days per month (`daysPerPeriod`).  
It also recalculates the `currentDay` value to keep your save consistent with the new configuration, clears cached weather forecast data, and updates **careerSavegame.xml** so that the in-game UI matches your chosen setting.

---

## Features

- ✅ Update `daysPerPeriod` inside `environment.xml`
- ✅ Recompute `currentDay` based on the existing save values (correct for the default **August start** in new games)
- ✅ Clear forecast/lastUpdate entries so FS25 regenerates weather data correctly
- ✅ Update `plannedDaysPerPeriod` inside `careerSavegame.xml` so UI & engine stay in sync
- ✅ Optional dry-run mode to preview changes without writing
- ✅ Automatic `.bak.TIMESTAMP` backups before modifying files

---

## Usage

```bash
python set_days_per_month.py --save "path/to/savegame1" --days N [options]
````

### Required arguments

* `--save` : Path to your FS25 save folder (e.g. `.../FarmingSimulator2025/savegame1`)
* `--days` : Desired number of days per month (1–28)

### Optional arguments

* `--target-day` : Day within the target month to use when recalculating (default: 1)
* `--keep-day` : Keep the same day-in-month as before (clamped if necessary)
* `--no-backup` : Skip creation of `.bak` backup files
* `--dry-run` : Show calculations and changes without writing files

---

## Examples

Set 3 days per month, starting August Day 1 (fresh save example):

```bash
python set_days_per_month.py --save "E:/FS25/savegame1" --days 3
```

Keep the same day-in-month when moving to 7 days per month:

```bash
python set_days_per_month.py --save "E:/FS25/savegame1" --days 7 --keep-day
```

Preview what would happen with 5 days per month (no changes written):

```bash
python set_days_per_month.py --save "E:/FS25/savegame1" --days 5 --dry-run
```

---

## How It Works

* **currentDay recalculation**
  The script inspects the old values (e.g. `daysPerPeriod=1`, `currentDay=6` for a fresh save).
  It infers how many months have already elapsed since March (`months_before=5` in this case).
  With a new setting of 3 days per month, August Day 1 becomes:

  ```
  currentDay = (months_before * new_days) + target_day
             = (5 * 3) + 1
             = 16
  ```

  This keeps your timeline aligned.

* **careerSavegame.xml update**
  The `plannedDaysPerPeriod` field is updated so that the UI in FS25 reflects your new days-per-month setting.

* **forecast reset**
  Cached forecast nodes and lastUpdate timestamps are cleared to force FS25 to rebuild its weather on load.

---

## Roadmap

Planned or possible future extensions:

* 🔄 **Reset statistics and finances**
  Add an option to reset player stats and account balances by editing `farms.xml`.

* 📅 **Change the starting month (safely)**
  Support for jumping the starting month (e.g. from August to October).
  This will **require a full field reset** (deleting density maps) to avoid growth/contract desync.

* 📊 **Enhanced verification mode**
  Add a `--verify` option that prints before/after summaries of all relevant save values and highlights mismatches.

* 💾 **Multi-file sync**
  Optionally update `savegameSettings.xml` (used by some mods/maps) alongside `careerSavegame.xml`.

---

## Requirements

* Python 3.9+
* No third-party packages required (uses only Python standard library)

---

## Notes

* Run this script only when the game is **closed**.
* Backups (`.bak.TIMESTAMP`) are created automatically unless you pass `--no-backup`.
* Always test on a copy of your save first.

```

