"""Dữ liệu mẫu Flow 4 cho `python manage.py seed_demo`: vật tư trong kho."""

# (tên vật tư, loại, đơn vị, số lượng tồn, mức tối thiểu)
DEMO_ITEMS = [("Yến mạch", "Food", "kg", 500, 100), ("Cỏ khô", "Food", "kg", 1000, 200),
              ("Băng chân", "Care Equipment", "cuộn", 40, 10), ("Thuốc sát trùng", "Medicine", "chai", 12, 5),
              ("Muối khoáng", "Food", "kg", 8, 10)]


def seed_demo(club):
    """Vật tư nào đã có (cùng tên, cùng CLB) thì giữ nguyên."""
    from .models import InventoryItem

    for name, item_type, unit, quantity, minimum in DEMO_ITEMS:
        if not InventoryItem.objects.filter(club=club, item_name=name).exists():
            item = InventoryItem(club=club, item_name=name, item_type=item_type, unit=unit, quantity=quantity,
                                 minimum_quantity=minimum)
            item.refresh_status()
            item.save()
