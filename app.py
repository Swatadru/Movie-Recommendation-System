<<<<<<< HEAD
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
=======
import pickle
import requests
import streamlit as st
from streamlit.components.v1 import html
import time

# Configuration
st.set_page_config(
    layout="wide",
    page_title="CineVision | Premium Movie Recommendations",
    page_icon="🎬",
    initial_sidebar_state="collapsed"
)

# CSS with premium animations and effects
cinematic_css = f"""
<style>
    /* Modern Base with Cinematic Flair */
    .main {{
        background: linear-gradient(135deg, rgba(10,10,25,0.95) 0%, rgba(0,0,0,0.95) 100%), 
                    url('https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?q=80&w=2070&auto=format&fit=crop') center/cover fixed;
        color: #f0f0f0;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        min-height: 100vh;
    }}
    
    /* Premium Glass Header */
    .app-header {{
        text-align: center;
        padding: 4rem 0 3rem;
        background: rgba(20, 20, 30, 0.6);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        margin: -2rem -1rem 3rem;
        border-bottom: 1px solid rgba(255, 77, 77, 0.3);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        position: relative;
        overflow: hidden;
    }}
    
    .app-header::before {{
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,77,77,0.1) 0%, transparent 70%);
        animation: rotate 20s linear infinite;
        z-index: -1;
    }}
    
    @keyframes rotate {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    
    .app-title {{
        font-size: 4.5rem;
        font-weight: 800;
        background: linear-gradient(45deg, #ff4d4d, #f9cb28, #ff4d4d);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        text-shadow: 0 4px 20px rgba(0,0,0,0.3);
        animation: gradient 3s ease infinite;
    }}
    
    @keyframes gradient {{
        0% {{ background-position: 0% 50%; }}
        50% {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
    }}
    
    /* Movie Grid with 3D Effect */
    .movie-columns {{
        display: flex;
        justify-content: center;
        gap: 2rem;
        padding: 0 2rem;
        margin: 3rem auto;
        max-width: 1600px;
        perspective: 2000px;
    }}
    
    .movie-card {{
        position: relative;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
        transition: all 0.6s cubic-bezier(0.25, 0.8, 0.25, 1);
        transform-style: preserve-3d;
        flex: 1;
        min-width: 220px;
        transform: translateZ(0);
        cursor: pointer;
    }}
    
    .movie-poster {{
        width: 100%;
        height: auto;
        aspect-ratio: 2/3;
        object-fit: cover;
        display: block;
        transition: all 0.6s ease;
        transform: translateZ(50px);
    }}
    
    .movie-overlay {{
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: linear-gradient(to top, rgba(0,0,0,0.95), transparent);
        padding: 2rem 1.5rem;
        transform: translateY(100%);
        transition: all 0.5s cubic-bezier(0.33, 1, 0.68, 1);
        opacity: 0;
        backdrop-filter: blur(5px);
    }}
    
    .movie-title {{
        font-size: 1.3rem;
        font-weight: 700;
        margin: 0 0 0.5rem;
        color: white;
        text-align: center;
        text-shadow: 0 2px 5px rgba(0,0,0,0.5);
    }}
    
    .movie-rating {{
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 0.3rem;
        font-size: 0.9rem;
        color: #f9cb28;
    }}
    
    /* Hover Animations */
    .movie-card:hover {{
        transform: translateY(-15px) rotateX(5deg) scale(1.05);
        box-shadow: 0 25px 60px rgba(255, 77, 77, 0.4);
        z-index: 10;
    }}
    
    .movie-card:hover .movie-poster {{
        transform: scale(1.15) translateZ(60px);
        filter: brightness(0.7);
    }}
    
    .movie-card:hover .movie-overlay {{
        transform: translateY(0);
        opacity: 1;
    }}
    
    /* Rank Badge Animation */
    .movie-rank {{
        position: absolute;
        top: 15px;
        right: 15px;
        background: linear-gradient(45deg, #ff4d4d, #f9cb28);
        color: black;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        transform: scale(0) rotate(180deg);
        transition: all 0.5s cubic-bezier(0.68, -0.6, 0.32, 1.6);
        z-index: 2;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    
    .movie-card:hover .movie-rank {{
        transform: scale(1) rotate(0deg);
    }}
    
    /* Selected Movie Card - Premium Glow */
    .selected-movie-card {{
        position: relative;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 15px 50px rgba(255, 77, 77, 0.6);
        transform-style: preserve-3d;
        flex: 1;
        min-width: 250px;
        border: 2px solid rgba(249, 203, 40, 0.5);
        transition: all 0.5s ease;
    }}
    
    .selected-movie-card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        border-radius: 14px;
        box-shadow: inset 0 0 30px rgba(249, 203, 40, 0.4);
        pointer-events: none;
    }}
    
    .selected-movie-badge {{
        position: absolute;
        top: 15px;
        left: 15px;
        background: linear-gradient(45deg, #ff4d4d, #f9cb28);
        color: black;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: 800;
        font-size: 0.9rem;
        z-index: 2;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    
    /* Movie Details Panel */
    .movie-details {{
        background: rgba(20, 20, 30, 0.8);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 2rem;
        margin-top: 2rem;
        border: 1px solid rgba(255, 77, 77, 0.3);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }}
    
    /* Hide Streamlit Defaults */
    header {{ visibility: hidden; }}
    thead tr th:first-child {{display:none}}
    thead tr th:last-child {{display:none}}
    tbody th {{display:none}}
    tbody tr td:last-child {{display:none}}
    footer {{ visibility: hidden; }}
    .st-emotion-cache-uf99v8 {{ padding: 0 !important; }}

</style>
"""

st.markdown(cinematic_css, unsafe_allow_html=True)


def fetch_poster(movie_id: int) -> str:
    """Fetch movie poster from TMDB API"""
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key=8265bd1679663a7ea12ac168da84d2e8&language=en-US"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return f"https://image.tmdb.org/t/p/w780/{data['poster_path']}"
    except:
        return "https://via.placeholder.com/500x750?text=Poster+Not+Available"

def fetch_movie_details(movie_id: int) -> dict:
    """Fetch detailed movie information from TMDB API"""
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key=8265bd1679663a7ea12ac168da84d2e8&language=en-US"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return {
            'title': data.get('title', 'Title not available'),
            'description': data.get('overview', 'Description not available'),
            'release_date': data.get('release_date', 'Date not available'),
            'rating': data.get('vote_average', 0),
            'poster': f"https://image.tmdb.org/t/p/w780/{data.get('poster_path', '')}",
            'genres': [genre['name'] for genre in data.get('genres', [])],
            'runtime': data.get('runtime', 0)
        }
    except:
        return {
            'title': 'Movie details not available',
            'description': 'Could not fetch details for this movie',
            'release_date': 'Date not available',
            'rating': 0,
            'poster': "https://via.placeholder.com/500x750?text=Poster+Not+Available",
            'genres': [],
            'runtime': 0
        }

def get_movie_details(movie_title: str) -> dict:
    """Get details for the selected movie"""
    try:
        movie_data = movies[movies['title'] == movie_title].iloc[0]
        details = fetch_movie_details(movie_data['movie_id'])
        return {
            'title': movie_data['title'],
            'poster': details['poster'],
            'description': details['description'],
            'release_date': details['release_date'],
            'rating': details['rating'],
            'runtime': details['runtime'],
            'genres': details['genres'],
            'id': movie_data['movie_id']
        }
    except:
        return {
            'title': movie_title,
            'poster': "https://via.placeholder.com/500x750?text=Poster+Not+Available",
            'description': 'Could not fetch details for this movie',
            'release_date': 'Date not available',
            'rating': 0,
            'runtime': 0,
            'genres': [],
            'id': 0
        }

def recommend(movie: str) -> list:
    """Get movie recommendations based on similarity"""
    try:
        index = movies[movies['title'] == movie].index[0]
        distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
        
        recommendations = []
        for i in distances[1:6]:
            movie_id = movies.iloc[i[0]].movie_id
            details = fetch_movie_details(movie_id)
            recommendations.append({
                'title': movies.iloc[i[0]].title,
                'poster': details['poster'],
                'rating': details['rating'],
                'genres': details['genres'],
                'rank': i[0],
                'id': movie_id,
                'release_date': details['release_date'],
                'runtime': details['runtime'],
                'description': details['description']
            })
        return recommendations
    except:
        return []

@st.cache_data
def load_data():
    """Load movie data and similarity matrix"""
    try:
        movies = pickle.load(open('movie_list.pkl', 'rb'))
        similarity = pickle.load(open('similarity.pkl', 'rb'))
        return movies, similarity
    except:
        return pd.DataFrame(), []

movies, similarity = load_data()

# Header Section
st.markdown("""
<div class="app-header">
    <h1 class="app-title">CineVision</h1>
    <p style="font-size: 1.3rem; opacity: 0.9; letter-spacing: 1px; margin-top: -0.5rem; text-shadow: 0 2px 5px rgba(0,0,0,0.3);">Your Personal Film Curator</p>
</div>
""", unsafe_allow_html=True)

# Input Panel
with st.container():
    st.markdown('<div style="max-width: 800px; margin: 0 auto 4rem; padding: 0 1rem;">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        selected_movie = st.selectbox(
            "Select a movie you love",
            movies['title'].values if not movies.empty else [],
            index=0,
            key="movie_select",
            help="Choose a movie to get premium recommendations"
        )
        if st.button("Get Recommendations", key="recommend_btn"):
            with st.spinner('Curating your cinematic experience...'):
                st.session_state.show_results = True
                st.session_state.selected_movie_details = get_movie_details(selected_movie)
                st.session_state.recommendations = recommend(selected_movie)
                time.sleep(0.5)
    st.markdown('</div>', unsafe_allow_html=True)

# Results Section
if st.session_state.get('show_results', False):
    if 'recommendations' not in st.session_state:
        with st.spinner("Finding perfect matches..."):
            st.session_state.selected_movie_details = get_movie_details(selected_movie)
            st.session_state.recommendations = recommend(selected_movie)
    
    st.markdown(f"""
    <div style="text-align: center; margin: 3rem 0 2rem;">
        <h2 style="font-weight: 700; font-size: 2rem; letter-spacing: 1px;">Because you enjoyed <span style="color: #f9cb28; text-shadow: 0 2px 10px rgba  (249, 203, 40, 0.5);">{selected_movie}</span></h2>
        <p style="opacity: 0.8; font-size: 1.1rem; margin-top: 0.5rem;">We've curated these premium selections just for you</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Display the selected movie first
    st.markdown("""
<div style="display: flex; justify-content: center; margin-bottom: 4rem;">
    <div style="max-width: 320px;">
        <div class="selected-movie-card">
            <span class="selected-movie-badge">Your Selection</span>
            <img class="movie-poster" src="{poster}" alt="{title}">
            <div class="movie-overlay" style="text-align: center;">
                <h3 class="movie-title">{title}</h3>
                <div class="movie-rating">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="#f9cb28" stroke="#f9cb28" stroke-width="2" stroke-linecap="round" stroke-line  -  join="round">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                    </svg>
                    <span>{rating}/10</span>
                </div>
            </div>
        </div>
    </div>
</div>
""".format(
    poster=st.session_state.selected_movie_details.get('poster', 'https://via.placeholder.com/500x750?text=Poster+Not+Available'),
    title=st.session_state.selected_movie_details.get('title', 'Movie Title'),
    rating=st.session_state.selected_movie_details.get('rating', 'N/A')
), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div style="text-align: center; margin: 3rem 0 2rem;">', unsafe_allow_html=True)
    st.markdown('<h3 style="font-weight: 700; font-size: 1.8rem; letter-spacing: 1px;">Premium Recommendations</h3>', unsafe_allow_html=True)
    st.markdown('<p style="opacity: 0.8; font-size: 1.1rem; margin-top: 0.5rem;">Based on your taste profile</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Create 5 columns for recommendations
    cols = st.columns(5)
    
    # Display animated posters for recommendations
    for i, movie in enumerate(st.session_state.recommendations, 1):
        with cols[i-1] if i-1 < len(cols) else st.container():
            # Create a clickable poster button
            if st.button(
                f"",
                key=f"poster_{movie['id']}",
                help=f"Click to view details about {movie['title']}",
            ):
                st.session_state["selected_movie_details"] = movie
                st.session_state["show_movie_details"] = True
            
            # Show the movie card
            st.markdown(f"""
            <div class="movie-card" onclick="document.getElementById('poster_{movie['id']}').click()">
                <span class="movie-rank">{i}</span>
                <img class="movie-poster" src="{movie.get('poster', 'https://via.placeholder.com/500x750?text=Poster+Not+Available')}" alt="{movie.get('title', 'Movie')}">
                <div class="movie-overlay">
                    <h3 class="movie-title">{movie.get('title', 'Movie')}</h3>
                    <div class="movie-rating">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="#f9cb28" stroke="#f9cb28" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                        </svg>
                        <span>{movie.get('rating', 'N/A')}/10</span>
                    </div>
                </div>
            </div>
            <p style="text-align: center; margin-top: 0.5rem; font-weight: 600; font-size: 0.95rem;">{movie.get('title', 'Movie')}</p>
            """, unsafe_allow_html=True)
    
    # Show details if a movie was selected
    if st.session_state.get("show_movie_details", False):
        movie_details = st.session_state.get("selected_movie_details", {})
        with st.container():
            st.markdown(f"""
            <div class="movie-details">
                <div style="display: flex; gap: 2rem; margin-bottom: 2rem;">
                    <div style="flex: 0 0 300px;">
                        <img src="{movie_details.get('poster', 'https://via.placeholder.com/500x750?text=Poster+Not+Available')}" style="width: 100%; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                    </div>
                    <div style="flex: 1;">
                        <h2 style="font-size: 2rem; margin-top: 0; color: #f9cb28; text-shadow: 0 2px 5px rgba(0,0,0,0.5);">{movie_details.get('title', 'Movie Title')}</h2>
                        <div style="display: flex; gap: 2rem; margin: 1.5rem 0;">
                            <div>
                                <div style="font-size: 0.9rem; opacity: 0.8; margin-bottom: 0.3rem;">Rating</div>
                                <div style="font-size: 1.5rem; font-weight: 700;">{movie_details.get('rating', 'N/A')}/10</div>
                            </div>
                            <div>
                                <div style="font-size: 0.9rem; opacity: 0.8; margin-bottom: 0.3rem;">Release Date</div>
                                <div style="font-size: 1.5rem; font-weight: 700;">{movie_details.get('release_date', 'N/A')}</div>
                            </div>
                            <div>
                                <div style="font-size: 0.9rem; opacity: 0.8; margin-bottom: 0.3rem;">Runtime</div>
                                <div style="font-size: 1.5rem; font-weight: 700;">{movie_details.get('runtime', 'N/A')} min</div>
                            </div>
                        </div>
                        <div style="margin-bottom: 1.5rem;">
                            <div style="font-size: 0.9rem; opacity: 0.8; margin-bottom: 0.3rem;">Genres</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                                {''.join([f'<span style="background: rgba(255,77,77,0.2); padding: 4px 12px; border-radius: 20px; border: 1px solid rgba(255,77,77,0.5);">{genre}</span>' for genre in movie_details.get('genres', [])])}
                            </div>
                        </div>
                        <div>
                            <div style="font-size: 0.9rem; opacity: 0.8; margin-bottom: 0.3rem;">Synopsis</div>
                            <p style="line-height: 1.6; margin: 0;">{movie_details.get('description', 'No description available')}</p>
                        </div>
                    </div>
                </div>
                <div style="text-align: center; margin-top: 2rem;">
                    <button style="background: linear-gradient(45deg, #ff4d4d, #f9cb28); color: #111; border: none; padding: 12px 24px; font-size: 1rem; font-weight: 600; border-radius: 8px; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(255, 77, 77, 0.5);" 
                            onclick="window.open('https://www.youtube.com/results?search_query={movie_details.get('title', '')}+trailer', '_blank')">
                        Watch Trailer
                    </button>
                </div>
            </div>
            """, unsafe_allow_html=True)

# Empty State
else:
    st.markdown("""
    <div style="text-align: center; padding: 6rem 0;">
        <div style="position: relative; display: inline-block;">
            <svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="#f9cb28" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 1.5rem; filter: drop-shadow(0 0 10px rgba(249, 203, 40, 0.5));">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1  - .45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11  - .45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path>
            </svg>
            <div style="position: absolute; top: -10px; right: -10px; width: 30px; height: 30px; background: linear-gradient(45deg, #ff4d4d, #f9cb28); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.8rem; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">
                NEW
            </div>
        </div>
        <h3 style="font-size: 1.8rem; opacity: 0.9; margin-top: 1.5rem; letter-spacing: 1px;">Discover Your Next Favorite Film</h3>
        <p style="opacity: 0.7; font-size: 1.1rem; max-width: 600px; margin: 1rem auto; line-height: 1.6;">Our advanced algorithm analyzes thousands of films to find perfect matches based on your unique taste in cinema.</p>
        <div style="margin-top: 2rem; opacity: 0.8; font-size: 0.9rem;">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f9cb28" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            <span style="vertical-align: middle; margin-left: 5px;">Select a movie above to begin</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
>>>>>>> e4d90ea13224230d185ac410992be665191de4ee
