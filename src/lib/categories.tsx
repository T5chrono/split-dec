import type { LucideIcon } from "lucide-react";
import {
  UtensilsCrossed, ShoppingBag, Coffee, ShoppingCart, Wine, CupSoda,
  Bath, Scissors, Pill, Stethoscope, HeartPulse,
  Shirt, SportShoe, Watch, Tags,
  Book, Film, Music, Gamepad2, Clapperboard, Palette, Ticket, Sparkles,
  GraduationCap, UserRound, Lightbulb,
  Mountain, MountainSnow, Waves, Footprints, Bike, Dumbbell, Volleyball, Trophy, Medal,
  TrainFront, Milestone, Fuel, Car, CircleParking, CarTaxiFront, Ship,
  Plane, Hotel, CarFront, FerrisWheel, Stamp, Luggage,
  Smartphone, Wifi, AppWindow, WandSparkles, Bot, Cloud, IdCard, Cpu,
  KeyRound, Landmark, Building2, Zap, WashingMachine, MonitorSmartphone, Armchair, SprayCan,
  Wrench, House, Lamp,
  CreditCard, ShieldCheck, Receipt, Gift, Baby, Scale,
  Gem, CircleDollarSign,
} from "lucide-react";

/** Immutable mapping of backend category values to lucide-react icons (spec §3,
 *  revised by public/categories/Categories-Version2.md). Group and category
 *  order is the order of that document, which is also the order of the
 *  backend's `Category` enum (api/_src/categories.py). */
export const CATEGORY_GROUPS: ReadonlyArray<{
  group: string;
  categories: ReadonlyArray<{ value: string; icon: LucideIcon }>;
}> = [
  {
    group: "Food and drink",
    categories: [
      { value: "Dining out", icon: UtensilsCrossed },
      { value: "Takeout/delivery", icon: ShoppingBag },
      { value: "Coffee & snacks", icon: Coffee },
      { value: "Groceries", icon: ShoppingCart },
      { value: "Alcohol", icon: Wine },
      { value: "Other Food and drink", icon: CupSoda },
    ],
  },
  {
    group: "Personal care & health",
    categories: [
      { value: "Hygiene/cosmetics", icon: Bath },
      { value: "Hair/beauty", icon: Scissors },
      { value: "Pharmacy", icon: Pill },
      { value: "Medical expenses", icon: Stethoscope },
      { value: "Other Personal care", icon: HeartPulse },
    ],
  },
  {
    group: "Clothing & footwear",
    categories: [
      { value: "Clothing", icon: Shirt },
      { value: "Footwear", icon: SportShoe },
      { value: "Accessories", icon: Watch },
      { value: "Other Clothing", icon: Tags },
    ],
  },
  {
    group: "Entertainment and learning",
    categories: [
      { value: "Books", icon: Book },
      { value: "Movies", icon: Film },
      { value: "Music", icon: Music },
      { value: "Games", icon: Gamepad2 },
      { value: "Streaming", icon: Clapperboard },
      { value: "Hobbies", icon: Palette },
      { value: "Concerts & events", icon: Ticket },
      { value: "Other Entertainment", icon: Sparkles },
      { value: "Courses", icon: GraduationCap },
      { value: "Tutor", icon: UserRound },
      { value: "Other Learning", icon: Lightbulb },
    ],
  },
  {
    group: "Sports",
    categories: [
      { value: "Climbing", icon: Mountain },
      { value: "Skiing", icon: MountainSnow },
      { value: "Swimming", icon: Waves },
      { value: "Running", icon: Footprints },
      { value: "Biking", icon: Bike },
      { value: "Gym/fitness", icon: Dumbbell },
      { value: "Sports gear", icon: Volleyball },
      { value: "Competitions", icon: Trophy },
      { value: "Other Sports", icon: Medal },
    ],
  },
  {
    group: "Transportation",
    categories: [
      { value: "Bus/train", icon: TrainFront },
      { value: "Highways", icon: Milestone },
      { value: "Gas/fuel", icon: Fuel },
      { value: "Car", icon: Car },
      { value: "Parking", icon: CircleParking },
      { value: "Taxi", icon: CarTaxiFront },
      { value: "Other Transportation", icon: Ship },
    ],
  },
  {
    group: "Travel and vacations",
    categories: [
      { value: "Flights", icon: Plane },
      { value: "Hotel", icon: Hotel },
      { value: "Travel transport", icon: CarFront },
      { value: "Attractions & tours", icon: FerrisWheel },
      { value: "Travel insurance & visas", icon: Stamp },
      { value: "Other Travel", icon: Luggage },
    ],
  },
  {
    group: "Tech, Software & AI",
    categories: [
      { value: "Phone", icon: Smartphone },
      { value: "Internet", icon: Wifi },
      { value: "Software", icon: AppWindow },
      { value: "AI subscriptions", icon: WandSparkles },
      { value: "LLM APIs", icon: Bot },
      { value: "Cloud & hosting", icon: Cloud },
      { value: "Memberships", icon: IdCard },
      { value: "Other Tech", icon: Cpu },
    ],
  },
  {
    group: "Home",
    categories: [
      { value: "Rent", icon: KeyRound },
      { value: "Mortgage", icon: Landmark },
      { value: "Building fees", icon: Building2 },
      { value: "Bills", icon: Zap },
      { value: "Maintenance", icon: Wrench },
      { value: "Other Home", icon: House },
    ],
  },
  {
    group: "Appliances",
    categories: [
      { value: "Appliances", icon: WashingMachine },
      { value: "Electronics", icon: MonitorSmartphone },
      { value: "Furniture", icon: Armchair },
      { value: "Household supplies", icon: SprayCan },
      { value: "Other Appliances", icon: Lamp },
    ],
  },
  {
    group: "Finance and life",
    categories: [
      { value: "Bank fees", icon: CreditCard },
      { value: "Insurance", icon: ShieldCheck },
      { value: "Taxes", icon: Receipt },
      { value: "Gifts", icon: Gift },
      { value: "Childcare", icon: Baby },
      { value: "Other Life", icon: Scale },
    ],
  },
  {
    group: "Uncategorized",
    categories: [
      { value: "Big purchases", icon: Gem },
      { value: "General", icon: CircleDollarSign },
    ],
  },
] as const;

const ICON_BY_CATEGORY: ReadonlyMap<string, LucideIcon> = new Map(
  CATEGORY_GROUPS.flatMap((g) => g.categories.map((c) => [c.value, c.icon] as const)),
);

export function CategoryIcon({ category, className }: { category: string; className?: string }) {
  const Icon = ICON_BY_CATEGORY.get(category) ?? CircleDollarSign;
  return <Icon className={className} />;
}
