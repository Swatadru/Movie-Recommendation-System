import streamlit as st
import pickle
import pandas as pd
import requests
import os
from dotenv import load_dotenv
import time
from concurrent.futures import ThreadPoolExecutor

# Load environment variables
load_dotenv()

# Configuration
st.set_page_config(
    page_title="CineVision | Premium Movie Recommendations",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Constants
API_KEY = os.getenv("TMDB_API_KEY", "8265bd1679663a7ea12ac168da84d2e8")
BASE_IMAGE_URL = "https://image.tmdb.org/t/p"
POSTER_SIZE = "w500"
BACKDROP_SIZE = "original"

# Initialize Session for better performance
# We use a global session or defined outside threads to avoid st.session_state in threads
if 'api_session' not in st.session_state:
    st.session_state.api_session = requests.Session()
API_SESSION = st.session_state.api_session

# Load Styles
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Helper Functions
def _fetch_movie_raw(movie_id, session, api_key):
    """Pure Python data fetcher - safe for background threads"""
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}&append_to_response=videos&language=en-US"
        response = session.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        videos = data.get('videos', {}).get('results', [])
        trailer_key = next((v['key'] for v in videos if v['type'] == 'Trailer' and v['site'] == 'YouTube'), None)
        
        return {
            "title": data.get("title"),
            "overview": data.get("overview"),
            "poster": f"{BASE_IMAGE_URL}/{POSTER_SIZE}{data.get('poster_path')}" if data.get('poster_path') else None,
            "backdrop": f"{BASE_IMAGE_URL}/{BACKDROP_SIZE}{data.get('backdrop_path')}" if data.get('backdrop_path') else None,
            "rating": data.get("vote_average"),
            "release_date": data.get("release_date"),
            "runtime": data.get("runtime"),
            "genres": [g["name"] for g in data.get("genres", [])],
            "trailer_url": f"https://www.youtube.com/watch?v={trailer_key}" if trailer_key else None
        }
    except Exception:
        return None

def fetch_movie_context(movie_id):
    """Main thread wrapper for fetching movie context"""
    return _fetch_movie_raw(movie_id, API_SESSION, API_KEY)

@st.cache_data(ttl=3600, show_spinner=False)
def recommend(movie_title):
    """Return top 10 recommended movies - Hashing optimized"""
    global movies, similarity # Access cached resources
    try:
        movie_index = movies[movies['title'] == movie_title].index[0]
        distances = similarity[movie_index]
        movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:11]
        
        # Parallelize row fetching using the pure Python fetcher (thread-safe)
        with ThreadPoolExecutor(max_workers=10) as executor:
            movie_ids = [movies.iloc[i[0]].movie_id for i in movies_list]
            # Pass the session explicitly to avoid calling st.session_state inside the thread pool
            results = list(executor.map(lambda mid: _fetch_movie_raw(mid, API_SESSION, API_KEY), movie_ids))
            
        return [r for r in results if r is not None]
    except Exception as e:
        return []

# Optimized Data Loading with Auto-Train Fallback
@st.cache_resource
def load_data():
    try:
        if not os.path.exists('movie_list.pkl') or not os.path.exists('similarity.pkl'):
            # Trigger Auto-Train if files are missing (Deployment Cold Start)
            with st.spinner("🚀 Cold Start: Initializing recommendation engine for the first time..."):
                from train import run_training
                run_training()
        
        movies = pickle.load(open('movie_list.pkl', 'rb'))
        similarity = pickle.load(open('similarity.pkl', 'rb'))
        return movies, similarity
    except Exception as e:
        st.error(f"Initialization Error: {e}")
        return None, None

# App Initialization
movies, similarity = load_data()
data_loaded = movies is not None
if not data_loaded:
    st.error("Could not load model files. Please run training first.")

# --- UI LOGIC ---
# Load Style (must be outside cached block to apply on every rerun)
if os.path.exists('assets/style.css'):
    local_css("assets/style.css")

if not data_loaded:
    st.warning("⚠️ **Data Files Missing**")
    st.markdown("""
    <div style="background: rgba(229, 9, 20, 0.1); padding: 20px; border-radius: 8px; border: 1px solid var(--netflix-red);">
        <h3 style="color: var(--netflix-red); margin-top:0;">Setup Required</h3>
        <p>CineVision requires <b>movie_list.pkl</b> and <b>similarity.pkl</b> to function.</p>
        <ol>
            <li>Ensure you have the TMDB 5k dataset CSVs in the root.</li>
            <li>Run <code>py train.py</code> to generate the required models.</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# --- STICKY NAVIGATION BAR & SEARCH ---
if 'search_query' not in st.session_state:
    st.session_state.search_query = movies['title'].values[0]

# Custom Nav with integrated logo
st.markdown(f"""
<div class="nav-container">
    <a href="/" class="nav-logo">CINEVISION</a>
    <div style="display: flex; gap: 20px; align-items: center; flex: 1; justify-content: center;">
        <!-- Search bar will be placed here by Streamlit columns -->
    </div>
</div>
""", unsafe_allow_html=True)

# Use columns to position search in the nav area
# We use a placeholder and then absolute positioning in CSS or just proper margin.
with st.container():
    # Centered floating search bar
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        selected_movie_name = st.selectbox(
            "SEARCH",
            movies['title'].values,
            index=list(movies['title'].values).index(st.session_state.search_query),
            label_visibility="collapsed",
            placeholder="Search for a movie...",
            key="main_search"
        )
        if selected_movie_name != st.session_state.search_query:
            st.session_state.search_query = selected_movie_name

# Fetch data for Hero
selected_movie_id = movies[movies['title'] == selected_movie_name].iloc[0].movie_id
hero_movie = fetch_movie_context(selected_movie_id)

@st.dialog("Movie Details", width="large")
def show_details(movie):
    st.markdown(f"""
    <div style="display: flex; gap: 20px;">
        <div style="flex: 1;">
            <img src="{movie['poster']}" style="width: 100%; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
        </div>
        <div style="flex: 2;">
            <h1 style="margin-top:0; color: #E50914;">{movie['title']}</h1>
            <div style="display: flex; gap: 15px; margin: 15px 0;">
                <span style="background: #46D369; padding: 2px 8px; border-radius: 4px; font-weight: bold;">⭐ {movie['rating']:.1f}</span>
                <span>{movie['release_date'][:4]}</span>
                <span>{movie['runtime']} min</span>
            </div>
            <p style="font-size: 1.1rem; line-height: 1.6; color: #B3B3B3;">{movie['overview']}</p>
            <div style="margin-top: 20px;">
                <h4 style="margin-bottom:10px;">GENRES</h4>
                <div style="display: flex; gap: 8px;">
                    {''.join([f'<span style="background: rgba(255,255,255,0.1); padding: 4px 12px; border-radius: 20px; font-size: 0.8rem;">{g}</span>' for g in movie['genres']])}
                </div>
            </div>
            <div style="margin-top: 30px; display: flex; gap: 10px;">
                <a href="{movie['trailer_url']}" target="_blank" style="text-decoration:none; flex: 1;">
                    <button class="action-btn play-btn" style="width: 100%; padding: 15px;">▶ WATCH TRAILER</button>
                </a>
            </div>
            <div style="margin-top: 10px;">
                <button id="select_btn" class="action-btn" style="width: 100%; padding: 12px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);">FOCUS THIS MOVIE</button>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Real Streamlit button for actual state update (hidden or below)
    if st.button(f"SELECT '{movie['title']}' AS CENTER", use_container_width=True, type="primary"):
        st.session_state.search_query = movie['title']
        st.rerun()

if hero_movie:
    # Hero Section 2.0
    st.markdown(f"""
    <div class="hero-wrapper">
        <div class="hero-bg" style="background-image: url('{hero_movie['backdrop']}');"></div>
        <div class="hero-overlay"></div>
        <div class="hero-content">
            <span class="hero-badge">FEATURED SELECTION</span>
            <h1 class="hero-title">{hero_movie['title']}</h1>
            <div class="hero-meta">
                <span class="rating-badge">⭐ {hero_movie['rating']:.1f}</span>
                <span>{hero_movie['release_date'][:4]}</span>
                <span>{hero_movie['runtime']} min</span>
                <span>{", ".join(hero_movie['genres'][:2])}</span>
            </div>
            <p class="hero-summary">{hero_movie['overview']}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Action Buttons (Streamlit Native inside Hero context)
    h_col1, h_col2, h_col3 = st.columns([1, 1, 4])
    with h_col1:
        if hero_movie['trailer_url']:
            st.link_button("▶ PLAY TRAILER", hero_movie['trailer_url'], use_container_width=True)
    with h_col2:
        if st.button("ⓘ MORE INFO", use_container_width=True):
            show_details(hero_movie)

# --- RECOMMENDATIONS ROW ---
with st.spinner("Curating your next watch..."):
    recommendations = recommend(selected_movie_name)

if recommendations:
    st.markdown(f'<div class="section-header">BECAUSE YOU LIKED {selected_movie_name}</div>', unsafe_allow_html=True)
    
    # Horizontal Scroll Container
    # Note: Streamlit widgets cannot live inside raw HTML scroll containers easily.
    # We will use a standard column grid for stability, but with premium CSS cards.
    
    n_cols = 5
    for i in range(0, len(recommendations), n_cols):
        cols = st.columns(n_cols)
        chunk = recommendations[i:i+n_cols]
        for idx, movie in enumerate(chunk):
            with cols[idx]:
                st.markdown(f"""
                <div class="movie-card-v2">
                    <img class="card-img" src="{movie['poster'] if movie['poster'] else 'https://via.placeholder.com/500x750'}">
                    <div class="card-hover-overlay">
                        <div style="font-weight: 800; font-size: 0.9rem; margin-bottom: 5px;">{movie['title']}</div>
                        <div style="font-size: 0.7rem; color: #46D369; font-weight: bold;">⭐ {movie['rating']:.1f}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Details", key=f"rec_btn_{movie['title']}_{i}_{idx}", use_container_width=True):
                    show_details(movie)

# Footer
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown('<div style="text-align:center; color:var(--text-muted); font-size:0.8rem; padding: 40px;">CineVision Oracle v2.0 • Data provided by TMDB API</div>', unsafe_allow_html=True)