from utils.helpers import get_product_ids_from_items


class FakeItem:
    def __init__(self, product_id):
        self.product_id = product_id


class TestGetProductIdsFromItems:
    def test_accepts_dicts_and_objects_and_deduplicates(self):
        items = [
            {"product_id": 1},
            FakeItem(2),
            {"product_id": 1},
            FakeItem(None),
            {"product_id": "3"},
        ]
        assert get_product_ids_from_items(items) == [1, 2, 3]

    def test_missing_product_id_on_object_is_skipped(self):
        assert get_product_ids_from_items([FakeItem(None)]) == []

    def test_empty_input_returns_empty_list(self):
        assert get_product_ids_from_items([]) == []

    def test_none_values_are_ignored(self):
        assert get_product_ids_from_items([None, {"product_id": 7}]) == [7]
