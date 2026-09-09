class FlipFinderScorer:
    """
    Core deal-scoring and valuation engine for FlipFinder AI / Deal Verdict.
    Calculates profit margins, ROI multipliers, liquidity scores, and profit velocity
    based on live market comps (eBay sold data) versus local cash-sale parameters.
    """

    def __init__(self, item_name: str, buy_in_cost: float, target_price: float, floor_price: float):
        self.item_name = item_name
        self.cogs = float(buy_in_cost)
        self.target_price = float(target_price)
        self.floor_price = float(floor_price)

    def calculate_metrics(self, ebay_avg_sold_price: float, platform_fee_pct: float = 0.1325, estimated_shipping: float = 0.0) -> dict:
        """
        Evaluates the deal against both online (eBay shipped) and local (cash-in-hand) models.
        """
        # Online / eBay Shipped Model
        ebay_fees = ebay_avg_sold_price * platform_fee_pct
        ebay_net_profit = ebay_avg_sold_price - ebay_fees - estimated_shipping - self.cogs
        ebay_roi = (ebay_net_profit / self.cogs) * 100 if self.cogs > 0 else float('inf')

        # Local Cash Model (Target & Floor)
        local_target_net = self.target_price - self.cogs
        local_target_roi = (local_target_net / self.cogs) * 100 if self.cogs > 0 else float('inf')

        local_floor_net = self.floor_price - self.cogs
        local_floor_roi = (local_floor_net / self.cogs) * 100 if self.cogs > 0 else float('inf')

        return {
            "item": self.item_name,
            "cogs": self.cogs,
            "ebay_metrics": {
                "avg_sold": ebay_avg_sold_price,
                "net_profit": round(ebay_net_profit, 2),
                "roi_pct": round(ebay_roi, 2)
            },
            "local_cash_metrics": {
                "target_net": round(local_target_net, 2),
                "target_roi_pct": round(local_target_roi, 2),
                "floor_net": round(local_floor_net, 2),
                "floor_roi_pct": round(local_floor_roi, 2)
            }
        }

    def generate_verdict(self, liquidity_score: int, turnover_days: int) -> tuple:
        """
        Applies decision logic to return a verdict and confidence score.
        liquidity_score: 1 to 10 (how fast it moves locally/online)
        turnover_days: estimated days to liquidate
        """
        roi = ((self.target_price - self.cogs) / self.cogs) * 100 if self.cogs > 0 else 999999

        if roi >= 300 and liquidity_score >= 7 and turnover_days <= 14:
            return "STRONG BUY / GOD-TIER FLIP", 9.5
        elif roi >= 100 and liquidity_score >= 5:
            return "BUY / SOLID MARGIN", 8.0
        elif roi >= 50:
            return "REVIEW / MODERATE VELOCITY", 6.5
        else:
            return "PASS / LOW MARGIN", 3.0


# --- Example Execution: Cookshack SM025 ---
if __name__ == "__main__":
    # Initialize engine with item data
    engine = FlipFinderScorer(
        item_name="Cookshack Smokette Elite SM025",
        buy_in_cost=3.00,
        target_price=500.00,
        floor_price=450.00
    )

    # Simulated eBay Market Comps Data
    market_data = engine.calculate_metrics(ebay_avg_sold_price=650.00)
    verdict, confidence = engine.generate_verdict(liquidity_score=9, turnover_days=1)

    print(f"--- DEAL VERDICT: {market_data['item']} ---")
    print(f"Verdict: {verdict} (Confidence: {confidence}/10)")
    print(f"Local Floor Net Profit: ${market_data['local_cash_metrics']['floor_net']}")
    print(f"Local Floor ROI: {market_data['local_cash_metrics']['floor_roi_pct']}%")
