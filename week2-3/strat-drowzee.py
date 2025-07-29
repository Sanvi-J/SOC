from src.backtester import Order
from typing import List
import pandas as pd

class Trader:
    def __init__(self):
        self.prices = pd.read_csv('data/drowzee_prices.csv')
        self.cp = (self.prices['bid_price_1'] + self.prices['ask_price_1']) / 2

    def SMA(self, prices, period):
        return prices.rolling(window=period).mean()
    
    def calculate_bollinger_bands(self, prices, period=20, std_multiplier=0.01):
        middle_band = self.SMA(prices, period)
        std_dev = prices.rolling(window=period).std(ddof=1)
        upper_band = middle_band + (std_multiplier * std_dev)
        lower_band = middle_band - (std_multiplier * std_dev)
        return upper_band, middle_band, lower_band

    def run(self, state, current_position):
        i = state.timestamp
        if i < 20:
            return {}

        result = {}
        orders: List[Order] = []
        current_price = self.cp.iloc[i]

        # Bollinger Bands
        upper, middle, lower = self.calculate_bollinger_bands(self.cp[:i+1])
        upper_val = upper.iloc[-1]
        lower_val = lower.iloc[-1]

        MAX_POSITION = 50
        POSITION_SIZE = 20

        # Mean reversion logic with limits
        if current_price > upper_val and current_position > -MAX_POSITION:
            sell_qty = min(POSITION_SIZE, current_position + MAX_POSITION)
            orders.append(Order("PRODUCT", current_price, -sell_qty))

        elif current_price < lower_val and current_position < MAX_POSITION:
            buy_qty = min(POSITION_SIZE, MAX_POSITION - current_position)
            orders.append(Order("PRODUCT", current_price, buy_qty))

        result["PRODUCT"] = orders
        return result
