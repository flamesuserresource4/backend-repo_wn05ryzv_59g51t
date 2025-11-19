"""
Database Schemas for Malta Student Accommodation Booking

Each Pydantic model below represents a MongoDB collection.
Collection name is the lowercase of the class name.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List

class Season(BaseModel):
    """
    Seasonality periods that repeat every year (by month/day).
    Example: Oct 1 - Jun 30 = High (academic year), Jul 1 - Sep 30 = Summer.
    rate is the base nightly rate in EUR for the apartment (before room multiplier if any).
    """
    name: str = Field(..., description="Season name e.g., Academic Year, Summer, Holiday")
    start_month: int = Field(..., ge=1, le=12)
    start_day: int = Field(..., ge=1, le=31)
    end_month: int = Field(..., ge=1, le=12)
    end_day: int = Field(..., ge=1, le=31)
    rate: float = Field(..., ge=0, description="Nightly base rate in EUR")

class Room(BaseModel):
    """
    Rooms or entire apartment units available for booking.
    multiplier adjusts season base rate (e.g., private room 1.0, entire place 1.4).
    """
    name: str
    description: Optional[str] = None
    capacity: int = Field(1, ge=1, le=8)
    multiplier: float = Field(1.0, ge=0.5, le=3.0)

class Student(BaseModel):
    name: str
    email: EmailStr
    university: Optional[str] = None
    phone: Optional[str] = None

class Booking(BaseModel):
    room_id: str = Field(..., description="ObjectId string for Room")
    check_in: str = Field(..., description="YYYY-MM-DD")
    check_out: str = Field(..., description="YYYY-MM-DD (exclusive)")
    guests: int = Field(1, ge=1, le=8)
    total_price: float = Field(..., ge=0)
    currency: str = Field("EUR")
    status: str = Field("pending", description="pending|confirmed|cancelled")
    student: Student

# Optional examples kept for reference
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
