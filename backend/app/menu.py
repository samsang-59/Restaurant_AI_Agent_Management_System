"""The predefined restaurant menu and its live stock.

The menu is created once at startup. Stock is reserved when `take_order`
succeeds, released if the order is abandoned (cook failure handed back to the
guest, or the session ending on a limit), and stays consumed once served.
"""

import copy
import threading
from dataclasses import asdict, dataclass

RESTAURANT_NAME = "Saffron & Spice"


@dataclass
class MenuItem:
    name: str
    category: str
    price: int  # in INR
    description: str
    available: int
    veg: bool


INITIAL_MENU: list[MenuItem] = [
    MenuItem("Paneer Tikka", "Starters", 280, "Char-grilled cottage cheese marinated in spiced yoghurt", 8, True),
    MenuItem("Chicken 65", "Starters", 300, "Crispy fried chicken tossed with curry leaves and red chilli", 10, False),
    MenuItem("Butter Chicken", "Mains", 350, "Tandoori chicken simmered in a velvety tomato-butter gravy", 10, False),
    MenuItem("Dal Makhani", "Mains", 220, "Black lentils slow-cooked overnight with cream and butter", 12, True),
    MenuItem("Palak Paneer", "Mains", 260, "Cottage cheese cubes in a smooth spiced spinach gravy", 8, True),
    MenuItem("Hyderabadi Chicken Biryani", "Rice", 320, "Dum-cooked basmati layered with saffron and spiced chicken", 12, False),
    MenuItem("Veg Biryani", "Rice", 260, "Fragrant basmati with seasonal vegetables and whole spices", 10, True),
    MenuItem("Masala Dosa", "South Indian", 180, "Crisp rice crepe filled with spiced potato, with sambar and chutney", 15, True),
    MenuItem("Garlic Naan", "Breads", 60, "Tandoor-baked flatbread brushed with garlic butter", 30, True),
    MenuItem("Gulab Jamun", "Desserts", 120, "Warm milk dumplings soaked in cardamom-rose syrup", 20, True),
    MenuItem("Mango Lassi", "Beverages", 110, "Chilled yoghurt drink blended with Alphonso mango", 15, True),
]


def _normalize(name: str) -> str:
    return " ".join(name.strip().lower().split())


class MenuStore:
    def __init__(self, items: list[MenuItem] | None = None):
        self._lock = threading.Lock()
        self._items = {_normalize(i.name): i for i in copy.deepcopy(items or INITIAL_MENU)}

    def find(self, dish_name: str) -> MenuItem | None:
        return self._items.get(_normalize(dish_name))

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [asdict(i) for i in self._items.values()]

    def reserve(self, dish_name: str, quantity: int) -> bool:
        """Atomically take `quantity` portions out of stock. Returns False if not enough."""
        with self._lock:
            item = self.find(dish_name)
            if item is None or quantity > item.available:
                return False
            item.available -= quantity
            return True

    def release(self, dish_name: str, quantity: int) -> None:
        with self._lock:
            item = self.find(dish_name)
            if item is not None:
                item.available += quantity

    def reset(self) -> None:
        with self._lock:
            self._items = {_normalize(i.name): i for i in copy.deepcopy(INITIAL_MENU)}


menu_store = MenuStore()
