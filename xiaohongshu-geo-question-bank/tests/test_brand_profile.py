import copy
import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.brand_profile import (  # noqa: E402
    BrandProfileError,
    JsonBrandFactsProvider,
    validate_brand_profile,
)


EXAMPLE_PATH = PROJECT_ROOT / "schemas" / "brand-profile.example.json"


class BrandProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    def test_example_is_valid(self) -> None:
        validate_brand_profile(self.profile)

    def test_json_provider_loads_valid_profile(self) -> None:
        loaded = JsonBrandFactsProvider(EXAMPLE_PATH).get_brand_profile()
        self.assertEqual(loaded["brand"]["name"], "示例品牌")

    def test_brand_name_is_required(self) -> None:
        invalid = copy.deepcopy(self.profile)
        invalid["brand"]["name"] = ""
        with self.assertRaises(BrandProfileError):
            validate_brand_profile(invalid)

    def test_scope_or_product_is_required(self) -> None:
        invalid = copy.deepcopy(self.profile)
        invalid["brand"]["category_scope"] = []
        invalid["products"] = []
        with self.assertRaises(BrandProfileError):
            validate_brand_profile(invalid)

    def test_duplicate_aliases_are_rejected(self) -> None:
        invalid = copy.deepcopy(self.profile)
        invalid["brand"]["aliases"] = ["Example Brand", "Example Brand"]
        with self.assertRaises(BrandProfileError):
            validate_brand_profile(invalid)


if __name__ == "__main__":
    unittest.main()

