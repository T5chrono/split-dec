import type { LucideIcon } from "lucide-react";
import {
  Gamepad2, Film, Music, Trophy, Sparkles,
  Mountain, MountainSnow, Waves, Footprints, Medal,
  UtensilsCrossed, ShoppingCart, Wine, CupSoda,
  MonitorSmartphone, Armchair, SprayCan, Wrench, Landmark, PawPrint, Home, HandPlatter, House,
  Baby, Shirt, GraduationCap, Gift, ShieldCheck, Stethoscope, Receipt, HeartPulse,
  Bike, TrainFront, Car, Fuel, Hotel, CircleParking, Plane, CarTaxiFront, Bus,
  Brush, Zap, Flame, Trash2, Wifi, Droplets, Plug,
  AppWindow, Clapperboard, IdCard, RefreshCcw,
  UserRound, BookOpenText, Book, Lightbulb,
  Bot, Terminal, WandSparkles, Cpu,
  CircleDollarSign,
} from "lucide-react";

/** Immutable mapping of backend category values to lucide-react icons (spec §3). */
export const CATEGORY_GROUPS: ReadonlyArray<{
  group: string;
  categories: ReadonlyArray<{ value: string; icon: LucideIcon }>;
}> = [
  // "General" leads the list: it is the default category, so the picker
  // opens on it and the user scrolls down through the specific groups.
  {
    group: "Uncategorized",
    categories: [{ value: "General", icon: CircleDollarSign }],
  },
  {
    group: "Entertainment",
    categories: [
      { value: "Games", icon: Gamepad2 },
      { value: "Movies", icon: Film },
      { value: "Music", icon: Music },
      { value: "Other Entertainment", icon: Sparkles },
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
      { value: "Other Sports", icon: Medal },
    ],
  },
  {
    group: "Food and drink",
    categories: [
      { value: "Dining out", icon: UtensilsCrossed },
      { value: "Groceries", icon: ShoppingCart },
      { value: "Liquor", icon: Wine },
      { value: "Other Food and drink", icon: CupSoda },
    ],
  },
  {
    group: "Home",
    categories: [
      { value: "Electronics", icon: MonitorSmartphone },
      { value: "Furniture", icon: Armchair },
      { value: "Household supplies", icon: SprayCan },
      { value: "Maintenance", icon: Wrench },
      { value: "Mortgage", icon: Landmark },
      { value: "Pets", icon: PawPrint },
      { value: "Rent", icon: Home },
      { value: "Services", icon: HandPlatter },
      { value: "Other Home", icon: House },
    ],
  },
  {
    group: "Life",
    categories: [
      { value: "Childcare", icon: Baby },
      { value: "Clothing", icon: Shirt },
      { value: "Education", icon: GraduationCap },
      { value: "Gifts", icon: Gift },
      { value: "Insurance", icon: ShieldCheck },
      { value: "Medical expenses", icon: Stethoscope },
      { value: "Taxes", icon: Receipt },
      { value: "Other Life", icon: HeartPulse },
    ],
  },
  {
    group: "Transportation",
    categories: [
      { value: "Bicycle", icon: Bike },
      { value: "Bus/train", icon: TrainFront },
      { value: "Car", icon: Car },
      { value: "Gas/fuel", icon: Fuel },
      { value: "Hotel", icon: Hotel },
      { value: "Parking", icon: CircleParking },
      { value: "Plane", icon: Plane },
      { value: "Taxi", icon: CarTaxiFront },
      { value: "Other Transportation", icon: Bus },
    ],
  },
  {
    group: "Utilities",
    categories: [
      { value: "Cleaning", icon: Brush },
      { value: "Electricity", icon: Zap },
      { value: "Heat/gas", icon: Flame },
      { value: "Trash", icon: Trash2 },
      { value: "TV/Phone/Internet", icon: Wifi },
      { value: "Water", icon: Droplets },
      { value: "Other Utilities", icon: Plug },
    ],
  },
  {
    group: "Subscriptions",
    categories: [
      { value: "Software", icon: AppWindow },
      { value: "Streaming", icon: Clapperboard },
      { value: "Memberships", icon: IdCard },
      { value: "Other Subscriptions", icon: RefreshCcw },
    ],
  },
  {
    group: "Learning",
    categories: [
      { value: "Tutor", icon: UserRound },
      { value: "Courses", icon: BookOpenText },
      { value: "Books", icon: Book },
      { value: "Other Learning", icon: Lightbulb },
    ],
  },
  {
    group: "AI Expenses",
    categories: [
      { value: "LLM APIs", icon: Bot },
      { value: "Copilots", icon: Terminal },
      { value: "Generation Tools", icon: WandSparkles },
      { value: "Other AI Expenses", icon: Cpu },
    ],
  },
] as const;

const ICON_BY_CATEGORY: ReadonlyMap<string, LucideIcon> = new Map([
  ...CATEGORY_GROUPS.flatMap((g) => g.categories.map((c) => [c.value, c.icon] as const)),
  // Legacy value from when Sports lived under Entertainment; old expenses keep it.
  ["Sports", Trophy] as const,
]);

export function CategoryIcon({ category, className }: { category: string; className?: string }) {
  const Icon = ICON_BY_CATEGORY.get(category) ?? CircleDollarSign;
  return <Icon className={className} />;
}
