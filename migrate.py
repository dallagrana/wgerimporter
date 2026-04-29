#!/usr/bin/env python3
"""
wger data migration script
==========================
Migrates all personal data from one wger instance to another using the REST API.

Covered endpoints (in order):
  1.  Weight entries
  2.  Measurement categories
  3.  Measurements
  4.  Nutrition plans
  5.  Meals
  6.  Meal items
  7.  Nutrition diary
  8.  Routines, days, slots, and slot entries
  9.  Slot configs (weight / reps / sets / rest / RIR, including max variants)
  10. Workout sessions and logs

Requirements:
  pip install requests

Usage:
  1. Set the four constants below (REMOTE_BASE, LOCAL_BASE,
     REMOTE_TOKEN, LOCAL_TOKEN).
  2. Run:  python migrate.py

Notes:
  - The script is intentionally read-only on the remote side and
    write-only on the local side; it never modifies the source.
  - Ingredients are referenced by their global wger ID and are not
    migrated (they are assumed to exist on the target instance via
    the built-in ingredient database or a prior sync).
  - Exercises are also referenced by ID and assumed to exist on the
    target instance.
  - Running the script twice will create duplicate entries. There is
    no upsert / dedup logic — clean the target first if needed.
"""

import requests

# ── Configuration ─────────────────────────────────────────────────────────────
# Base URLs for the source (remote) and destination (local) wger instances.
# No trailing slash.
REMOTE_BASE = "https://wger.de/api/v2"          # source instance
LOCAL_BASE  = "http://<YOUR_LOCAL_HOST>/api/v2"  # destination instance

# API tokens.  Generate them at:
#   <instance>/en/user/<id>/trainer-login  →  API tab  →  "Generate new token"
REMOTE_TOKEN = "<YOUR_REMOTE_API_TOKEN>"
LOCAL_TOKEN  = "<YOUR_LOCAL_API_TOKEN>"
# ──────────────────────────────────────────────────────────────────────────────

remote_h = {"Authorization": f"Token {REMOTE_TOKEN}"}
local_h  = {"Authorization": f"Token {LOCAL_TOKEN}", "Content-Type": "application/json"}

# Remote ID -> local ID maps (populated as objects are created)
plan_map       = {}
meal_map       = {}
cat_map        = {}
routine_map    = {}
day_map        = {}
slot_map       = {}
slot_entry_map = {}
session_map    = {}


def fetch_all(base, endpoint, headers):
    """Fetch every page of a paginated API endpoint and return a flat list."""
    items, url = [], f"{base}/{endpoint}/?format=json&limit=100"
    while url:
        for attempt in range(4):
            try:
                r = requests.get(url, headers=headers, timeout=60)
                r.raise_for_status()
                break
            except requests.exceptions.Timeout:
                if attempt == 3:
                    raise
                print(f"    timeout, retrying {endpoint}...")
        data = r.json()
        if isinstance(data, list):
            return data
        items.extend(data.get("results", []))
        url = data.get("next")
    return items


def post(endpoint, payload):
    """POST payload to the local instance, stripping None values first."""
    clean = {k: v for k, v in payload.items() if v is not None}
    r = requests.post(f"{LOCAL_BASE}/{endpoint}/", headers=local_h, json=clean, timeout=30)
    if not r.ok:
        print(f"    ERR {r.status_code} [{endpoint}]: {r.text[:200]}")
        return None
    return r.json()


def section(title):
    print(f"\n{'─'*58}\n  {title}\n{'─'*58}")


# ── 1. Weight entries ─────────────────────────────────────────────────────────
section("1/10  Weight entries")
entries = fetch_all(REMOTE_BASE, "weightentry", remote_h)
ok = sum(1 for e in entries if post("weightentry", {"date": e["date"], "weight": e["weight"]}))
print(f"  {ok}/{len(entries)} imported")

# ── 2. Measurement categories ─────────────────────────────────────────────────
section("2/10  Measurement categories")
cats = fetch_all(REMOTE_BASE, "measurement-category", remote_h)
ok = 0
for c in cats:
    r = post("measurement-category", {"name": c["name"], "unit": c["unit"]})
    if r:
        cat_map[c["id"]] = r["id"]
        ok += 1
print(f"  {ok}/{len(cats)} imported")

# ── 3. Measurements ───────────────────────────────────────────────────────────
section("3/10  Measurements")
measurements = fetch_all(REMOTE_BASE, "measurement", remote_h)
ok = 0
for m in measurements:
    local_cat = cat_map.get(m["category"])
    if not local_cat:
        print(f"    SKIP: unknown category {m['category']}")
        continue
    r = post("measurement", {
        "category": local_cat,
        "date":     m["date"],
        "value":    m["value"],
        "notes":    m.get("notes", ""),
    })
    if r:
        ok += 1
print(f"  {ok}/{len(measurements)} imported")

# ── 4. Nutrition plans ────────────────────────────────────────────────────────
section("4/10  Nutrition plans")
plans = fetch_all(REMOTE_BASE, "nutritionplan", remote_h)
ok = 0
for p in plans:
    r = post("nutritionplan", {
        "description":        p.get("description", ""),
        "creation_date":      p.get("creation_date"),
        "only_log":           p.get("only_log", False),
        "goal_energy":        p.get("goal_energy"),
        "goal_protein":       p.get("goal_protein"),
        "goal_carbohydrates": p.get("goal_carbohydrates"),
        "goal_fat":           p.get("goal_fat"),
        "goal_fiber":         p.get("goal_fiber"),
    })
    if r:
        plan_map[p["id"]] = r["id"]
        ok += 1
print(f"  {ok}/{len(plans)} imported")

# ── 5. Meals ──────────────────────────────────────────────────────────────────
section("5/10  Meals")
meals = fetch_all(REMOTE_BASE, "meal", remote_h)
ok = 0
for m in meals:
    local_plan = plan_map.get(m["plan"])
    if not local_plan:
        print(f"    SKIP meal {m['id']}: unknown plan {m['plan']}")
        continue
    r = post("meal", {"plan": local_plan, "name": m.get("name", ""), "time": m.get("time")})
    if r:
        meal_map[m["id"]] = r["id"]
        ok += 1
print(f"  {ok}/{len(meals)} imported")

# ── 6. Meal items ─────────────────────────────────────────────────────────────
section("6/10  Meal items")
items = fetch_all(REMOTE_BASE, "mealitem", remote_h)
ok = 0
for i in items:
    local_meal = meal_map.get(i["meal"])
    if not local_meal:
        print(f"    SKIP mealitem {i['id']}: unknown meal {i['meal']}")
        continue
    r = post("mealitem", {
        "meal":        local_meal,
        "ingredient":  i["ingredient"],
        "amount":      i["amount"],
        "weight_unit": i.get("weight_unit"),
    })
    if r:
        ok += 1
print(f"  {ok}/{len(items)} imported")

# ── 7. Nutrition diary ────────────────────────────────────────────────────────
section("7/10  Nutrition diary")
diary = fetch_all(REMOTE_BASE, "nutritiondiary", remote_h)
ok = 0
for d in diary:
    local_plan = plan_map.get(d.get("plan"))
    if not local_plan:
        continue
    r = post("nutritiondiary", {
        "plan":        local_plan,
        "ingredient":  d["ingredient"],
        "weight_unit": d.get("weight_unit"),
        "datetime":    d["datetime"],
        "amount":      d["amount"],
    })
    if r:
        ok += 1
print(f"  {ok}/{len(diary)} imported")

# ── 8. Routines, days, slots, slot entries ────────────────────────────────────
section("8/10  Routines + days + slots + slot-entries")
routines = fetch_all(REMOTE_BASE, "routine", remote_h)
ok = 0
for rt in routines:
    r = post("routine", {
        "name":        rt.get("name", ""),
        "description": rt.get("description", ""),
        "start":       rt.get("start"),
        "end":         rt.get("end"),
        "fit_in_week": rt.get("fit_in_week", True),
        "is_public":   rt.get("is_public", False),
    })
    if r:
        routine_map[rt["id"]] = r["id"]
        ok += 1
print(f"  Routines:     {ok}/{len(routines)}")

days = fetch_all(REMOTE_BASE, "day", remote_h)
ok = 0
for d in days:
    local_rt = routine_map.get(d.get("routine"))
    if not local_rt:
        continue
    r = post("day", {
        "routine":              local_rt,
        "name":                 d.get("name", ""),
        "description":          d.get("description", ""),
        "order":                d.get("order", 1),
        "is_rest":              d.get("is_rest", False),
        "need_logs_to_advance": d.get("need_logs_to_advance", False),
        "type":                 d.get("type", "custom"),
    })
    if r:
        day_map[d["id"]] = r["id"]
        ok += 1
print(f"  Days:         {ok}/{len(days)}")

slots = fetch_all(REMOTE_BASE, "slot", remote_h)
ok = 0
for s in slots:
    local_day = day_map.get(s.get("day"))
    if not local_day:
        continue
    r = post("slot", {"day": local_day, "order": s.get("order", 1), "comment": s.get("comment", "")})
    if r:
        slot_map[s["id"]] = r["id"]
        ok += 1
print(f"  Slots:        {ok}/{len(slots)}")

slot_entries = fetch_all(REMOTE_BASE, "slot-entry", remote_h)
ok = 0
for se in slot_entries:
    local_slot = slot_map.get(se.get("slot"))
    if not local_slot:
        continue
    r = post("slot-entry", {
        "slot":                local_slot,
        "exercise":            se["exercise"],
        "order":               se.get("order", 1),
        "type":                se.get("type", "normal"),
        "repetition_unit":     se.get("repetition_unit", 1),
        "repetition_rounding": se.get("repetition_rounding"),
        "weight_unit":         se.get("weight_unit", 1),
        "weight_rounding":     se.get("weight_rounding"),
        "comment":             se.get("comment", ""),
    })
    if r:
        slot_entry_map[se["id"]] = r["id"]
        ok += 1
print(f"  Slot entries: {ok}/{len(slot_entries)}")

# ── 9. Slot configs ───────────────────────────────────────────────────────────
section("9/10  Slot configs (weight / reps / sets / rest / rir)")
config_endpoints = [
    "weight-config",      "max-weight-config",
    "repetitions-config", "max-repetitions-config",
    "sets-config",        "max-sets-config",
    "rest-config",        "max-rest-config",
    "rir-config",         "max-rir-config",
]
for ep in config_endpoints:
    cfgs = fetch_all(REMOTE_BASE, ep, remote_h)
    if not cfgs:
        continue
    ok = 0
    for cfg in cfgs:
        local_se = slot_entry_map.get(cfg.get("slot_entry"))
        if not local_se:
            continue
        payload = {k: v for k, v in cfg.items() if k not in ("id", "slot_entry")}
        payload["slot_entry"] = local_se
        r = post(ep, payload)
        if r:
            ok += 1
    print(f"  {ep}: {ok}/{len(cfgs)}")

# ── 10. Workout sessions and logs ─────────────────────────────────────────────
section("10/10  Workout sessions + logs")
sessions = fetch_all(REMOTE_BASE, "workoutsession", remote_h)
ok = 0
for s in sessions:
    r = post("workoutsession", {
        "date":       s["date"],
        "notes":      s.get("notes", ""),
        "impression": s.get("impression", "3"),
        "time_start": s.get("time_start"),
        "time_end":   s.get("time_end"),
    })
    if r:
        session_map[s["id"]] = r["id"]
        ok += 1
print(f"  Sessions: {ok}/{len(sessions)}")

logs = fetch_all(REMOTE_BASE, "workoutlog", remote_h)
ok = 0
for l in logs:
    r = post("workoutlog", {
        "exercise":        l["exercise"],
        "workoutsession":  session_map.get(l.get("workoutsession")),
        "repetitions":     l.get("repetitions"),
        "repetition_unit": l.get("repetition_unit", 1),
        "weight":          l.get("weight"),
        "weight_unit":     l.get("weight_unit", 1),
        "date":            l["date"],
        "rir":             l.get("rir"),
    })
    if r:
        ok += 1
print(f"  Logs:     {ok}/{len(logs)}")

print(f"\n{'═'*58}")
print("  Migration complete!")
print(f"{'═'*58}\n")
