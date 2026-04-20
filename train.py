import pandas as pd
import numpy as np
import os
import nltk
from nltk.stem.porter import PorterStemmer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pickle

def run_training():
    """Main training pipeline for the CineVision recommendation engine"""
    print("Loading datasets...")
    # datasets already in root
    try:
        movies = pd.read_csv('tmdb_5000_movies.csv')
        credits = pd.read_csv('tmdb_5000_credits.csv')
    except Exception as e:
        print(f"Error: {e}")
        return

    print("Preprocessing data...")
    # Merge datasets
    movies = movies.merge(credits, on='title')
    
    # Feature Selection
    movies = movies[['movie_id', 'title', 'overview', 'genres', 'keywords', 'cast', 'crew']]
    movies.dropna(inplace=True)

    # Data Cleaning Helpers
    import ast
    def convert(obj):
        L = []
        for i in ast.literal_eval(obj):
            L.append(i['name'])
        return L

    def convert3(obj):
        L = []
        counter = 0
        for i in ast.literal_eval(obj):
            if counter != 3:
                L.append(i['name'])
                counter+=1
            else:
                break
        return L

    def fetch_director(obj):
        L = []
        for i in ast.literal_eval(obj):
            if i['job'] == 'Director':
                L.append(i['name'])
                break
        return L

    movies['genres'] = movies['genres'].apply(convert)
    movies['keywords'] = movies['keywords'].apply(convert)
    movies['cast'] = movies['cast'].apply(convert3)
    movies['crew'] = movies['crew'].apply(fetch_director)
    
    # Text Processing
    movies['overview'] = movies['overview'].apply(lambda x:x.split())
    movies['genres'] = movies['genres'].apply(lambda x:[i.replace(" ","") for i in x])
    movies['keywords'] = movies['keywords'].apply(lambda x:[i.replace(" ","") for i in x])
    movies['cast'] = movies['cast'].apply(lambda x:[i.replace(" ","") for i in x])
    movies['crew'] = movies['crew'].apply(lambda x:[i.replace(" ","") for i in x])

    movies['tags'] = movies['overview'] + movies['genres'] + movies['keywords'] + movies['cast'] + movies['crew']
    new_df = movies[['movie_id', 'title', 'tags']]
    new_df['tags'] = new_df['tags'].apply(lambda x:" ".join(x))
    new_df['tags'] = new_df['tags'].apply(lambda x:x.lower())

    # Stemming
    print("Stemming tags...")
    ps = PorterStemmer()
    def stem(text):
        y = []
        for i in text.split():
            y.append(ps.stem(i))
        return " ".join(y)
    
    new_df['tags'] = new_df['tags'].apply(stem)

    # Vectorization
    print("Vectorizing...")
    cv = CountVectorizer(max_features=5000, stop_words='english')
    vectors = cv.fit_transform(new_df['tags']).toarray()

    # Calculating cosine similarity
    print("Calculating cosine similarity...")
    similarity = cosine_similarity(vectors).astype(np.float16) # Optimization: Shrink matrix size by 75%

    # Saving models
    print("Saving models...")
    pickle.dump(new_df, open('movie_list.pkl', 'wb'))
    pickle.dump(similarity, open('similarity.pkl', 'wb'))
    print("Optimization Complete! movie_list.pkl and similarity.pkl have been generated.")

if __name__ == "__main__":
    run_training()
