from datetime import date, timedelta

MILESTONE_ACH = [(1,"d1"),(3,"d3"),(7,"d7"),(21,"d21"),(30,"d30"),(90,"d90"),(365,"d365")]

def compute_streak(logged: set[date], today: date) -> int:
    streak, day = 0, today if today in logged else today - timedelta(days=1)
    while day in logged:
        streak += 1
        day -= timedelta(days=1)
    return streak

def achievements_for(days_clean: int, streaks: dict[str, int], all_today: bool) -> list[str]:
    earned = [aid for days, aid in MILESTONE_ACH if days_clean >= days]
    if streaks.get("steps", 0) >= 10: earned.append("steps10")
    if streaks.get("sport", 0) >= 7:  earned.append("sport7")
    if streaks.get("read", 0) >= 7:   earned.append("read7")
    if all_today: earned.append("all3")
    return earned
