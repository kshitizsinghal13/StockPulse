import sqlite3
import pandas as pd
import datetime
import random
from loguru import logger

# Setup logging
logger.remove()
logger.add("stocks_data.log", format="{time} - {name} - {level} - {message}", level="DEBUG", rotation="10 MB")
logger.add(lambda msg: print(msg, end=""), format="{time} - {name} - {level} - {message}", level="DEBUG")

DB_PATH = "stock_history.db"
SYMBOLS = ["NVDA", "AAPL", "MSFT", "GOOGL"]
REAL_TIME_PRICES = {
    "NVDA": 105.527,
    "AAPL": 206.126,
    "MSFT": 383.774,
    "GOOGL": 157.946
}

def calculate_analytics(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()
        window_size = 5
        for symbol in df['symbol'].unique():
            mask = df['symbol'] == symbol
            df.loc[mask, 'moving_avg'] = df.loc[mask, 'price'].rolling(window=window_size, min_periods=1).mean()
            df.loc[mask, 'volatility'] = df.loc[mask, 'price'].rolling(window=window_size, min_periods=1).std()
        df['volatility'] = df['volatility'].fillna(0)
        logger.debug(f"Calculated analytics for mock data: {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Error calculating analytics for mock data: {e}")
        return df

def populate_historical_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stock_data")
        conn.commit()
        start_time = datetime.datetime(2025, 5, 2, 9, 30)
        end_time = datetime.datetime(2025, 5, 2, 16, 0)
        time_step = datetime.timedelta(minutes=1)
        VOLATILITY = 0.005
        TREND_STRENGTH = 0.0005
        mock_data = []
        for symbol in SYMBOLS:
            current_price = REAL_TIME_PRICES.get(symbol, 100.0)
            trend_direction = random.choice([-1, 1])
            current_time = start_time
            while current_time <= end_time:
                change = random.gauss(0, VOLATILITY) + (TREND_STRENGTH * trend_direction)
                price_change = current_price * change
                current_price = round(current_price + price_change, 3)
                current_price = max(current_price, REAL_TIME_PRICES.get(symbol, 100.0) * 0.5)
                if random.random() < 0.05:
                    jump = random.uniform(0.01, 0.03) * current_price
                    current_price = round(current_price + (jump * random.choice([-1, 1])), 3)
                mock_data.append({
                    "symbol": symbol,
                    "price": current_price,
                    "datetime": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "fetch_time": datetime.datetime.now().isoformat(),
                    "text": f"The current price of {symbol} is ${current_price} as of {current_time.strftime('%Y-%m-%d %H:%M:%S')}."
                })
                current_time += time_step
        df = pd.DataFrame(mock_data)
        df = calculate_analytics(df)
        df.to_sql('stock_data', conn, if_exists='append', index=False)
        conn.close()
        logger.info(f"Populated historical data with {len(df)} entries")
    except Exception as e:
        logger.error(f"Error populating historical data: {e}")

if __name__ == "__main__":
    populate_historical_data()