from fastapi import FastAPI
from . import models, db, api  # Import our new api router
from fastapi.middleware.cors import CORSMiddleware

# --- Database Table Creation ---
# This command tells SQLAlchemy to look at all the classes
# that inherit from 'Base' (in models.py) and create
# tables for them in the database.
# We run this *before* the app starts.
try:
    print("Creating database tables...")
    models.Base.metadata.create_all(bind=db.engine)
    print("Database tables created successfully.")
except Exception as e:
    print(f"Error creating database tables: {e}")
    # In a real app, you might want to handle this more gracefully
    # For now, we'll just print the error and continue.

# --- FastAPI App Initialization ---
app = FastAPI(title="AI News Aggregator")

# --- CORS Middleware (ADDED) ---
# This is the new block that allows your frontend to communicate
# with your backend from a different origin (e.g., :5500 -> :8000)

origins = [
    "http://localhost:5173",  # <-- The new one for Vite
    "http://127.0.0.1:5173", # <-- Also for Vite
    "http://localhost:5500",  # For the old "Live Server"
    "http://127.0.0.1:5500", # For the old "Live Server"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # List of origins that are allowed
    allow_credentials=True,      # Allow cookies
    allow_methods=["*"],         # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],         # Allow all headers
)
# --- End of new block ---


# --- Include API Routers ---
# This line tells our main 'app' object to include all the
# endpoints (like /signup, /login, /topics) that are defined
# in the 'api_router' object from our 'api.py' file.
app.include_router(api.api_router)


# --- Root Endpoint ---
@app.get("/")
def root():
    return {"message": "🚀 AI News Aggregator Backend is running!"}
