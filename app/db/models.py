"""Database models and database connection setup for Taste Memory Vault.

Supports SQLAlchemy 2.0 with standard library sqlite3 fallback.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any, List, Optional

from app.config import settings

# Attempt SQLAlchemy import; fallback gracefully if not installed in environment
try:
    from sqlalchemy import (
        Boolean,
        Column,
        DateTime,
        ForeignKey,
        Integer,
        String,
        Text,
        create_engine,
    )
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


if HAS_SQLALCHEMY:
    class Base(DeclarativeBase):
        """Base SQLAlchemy model class."""
        pass

    class User(Base):
        """User profile record in the Taste Memory Vault."""
        __tablename__ = "users"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
        full_name: Mapped[str] = mapped_column(String(255), nullable=False)
        created_at: Mapped[datetime.datetime] = mapped_column(
            DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)
        )

        dietary_profile: Mapped[Optional["DietaryProfile"]] = relationship(
            "DietaryProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
        )

        def to_dict(self) -> dict[str, Any]:
            return {
                "id": self.id,
                "email": self.email,
                "full_name": self.full_name,
                "dietary_profile": self.dietary_profile.to_dict() if self.dietary_profile else None,
            }

    class DietaryProfile(Base):
        """Dietary preferences, restrictions, and spice tolerances per user."""
        __tablename__ = "dietary_profiles"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

        is_vegetarian: Mapped[bool] = mapped_column(Boolean, default=False)
        is_vegan: Mapped[bool] = mapped_column(Boolean, default=False)
        is_eggetarian: Mapped[bool] = mapped_column(Boolean, default=False)
        is_gluten_free: Mapped[bool] = mapped_column(Boolean, default=False)
        is_jain: Mapped[bool] = mapped_column(Boolean, default=False)
        is_halal: Mapped[bool] = mapped_column(Boolean, default=False)

        spice_tolerance: Mapped[int] = mapped_column(Integer, default=3)

        allergies_json: Mapped[str] = mapped_column(Text, default="[]")
        fav_cuisines_json: Mapped[str] = mapped_column(Text, default="[]")
        disliked_ingredients_json: Mapped[str] = mapped_column(Text, default="[]")

        user: Mapped["User"] = relationship("User", back_populates="dietary_profile")

        @property
        def allergies(self) -> list[str]:
            try:
                return json.loads(self.allergies_json or "[]")
            except Exception:
                return []

        @allergies.setter
        def allergies(self, val: list[str]) -> None:
            self.allergies_json = json.dumps(val)

        @property
        def fav_cuisines(self) -> list[str]:
            try:
                return json.loads(self.fav_cuisines_json or "[]")
            except Exception:
                return []

        @fav_cuisines.setter
        def fav_cuisines(self, val: list[str]) -> None:
            self.fav_cuisines_json = json.dumps(val)

        @property
        def disliked_ingredients(self) -> list[str]:
            try:
                return json.loads(self.disliked_ingredients_json or "[]")
            except Exception:
                return []

        @disliked_ingredients.setter
        def disliked_ingredients(self, val: list[str]) -> None:
            self.disliked_ingredients_json = json.dumps(val)

        def to_dict(self) -> dict[str, Any]:
            return {
                "is_vegetarian": self.is_vegetarian,
                "is_vegan": self.is_vegan,
                "is_eggetarian": self.is_eggetarian,
                "is_gluten_free": self.is_gluten_free,
                "is_jain": self.is_jain,
                "is_halal": self.is_halal,
                "spice_tolerance": self.spice_tolerance,
                "allergies": self.allergies,
                "fav_cuisines": self.fav_cuisines,
                "disliked_ingredients": self.disliked_ingredients,
            }

    class DishHistory(Base):
        """Past ordered or preferred dishes for taste profiling."""
        __tablename__ = "dish_histories"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
        user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
        dish_name: Mapped[str] = mapped_column(String(255), nullable=False)
        restaurant_name: Mapped[str] = mapped_column(String(255), nullable=False)
        rating: Mapped[int] = mapped_column(Integer, default=5)
        vertical: Mapped[str] = mapped_column(String(50), default="food")
        ordered_at: Mapped[datetime.datetime] = mapped_column(
            DateTime, default=datetime.datetime.utcnow
        )

    connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
    engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

else:
    # Fallback sqlite3 implementation when SQLAlchemy is not installed
    Base = object  # type: ignore
    User = object  # type: ignore
    DietaryProfile = object  # type: ignore
    DishHistory = object  # type: ignore
    engine = None
    SessionLocal = None


DB_FILE = Path(__file__).parent.parent.parent / "nexus_memory.db"


def init_db() -> None:
    """Initialize database tables and seed demo users."""
    _init_db_sqlite()
    if HAS_SQLALCHEMY:
        Base.metadata.create_all(bind=engine)
        seed_demo_users()
    ensure_night_out_guests()


def _init_db_sqlite() -> None:
    """Standard library sqlite3 initialization."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dietary_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                is_vegetarian INTEGER DEFAULT 0,
                is_vegan INTEGER DEFAULT 0,
                is_eggetarian INTEGER DEFAULT 0,
                is_gluten_free INTEGER DEFAULT 0,
                is_jain INTEGER DEFAULT 0,
                is_halal INTEGER DEFAULT 0,
                spice_tolerance INTEGER DEFAULT 3,
                allergies_json TEXT DEFAULT '[]',
                fav_cuisines_json TEXT DEFAULT '[]',
                disliked_ingredients_json TEXT DEFAULT '[]',
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        try:
            conn.execute("ALTER TABLE dietary_profiles ADD COLUMN is_halal INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Seed users if empty
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            demo_users = [
                ("aryan@nexus.ai", "Aryan", 1, 0, 4, '["peanuts"]', '["Italian", "North Indian"]', '["mushrooms"]'),
                ("himali@nexus.ai", "Himali", 1, 0, 2, '[]', '["South Indian", "Asian"]', '[]'),
                ("siya@nexus.ai", "Siya", 1, 0, 3, '[]', '["North Indian", "Continental"]', '["mushroom"]'),
                ("swayam@nexus.ai", "Swayam", 0, 0, 4, '[]', '["Continental", "Asian"]', '[]'),
                ("priya@nexus.ai", "Priya Sharma", 1, 1, 2, '["lactose"]', '["Asian", "South Indian"]', '["capsicum"]'),
                ("kabir@nexus.ai", "Kabir", 0, 0, 5, '[]', '["North Indian", "Mughlai"]', '[]'),
            ]
            for email, name, is_veg, is_vegan, spice, alg, cuis, dis in demo_users:
                cur.execute("INSERT INTO users (email, full_name) VALUES (?, ?)", (email, name))
                uid = cur.lastrowid
                cur.execute("""
                    INSERT INTO dietary_profiles 
                    (user_id, is_vegetarian, is_vegan, spice_tolerance, allergies_json, fav_cuisines_json, disliked_ingredients_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (uid, is_veg, is_vegan, spice, alg, cuis, dis))
            conn.commit()


def seed_demo_users() -> None:
    if not HAS_SQLALCHEMY or not SessionLocal:
        _init_db_sqlite()
        return

    db = SessionLocal()
    try:
        if db.query(User).first() is not None:
            return

        demo_users = [
            {
                "email": "aryan@nexus.ai",
                "full_name": "Aryan",
                "is_vegetarian": True,
                "is_vegan": False,
                "spice_tolerance": 4,
                "allergies": ["peanuts"],
                "fav_cuisines": ["Italian", "North Indian"],
                "disliked_ingredients": ["mushrooms"],
            },
            {
                "email": "himali@nexus.ai",
                "full_name": "Himali",
                "is_vegetarian": True,
                "is_vegan": False,
                "spice_tolerance": 2,
                "allergies": [],
                "fav_cuisines": ["South Indian", "Asian"],
                "disliked_ingredients": [],
            },
            {
                "email": "siya@nexus.ai",
                "full_name": "Siya",
                "is_vegetarian": True,
                "is_vegan": False,
                "spice_tolerance": 3,
                "allergies": [],
                "fav_cuisines": ["North Indian", "Continental"],
                "disliked_ingredients": ["mushroom"],
            },
            {
                "email": "swayam@nexus.ai",
                "full_name": "Swayam",
                "is_vegetarian": False,
                "is_vegan": False,
                "spice_tolerance": 4,
                "allergies": [],
                "fav_cuisines": ["Continental", "Asian"],
                "disliked_ingredients": [],
            },
            {
                "email": "priya@nexus.ai",
                "full_name": "Priya Sharma",
                "is_vegetarian": True,
                "is_vegan": True,
                "spice_tolerance": 2,
                "allergies": ["lactose"],
                "fav_cuisines": ["Asian", "South Indian"],
                "disliked_ingredients": ["capsicum"],
            },
            {
                "email": "kabir@nexus.ai",
                "full_name": "Kabir",
                "is_vegetarian": False,
                "is_vegan": False,
                "spice_tolerance": 5,
                "allergies": [],
                "fav_cuisines": ["North Indian", "Mughlai"],
                "disliked_ingredients": [],
            },
            {
                "email": "ananya@nexus.ai",
                "full_name": "Ananya",
                "is_vegetarian": True,
                "is_vegan": True,
                "spice_tolerance": 2,
                "allergies": ["lactose"],
                "fav_cuisines": ["Asian", "South Indian"],
                "disliked_ingredients": [],
            },
        ]

        for udata in demo_users:
            u = User(email=udata["email"], full_name=udata["full_name"])
            db.add(u)
            db.flush()

            dp = DietaryProfile(
                user_id=u.id,
                is_vegetarian=udata["is_vegetarian"],
                is_vegan=udata["is_vegan"],
                spice_tolerance=udata["spice_tolerance"],
            )
            dp.allergies = udata["allergies"]
            dp.fav_cuisines = udata["fav_cuisines"]
            dp.disliked_ingredients = udata["disliked_ingredients"]
            db.add(dp)

        db.commit()
    finally:
        db.close()


_EXTRA_GUESTS = [
    ("aryan@nexus.ai", "Aryan", 1, 0, 4, '["peanuts"]', '["Italian", "North Indian"]', '["mushrooms"]'),
    ("himali@nexus.ai", "Himali", 1, 0, 2, "[]", '["South Indian", "Asian"]', "[]"),
    ("siya@nexus.ai", "Siya", 1, 0, 3, "[]", '["North Indian", "Continental"]', '["mushroom"]'),
    ("swayam@nexus.ai", "Swayam", 0, 0, 4, "[]", '["Continental", "Asian"]', "[]"),
    ("kabir@nexus.ai", "Kabir", 0, 0, 5, "[]", '["North Indian", "Mughlai"]', "[]"),
    ("ananya@nexus.ai", "Ananya", 1, 1, 2, '["lactose"]', '["Asian", "South Indian"]', "[]"),
    ("rohan@nexus.ai", "Rohan", 0, 0, 4, "[]", '["Italian", "Continental"]', "[]"),
    ("meera@nexus.ai", "Meera", 1, 0, 3, "[]", '["Gujarati", "North Indian"]', "[]"),
]


def ensure_night_out_guests() -> None:
    """Idempotent: add Aryan/Himali/Siya/Swayam and friends to Taste Vault."""
    if HAS_SQLALCHEMY and SessionLocal:
        db = SessionLocal()
        try:
            for email, name, is_veg, is_vegan, spice, alg, cuis, dis in _EXTRA_GUESTS:
                if db.query(User).filter(User.email == email).first():
                    continue
                u = User(email=email, full_name=name)
                db.add(u)
                db.flush()
                dp = DietaryProfile(
                    user_id=u.id,
                    is_vegetarian=bool(is_veg),
                    is_vegan=bool(is_vegan),
                    spice_tolerance=spice,
                )
                dp.allergies = json.loads(alg)
                dp.fav_cuisines = json.loads(cuis)
                dp.disliked_ingredients = json.loads(dis)
                db.add(dp)
            db.commit()
        finally:
            db.close()
        return

    with sqlite3.connect(DB_FILE) as conn:
        for email, name, is_veg, is_vegan, spice, alg, cuis, dis in _EXTRA_GUESTS:
            row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                continue
            cur = conn.execute("INSERT INTO users (email, full_name) VALUES (?, ?)", (email, name))
            uid = cur.lastrowid
            conn.execute(
                """
                INSERT INTO dietary_profiles
                (user_id, is_vegetarian, is_vegan, spice_tolerance, allergies_json, fav_cuisines_json, disliked_ingredients_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (uid, is_veg, is_vegan, spice, alg, cuis, dis),
            )
        conn.commit()


init_db()
