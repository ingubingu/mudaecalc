import json
from dataclasses import dataclass, field
import os
from fastapi import FastAPI
from fastapi import Form
from typing import Optional
app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


CARD_TOTAL = 43848
DOTJSON = ".json"
PROFILE_DIR = "profiles"

# ====================================================================
# 1. Data Structures using dataclasses
# ====================================================================

@dataclass
class PlayerStats:
    """Stores all player statistics."""
    rolls: int = 10
    w_slots: int = 5
    sw_slots: int = 1
    w_boost: float = 0.0  # Changed to float for better math
    sw_boost: float = 0.0
    disabled_cards: int = 0
    cards_left: int = CARD_TOTAL
    cards_claimed: int = 0
    kp_limit: int = 100
    kp_usage: int = 100
    kp_bonus: int = 0
    og_server: bool = False
    tuto_lvl: int = 0
    persrare: int = 1

    @property
    def cards_available(self) -> int:
        """Helper property to calculate available cards dynamically."""
        return self.cards_left - self.disabled_cards
    
    def update_claimed(self):
        """Calculates cards claimed based on cards left."""
        self.cards_claimed = CARD_TOTAL - self.cards_left

@dataclass
class Odds:
    """Stores calculated odds."""
    specific_roll_odds: float = 0.0
    specific_wish_odds: float = 0.0
    wish_odds: float = 0.0
    star_wish_odds: float = 0.0
    kspawn_odds: float = 0.0

# ====================================================================
# 2. Upgrade Classes (Remain largely the same logic)
# ====================================================================

class Upgrade:
    def apply_effect(self, stats: PlayerStats, level: int):
        pass

class BronzeUpgrade(Upgrade):
    def apply_effect(self, stats: PlayerStats, level: int):
        stats.w_slots += level * 1

class SilverUpgrade(Upgrade):
    def apply_effect(self, stats: PlayerStats, level: int):
        stats.w_boost += level * 25

class GoldUpgrade(Upgrade):
    def apply_effect(self, stats: PlayerStats, level: int):
        stats.kp_usage -= level * 10

class SapphireUpgrade(Upgrade):
    def apply_effect(self, stats: PlayerStats, level: int):
        stats.rolls += level * 1

class RubyUpgrade(Upgrade):
    def apply_effect(self, stats: PlayerStats, level: int):
        if level >= 1: stats.w_slots += 2
        if level >= 2: stats.w_boost += 50
        if level >= 3: stats.kp_usage -= 20
        if level >= 4: stats.rolls += 2

UPGRADE_MAP = {
    "Bronze": BronzeUpgrade(), 
    "Silver": SilverUpgrade(), 
    "Gold": GoldUpgrade(),
    "Sapphire": SapphireUpgrade(),
    "Ruby": RubyUpgrade(),
    # "Emerald" has no class, so it's safely ignored later
}


# ====================================================================
# 3. Main Logic Encapsulated in Functions
# ====================================================================

def compute_effective_stats(base_stats: PlayerStats, upgrades: dict) -> PlayerStats:
    # Create a COPY of stats so we don't mutate the base version
    stats = PlayerStats(**vars(base_stats))

    # Apply upgrades
    for name, level in upgrades.items():
        if level > 0 and name in UPGRADE_MAP:
            UPGRADE_MAP[name].apply_effect(stats, level)

    # Apply OG bonus
    if stats.og_server:
        stats.rolls += 3

    # Apply tutorial boost
    tuto_check(stats)

    # Recompute cards claimed
    stats.update_claimed()

    return stats


def tuto_check(stats: PlayerStats):
    """Adjusts stats based on tutorial level."""
    if stats.tuto_lvl >= 16:
        stats.sw_boost += 100
    elif stats.tuto_lvl >= 10:
        stats.sw_boost += 50

def calculate_odds(stats: PlayerStats) -> Odds:
    cards_available = stats.cards_available
    if cards_available <= 0:
        return Odds()

    base = 1.0 / cards_available

    # Interpret boosts as percentages
    wish_mult = 1.0 + stats.w_boost / 100.0
    star_mult = 1.0 + (stats.w_boost + stats.sw_boost) / 100.0

    # Specific card odds
    specific_roll_odds = base
    specific_wish_odds = base * wish_mult

    # Any wish (non-star)
    normal_wish_slots = max(0, stats.w_slots - stats.sw_slots)
    wish_odds = normal_wish_slots * base * wish_mult

    # Any star wish
    star_wish_odds = stats.sw_slots * base * star_mult

    # Kakera spawn – still using your structure but clamped to [0,1]
    k_raw = (stats.cards_claimed * (50.0 / max(1, stats.persrare))) / cards_available
    kspawn_odds = max(0.0, min(1.0, k_raw))

    return Odds(
        specific_roll_odds=specific_roll_odds,
        specific_wish_odds=specific_wish_odds,
        wish_odds=wish_odds,
        star_wish_odds=star_wish_odds,
        kspawn_odds=kspawn_odds,
    )


@app.post("/apply_upgrades")
def apply_upgrades_and_prompts(
    Bronze: int = Form(...),
    Silver: int = Form(...),
    Gold: int = Form(...),
    Sapphire: int = Form(...),
    Ruby: int = Form(...),

    disabled_cards: int = Form(...),
    cards_left: int = Form(...),
    og_server: int = Form(...),
    tuto_lvl: int = Form(...),
    persrare: int = Form(...)
):
    # Base stats (NOT upgraded)
    base_stats = PlayerStats(
        disabled_cards=disabled_cards,
        cards_left=cards_left,
        og_server=bool(og_server),
        tuto_lvl=tuto_lvl,
        persrare=persrare
    )

    # Upgrade levels
    upgrades = {
        "Bronze": Bronze,
        "Silver": Silver,
        "Gold": Gold,
        "Sapphire": Sapphire,
        "Ruby": Ruby,
    }

    # Compute upgraded stats
    effective_stats = compute_effective_stats(base_stats, upgrades)
    odds = calculate_odds(effective_stats)
    return {
        "base_stats": vars(base_stats),
        "upgraded_stats": vars(effective_stats),
        "upgrades": upgrades,
        "odds": vars(odds)
    }


def create_profile_file(path, stats: PlayerStats, upgrades_input: dict):
    """Saves current stats and upgrade levels to a JSON file."""
    data_to_save = {
        "stats": vars(stats), # vars() converts dataclass to dict
        "upgrades": upgrades_input
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, indent=4)
        print(f"\nProfile created and saved at {path}")

def load_profile_file(path) -> tuple[PlayerStats, dict]:
    """Loads a profile from JSON and returns stats/upgrades objects."""
    with open(path, 'r') as f:
        loaded_data = json.load(f)
    
    # Recreate the dataclass object from the loaded dict
    loaded_stats = PlayerStats(**loaded_data["stats"])
    loaded_upgrades = loaded_data.get("upgrades", {}) # Handle case where upgrades weren't saved
    return loaded_stats, loaded_upgrades

@app.get("/prompts")
def user_prompts():
    while True:
        temp = input("Load or Create Profile? (1/2, Q to quit): ").lower()
        if temp == 'q':
            break
        
        current_stats = PlayerStats() # Start with default stats
        upgrades_used = {}

        if temp == "1":
            filename = input("Enter the filename for the profile: ") + DOTJSON
            if os.path.exists(filename):
                try:
                    current_stats, upgrades_used = load_profile_file(filename)
                    print(f"Profile {filename} loaded successfully.")
                except json.JSONDecodeError:
                    print(f"Error reading JSON from {filename}.")
                    continue
            else:
                print(f"File not found: {filename}")
                continue
                
        elif temp == "2":
            print("Creating new profile...")
            # This function modifies current_stats in place
            upgrades_used = apply_upgrades_and_prompts(current_stats)
            filename = input("Enter the filename to save as: ") + DOTJSON
            create_profile_file(filename, current_stats, upgrades_used)
        
        else:
            print("Invalid option.")
            continue
        
        # Display Final Stats
        print("\n--- Current Stats ---")
        for stat, value in vars(current_stats).items():
            print(f"{stat.ljust(15)}: {value}")
        
       
        # Calculate and Display Odds
        current_odds = calculate_odds(current_stats)
        rph = current_stats.rolls
        rpd = rph * 24
        print("\n--- Per Roll Odds ---")
        for key, value in vars(current_odds).items():
            print(f"{key.ljust(20)}: {(value):.4f}")
        print("\n--- Per Roll Set Odds ---")
        for key, value in vars(current_odds).items():
            print(f"{key.ljust(20)}: {value * rph:.2f}")
        print("\n--- Per Day Odds ---")
        for key, value in vars(current_odds).items():
            print(f"{key.ljust(20)}: {value * rpd:.2f}")
        
        # Exit loop after processing
        break
# Ensure folder exists
os.makedirs(PROFILE_DIR, exist_ok=True)


@app.get("/profiles")
def list_profiles():
    """Return list of profile JSON filenames inside profiles/."""
    files = [
        f for f in os.listdir(PROFILE_DIR)
        if f.endswith(".json")
    ]
    return {"profiles": files}


@app.get("/load_profile")
def load_profile(filename: str):
    path = os.path.join(PROFILE_DIR, filename)

    if not os.path.exists(path):
        return {"error": "File not found"}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    base_stats = PlayerStats(**data["stats"])
    upgrades = data["upgrades"]

    effective_stats = compute_effective_stats(base_stats, upgrades)

    return {
        "base_stats": vars(base_stats),
        "upgraded_stats": vars(effective_stats),
        "upgrades": upgrades
    }


@app.post("/save_profile")
def save_profile(
    name: str = Form(...),
    data: str = Form(...)
):
    """Save a profile JSON file into profiles/."""
    filename = name + ".json"
    path = os.path.join(PROFILE_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(data)

    return {"saved": filename}


if __name__ == "__main__":
    user_prompts()
