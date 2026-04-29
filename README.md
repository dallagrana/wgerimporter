# wger importer

Migrates all personal data from one [wger](https://wger.de) instance to another using the REST API.

## What gets migrated

| # | Data |
|---|------|
| 1 | Weight entries |
| 2 | Measurement categories |
| 3 | Measurements |
| 4 | Nutrition plans |
| 5 | Meals |
| 6 | Meal items |
| 7 | Nutrition diary |
| 8 | Routines, days, slots, and slot entries |
| 9 | Slot configs (weight / reps / sets / rest / RIR, including max variants) |
| 10 | Workout sessions and logs |

## Requirements

```
pip install requests
```

## Setup

1. Open `migrate.py` and set the four constants at the top:

```python
REMOTE_BASE  = "https://wger.de/api/v2"         # source instance
LOCAL_BASE   = "http://<YOUR_LOCAL_HOST>/api/v2" # destination instance
REMOTE_TOKEN = "<YOUR_REMOTE_API_TOKEN>"
LOCAL_TOKEN  = "<YOUR_LOCAL_API_TOKEN>"
```

2. **Get your API tokens** — on each instance go to:
   `Settings → API → Generate new token`
   (URL: `<instance>/en/user/token`)

## Usage

```bash
python migrate.py
```

The script prints progress for each section and a final summary.

## Notes

- **Read-only on the source** — the script never modifies the remote instance.
- **Ingredients and exercises are not migrated.** They are referenced by their global wger ID and are assumed to already exist on the target (via the built-in ingredient database or a prior sync).
- **No deduplication.** Running the script twice will create duplicate entries. Clean the target instance first if you need to re-run.
