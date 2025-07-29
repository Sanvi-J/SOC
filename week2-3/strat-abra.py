from src.backtester import Order, OrderBook
from typing import List
import pandas as pd
import numpy as np

class Trader:
    def __init__(self):
        # Load data once during initialization
        self.prices = pd.read_csv('data/abra_price.csv')
        self.cp = (self.prices['bid_price_1'] + self.prices['ask_price_1']) / 2
        self.position = 0  # Track current position
        self.max_position = 50  # Maximum allowed position (both long and short)
        
    def SMA(self, prices, period):
        return prices.rolling(window=period).mean()
    
    def calculate_bollinger_bands(self, prices, period=20, std_multiplier=2.0):
        middle_band = self.SMA(prices, period)
        std_deviation = prices.rolling(window=period).std(ddof=1)
        upper_band = middle_band + (std_multiplier * std_deviation)
        lower_band = middle_band - (std_multiplier * std_deviation)
        return upper_band, middle_band, lower_band
    
    def MM(self, prices):
        best_bid = prices['bid_price_1'].iloc[-1]
        best_ask = prices['ask_price_1'].iloc[-1]
        min_desired_spread = 0.01
        mid_price = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        if spread > min_desired_spread:
            buy_price = mid_price - spread/2
            sell_price = mid_price + spread/2
            return buy_price, sell_price
        return 0, 0
    
    def calculate_rsi(self, prices, period=14):
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def run(self, state, current_position):
        result = {}
        orders: List[Order] = []
        self.position = current_position  # Update current position
        
        # Use the last price only
        current_price = self.cp.iloc[-1]
        
        # Market Making with position limits
        buy_price, sell_price = self.MM(self.prices)
        if buy_price > 0 and sell_price > 0:
            if self.position < self.max_position:
                orders.append(Order("PRODUCT", buy_price, min(10, self.max_position - self.position)))
            if self.position > -self.max_position:
                orders.append(Order("PRODUCT", sell_price, -min(10, self.max_position + self.position)))
        
        # High/Low Breakout with position limits
        lookback = 20
        recent_high = max(self.cp[-lookback:])
        recent_low = min(self.cp[-lookback:])
        
        if current_price > recent_high and self.position < self.max_position:
            orders.append(Order("PRODUCT", buy_price, min(10, self.max_position - self.position)))
        elif current_price < recent_low and self.position > -self.max_position:
            orders.append(Order("PRODUCT", sell_price, -min(10, self.max_position + self.position)))
        
        # RSI with position limits
        rsi = self.calculate_rsi(self.cp).iloc[-1]
        if rsi > 70 and self.position > -self.max_position:
            orders.append(Order("PRODUCT", sell_price, -min(10, self.max_position + self.position)))
        elif rsi < 30 and self.position < self.max_position:
            orders.append(Order("PRODUCT", buy_price, min(10, self.max_position - self.position)))
        
        # Bollinger Bands with position limits
        upper, middle, lower = self.calculate_bollinger_bands(self.cp)
        if current_price > upper.iloc[-1] and self.position > -self.max_position:
            orders.append(Order("PRODUCT", sell_price, -min(10, self.max_position + self.position)))
        if current_price < lower.iloc[-1] and self.position < self.max_position:
            orders.append(Order("PRODUCT", buy_price, min(10, self.max_position - self.position)))
        
        result["PRODUCT"] = orders
        return result