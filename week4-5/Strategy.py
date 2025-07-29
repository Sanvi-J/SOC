from src.backtester import Order, OrderBook
from typing import List
import pandas as pd
import numpy as np
import statistics
import math

# Base Class
class BaseClass:
    def __init__(self, product_name, max_position):
        self.product_name = product_name
        self.max_position = max_position
    
    def get_orders(self, state, orderbook, position):
        """Override this method in product-specific strategies"""
        return []

class SudowoodoStrategy(BaseClass): # Inherit from Base Class
    def __init__(self):
        super().__init__("SUDOWOODO", 50) # Initialize using the init dunder from its Parent class
        self.fair_value = 10000
    
    def get_orders(self, state, orderbook, position):
        orders = []
        
        if not orderbook.buy_orders and not orderbook.sell_orders:
            return orders
        # LOGIC FROM THE NOTEBOOK SHARED ON NOTION FOR SUDOWOODO
        orders.append(Order(self.product_name, self.fair_value + 2, -10))
        orders.append(Order(self.product_name, self.fair_value - 2, 10))

        return orders

class DrowzeeStrategy(BaseClass):
    def __init__(self):
        super().__init__("DROWZEE", 50)
        self.lookback = 50
        self.z_threshold = 3.75
        self.prices = []
    
    def get_orders(self, state, orderbook, position):
        orders = []
        if not orderbook.buy_orders and not orderbook.sell_orders:
            return orders
        
        best_ask = min(orderbook.sell_orders.keys()) if orderbook.sell_orders else None
        best_bid = max(orderbook.buy_orders.keys()) if orderbook.buy_orders else None
        mid_price = (best_ask + best_bid) // 2
        self.prices.append(mid_price)

        if len(self.prices) > self.lookback:
            mean_price = statistics.mean(self.prices[-self.lookback:])
            stddev_price = statistics.stdev(self.prices[-self.lookback:])
            z_score = (mid_price - mean_price) / stddev_price
            if z_score > self.z_threshold:
                orders.append(Order(self.product_name, best_bid, -self.max_position + position))
            elif z_score < -self.z_threshold:
                orders.append(Order(self.product_name, best_ask, self.max_position - position))
            else:
                return self.market_make(mid_price)
        elif len(self.prices) <= self.lookback:
            return self.market_make(mid_price)
        return orders
    
    def market_make(self, price):
        orders = []
        orders.append(Order(self.product_name, price - 1, 25))
        orders.append(Order(self.product_name, price + 1, -25))
        return orders

class AbraStrategy(BaseClass):
    def __init__(self):
        super().__init__("ABRA", 50)
        self.prices = []
        self.lookback = 200
        self.z_threshold = 2.0
        self.z_mm_threshold = 0.3
        self.skew_factor = 0.1
    def get_orders(self, state, orderbook, position):
        orders = []

        if not orderbook.buy_orders and not orderbook.sell_orders:
            return orders

        best_ask = min(orderbook.sell_orders.keys()) if orderbook.sell_orders else None
        best_bid = max(orderbook.buy_orders.keys()) if orderbook.buy_orders else None
        mid_price = (best_ask + best_bid) // 2
        self.prices.append(mid_price)

        if len(self.prices) > self.lookback:
            mean_price = statistics.mean(self.prices[-self.lookback:])
            stddev_price = statistics.stdev(self.prices[-self.lookback:])
            z_score = (mid_price - mean_price) / stddev_price
            if z_score > self.z_threshold:
                orders.append(Order(self.product_name, best_bid, -7))
            elif z_score < -self.z_threshold:
                orders.append(Order(self.product_name, best_ask, 7))
            elif abs(z_score) < self.z_mm_threshold:
                return self.market_make(mid_price, position)
        elif len(self.prices) <= self.lookback:
            return self.market_make(mid_price, position)
        return orders

    def market_make(self, mid_price, position):
        orders = []
        adjusted_mid_price = mid_price + self.skew_factor*position
        orders.append(Order(self.product_name, adjusted_mid_price - 2, 7))
        orders.append(Order(self.product_name, adjusted_mid_price + 2, -7))
        return orders

class MistyStrategy(BaseClass):
    def __init__(self):
        super().__init__("MISTY", 100)
        self.prices = []
        self.rsi_period = 14
        self.atr_window = 14
        self.entry_info = None
        self.cooldown = 0

    def calculate_rsi(self):
        if len(self.prices) < self.rsi_period + 1:
            return 50
        deltas = [self.prices[i] - self.prices[i - 1] for i in range(1, len(self.prices))]
        gains = [max(0, d) for d in deltas[-self.rsi_period:]]
        losses = [max(0, -d) for d in deltas[-self.rsi_period:]]
        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period
        rs = avg_gain / max(avg_loss, 1e-6)
        return 100 - (100 / (1 + rs))

    def calculate_atr(self):
        if len(self.prices) < 2:
            return 1
        true_ranges = [abs(self.prices[i] - self.prices[i-1]) for i in range(1, len(self.prices))]
        return sum(true_ranges[-self.atr_window:]) / min(len(true_ranges), self.atr_window)

    def get_orders(self, state, orderbook, position):
        best_bid = max(orderbook.buy_orders.keys()) if orderbook.buy_orders else None
        best_ask = min(orderbook.sell_orders.keys()) if orderbook.sell_orders else None
        if not best_bid or not best_ask:
            return []

        mid = (best_bid + best_ask) / 2
        self.prices.append(mid)
        if len(self.prices) > 300:
            self.prices.pop(0)

        tick = len(self.prices)
        atr = self.calculate_atr()
        rsi = self.calculate_rsi()
        mean = sum(self.prices[-20:]) / min(len(self.prices), 20)
        orders = []

        if self.cooldown > 0:
            self.cooldown -= 1

        # ---- EXIT logic ----
        if self.entry_info:
            entry = self.entry_info
            direction = entry["side"]
            move = mid - entry["price"] if direction == "buy" else entry["price"] - mid

            # Fixed TP/SL style
            if move >= 1.5 * atr or move <= -1.2 * atr:
                exit_qty = -position
                exit_price = best_bid if position > 0 else best_ask
                orders.append(Order("MISTY", exit_price, exit_qty))
                print(f"[EXIT] {direction.upper()} | PnL: {move:.1f}")
                self.entry_info = None
                self.cooldown = 5
                return orders
            return []

        # ---- ENTRY logic ----
        if abs(position) == 0 and self.cooldown == 0:
            if atr < 5:
                if mid < mean - 10 and rsi < 45:
                    orders.append(Order("MISTY", best_ask, 5))
                    self.entry_info = {"side": "buy", "price": mid}
                    print(f"[ENTRY-R] BUY at {mid:.1f} | Mean: {mean:.1f} | RSI: {rsi:.1f}")

                elif mid > mean + 10 and rsi > 55:
                    orders.append(Order("MISTY", best_bid, -5))
                    self.entry_info = {"side": "sell", "price": mid}
                    print(f"[ENTRY-R] SELL at {mid:.1f} | Mean: {mean:.1f} | RSI: {rsi:.1f}")

            else:
                high = max(self.prices[-20:])
                low = min(self.prices[-20:])

                if mid > high + 0.5 * atr:
                    orders.append(Order("MISTY", best_ask, 6))
                    self.entry_info = {"side": "buy", "price": mid}
                    print(f"[ENTRY-T] BREAKOUT BUY at {mid:.1f} | High: {high:.1f}")

                elif mid < low - 0.5 * atr:
                    orders.append(Order("MISTY", best_bid, -6))
                    self.entry_info = {"side": "sell", "price": mid}
                    print(f"[ENTRY-T] BREAKDOWN SELL at {mid:.1f} | Low: {low:.1f}")

        return orders


class ShinxStrategy(BaseClass):
    def __init__(self):
        super().__init__("SHINX", 100)
        self.prices = []
        self.rsi_period = 14
        self.entry_info = None

    def calculate_rsi(self):
        if len(self.prices) < self.rsi_period + 1:
            return 50
        deltas = [self.prices[i] - self.prices[i - 1] for i in range(1, len(self.prices))]
        gains = [max(0, d) for d in deltas[-self.rsi_period:]]
        losses = [max(0, -d) for d in deltas[-self.rsi_period:]]
        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period
        rs = avg_gain / max(avg_loss, 1e-6)
        return 100 - (100 / (1 + rs))

    def get_orders(self, state, orderbook, position):
        best_bid = max(orderbook.buy_orders.keys()) if orderbook.buy_orders else None
        best_ask = min(orderbook.sell_orders.keys()) if orderbook.sell_orders else None
        if not best_bid or not best_ask:
            return []

        mid = (best_bid + best_ask) / 2
        self.prices.append(mid)
        if len(self.prices) > 200:
            self.prices.pop(0)

        orders = []
        rsi = self.calculate_rsi()
        mean = sum(self.prices[-20:]) / min(len(self.prices), 20)

        # Exit if price reverts to mean
        if self.entry_info:
            side = self.entry_info["side"]
            if (side == "buy" and mid >= mean) or (side == "sell" and mid <= mean):
                exit_qty = -position
                exit_price = best_bid if position > 0 else best_ask
                orders.append(Order("SHINX", exit_price, exit_qty))
                self.entry_info = None
                print(f"EXIT {side.upper()} at {mid:.1f} (mean {mean:.1f})")
                return orders
            return []

        # Entry
        if abs(position) == 0:
            if mid < mean - 10 and rsi < 45:
                orders.append(Order("SHINX", best_ask, 5))
                self.entry_info = {"side": "buy", "price": mid}
                print(f"BUY @ {mid:.1f}, RSI {rsi:.1f}, Mean {mean:.1f}")
            elif mid > mean + 10 and rsi > 55:
                orders.append(Order("SHINX", best_bid, -5))
                self.entry_info = {"side": "sell", "price": mid}
                print(f"SELL @ {mid:.1f}, RSI {rsi:.1f}, Mean {mean:.1f}")

        return orders

class LuxrayStrategy(BaseClass):
    def __init__(self):
        super().__init__("LUXRAY", 250)
        self.prices = []
        self.rsi_period = 10
        self.entry = None

    def calculate_rsi(self):
        if len(self.prices) < self.rsi_period + 1:
            return 50
        deltas = [self.prices[i] - self.prices[i - 1] for i in range(1, len(self.prices))]
        gains = [max(0, d) for d in deltas[-self.rsi_period:]]
        losses = [max(0, -d) for d in deltas[-self.rsi_period:]]
        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period
        rs = avg_gain / max(avg_loss, 1e-6)
        return 100 - (100 / (1 + rs))

    def get_orders(self, state, orderbook, position):
        best_bid = max(orderbook.buy_orders.keys()) if orderbook.buy_orders else None
        best_ask = min(orderbook.sell_orders.keys()) if orderbook.sell_orders else None
        if not best_bid or not best_ask:
            return []

        mid = (best_bid + best_ask) / 2
        self.prices.append(mid)
        if len(self.prices) > 200:
            self.prices.pop(0)

        rsi = self.calculate_rsi()
        mean = sum(self.prices[-20:]) / min(len(self.prices), 20)
        orders = []

        # === EXIT ===
        if self.entry:
            entry_price = self.entry["price"]
            side = self.entry["side"]
            pnl = mid - entry_price if side == "buy" else entry_price - mid

            if pnl >= 8 or pnl <= -3:
                orders.append(Order("LUXRAY", best_bid if position > 0 else best_ask, -position))
                self.entry = None
                return orders

        # === ENTRY ===
        if position == 0 and self.entry is None:
            rsi_diff = abs(rsi - 50)
            base_size = 80
            size = min(120, base_size + int(rsi_diff * 2))  # Scales with RSI confidence

            if mid < mean - 3 and rsi < 45:
                orders.append(Order("LUXRAY", best_ask, size))
                self.entry = {"side": "buy", "price": mid}

            elif mid > mean + 3 and rsi > 55:
                orders.append(Order("LUXRAY", best_bid, -size))
                self.entry = {"side": "sell", "price": mid}

        return orders

class JolteonStrategy(BaseClass):
    def __init__(self):
        super().__init__("JOLTEON", 350)
        self.prices = []
        self.rsi_period = 9
        self.entry = None

    def calculate_rsi(self):
        if len(self.prices) < self.rsi_period + 1:
            return 50
        deltas = [self.prices[i] - self.prices[i - 1] for i in range(1, len(self.prices))]
        gains = [max(0, d) for d in deltas[-self.rsi_period:]]
        losses = [max(0, -d) for d in deltas[-self.rsi_period:]]
        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period
        rs = avg_gain / max(avg_loss, 1e-6)
        return 100 - (100 / (1 + rs))

    def get_orders(self, state, orderbook, position):
        best_bid = max(orderbook.buy_orders.keys()) if orderbook.buy_orders else None
        best_ask = min(orderbook.sell_orders.keys()) if orderbook.sell_orders else None
        if not best_bid or not best_ask:
            return []

        mid = (best_bid + best_ask) / 2
        self.prices.append(mid)
        if len(self.prices) > 200:
            self.prices.pop(0)

        rsi = self.calculate_rsi()
        mean = sum(self.prices[-15:]) / min(len(self.prices), 15)
        orders = []

        # === EXIT ===
        if self.entry:
            entry_price = self.entry["price"]
            side = self.entry["side"]
            pnl = mid - entry_price if side == "buy" else entry_price - mid

            if pnl >= 5 or pnl <= -2.5:
                orders.append(Order("JOLTEON", best_bid if position > 0 else best_ask, -position))
                self.entry = None
                return orders

        # === ENTRY ===
        if position == 0 and self.entry is None:
            size = 120  # Jolteon strikes hard

            if mid < mean - 2.5 and rsi < 42:
                orders.append(Order("JOLTEON", best_ask, size))
                self.entry = {"side": "buy", "price": mid}

            elif mid > mean + 2.5 and rsi > 58:
                orders.append(Order("JOLTEON", best_bid, -size))
                self.entry = {"side": "sell", "price": mid}

        return orders

class AshStrategy(BaseClass):
    def __init__(self):
        super().__init__("ASH", 60)
        self.prices = []
        self.rsi_period = 9
        self.entry = None
        self.atr_period = 14
        self.true_ranges = []

    def calculate_rsi(self):
        if len(self.prices) < self.rsi_period + 1:
            return 50
        deltas = [self.prices[i] - self.prices[i - 1] for i in range(1, len(self.prices))]
        gains = [max(0, d) for d in deltas[-self.rsi_period:]]
        losses = [max(0, -d) for d in deltas[-self.rsi_period:]]
        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period
        rs = avg_gain / max(avg_loss, 1e-6)
        return 100 - (100 / (1 + rs))

    def calculate_atr(self):
        if len(self.true_ranges) < self.atr_period:
            return 1
        return sum(self.true_ranges[-self.atr_period:]) / self.atr_period

    def get_orders(self, state, orderbook, position):
        best_bid = max(orderbook.buy_orders.keys()) if orderbook.buy_orders else None
        best_ask = min(orderbook.sell_orders.keys()) if orderbook.sell_orders else None
        if not best_bid or not best_ask:
            return []

        mid = (best_bid + best_ask) / 2
        self.prices.append(mid)
        if len(self.prices) > 200:
            self.prices.pop(0)

        self.true_ranges.append(best_ask - best_bid)
        if len(self.true_ranges) > 100:
            self.true_ranges.pop(0)

        atr = self.calculate_atr()
        if atr < 1:
            return []  # Skip low volatility zones

        rsi = self.calculate_rsi()
        mean = sum(self.prices[-12:]) / min(len(self.prices), 12)
        orders = []

        # === EXIT LOGIC ===
        if self.entry:
            entry_price = self.entry["price"]
            side = self.entry["side"]
            pnl = mid - entry_price if side == "buy" else entry_price - mid
            tp = 4.5 if atr > 3 else 3
            sl = 2.0

            if pnl >= tp or pnl <= -sl:
                orders.append(Order("ASH", best_bid if position > 0 else best_ask, -position))
                self.entry = None

        # === ENTRY LOGIC ===
        can_enter = (position + 30 <= 60 and position >= 0) or (position - 30 >= -60 and position <= 0)
        if can_enter:
            size = 30
            if mid < mean - 1.5 and rsi < 45:
                orders.append(Order("ASH", best_ask, size))
                self.entry = {"side": "buy", "price": mid}
            elif mid > mean + 1.5 and rsi > 55:
                orders.append(Order("ASH", best_bid, -size))
                self.entry = {"side": "sell", "price": mid}

        return orders

class Trader:
    MAX_LIMIT = 0 # for single product mode only, don't remove
    def __init__(self):
        self.strategies = {
            "SUDOWOODO": SudowoodoStrategy(),
            "DROWZEE": DrowzeeStrategy(), 
            "ABRA": AbraStrategy(),
            "MISTY": MistyStrategy(),
            "SHINX": ShinxStrategy(),
            "LUXRAY": LuxrayStrategy(),
            "JOLTEON": JolteonStrategy(),
            "ASH": AshStrategy()
        }
    
    def run(self, state):
        result = {}
        positions = getattr(state, 'positions', {})
        if len(self.strategies) == 1: self.MAX_LIMIT= self.strategies["PRODUCT"].max_position # for single product mode only, don't remove

        for product, orderbook in state.order_depth.items():
            current_position = positions.get(product, 0)
            product_orders = self.strategies[product].get_orders(state, orderbook, current_position)
            result[product] = product_orders
        
        return result, self.MAX_LIMIT
