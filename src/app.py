import sys
import os
import requests
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import sqlite3
import pandas as pd
import threading
from loguru import logger
from llm_query import query_llm
from datetime import datetime, timedelta
import time

app = Flask(__name__, template_folder="../templates")
app.config["SECRET_KEY"] = "your-secret-key"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Logging setup
logger.remove()
logger.add(
    "stocks_data.log",
    format="{time} - {name} - {level} - {message}",
    level="DEBUG",
    rotation="10 MB",
)
logger.add(
    lambda msg: print(msg, end=""),
    format="{time} - {name} - {level} - {message}",
    level="DEBUG",
)

DB_PATH = "stock_history.db"
current_symbols = ["NVDA", "AAPL", "MSFT", "GOOGL"]
pipeline_thread = None
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "YOUR_POLYGON_API_KEY_HERE")  # Use environment variable or placeholder

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        logger.debug("Database connection established")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

def start_pipeline():
    global pipeline_thread
    try:
        if pipeline_thread is None or not pipeline_thread.is_alive():
            logger.info("Starting Pathway pipeline")
            from ingestion import pipeline
            pipeline_thread = threading.Thread(
                target=pipeline, args=(current_symbols, socketio)
            )
            pipeline_thread.daemon = True
            pipeline_thread.start()
            logger.info("Pathway pipeline started")
    except Exception as e:
        logger.error(f"Error starting pipeline: {e}")

def get_mock_ipo_data(limit=10):
    """Return mock IPO data for consistent display"""
    try:
        # Simulate recent and upcoming IPOs with realistic data
        base_date = datetime.now()
        mock_ipos = [
            {
                "company": "TechTrend Innovations",
                "symbol": "TTI",
                "ipo_date": (base_date + timedelta(days=10)).strftime("%Y-%m-%d"),
                "price_range": "$12-$15"
            },
            {
                "company": "GreenWave Energy",
                "symbol": "GWE",
                "ipo_date": (base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
                "price_range": "$18-$22"
            },
            {
                "company": "AIHealth Solutions",
                "symbol": "AIHS",
                "ipo_date": (base_date - timedelta(days=2)).strftime("%Y-%m-%d"),
                "price_range": "$25-$30"
            },
            {
                "company": "Quantum Computing Inc.",
                "symbol": "QCI",
                "ipo_date": (base_date + timedelta(days=15)).strftime("%Y-%m-%d"),
                "price_range": "$10-$14"
            },
            {
                "company": "EcoMaterials Ltd.",
                "symbol": "EML",
                "ipo_date": (base_date - timedelta(days=10)).strftime("%Y-%m-%d"),
                "price_range": "$16-$20"
            }
        ]
        logger.debug(f"Generated mock IPO data: {len(mock_ipos)} IPOs")
        return mock_ipos[:limit]
    except Exception as e:
        logger.error(f"Error generating mock IPO data: {e}")
        return None

def background_ipo_task():
    """Periodically emit IPO data to keep frontend updated"""
    while True:
        try:
            ipo_data = get_mock_ipo_data(limit=10)
            if ipo_data:
                socketio.emit("ipo_update", {"ipos": ipo_data})
                logger.debug("Emitted IPO data via SocketIO")
            else:
                logger.warning("No IPO data to emit")
            time.sleep(30)  # Emit every 30 seconds
        except Exception as e:
            logger.error(f"Error in background IPO task: {e}")
            time.sleep(30)

@app.route("/")
def index():
    logger.info("Serving index.html")
    return render_template("index.html")

@app.route("/api/data", methods=["GET"])
def get_data():
    try:
        conn = get_db_connection()
        query = """
        SELECT symbol, price, datetime, moving_avg, volatility 
        FROM stock_data 
        WHERE symbol IN ({}) 
        ORDER BY datetime DESC 
        LIMIT 100
        """.format(",".join("?" for _ in current_symbols))
        df = pd.read_sql_query(query, conn, params=current_symbols)
        conn.close()
        if df.empty:
            logger.warning("No data found in database")
            return jsonify({"error": "No data available", "symbols": current_symbols}), 200
        data = (
            df.groupby("symbol")
            .apply(lambda x: x[["price", "datetime", "moving_avg", "volatility"]].to_dict(orient="records"))
            .to_dict()
        )
        logger.debug(f"API /api/data returned data for symbols: {list(data.keys())}")
        return jsonify({"data": data, "symbols": current_symbols})
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return jsonify({"error": str(e), "symbols": current_symbols}), 500

@app.route("/api/alert_history", methods=["GET"])
def get_alert_history():
    try:
        conn = get_db_connection()
        query = "SELECT message, trigger_time FROM alert_history ORDER BY trigger_time DESC LIMIT 50"
        df = pd.read_sql_query(query, conn)
        conn.close()
        alerts = df.to_dict(orient="records")
        logger.debug(f"Fetched alert history: {len(alerts)} alerts")
        return jsonify({"alerts": alerts})
    except Exception as e:
        logger.error(f"Error fetching alert history: {e}")
        return jsonify({"alerts": [], "error": str(e)}), 500

@app.route("/api/ipo_data", methods=["GET"])
def get_ipo_data():
    try:
        ipo_data = get_mock_ipo_data(limit=10)
        if ipo_data:
            logger.debug(f"Fetched IPO data: {len(ipo_data)} IPOs")
            return jsonify({"ipos": ipo_data})
        else:
            logger.warning("No IPO data returned from mock data")
            fallback_data = [
                {
                    "company": "TechTrend Innovations",
                    "symbol": "TTI",
                    "ipo_date": "2025-06-15",
                    "price_range": "$12-$15"
                },
                {
                    "company": "GreenWave Energy",
                    "symbol": "GWE",
                    "ipo_date": "2025-07-01",
                    "price_range": "$18-$22"
                }
            ]
            logger.info(f"Using fallback IPO data: {len(fallback_data)} IPOs")
            return jsonify({"ipos": fallback_data})
    except Exception as e:
        logger.error(f"Error fetching IPO data: {e}")
        fallback_data = [
            {
                "company": "TechTrend Innovations",
                "symbol": "TTI",
                "ipo_date": "2025-06-15",
                "price_range": "$12-$15"
            },
            {
                "company": "GreenWave Energy",
                "symbol": "GWE",
                "ipo_date": "2025-07-01",
                "price_range": "$18-$22"
            }
        ]
        logger.info(f"Using fallback IPO data: {len(fallback_data)} IPOs")
        return jsonify({"ipos": fallback_data})

@app.route("/api/news_data", methods=["GET"])
def get_news_data():
    try:
        conn = get_db_connection()
        query = "SELECT title, date FROM news ORDER BY date DESC LIMIT 10"
        df = pd.read_sql_query(query, conn)
        conn.close()
        news_data = df.to_dict(orient="records")
        logger.debug(f"Fetched news data: {len(news_data)} articles")
        return jsonify({"news": news_data})
    except Exception as e:
        logger.error(f"Error fetching news data: {e}")
        fallback_data = [
            {
                "title": "Tech stocks rally as AI sector shows strong growth",
                "date": "2025-05-03"
            },
            {
                "title": "Federal Reserve signals steady interest rates",
                "date": "2025-05-02"
            }
        ]
        logger.info(f"Using fallback news data: {len(fallback_data)} articles")
        return jsonify({"news": fallback_data})

@app.route("/api/set_alert", methods=["POST"])
def set_alert():
    try:
        data = request.json
        alert_type = data.get("alert_type")
        symbol = data.get("symbol").upper()
        value = data.get("value", "")
        if not symbol or not alert_type:
            logger.warning("Missing symbol or alert_type in set_alert request")
            return jsonify({"error": "Symbol and alert type are required"}), 400
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT price FROM stock_data WHERE symbol = ? ORDER BY datetime DESC LIMIT 1",
            (symbol,),
        )
        result = cursor.fetchone()
        reference_price = result["price"] if result else None
        from ingestion import create_alert
        if alert_type == "price_change":
            create_alert(symbol, "price_change", reference_price=reference_price)
            response = f"Alert set for {symbol} price change."
        elif alert_type == "percent_change":
            percent = float(value) if value else 0.02
            create_alert(
                symbol,
                "percent_change",
                percent=percent,
                reference_price=reference_price,
            )
            response = f"Alert set for {symbol} {percent}% change."
        elif alert_type == "high_low":
            threshold = float(value) if value else None
            if threshold:
                create_alert(
                    symbol, "high_low", low=threshold * 0.95, high=threshold * 1.05
                )
                response = f"Alert set for {symbol} high/low around {threshold} (±5%)."
            else:
                logger.warning("Value required for high/low alert")
                return jsonify({"error": "Value required for high/low alert"}), 400
        else:
            logger.warning(f"Invalid alert type: {alert_type}")
            return jsonify({"error": "Invalid alert type"}), 400
        conn.close()
        logger.info(f"Emitting query_response: {response}")
        socketio.emit("query_response", {"response": response})
        return jsonify({"status": "success", "message": response})
    except Exception as e:
        logger.error(f"Error setting alert: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/query", methods=["POST"])
def handle_query():
    try:
        query = request.json.get("query", "").lower()
        logger.info(f"Received query: {query}")
        conn = get_db_connection()
        if "notify" in query:
            symbol = None
            for s in current_symbols:
                if s.lower() in query:
                    symbol = s
                    break
            if symbol:
                if "increase" in query:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT price FROM stock_data WHERE symbol = ? ORDER BY datetime DESC LIMIT 1",
                        (symbol,),
                    )
                    result = cursor.fetchone()
                    reference_price = result["price"] if result else None
                    if reference_price:
                        from ingestion import create_alert
                        create_alert(
                            symbol,
                            "percent_change",
                            percent=0.02,
                            reference_price=reference_price,
                        )
                        response = f"Alert set for {symbol} price increase."
                        logger.info(f"Emitting query_response: {response}")
                        socketio.emit("query_response", {"response": response})
                elif "change" in query:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT price FROM stock_data WHERE symbol = ? ORDER BY datetime DESC LIMIT 1",
                        (symbol,),
                    )
                    result = cursor.fetchone()
                    reference_price = result["price"] if result else None
                    if reference_price:
                        from ingestion import create_alert
                        create_alert(
                            symbol, "price_change", reference_price=reference_price
                        )
                        response = f"Alert set for {symbol} price change."
                        logger.info(f"Emitting query_response: {response}")
                        socketio.emit("query_response", {"response": response})
        response = query_llm(query)
        logger.debug(f"LLM raw response: {response}")
        response_str = str(response).strip() if response else "No response from LLM"
        logger.info(f"Emitting query_response: {response_str}")
        socketio.emit("query_response", {"response": response_str})
        conn.close()
        logger.info(f"Query processed successfully for: {query}")
        return jsonify({"status": "success", "response": response_str})
    except Exception as e:
        logger.error(f"Error handling query: {e}")
        error_response = f"Error processing query: {str(e)}"
        socketio.emit("query_response", {"response": error_response})
        return jsonify({"error": str(e)}), 500

@app.route("/api/update_symbols", methods=["POST"])
def update_symbols():
    global current_symbols
    try:
        symbols = request.json.get("symbols", "")
        new_symbols = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if not new_symbols:
            logger.warning("No valid symbols provided in update_symbols request")
            return jsonify({"error": "No valid symbols provided"}), 400
        current_symbols = new_symbols
        logger.info(f"Updated symbols: {current_symbols}")
        start_pipeline()
        return jsonify({"status": "success", "symbols": current_symbols})
    except Exception as e:
        logger.error(f"Error updating symbols: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    logger.info("Starting Flask server and Pathway pipeline")
    start_pipeline()
    # Start background task for IPO data emission
    ipo_thread = threading.Thread(target=background_ipo_task, daemon=True)
    ipo_thread.start()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
