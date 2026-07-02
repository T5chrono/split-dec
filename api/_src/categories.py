from enum import StrEnum


class Category(StrEnum):
    """Hardcoded expense categories (spec §3). No categories table exists."""

    # Entertainment
    GAMES = "Games"
    MOVIES = "Movies"
    MUSIC = "Music"
    SPORTS = "Sports"
    OTHER_ENTERTAINMENT = "Other Entertainment"
    # Food and drink
    DINING_OUT = "Dining out"
    GROCERIES = "Groceries"
    LIQUOR = "Liquor"
    OTHER_FOOD_AND_DRINK = "Other Food and drink"
    # Home
    ELECTRONICS = "Electronics"
    FURNITURE = "Furniture"
    HOUSEHOLD_SUPPLIES = "Household supplies"
    MAINTENANCE = "Maintenance"
    MORTGAGE = "Mortgage"
    PETS = "Pets"
    RENT = "Rent"
    SERVICES = "Services"
    OTHER_HOME = "Other Home"
    # Life
    CHILDCARE = "Childcare"
    CLOTHING = "Clothing"
    EDUCATION = "Education"
    GIFTS = "Gifts"
    INSURANCE = "Insurance"
    MEDICAL_EXPENSES = "Medical expenses"
    TAXES = "Taxes"
    OTHER_LIFE = "Other Life"
    # Transportation
    BICYCLE = "Bicycle"
    BUS_TRAIN = "Bus/train"
    CAR = "Car"
    GAS_FUEL = "Gas/fuel"
    HOTEL = "Hotel"
    PARKING = "Parking"
    PLANE = "Plane"
    TAXI = "Taxi"
    OTHER_TRANSPORTATION = "Other Transportation"
    # Utilities
    CLEANING = "Cleaning"
    ELECTRICITY = "Electricity"
    HEAT_GAS = "Heat/gas"
    TRASH = "Trash"
    TV_PHONE_INTERNET = "TV/Phone/Internet"
    WATER = "Water"
    OTHER_UTILITIES = "Other Utilities"
    # Subscriptions
    SOFTWARE = "Software"
    STREAMING = "Streaming"
    MEMBERSHIPS = "Memberships"
    OTHER_SUBSCRIPTIONS = "Other Subscriptions"
    # Learning
    TUTOR = "Tutor"
    COURSES = "Courses"
    BOOKS = "Books"
    OTHER_LEARNING = "Other Learning"
    # AI Expenses
    LLM_APIS = "LLM APIs"
    COPILOTS = "Copilots"
    GENERATION_TOOLS = "Generation Tools"
    OTHER_AI_EXPENSES = "Other AI Expenses"
    # Uncategorized
    GENERAL = "General"
