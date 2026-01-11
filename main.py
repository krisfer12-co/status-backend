from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
import os
import random
import string
import requests
import stripe
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "Krisfer12@gmail.com")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
MONGODB_URI = os.environ.get("MONGODB_URI", "")

stripe.api_key = STRIPE_SECRET_KEY

client = None
db = None
couples_collection = None
codes_collection = None

def init_db():
    global client, db, couples_collection, codes_collection
    if client is None and MONGODB_URI:
        try:
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
