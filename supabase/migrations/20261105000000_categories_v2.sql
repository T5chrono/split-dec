-- Revised expense categories (public/categories/Categories-Version2.md).
--
-- Categories are free TEXT in the database and validated only by the API's
-- StrEnum (api/_src/categories.py), so the new values need no DDL. What does
-- need doing is the old values the revision dropped: rows carrying them would
-- render with a fallback icon and an untranslated label, and an edit would
-- resubmit a value the API no longer recognises. Each is moved to its nearest
-- replacement, using exactly the table in `categories.LEGACY_CATEGORIES`
-- (tests/test_categories.py parses this file and compares the two).
--
-- Deliberately not stamped as an edit: `updated_by` / `updated_at` record who
-- changed a row, and nobody did — the vocabulary changed underneath it.
-- Soft-deleted rows are moved too, so a value the API no longer knows does not
-- survive anywhere. Idempotent: a second run matches nothing.
--
-- Apply AFTER the code that ships with it is deployed. The previous API build
-- refuses the new values, and the form sends the category on every save, so
-- migrating first would turn editing a migrated row into a 422 until deploy.
UPDATE public.expenses
SET category = CASE category
    WHEN 'Sports' THEN 'Other Sports'
    WHEN 'Liquor' THEN 'Alcohol'
    WHEN 'Pets' THEN 'Other Home'
    WHEN 'Services' THEN 'Other Home'
    WHEN 'Education' THEN 'Other Learning'
    WHEN 'Bicycle' THEN 'Other Transportation'
    WHEN 'Plane' THEN 'Flights'
    WHEN 'Cleaning' THEN 'Household supplies'
    WHEN 'Electricity' THEN 'Bills'
    WHEN 'Heat/gas' THEN 'Bills'
    WHEN 'Trash' THEN 'Bills'
    WHEN 'Water' THEN 'Bills'
    WHEN 'Other Utilities' THEN 'Bills'
    WHEN 'TV/Phone/Internet' THEN 'Internet'
    WHEN 'Other Subscriptions' THEN 'Memberships'
    WHEN 'Copilots' THEN 'AI subscriptions'
    WHEN 'Generation Tools' THEN 'AI subscriptions'
    WHEN 'Other AI Expenses' THEN 'Other Tech'
END
WHERE category IN (
    'Sports', 'Liquor', 'Pets', 'Services', 'Education', 'Bicycle', 'Plane',
    'Cleaning', 'Electricity', 'Heat/gas', 'Trash', 'Water', 'Other Utilities',
    'TV/Phone/Internet', 'Other Subscriptions', 'Copilots', 'Generation Tools',
    'Other AI Expenses'
);
