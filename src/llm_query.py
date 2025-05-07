import os
import requests
from loguru import logger
import sqlite3
import pandas as pd
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional

# Setup logging
logger.remove()
logger.add("stocks_data.log", format="{time} - {name} - {level} - {message}", level="DEBUG", rotation="10 MB")
logger.add(lambda msg: print(msg, end=""), format="{time} - {name} - {level} - {message}", level="DEBUG")

DB_PATH = "stock_history.db"
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "YOUR_TOGETHER_API_KEY_HERE")
TOGETHER_API_URL = "https://api.together.ai/v1/chat/completions"
FAISS_INDEX_PATH = "faiss_index.bin"
FAISS_METADATA_PATH = "faiss_metadata.json"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Initialize embedding model
try:
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    logger.debug("SentenceTransformer model loaded")
except Exception as e:
    logger.error(f"Error loading SentenceTransformer: {e}")
    raise

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        logger.debug("Database connection established")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

def load_faiss_index() -> Optional[faiss.IndexFlatL2]:
    try:
        if os.path.exists(FAISS_INDEX_PATH):
            index = faiss.read_index(FAISS_INDEX_PATH)
            logger.debug("Loaded FAISS index")
            return index
        logger.warning("FAISS index file not found")
        return None
    except Exception as e:
        logger.error(f"Error loading FAISS index: {e}")
        return None

def fetch_stock_data(symbol: str) -> Dict:
    try:
        conn = get_db_connection()
        query = """
        SELECT price, datetime, moving_avg, volatility 
        FROM stock_data 
        WHERE symbol = ? 
        ORDER BY datetime DESC 
        LIMIT 10
        """
        df = pd.read_sql_query(query, conn, params=(symbol,))
        conn.close()
        if df.empty:
            logger.warning(f"No data for {symbol}")
            return {"error": f"No data for {symbol}"}
        latest = df.iloc[0]
        trends = df[['price', 'datetime']].to_dict(orient="records")
        logger.debug(f"Fetched stock data for {symbol}")
        return {
            "latest_price": latest["price"],
            "datetime": latest["datetime"],
            "moving_avg": latest["moving_avg"],
            "volatility": latest["volatility"],
            "trends": trends
        }
    except Exception as e:
        logger.error(f"Error fetching stock data for {symbol}: {e}")
        return {"error": str(e)}

def fetch_ipo_data() -> List[Dict]:
    try:
        url = "https://stock-market-ipo.p.rapidapi.com/sme"
        headers = {
            "x-rapidapi-key": os.getenv("RAPIDAPI_KEY", "YOUR_RAPIDAPI_KEY_HERE"),
            "x-rapidapi-host": "stock-market-ipo.p.rapidapi.com",
        }
        response = requests.get(url, headers=headers)
        logger.debug(f"IPO API response status: {response.status_code}")
        if response.status_code == 200:
            ipo_data = response.json()
            ipos = [
                {
                    "company": ipo.get("companyName", "Unknown"),
                    "symbol": ipo.get("symbol", "N/A"),
                    "ipo_date": ipo.get("ipoDate", "N/A"),
                    "price_range": ipo.get("priceRange", "N/A"),
                }
                for ipo in ipo_data
            ]
            logger.debug(f"Fetched {len(ipos)} IPOs")
            return ipos
        else:
            logger.warning(f"IPO API failed with status {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching IPO data: {e}")
        return []

def fetch_news_data() -> List[Dict]:
    try:
        conn = get_db_connection()
        query = "SELECT title, date FROM news ORDER BY date DESC LIMIT 5"
        df = pd.read_sql_query(query, conn)
        conn.close()
        news = df.to_dict(orient="records")
        logger.debug(f"Fetched {len(news)} news articles")
        return news
    except Exception as e:
        logger.error(f"Error fetching news data: {e}")
        return []

def fetch_alerts(symbol: str) -> List[Dict]:
    try:
        conn = get_db_connection()
        query = "SELECT message, trigger_time FROM alert_history WHERE symbol = ? ORDER BY trigger_time DESC LIMIT 5"
        df = pd.read_sql_query(query, conn, params=(symbol,))
        conn.close()
        alerts = df.to_dict(orient="records")
        logger.debug(f"Fetched {len(alerts)} alerts for {symbol}")
        return alerts
    except Exception as e:
        logger.error(f"Error fetching alerts for {symbol}: {e}")
        return []

def semantic_search(query: str, index: faiss.IndexFlatL2, metadata: List[Dict], top_k: int = 5) -> List[Dict]:
    try:
        query_embedding = embedding_model.encode([query])[0]
        D, I = index.search(np.array([query_embedding]), top_k)
        results = [metadata[i] for i in I[0] if i < len(metadata)]
        logger.debug(f"Semantic search results: {results}")
        return results
    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        return []

def query_llm(query: str) -> str:
    try:
        symbols = ["NVDA", "AAPL", "MSFT", "GOOGL"]
        query_lower = query.lower()
        context = []
        for symbol in symbols:
            if symbol.lower() in query_lower and ("price" in query_lower or "value" in query_lower):
                stock_data = fetch_stock_data(symbol)
                if "error" not in stock_data:
                    context.append(
                        f"Latest price of {symbol}: ${stock_data['latest_price']} as of {stock_data['datetime']}.\n"
                        f"Moving average: ${stock_data['moving_avg']:.2f}, Volatility: {stock_data['volatility']:.2f}.\n"
                        f"Recent trends: {', '.join([f'${t['price']} at {t['datetime']}' for t in stock_data['trends'][:3]])}."
                    )
                    alerts = fetch_alerts(symbol)
                    if alerts:
                        context.append(f"Recent alerts for {symbol}: {', '.join([a['message'] for a in alerts[:2]])}.")
                else:
                    context.append(f"No recent price data for {symbol}.")
        if "ipo" in query_lower:
            ipos = fetch_ipo_data()
            if ipos:
                context.append(
                    "Recent IPOs:\n" +
                    "\n".join([f"- {ipo['company']} ({ipo['symbol']}): IPO Date {ipo['ipo_date']}, Price Range {ipo['price_range']}" for ipo in ipos[:3]])
                )
            else:
                context.append("No recent IPO data available.")
        if "news" in query_lower or "market" in query_lower:
            news = fetch_news_data()
            if news:
                context.append(
                    "Recent Market News:\n" +
                    "\n".join([f"- {n['title']} ({n['date']})" for n in news[:3]])
                )
            else:
                context.append("No recent news available.")
        index = load_faiss_index()
        if index:
            import json
            with open(FAISS_METADATA_PATH, 'r') as f:
                metadata = json.load(f)
            search_results = semantic_search(query, index, metadata)
            if search_results:
                context.append(
                    "Relevant Data:\n" +
                    "\n".join([f"- {r['type']}: {r['text']}" for r in search_results])
                )
        prompt = f"Query: {query}\n\nContext:\n{''.join(context) if context else 'No relevant data found.'}\n\nAnswer based on the context where available, otherwise use your knowledge."
        headers = {
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "meta-llama/Llama-3-8b-chat-hf",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512,
            "temperature": 0.7,
            "top_p": 0.7,
            "top_k": 50,
            "repetition_penalty": 1,
            "stop": ["<|eot_id|>"]
        }
        response = requests.post(TOGETHER_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        answer = result['choices'][0]['message']['content'].strip()
        logger.debug(f"LLM response: {answer}")
        return answer
    except Exception as e:
        logger.error(f"Together AI API error: {e}")
        return f"Sorry, I couldn't process your query due to an error: {str(e)}. Please try again later."
