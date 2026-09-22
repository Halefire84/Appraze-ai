import unittest

from opportunity_radar import analyze_listing


class TestHolyGrailCoverage(unittest.TestCase):
    def test_bulk_quantity_signal(self):
        result = analyze_listing({"title": "box of 25 tools", "price": 40, "quantity": 25})
        self.assertTrue(any(s.code == "bulk_quantity" for s in result.signals))

    def test_hidden_brand_signal(self):
        result = analyze_listing({"title": "vintage receiver", "description": "Marantz stereo receiver"})
        self.assertTrue(any(s.code == "brand_hidden_in_description" for s in result.signals))

    def test_hidden_model_signal(self):
        result = analyze_listing({"title": "old equipment", "description": "Model: ABC1234 professional unit"})
        self.assertTrue(any(s.code == "model_number_hidden" for s in result.signals))

    def test_precious_material_signal(self):
        result = analyze_listing({"title": "old ring", "description": "14K gold"})
        self.assertTrue(any(s.code == "precious_material_present" for s in result.signals))


if __name__ == "__main__":
    unittest.main()
