# StockPulse: Your Real-Time Stock Market Companion

*"Stay ahead of the market with StockPulse – where real-time data meets intelligent insights."*

**StockPulse** is a dynamic web application that delivers live stock market data, IPO updates, market news, and personalized alerts through an interactive dashboard. Built with a Flask backend, a sleek frontend using Chart.js, and SocketIO for real-time updates, it’s perfect for traders, investors, and financial enthusiasts. The project shines by leveraging **Retrieval-Augmented Generation (RAG)** for smart query handling and **Pathway** for scalable, real-time data processing.

This README is your comprehensive guide to understanding, setting up, and running StockPulse. It emphasizes the core technologies—RAG and Pathway—and provides clear instructions for configuring your development environment using **Windows Subsystem for Linux (WSL)** and **Python virtual environments (venv)**. Whether you’re a beginner or an experienced developer, this guide will help you get StockPulse up and running on GitHub.

## Table of Contents
- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Technologies Used](#technologies-used)
- [Core Components](#core-components)
  - [Retrieval-Augmented Generation (RAG)](#retrieval-augmented-generation-rag)
  - [Pathway for Real-Time Data Processing](#pathway-for-real-time-data-processing)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
  - [Prerequisites](#prerequisites)
  - [Setting Up WSL](#setting-up-wsl)
  - [Creating a Virtual Environment](#creating-a-virtual-environment)
  - [Installing Dependencies](#installing-dependencies)
  - [Configuring API Keys](#configuring-api-keys)
  - [Running the Application](#running-the-application)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Project Overview

StockPulse is a full-stack web application designed to provide real-time insights into the stock market. It allows users to monitor live stock prices, set custom alerts, query market data using natural language, and visualize trends through dynamic charts. The project integrates advanced technologies like **RAG** for context-aware query responses and **Pathway** for efficient, scalable data streaming.

The backend, built with Flask, uses SQLite for data storage and fetches stock data from the [Twelve Data API](https://twelvedata.com/). When markets are closed or API limits are reached, StockPulse generates realistic mock data. The frontend, crafted with HTML, CSS, JavaScript, and Chart.js, offers a modern, user-friendly interface. Real-time updates are powered by SocketIO, ensuring a seamless experience. For natural language queries, StockPulse uses the [Together AI API](https://together.ai/) to deliver accurate, data-driven answers.

This project is ideal for showcasing on GitHub, demonstrating expertise in AI, real-time data processing, and full-stack development.

## Key Features

| Feature | Description |
|---------|-------------|
| **Real-Time Stock Data** | Streams live prices for stocks like NVDA, AAPL, and more using Pathway. |
| **Interactive Dashboard** | Displays charts, IPOs, news, and alerts with a futuristic UI. |
| **Natural Language Queries** | Ask questions like “What’s AAPL’s price?” and get answers via RAG. |
| **Custom Alerts** | Set price change or threshold alerts with instant notifications. |
| **Mock Data Fallback** | Simulates realistic stock data during market closures or API limits. |
| **Scalable Processing** | Pathway handles large-scale, real-time data ingestion and analytics. |
| **Persistent Storage** | Stores data in SQLite with FAISS indexing for fast retrieval. |

## Technologies Used

### Backend
- **Python 3.10+**: Core programming language.
- **Flask**: Lightweight web framework for the backend.
- **Flask-SocketIO**: Enables real-time communication with the frontend.
- **Pathway**: Processes real-time data streams and analytics.
- **SQLite**: Stores stock data, alerts, and news.
- **FAISS**: Powers fast semantic search for RAG.
- **Sentence Transformers**: Generates embeddings for query processing.
- **Pandas**: Handles data manipulation and analytics.
- **Loguru**: Simplifies logging for debugging.
- **Twelve Data API**: Provides real-time stock data.
- **Together AI API**: Drives natural language query responses.

### Frontend
- **HTML5, CSS3, JavaScript**: Builds the user interface.
- **Chart.js**: Creates dynamic stock price visualizations.
- **SocketIO**: Delivers real-time updates to the dashboard.
- **Google Fonts (Orbitron, Inter)**: Enhances typography.

### Development Tools
- **WSL**: Provides a Linux environment for Windows users.
- **venv**: Isolates Python dependencies.
- **Git**: Manages version control.

## Core Components

### Retrieval-Augmented Generation (RAG)

**What is RAG?**  
Retrieval-Augmented Generation (RAG) is an advanced AI technique that combines information retrieval with language model generation. Unlike traditional language models that rely solely on pre-trained knowledge, RAG retrieves relevant data from a knowledge base to provide accurate, context-specific answers. In StockPulse, RAG is implemented in `llm_query.py` to answer user queries about stocks, IPOs, and market trends.

#### How RAG Works in StockPulse
1. **Query Embedding**:
   - When a user asks a question (e.g., “What is AAPL’s current price?”), the query is converted into a vector using the `all-MiniLM-L6-v2` Sentence Transformer model from [Hugging Face](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).
2. **Semantic Search**:
   - The query vector is searched against a FAISS index (`faiss_index.bin`), which stores embeddings of stock data, news, and alerts. FAISS, developed by [Meta AI](https://ai.meta.com/tools/faiss/), ensures fast and accurate retrieval.
3. **Context Augmentation**:
   - Relevant data (e.g., latest prices, trends, or news) is combined with the query to create a detailed prompt.
4. **Response Generation**:
   - The prompt is sent to the Together AI API, using the Llama-3-8b model, to generate a precise response.
5. **Fallback Mechanisms**:
   - If APIs are unavailable, mock data ensures continuous functionality.

#### Example Query
- **Input**: “Has TSLA had any major news today?”
- **Process**: RAG retrieves recent TSLA news, summarizes it, and generates a response like: “TSLA’s stock rose 3% today after announcing a new factory opening.”
- **Output**: A concise, data-driven answer grounded in real-time information.

#### Why RAG?
- **Accuracy**: Reduces errors by using up-to-date data.
- **Relevance**: Delivers answers tailored to the query.
- **Scalability**: FAISS handles large datasets efficiently.
- **Flexibility**: Adapts to new data types or queries.

### Pathway for Real-Time Data Processing

**What is Pathway?**  
Pathway is a Python framework for building scalable, real-time data pipelines, ideal for applications requiring live data processing. In StockPulse, Pathway, implemented in `ingestion.py`, manages stock data ingestion, analytics, and alert monitoring. Learn more about Pathway at [Pathway’s official site](https://pathway.com/).

#### How Pathway Works in StockPulse
1. **Data Ingestion**:
   - The `StockDataConnector` class fetches live stock data from the Twelve Data API for user-selected symbols (e.g., AAPL, NVDA). During market closures, it generates mock data with realistic trends.
2. **Real-Time Streaming**:
   - Pathway processes data streams, emitting updates to the frontend via SocketIO.
3. **Analytics**:
   - Computes metrics like moving averages and volatility using a 5-point sliding window.
4. **Alert Monitoring**:
   - Continuously checks user-defined alerts (e.g., “Notify if AAPL drops below $140”) and triggers notifications when conditions are met.
5. **Persistence**:
   - Stores data in SQLite (`stock_history.db`) and updates the FAISS index for RAG.

#### Example Workflow
- **Input**: User tracks AAPL with an alert for a 5% price drop.
- **Process**: Pathway streams AAPL’s price, detects a 5% drop, and sends a SocketIO notification.
- **Output**: The dashboard updates instantly, and the user receives an alert.

#### Why Pathway?
- **Scalability**: Handles high-volume data streams.
- **Real-Time**: Ensures instant updates for a dynamic UI.
- **Simplicity**: Abstracts complex streaming logic.
- **Integration**: Works seamlessly with Flask and SocketIO.

## Project Structure

```
StockPulse/
│
├── app.py                    # Main Flask app with API routes and SocketIO
├── ingestion.py              # Pathway pipeline for real-time data
├── llm_query.py              # RAG for natural language queries
├── populate_historical_data.py # Populates SQLite with mock data
├── templates/
│   └── index.html            # Frontend dashboard with Chart.js
├── stocks_data.log           # Debug logs
├── stock_history.db          # SQLite database (auto-generated)
├── faiss_index.bin           # FAISS index for RAG
├── faiss_metadata.json       # FAISS index metadata
├── requirements.txt          # Python dependencies
└── README.md                 # This documentation
```

## Setup Instructions

### Prerequisites
- **Operating System**: Windows, macOS, or Linux (WSL recommended for Windows).
- **Python**: 3.10 or higher.
- **Git**: For cloning the repository.
- **API Keys**:
  - [Twelve Data API](https://twelvedata.com/) for stock data.
  - [Together AI API](https://together.ai/) for language model queries.
- **WSL**: For Windows users, to run a Linux environment.
- **Node.js**: Optional, for frontend tweaks.

### Setting Up WSL
WSL allows Windows users to run a Linux environment, simplifying dependency management.

1. **Install WSL2**:
   ```bash
   wsl --install
   ```
   Installs Ubuntu by default. Set up a username and password as prompted.
2. **Update Ubuntu**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
3. **Install Python**:
   ```bash
   sudo apt install python3 python3-pip python3-venv -y
   ```
4. **Verify**:
   ```bash
   python3 --version
   ```

### Creating a Virtual Environment
A virtual environment isolates project dependencies.

1. **Clone the Repository**:
   ```bash
   https://github.com/kshitizsinghal13/StockPulse.git
   cd StockPulse
   ```
2. **Create venv**:
   ```bash
   python3 -m venv venv
   ```
3. **Activate venv**:
   - Linux/macOS/WSL:
     ```bash
     source venv/bin/activate
     ```
   - Windows (non-WSL):
     ```bash
     venv\Scripts\activate
     ```
4. **Verify**: Terminal prompt shows `(venv)`.

### Installing Dependencies
With venv active:
```bash
pip install -r requirements.txt
```

Sample `requirements.txt`:
```
flask==2.3.3
flask-socketio==5.3.6
pathway==0.10.1
pandas==2.2.2
faiss-cpu==1.8.0
sentence-transformers==3.0.1
loguru==0.7.2
twelvedata==1.2.10
requests==2.32.3
retry==0.9.2
```

### Configuring API Keys
1. **Twelve Data API**:
   - Edit `ingestion.py`:
     ```python
     API_KEYS = ["your_api_key_1", "your_api_key_2"]
     ```
2. **Together AI API**:
   - Edit `llm_query.py`:
     ```python
     TOGETHER_API_KEY = "your_together_api_key"
     ```

### Running the Application
1. **Populate Historical Data** (optional):
   ```bash
   python populate_historical_data.py
   ```
2. **Start Flask Server**:
   ```bash
   python app.py
   ```
3. **Access Dashboard**:
   - Open [http://localhost:5000](http://localhost:5000) in a browser.

## Usage

- **Dashboard**: View live stock charts, IPOs, news, and alerts for default symbols (NVDA, AAPL, etc.).
- **Set Alerts**: Add alerts for price changes or thresholds in the “Alerts” section.
- **Query AI**: Ask questions like “What’s TSLA’s volatility?” in the “Ask StockPulse AI” section.
- **Update Watchlist**: Add symbols (e.g., TSLA, AMZN) to track in the “Watchlist” section.

## Contributing

We welcome contributions to enhance StockPulse! To contribute:
1. Fork the repository.
2. Create a branch: `git checkout -b feature/your-feature`.
3. Commit changes: `git commit -m "Add feature"`.
4. Push: `git push origin feature/your-feature`.
5. Open a pull request on GitHub.

Report bugs or suggest features via the [Issues page](https://github.com/your-username/StockPulse/issues).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

Happy trading with **StockPulse**! 🚀
