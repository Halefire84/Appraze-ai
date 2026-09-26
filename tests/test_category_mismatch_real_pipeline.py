"""Regression tests for F-04 (category-mismatch self-cancelling bug) run
through the REAL production pipeline: a raw source record -> normalize_listing()
-> analyze_listing(), exactly as holy_grail_pipeline.score_listing() calls it
for every eBay-scanned listing.

Before the fix, expected_keywords was manufactured from the listing's own
category/title/description, so a wrong category could never be caught --
the "expected" evidence and the thing being validated were the same data.
listing_normalizer.normalize_listing() no longer does that; these tests
prove the mismatch still gets caught with NO caller-supplied taxonomy,
which is the normal case for every real eBay/auction-sourced listing.
"""
import unittest

from holy_grail_pipeline import score_listing


class TestCategoryMismatchRealPipeline(unittest.TestCase):
    def test_correct_category_is_not_flagged(self):
        candidate = score_listing({
            "title": "Dell Latitude laptop",
            "description": "14 inch business laptop, works great",
            "category": "Computers",
            "price": 80,
        })
        self.assertFalse(any(s["code"] == "possible_misclassification" for s in candidate.signals))

    def test_wrong_category_is_flagged_with_no_supplied_taxonomy(self):
        # Camera under "Clothing, Shoes & Accessories" -- the canonical F-04
        # scenario. No expected_keywords passed in from the source record.
        candidate = score_listing({
            "title": "Nikon camera lens 50mm",
            "description": "Nikon DSLR lens, excellent glass, no fungus.",
            "category": "Clothing, Shoes & Accessories",
        })
        self.assertTrue(any(s["code"] == "possible_misclassification" for s in candidate.signals))

    def test_brand_category_conflict_is_flagged(self):
        # Rolex watch under Furniture -- direct analog of the low-level
        # detect_category_mismatch test, but through the real pipeline.
        candidate = score_listing({
            "title": "Rolex Submariner watch",
            "description": "Mechanical wristwatch, automatic movement",
            "category": "Furniture",
        })
        self.assertTrue(any(s["code"] == "possible_misclassification" for s in candidate.signals))

    def test_missing_category_does_not_crash_or_flag(self):
        candidate = score_listing({
            "title": "Assorted household items",
            "description": "Box lot, various condition",
        })
        self.assertFalse(any(s["code"] == "possible_misclassification" for s in candidate.signals))

    def test_ambiguous_category_single_incidental_term_is_not_flagged(self):
        # Unrecognized category, and the text has only ONE incidental term
        # ("chair") that overlaps a different recognized category
        # (furniture). _MIN_CROSS_CATEGORY_HITS=2 exists precisely so this
        # does not fire on ordinary listings.
        candidate = score_listing({
            "title": "Patio umbrella and outdoor chair cover",
            "description": "Weatherproof cover, fits most standard chairs",
            "category": "Home & Garden",
        })
        self.assertFalse(any(s["code"] == "possible_misclassification" for s in candidate.signals))

    def test_misleading_title_and_description_is_flagged(self):
        # Title and description both describe tools, category claims jewelry.
        candidate = score_listing({
            "title": "Cordless drill and impact driver combo",
            "description": "DeWalt drill, includes battery and charger, tested working",
            "category": "Jewelry",
        })
        self.assertTrue(any(s["code"] == "possible_misclassification" for s in candidate.signals))

    def test_independent_taxonomy_still_overrides_when_supplied(self):
        # A source with its own classifier can still supply expected_keywords
        # explicitly; that independent evidence is honored.
        candidate = score_listing({
            "title": "Unlabeled instrument case",
            "description": "Hard case, foam interior, some scuffs",
            "category": "Musical Instruments",
            "expected_keywords": ["instrument", "case", "guitar"],
        })
        self.assertFalse(any(s["code"] == "possible_misclassification" for s in candidate.signals))


if __name__ == "__main__":
    unittest.main()
