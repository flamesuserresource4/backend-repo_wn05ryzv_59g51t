import os
from datetime import date, datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from database import db, create_document, get_documents

app = FastAPI(title="Malta Student Accommodation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------
# Helpers
# ------------------------

def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def daterange(start: date, end: date):
    cur = start
    while cur < end:
        yield cur
        cur += timedelta(days=1)


def get_active_seasons() -> List[dict]:
    # Seasons repeat annually; stored as month/day ranges
    seasons = get_documents("season")
    return seasons


def season_for_day(d: date, seasons: List[dict]) -> Optional[dict]:
    for s in seasons:
        sm, sd, em, ed = s.get("start_month"), s.get("start_day"), s.get("end_month"), s.get("end_day")
        start_this_year = date(d.year, sm, sd)
        end_this_year = date(d.year, em, ed)
        if end_this_year < start_this_year:
            # Wraps year end
            if d >= start_this_year or d <= date(d.year, em, ed):
                return s
        else:
            if start_this_year <= d <= end_this_year:
                return s
    return None


def compute_price(room: dict, check_in: date, check_out: date) -> float:
    seasons = get_active_seasons()
    total = 0.0
    for d in daterange(check_in, check_out):
        s = season_for_day(d, seasons)
        base = s.get("rate", 0.0) if s else 0.0
        total += base * float(room.get("multiplier", 1.0))
    return round(total, 2)


# ------------------------
# Seed minimal data if empty
# ------------------------
@app.on_event("startup")
def seed_defaults():
    if db is None:
        return
    if db["season"].count_documents({}) == 0:
        # Academic year (Oct-Jun) higher demand
        db["season"].insert_many([
            {"name": "Academic Year", "start_month": 10, "start_day": 1, "end_month": 6, "end_day": 30, "rate": 45.0},
            {"name": "Summer", "start_month": 7, "start_day": 1, "end_month": 9, "end_day": 30, "rate": 35.0},
            {"name": "Holiday", "start_month": 12, "start_day": 20, "end_month": 12, "end_day": 31, "rate": 50.0},
        ])
    if db["room"].count_documents({}) == 0:
        db["room"].insert_many([
            {"name": "Private Room", "description": "Cozy private room in shared apartment", "capacity": 2, "multiplier": 1.0},
            {"name": "Entire Apartment", "description": "Whole apartment perfect for a small group", "capacity": 4, "multiplier": 1.4},
        ])


# ------------------------
# Request models
# ------------------------
class QuoteRequest(BaseModel):
    room_id: str
    check_in: str
    check_out: str
    guests: int = 1

class BookingRequest(QuoteRequest):
    name: str
    email: str
    university: Optional[str] = None
    phone: Optional[str] = None

# ------------------------
# Routes
# ------------------------
@app.get("/")
def root():
    return {"message": "Malta Student Accommodation API"}

@app.get("/rooms")
def list_rooms():
    return get_documents("room")

@app.get("/seasons")
def list_seasons():
    return get_documents("season")

@app.post("/quote")
def get_quote(payload: QuoteRequest):
    rooms = db["room"].find({"_id": {"$exists": True}})
    room = next((r for r in rooms if str(r.get("_id")) == payload.room_id), None)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    ci = parse_date(payload.check_in)
    co = parse_date(payload.check_out)
    if ci >= co:
        raise HTTPException(status_code=400, detail="check_out must be after check_in")
    if payload.guests < 1 or payload.guests > room.get("capacity", 1):
        raise HTTPException(status_code=400, detail="Invalid number of guests for this room")
    price = compute_price(room, ci, co)
    return {"room_id": payload.room_id, "check_in": payload.check_in, "check_out": payload.check_out, "guests": payload.guests, "total_price": price, "currency": "EUR"}

@app.post("/book")
def create_booking(payload: BookingRequest):
    rooms = db["room"].find({"_id": {"$exists": True}})
    room = next((r for r in rooms if str(r.get("_id")) == payload.room_id), None)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    ci = parse_date(payload.check_in)
    co = parse_date(payload.check_out)
    if ci >= co:
        raise HTTPException(status_code=400, detail="check_out must be after check_in")
    if payload.guests < 1 or payload.guests > room.get("capacity", 1):
        raise HTTPException(status_code=400, detail="Invalid number of guests for this room")

    total = compute_price(room, ci, co)
    booking_doc = {
        "room_id": payload.room_id,
        "check_in": payload.check_in,
        "check_out": payload.check_out,
        "guests": payload.guests,
        "total_price": total,
        "currency": "EUR",
        "status": "confirmed",
        "student": {
            "name": payload.name,
            "email": payload.email,
            "university": payload.university,
            "phone": payload.phone,
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    inserted_id = db["booking"].insert_one(booking_doc).inserted_id
    return {"booking_id": str(inserted_id), "total_price": total, "currency": "EUR", "status": "confirmed"}

@app.get("/bookings")
def list_bookings(limit: int = Query(50, ge=1, le=200)):
    items = db["booking"].find({}).sort("created_at", -1).limit(limit)
    return [
        {
            "_id": str(i.get("_id")),
            "room_id": i.get("room_id"),
            "check_in": i.get("check_in"),
            "check_out": i.get("check_out"),
            "guests": i.get("guests"),
            "total_price": i.get("total_price"),
            "currency": i.get("currency"),
            "status": i.get("status"),
            "student": i.get("student"),
        }
        for i in items
    ]


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
