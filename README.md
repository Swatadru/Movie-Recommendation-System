# 🎬 CineVision: Premium Movie Recommendation Oracle

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-red.svg)](https://www.python.org/downloads/)
[![ML](https://img.shields.io/badge/ML-Content--Based-blue.svg)](https://en.wikipedia.org/wiki/Recommender_system)

CineVision is a production-grade, Netflix-inspired movie recommendation platform. It leverages advanced Content-Based Filtering and the TMDB API to deliver a high-fidelity, cinematic browsing experience directly in your browser.

![CineVision Preview](image.webp)

---

## ✨ Features

- **🚀 Cinematic UI/UX**: Sticky navigation, glassmorphic card designs, and dynamic hero banners with radial overlays.
- **🧠 ML-Powered Engine**: Uses `CountVectorizer` and `Cosine Similarity` to analyze movie metadata (genres, keywords, cast, crew) and find your next favorites.
- **🛰️ Real-time Metadata**: Integrated with TMDB API for high-definition posters, backdrops, ratings, and YouTube trailers.
- **⚡ Performance Optimized**: Implements **Parallel Threading** for near-instant metadata fetching and **Resource Caching** for a lag-free experience.
- **🛡️ Resilience Logic**: Features an automated **"Cold Start"** system that self-trains the recommendation models on the first deployment run.

---

## 🛠️ Technology Stack

- **Frontend**: Streamlit (with Custom CSS/HTML Injection)
- **Machine Learning**: Scikit-learn, Pandas, NumPy, NLTK
- **APIs**: The Movie Database (TMDB)
- **Packaging**: Pickle, Python-dotenv

---

## 🚀 Quick Start & Deployment

### 1. Local Setup
```bash
# Clone the repository
git clone https://github.com/Swatadru/Movie-Recommendation-System.git
cd Movie-Recommendation-System

# Install dependencies
pip install -r requirements.txt

# Run the platform
streamlit run app.py
```

### 2. Environment Configuration
Create a `.env` file or set your Streamlit Secrets with the following key:
```env
TMDB_API_KEY = "your_api_key_here"
```

### 3. Automated Training
The app is designed to be autonomous. On its first run, it will detect missing model files and automatically execute `train.py` using the included TMDB 5k dataset files.

---

## 📂 Project Structure

```text
├── assets/             # Premium CSS styles
├── app.py              # Main Streamlit Application
├── train.py            # ML Training Pipeline & Model Generator
├── requirements.txt    # Project Dependencies
├── movie_list.pkl      # Precomputed Movie Data (Optimized)
├── similarity.pkl      # Content Similarity Matrix (Optimized float16)
└── tmdb_5000_*.csv     # Raw Dataset files
```

---

## 🤝 Contribution
Contributions are welcome! If you have ideas for improving the recommendation algorithm or adding new UI features, feel free to fork the repo and submit a PR.

---

## ⚖️ License & Data Attribution
Data provided by **The Movie Database (TMDB)**. This project is for educational and portfolio purposes.

*Created with ❤️ by Swatadru*
