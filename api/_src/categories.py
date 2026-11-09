from enum import StrEnum
from typing import Any


class Category(StrEnum):
    """Hardcoded expense categories (spec §3, revised by
    `public/categories/Categories-Version2.md`). No categories table exists.

    Declaration order is the order the picker shows them in; the frontend's
    `CATEGORY_GROUPS` (src/lib/categories.tsx) mirrors it group by group."""

    # Food and drink
    DINING_OUT = "Dining out"
    TAKEOUT_DELIVERY = "Takeout/delivery"
    COFFEE_SNACKS = "Coffee & snacks"
    GROCERIES = "Groceries"
    ALCOHOL = "Alcohol"
    OTHER_FOOD_AND_DRINK = "Other Food and drink"
    # Personal care & health
    HYGIENE_COSMETICS = "Hygiene/cosmetics"
    HAIR_BEAUTY = "Hair/beauty"
    PHARMACY = "Pharmacy"
    MEDICAL_EXPENSES = "Medical expenses"
    OTHER_PERSONAL_CARE = "Other Personal care"
    # Clothing & footwear
    CLOTHING = "Clothing"
    FOOTWEAR = "Footwear"
    ACCESSORIES = "Accessories"
    OTHER_CLOTHING = "Other Clothing"
    # Entertainment and learning
    BOOKS = "Books"
    MOVIES = "Movies"
    MUSIC = "Music"
    GAMES = "Games"
    STREAMING = "Streaming"
    HOBBIES = "Hobbies"
    CONCERTS_EVENTS = "Concerts & events"
    OTHER_ENTERTAINMENT = "Other Entertainment"
    COURSES = "Courses"
    TUTOR = "Tutor"
    OTHER_LEARNING = "Other Learning"
    # Sports
    CLIMBING = "Climbing"
    SKIING = "Skiing"
    SWIMMING = "Swimming"
    RUNNING = "Running"
    BIKING = "Biking"
    GYM_FITNESS = "Gym/fitness"
    SPORTS_GEAR = "Sports gear"
    COMPETITIONS = "Competitions"
    OTHER_SPORTS = "Other Sports"
    # Transportation
    BUS_TRAIN = "Bus/train"
    HIGHWAYS = "Highways"
    GAS_FUEL = "Gas/fuel"
    CAR = "Car"
    PARKING = "Parking"
    TAXI = "Taxi"
    OTHER_TRANSPORTATION = "Other Transportation"
    # Travel and vacations
    FLIGHTS = "Flights"
    HOTEL = "Hotel"
    TRAVEL_TRANSPORT = "Travel transport"
    ATTRACTIONS_TOURS = "Attractions & tours"
    TRAVEL_INSURANCE_VISAS = "Travel insurance & visas"
    OTHER_TRAVEL = "Other Travel"
    # Tech, Software & AI
    PHONE = "Phone"
    INTERNET = "Internet"
    SOFTWARE = "Software"
    AI_SUBSCRIPTIONS = "AI subscriptions"
    LLM_APIS = "LLM APIs"
    CLOUD_HOSTING = "Cloud & hosting"
    MEMBERSHIPS = "Memberships"
    OTHER_TECH = "Other Tech"
    # Home
    RENT = "Rent"
    MORTGAGE = "Mortgage"
    BUILDING_FEES = "Building fees"
    BILLS = "Bills"
    MAINTENANCE = "Maintenance"
    OTHER_HOME = "Other Home"
    # Appliances
    APPLIANCES = "Appliances"
    ELECTRONICS = "Electronics"
    FURNITURE = "Furniture"
    HOUSEHOLD_SUPPLIES = "Household supplies"
    OTHER_APPLIANCES = "Other Appliances"
    # Finance and life
    BANK_FEES = "Bank fees"
    INSURANCE = "Insurance"
    TAXES = "Taxes"
    GIFTS = "Gifts"
    CHILDCARE = "Childcare"
    OTHER_LIFE = "Other Life"
    # Uncategorized
    BIG_PURCHASES = "Big purchases"
    GENERAL = "General"


# Values the first category list used that the revised one dropped, and where
# each one went. Migration 20261105000000 rewrote stored rows with exactly this
# table; it stays here so a request from a client still running the old bundle
# (an installed PWA updates on its own schedule) is translated instead of
# refused with a 422. Keep it in sync with that migration — a test checks.
LEGACY_CATEGORIES: dict[str, Category] = {
    "Sports": Category.OTHER_SPORTS,
    "Liquor": Category.ALCOHOL,
    "Pets": Category.OTHER_HOME,
    "Services": Category.OTHER_HOME,
    "Education": Category.OTHER_LEARNING,
    "Bicycle": Category.OTHER_TRANSPORTATION,
    "Plane": Category.FLIGHTS,
    "Cleaning": Category.HOUSEHOLD_SUPPLIES,
    "Electricity": Category.BILLS,
    "Heat/gas": Category.BILLS,
    "Trash": Category.BILLS,
    "Water": Category.BILLS,
    "Other Utilities": Category.BILLS,
    "TV/Phone/Internet": Category.INTERNET,
    "Other Subscriptions": Category.MEMBERSHIPS,
    "Copilots": Category.AI_SUBSCRIPTIONS,
    "Generation Tools": Category.AI_SUBSCRIPTIONS,
    "Other AI Expenses": Category.OTHER_TECH,
}


def upgrade_legacy_category(value: Any) -> Any:
    """Pydantic before-validator: swap a retired value for its replacement and
    pass everything else through for the enum to judge."""
    if isinstance(value, str):
        return LEGACY_CATEGORIES.get(value, value)
    return value
