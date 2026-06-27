"""Startup seeder for the menu domain.

Inserts a small static drive-thru menu into `menu_items` on first boot if the
table is empty. Idempotent — safe to call on every startup. The persona of the
default menu is a classic American drive-thru ("Burger Barn").
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.menu.models import MenuItem

DEFAULT_MENU: list[dict] = [
    # --- Burgers ----------------------------------------------------------
    {
        "name": "Classic Cheeseburger",
        "description": "Quarter-pound beef patty, American cheese, lettuce, tomato, onion, house sauce.",
        "price_cents": 699,
        "category": "Burgers",
    },
    {
        "name": "Double Bacon Burger",
        "description": "Two beef patties, cheddar, crispy bacon, smoky BBQ sauce.",
        "price_cents": 949,
        "category": "Burgers",
    },
    {
        "name": "Crispy Chicken Sandwich",
        "description": "Buttermilk-fried chicken breast, pickles, mayo, brioche bun.",
        "price_cents": 749,
        "category": "Burgers",
    },
    # --- Sides ------------------------------------------------------------
    {
        "name": "Small Fries",
        "description": "Crinkle-cut fries, lightly salted.",
        "price_cents": 299,
        "category": "Sides",
    },
    {
        "name": "Large Fries",
        "description": "Crinkle-cut fries, lightly salted. Big portion.",
        "price_cents": 399,
        "category": "Sides",
    },
    {
        "name": "Onion Rings",
        "description": "Golden breaded onion rings, eight pieces.",
        "price_cents": 349,
        "category": "Sides",
    },
    {
        "name": "Chicken Tenders",
        "description": "Four hand-breaded chicken tenders with your choice of dipping sauce.",
        "price_cents": 599,
        "category": "Sides",
    },
    # --- Drinks -----------------------------------------------------------
    {
        "name": "Coke",
        "description": "Refreshing Coca-Cola, 22oz. Free refills on dine-in.",
        "price_cents": 249,
        "category": "Drinks",
    },
    {
        "name": "Sprite",
        "description": "Lemon-lime soda, 22oz.",
        "price_cents": 249,
        "category": "Drinks",
    },
    {
        "name": "Iced Tea",
        "description": "Freshly brewed iced tea, sweetened or unsweetened.",
        "price_cents": 229,
        "category": "Drinks",
    },
    {
        "name": "Chocolate Milkshake",
        "description": "Thick chocolate milkshake topped with whipped cream.",
        "price_cents": 499,
        "category": "Drinks",
    },
    # --- Combos -----------------------------------------------------------
    {
        "name": "Cheeseburger Combo",
        "description": "Classic Cheeseburger with small fries and a 22oz drink.",
        "price_cents": 1099,
        "category": "Combos",
    },
    {
        "name": "Chicken Tenders Combo",
        "description": "Four-piece chicken tenders with small fries and a 22oz drink.",
        "price_cents": 999,
        "category": "Combos",
    },
]


async def seed_if_empty(session: AsyncSession) -> int:
    """Insert DEFAULT_MENU into menu_items if the table is empty.

    Returns the number of rows inserted (0 if already seeded).
    """
    count_stmt = select(MenuItem.id)
    existing = (await session.execute(count_stmt)).first()
    if existing is not None:
        return 0

    session.add_all([MenuItem(**item) for item in DEFAULT_MENU])
    await session.commit()
    return len(DEFAULT_MENU)
