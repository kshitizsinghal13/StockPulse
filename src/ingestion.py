import pathway as pw
from twelvedata import TDClient
import pandas as pd
import time
import datetime
import pytz
from typing import Any, Dict, List, Optional
import os
from loguru import logger
import sqlite3
from retry import retry
import random
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import json

logger.remove()
logger.add("stocks_data.log", format="{time} - {name} - {level} - {message}", level="DEBUG", rotation="10 MB")
logger.add(lambda msg: print(msg, end=""), format="{time} - {name} - {level} - {message}", level="DEBUG")

API_KEYS = [
    "0d1cc75b3a244a98ac540c7daeb031f4",
    "affae8a17ff54c0a8aa8de9778118e8a",
    "21442f51f18b4a51b6311131625cb7cf",
    "673c5daaf0534670bf4ea76a80fc6e56",
    "428c585172944da6807ea26b1b8fb2c3",
    "0b396bb6221e426da8d04d8c99dd6f05",
    "529ced0e780b49a2a99dbf9e8d15ebda"
]
DB_PATH = "stock_history.db"
FAISS_INDEX_PATH = "faiss_index.bin"
FAISS_METADATA_PATH = "faiss_metadata.json"
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "GOOGL"]
FETCH_INTERVAL = "1min"
MAX_RETRIES = 3
BACKOFF_FACTOR = 2
API_REQUESTS_PER_MINUTE = 8
SLEEP_BETWEEN_SYMBOL_REQUESTS = 10
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

API_KEY_INDEX = 0
API_KEY_REQUEST_COUNTS = {key: 0 for key in API_KEYS}
LAST_RESET_TIME = time.time()

prev_prices = {}
embedding_model = SentenceTransformer(EMBEDDING_MODEL)

REAL_TIME_PRICES = {
    "NVDA": 105.527,
    "AAPL": 206.126,
    "MSFT": 383.774,
    "GOOGL": 157.946
}

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            datetime TEXT NOT NULL,
            fetch_time TEXT NOT NULL,
            moving_avg REAL,
            volatility REAL,
            text TEXT
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            low REAL,
            high REAL,
            range_low REAL,
            range_high REAL,
            trend_condition TEXT,
            percent REAL,
            reference_price REAL,
            status TEXT NOT NULL
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            message TEXT NOT NULL,
            trigger_time TEXT NOT NULL
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL
        )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON stock_data(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_datetime ON stock_data(datetime)')
        cursor.execute("PRAGMA table_info(stock_data)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'moving_avg' not in columns:
            cursor.execute('ALTER TABLE stock_data ADD COLUMN moving_avg REAL')
            logger.info("Added missing 'moving_avg' column to stock_data table")
        if 'volatility' not in columns:
            cursor.execute('ALTER TABLE stock_data ADD COLUMN volatility REAL')
            logger.info("Added missing 'volatility' column to stock_data table")
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def update_faiss_index(data: pd.DataFrame, metadata: List[Dict]):
    try:
        texts = data['text'].tolist()
        embeddings = embedding_model.encode(texts)
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings)
        faiss.write_index(index, FAISS_INDEX_PATH)
        with open(FAISS_METADATA_PATH, 'w') as f:
            json.dump(metadata, f)
        logger.debug(f"Updated FAISS index with {len(data)} entries")
    except Exception as e:
        logger.error(f"Error updating FAISS index: {e}")

def calculate_analytics(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()
        window_size = 5
        for symbol in df['symbol'].unique():
            mask = df['symbol'] == symbol
            df.loc[mask, 'moving_avg'] = df.loc[mask, 'price'].rolling(window=window_size, min_periods=1).mean()
            df.loc[mask, 'volatility'] = df.loc[mask, 'price'].rolling(window=window_size, min_periods=1).std()
        df['volatility'] = df['volatility'].fillna(0)
        logger.debug(f"Calculated analytics for {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Error calculating analytics: {e}")
        return df

def save_to_db(df: pd.DataFrame):
    if df is None or df.empty:
        logger.warning("No data to save to database")
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        fetch_time = datetime.datetime.now().isoformat()
        df_to_save = df.copy()
        df_to_save['fetch_time'] = fetch_time
        df_to_save['text'] = df_to_save.apply(
            lambda row: f"The current price of {row['symbol']} is ${row['price']} as of {row['datetime']}. "
                       f"Moving average: ${row['moving_avg']:.2f}, Volatility: {row['volatility']:.2f}.",
            axis=1
        )
        metadata = [
            {"type": "stock", "symbol": row['symbol'], "text": row['text']}
            for _, row in df_to_save.iterrows()
        ]
        df_to_save.to_sql('stock_data', conn, if_exists='append', index=False)
        update_faiss_index(df_to_save, metadata)
        conn.close()
        logger.debug(f"Saved data to database: {df_to_save[['symbol', 'price', 'datetime']].to_dict()}")
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise

@retry(tries=MAX_RETRIES, delay=1, backoff=BACKOFF_FACTOR, logger=logger)
def fetch_stock_data(symbols: List[str] = DEFAULT_SYMBOLS, interval: str = FETCH_INTERVAL, outputsize: int = 5) -> pd.DataFrame:
    global API_KEY_INDEX, API_KEY_REQUEST_COUNTS, LAST_RESET_TIME
    try:
        if not symbols:
            raise ValueError("No symbols provided")
        current_time = time.time()
        if current_time - LAST_RESET_TIME >= 60:
            API_KEY_REQUEST_COUNTS = {key: 0 for key in API_KEYS}
            LAST_RESET_TIME = current_time
            logger.debug("Reset API key request counts")
        market_open = is_market_open()
        if not market_open:
            logger.info("Market is closed. Using mock data")
            return create_mock_data(symbols)
        all_data = pd.DataFrame()
        for symbol in symbols:
            api_key = API_KEYS[API_KEY_INDEX]
            API_KEY_REQUEST_COUNTS[api_key] += 1
            logger.debug(f"Using API key {api_key} for {symbol} (Request {API_KEY_REQUEST_COUNTS[api_key]}/{API_REQUESTS_PER_MINUTE})")
            if API_KEY_REQUEST_COUNTS[api_key] > API_REQUESTS_PER_MINUTE:
                logger.info(f"API key {api_key} limit reached, waiting 60 seconds")
                time.sleep(60)
                API_KEY_REQUEST_COUNTS = {key: 0 for key in API_KEYS}
                LAST_RESET_TIME = time.time()
                API_KEY_REQUEST_COUNTS[api_key] = 1
            try:
                td = TDClient(apikey=api_key)
                ts = td.time_series(symbol=symbol, interval=interval, outputsize=outputsize, timezone="America/New_York")
                df = ts.as_pandas()
                if df is not None and not df.empty:
                    df['symbol'] = symbol
                    all_data = pd.concat([all_data, df])
                else:
                    logger.warning(f"No data for {symbol} with key {api_key}, using mock data")
                    mock_df = create_mock_data([symbol])
                    all_data = pd.concat([all_data, mock_df])
            except Exception as e:
                logger.warning(f"Error fetching {symbol} with key {api_key}: {e}, using mock data")
                mock_df = create_mock_data([symbol])
                all_data = pd.concat([all_data, mock_df])
            API_KEY_INDEX = (API_KEY_INDEX + 1) % len(API_KEYS)
            time.sleep(SLEEP_BETWEEN_SYMBOL_REQUESTS)
        if all_data.empty:
            logger.info("No data from API, falling back to mock data")
            return create_mock_data(symbols)
        all_data = all_data.reset_index().rename(columns={"index": "datetime", "close": "price"})
        all_data = all_data[["symbol", "price", "datetime"]]
        all_data['datetime'] = all_data['datetime'].astype(str)
        all_data = calculate_analytics(all_data)
        save_to_db(all_data)
        logger.debug(f"Fetched stock data: {all_data[['symbol', 'price', 'datetime']].to_dict()}")
        return all_data
    except Exception as e:
        logger.error(f"API error: {e}")
        return create_mock_data(symbols)

def create_mock_data(symbols: List[str], base_time=None) -> pd.DataFrame:
    try:
        mock_data = []
        if base_time is None:
            base_time = datetime.datetime.now()
        VOLATILITY = 0.005
        TREND_STRENGTH = 0.0005
        for symbol in symbols:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT price FROM stock_data WHERE symbol = ? ORDER BY datetime DESC LIMIT 1", (symbol,))
            result = cursor.fetchone()
            conn.close()
            base_price = result[0] if result else REAL_TIME_PRICES.get(symbol, 100.0)
            trend_direction = random.choice([-1, 1])
            change = random.gauss(0, VOLATILITY) + (TREND_STRENGTH * trend_direction)
            price_change = base_price * change
            new_price = round(base_price + price_change, 3)
            new_price = max(new_price, base_price * 0.5)
            if random.random() < 0.1:
                jump = random.uniform(0.01, 0.03) * base_price
                new_price = round(new_price + (jump * random.choice([-1, 1])), 3)
            mock_data.append({
                "symbol": symbol,
                "price": new_price,
                "datetime": base_time.strftime("%Y-%m-%d %H:%M:%S")
            })
        df = pd.DataFrame(mock_data)
        df = calculate_analytics(df)
        logger.debug(f"Generated mock data: {df.to_dict()}")
        save_to_db(df)
        return df
    except Exception as e:
        logger.error(f"Error creating mock data: {e}")
        return pd.DataFrame()

def is_market_open() -> bool:
    try:
        now = datetime.datetime.now(pytz.timezone('America/New_York'))
        if now.weekday() >= 5:
            return False
        market_open = now.replace(hour=9, minute=30, second=0)
        market_close = now.replace(hour=16, minute=0, second=0)
        return market_open <= now <= market_close
    except Exception as e:
        logger.error(f"Error checking market status: {e}")
        return False

def monitor_alerts(socketio):
    global prev_prices
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, symbol, alert_type, low, high, range_low, range_high, trend_condition, percent, reference_price FROM alerts WHERE status = 'active'")
        alerts = cursor.fetchall()
        recent_data = pd.read_sql_query("SELECT symbol, price FROM stock_data ORDER BY datetime DESC LIMIT 100", conn)
        logger.debug(f"Checking {len(alerts)} active alerts")
        for alert in alerts:
            alert_id, symbol, alert_type, low, high, range_low, range_high, trend_condition, percent, reference_price = alert
            symbol_data = recent_data[recent_data['symbol'] == symbol]
            if symbol_data.empty:
                logger.info(f"No recent data for {symbol}")
                continue
            latest_price = symbol_data.iloc[0]['price']
            triggered = False
            message = ""
            logger.debug(f"Checking alert for {symbol}: type={alert_type}, price={latest_price}")
            if alert_type == "high_low":
                if low and latest_price < low:
                    message = f"{symbol} dropped below {low}. Price: {latest_price}"
                    triggered = True
                elif high and latest_price > high:
                    message = f"{symbol} rose above {high}. Price: {latest_price}"
                    triggered = True
            elif alert_type == "percent_change" and percent is not None and reference_price is not None:
                change = (latest_price - reference_price) / reference_price * 100
                if (percent > 0 and change >= percent) or (percent < 0 and change <= percent):
                    message = f"{symbol} price changed by {change:.2f}% from {reference_price} to {latest_price}"
                    triggered = True
            elif alert_type == "price_change":
                prev_price = prev_prices.get(symbol, latest_price)
                if prev_price and abs(latest_price - prev_price) / prev_price * 100 >= 0.01:
                    change = ((latest_price - prev_price) / prev_price) * 100
                    message = f"{symbol} price changed by {change:.2f}% from {prev_price} to {latest_price}"
                    triggered = True
            if triggered:
                logger.info(f"Alert triggered: {message}")
                cursor.execute("UPDATE alerts SET status = 'triggered' WHERE id = ?", (alert_id,))
                cursor.execute('''
                INSERT INTO alert_history (alert_id, symbol, message, trigger_time)
                VALUES (?, ?, ?, ?)
                ''', (alert_id, symbol, message, datetime.datetime.now().isoformat()))
                logger.debug(f"Emitting alert_triggered: {message}")
                socketio.emit('alert_triggered', {'message': message})
            prev_prices[symbol] = latest_price
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error monitoring alerts: {e}")

def create_alert(symbol: str, alert_type: str, low: float = None, high: float = None, range_low: float = None, range_high: float = None, trend_condition: str = None, percent: float = None, reference_price: float = None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO alerts (symbol, alert_type, low, high, range_low, range_high, trend_condition, percent, reference_price, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, alert_type, low, high, range_low, range_high, trend_condition, percent, reference_price, 'active'))
        conn.commit()
        conn.close()
        logger.debug(f"Created alert for {symbol}: {alert_type}")
    except Exception as e:
        logger.error(f"Error creating alert: {e}")

class StockDataConnector(pw.io.python.ConnectorSubject):
    def __init__(self, symbols: List[str], socketio):
        super().__init__()
        self.symbols = symbols
        self.socketio = socketio
        self.last_timestamp = None

    def run(self):
        try:
            while True:
                market_open = is_market_open()
                if market_open:
                    df = fetch_stock_data(self.symbols)
                else:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("SELECT MAX(datetime) FROM stock_data")
                    result = cursor.fetchone()
                    conn.close()
                    self.last_timestamp = pd.to_datetime(result[0]) if result[0] else datetime.datetime.now()
                    self.last_timestamp += datetime.timedelta(minutes=1)
                    df = create_mock_data(self.symbols, self.last_timestamp)
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        record = {
                            "symbol": row["symbol"],
                            "price": float(row["price"]),
                            "timestamp": pd.to_datetime(row["datetime"]).replace(tzinfo=pytz.UTC).isoformat()
                        }
                        self.socketio.emit('stock_update', record)
                        logger.debug(f"Streamed: {record['symbol']} - ${record['price']} at {record['timestamp']}")
                    monitor_alerts(self.socketio)
                time.sleep(5)
        except Exception as e:
            logger.error(f"Error in StockDataConnector: {e}")

def stream_stock_data(symbols: List[str], socketio):
    try:
        class StockSchema(pw.Schema):
            symbol: str
            price: float
            timestamp: str
        connector = StockDataConnector(symbols, socketio)
        table = pw.io.python.read(connector, schema=StockSchema)
        def on_row(row: dict):
            logger.debug(f"Pathway processed: {row['symbol']} - ${row['price']} at {row['timestamp']}")
        pw.io.subscribe(table, on_row)
        return table
    except Exception as e:
        logger.error(f"Error streaming stock data: {e}")
        return None

def pipeline(symbols: List[str], socketio):
    try:
        init_db()
        analytics_table = stream_stock_data(symbols, socketio)
        pw.run()
        logger.info("Pathway pipeline running")
    except Exception as e:
        logger.error(f"Error in pipeline: {e}")

if __name__ == "__main__":
    pipeline(DEFAULT_SYMBOLS, None)