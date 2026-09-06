"""
Appraze
A single-page Streamlit dashboard for tracking, filtering, and evaluating
resale/auction deals across Estate Auctions, eBay, HiBid, Facebook Marketplace,
Mercari, Chairish, and Etsy.

Run locally (optional, no terminal needed for deployment - see DEPLOY.md):
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
import io
import secrets
import base64
import json
import urllib.request
import urllib.error
import urllib.parse
from finance import (
    compute_verdict, deal_roi, profit_calc, inventory_margin,
    melt_value, max_bid_after_premium, sales_tax, GOLD_PURITY, SILVER_PURITY,
)
