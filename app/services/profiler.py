"""Taste Memory Vault Profiler: merges individual profiles into a Group Constraint Profile."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, List
from pydantic import BaseModel, Field

from app.config import settings
from app.db.models import DB_FILE, HAS_SQLALCHEMY, SessionLocal, User


class GroupConstraintProfile(BaseModel):
    """Merged non-negotiable constraint profile for a group of event attendees."""

    attendee_count: int
    recognized_emails: List[str]
    unrecognized_emails: List[str]

    # Dominant dietary flags
    must_be_vegan: bool = False
    must_be_vegetarian: bool = False
    must_be_eggetarian: bool = False
    must_be_gluten_free: bool = False
    must_be_jain: bool = False
    must_be_halal: bool = False

    # Maximum spice level tolerable by the group (lowest tolerance of any attendee)
    max_spice_tolerance: int = 5

    # Union of all allergies across all attendees
    all_allergies: List[str] = Field(default_factory=list)

    # Union of all disliked ingredients
    all_disliked_ingredients: List[str] = Field(default_factory=list)

    # Intersected/popular cuisines
    recommended_cuisines: List[str] = Field(default_factory=list)

    # Individual attendee profiles breakdown
    individual_profiles: List[dict[str, Any]] = Field(default_factory=list)

    # Lightweight onboarding schema for missing profiles
    onboarding_schema: dict[str, Any] | None = None


def get_group_preferences(email_list: List[str]) -> GroupConstraintProfile:
    """Query Taste Vault for each attendee and merge into a strict group constraint profile."""
    cleaned_emails = [e.strip().lower() for e in email_list if e and e.strip()]

    if HAS_SQLALCHEMY and SessionLocal:
        return _get_preferences_sqlalchemy(cleaned_emails)
    return _get_preferences_sqlite(cleaned_emails)


def _get_preferences_sqlalchemy(cleaned_emails: list[str]) -> GroupConstraintProfile:
    db = SessionLocal()
    try:
        recognized_users = (
            db.query(User).filter(User.email.in_(cleaned_emails)).all()
            if cleaned_emails
            else []
        )

        recognized_map = {u.email.lower(): u for u in recognized_users}
        recognized_emails = list(recognized_map.keys())
        unrecognized_emails = [e for e in cleaned_emails if e not in recognized_map]

        must_be_vegan = False
        must_be_vegetarian = False
        must_be_eggetarian = False
        must_be_gluten_free = False
        must_be_jain = False
        must_be_halal = False

        max_spice = 5
        allergies_set: set[str] = set()
        disliked_set: set[str] = set()
        cuisine_counts: dict[str, int] = {}
        individual_summaries: list[dict[str, Any]] = []

        for email in cleaned_emails:
            user = recognized_map.get(email)
            if not user or not user.dietary_profile:
                individual_summaries.append({
                    "email": email,
                    "status": "UNRECOGNIZED",
                    "notes": "No profile found in vault. Sent onboarding prompt.",
                })
                continue

            dp = user.dietary_profile
            individual_summaries.append({
                "email": user.email,
                "full_name": user.full_name,
                "status": "RECOGNIZED",
                "profile": dp.to_dict(),
            })

            if dp.is_vegan:
                must_be_vegan = True
            if dp.is_vegetarian or dp.is_vegan:
                must_be_vegetarian = True
            if dp.is_eggetarian:
                must_be_eggetarian = True
            if dp.is_gluten_free:
                must_be_gluten_free = True
            if dp.is_jain:
                must_be_jain = True
            if getattr(dp, "is_halal", False):
                must_be_halal = True

            if dp.spice_tolerance < max_spice:
                max_spice = dp.spice_tolerance

            allergies_set.update(dp.allergies)
            disliked_set.update(dp.disliked_ingredients)

            for c in dp.fav_cuisines:
                c_norm = c.strip().title()
                cuisine_counts[c_norm] = cuisine_counts.get(c_norm, 0) + 1

        sorted_cuisines = sorted(cuisine_counts.keys(), key=lambda x: cuisine_counts[x], reverse=True)
        if not sorted_cuisines:
            sorted_cuisines = ["North Indian", "Italian", "Chinese", "Multi-Cuisine"]

        onboarding_schema = None
        if unrecognized_emails:
            onboarding_schema = generate_onboarding_schema(unrecognized_emails)

        return GroupConstraintProfile(
            attendee_count=len(cleaned_emails),
            recognized_emails=recognized_emails,
            unrecognized_emails=unrecognized_emails,
            must_be_vegan=must_be_vegan,
            must_be_vegetarian=must_be_vegetarian,
            must_be_eggetarian=must_be_eggetarian,
            must_be_gluten_free=must_be_gluten_free,
            must_be_jain=must_be_jain,
            must_be_halal=must_be_halal,
            max_spice_tolerance=max_spice,
            all_allergies=sorted(list(allergies_set)),
            all_disliked_ingredients=sorted(list(disliked_set)),
            recommended_cuisines=sorted_cuisines,
            individual_profiles=individual_summaries,
            onboarding_schema=onboarding_schema,
        )
    finally:
        db.close()


def _get_preferences_sqlite(cleaned_emails: list[str]) -> GroupConstraintProfile:
    must_be_vegan = False
    must_be_vegetarian = False
    must_be_eggetarian = False
    must_be_gluten_free = False
    must_be_jain = False
    must_be_halal = False

    max_spice = 5
    allergies_set: set[str] = set()
    disliked_set: set[str] = set()
    cuisine_counts: dict[str, int] = {}
    individual_summaries: list[dict[str, Any]] = []
    recognized_emails = []
    unrecognized_emails = []

    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        for email in cleaned_emails:
            cur.execute("""
                SELECT u.email, u.full_name, dp.is_vegetarian, dp.is_vegan, dp.is_eggetarian, 
                       dp.is_gluten_free, dp.is_jain, dp.is_halal, dp.spice_tolerance, dp.allergies_json, 
                       dp.fav_cuisines_json, dp.disliked_ingredients_json
                FROM users u
                LEFT JOIN dietary_profiles dp ON u.id = dp.user_id
                WHERE u.email = ?
            """, (email,))
            row = cur.fetchone()

            if not row:
                unrecognized_emails.append(email)
                individual_summaries.append({
                    "email": email,
                    "status": "UNRECOGNIZED",
                    "notes": "No profile found in vault. Sent onboarding prompt.",
                })
                continue

            recognized_emails.append(email)
            is_veg = bool(row["is_vegetarian"])
            is_vegan = bool(row["is_vegan"])
            is_halal = bool(row["is_halal"]) if "is_halal" in row.keys() else False
            spice = int(row["spice_tolerance"] or 3)
            allergies = json.loads(row["allergies_json"] or "[]")
            cuisines = json.loads(row["fav_cuisines_json"] or "[]")
            disliked = json.loads(row["disliked_ingredients_json"] or "[]")

            individual_summaries.append({
                "email": row["email"],
                "full_name": row["full_name"],
                "status": "RECOGNIZED",
                "profile": {
                    "is_vegetarian": is_veg,
                    "is_vegan": is_vegan,
                    "is_halal": is_halal,
                    "spice_tolerance": spice,
                    "allergies": allergies,
                    "fav_cuisines": cuisines,
                    "disliked_ingredients": disliked,
                },
            })

            if is_vegan:
                must_be_vegan = True
            if is_veg or is_vegan:
                must_be_vegetarian = True
            if is_halal:
                must_be_halal = True

            if spice < max_spice:
                max_spice = spice

            allergies_set.update(allergies)
            disliked_set.update(disliked)

            for c in cuisines:
                c_norm = c.strip().title()
                cuisine_counts[c_norm] = cuisine_counts.get(c_norm, 0) + 1

    sorted_cuisines = sorted(cuisine_counts.keys(), key=lambda x: cuisine_counts[x], reverse=True)
    if not sorted_cuisines:
        sorted_cuisines = ["North Indian", "Italian", "Chinese", "Multi-Cuisine"]

    onboarding_schema = None
    if unrecognized_emails:
        onboarding_schema = generate_onboarding_schema(unrecognized_emails)

    return GroupConstraintProfile(
        attendee_count=len(cleaned_emails),
        recognized_emails=recognized_emails,
        unrecognized_emails=unrecognized_emails,
        must_be_vegan=must_be_vegan,
        must_be_vegetarian=must_be_vegetarian,
        must_be_eggetarian=must_be_eggetarian,
        must_be_gluten_free=must_be_gluten_free,
        must_be_jain=must_be_jain,
        must_be_halal=must_be_halal,
        max_spice_tolerance=max_spice,
        all_allergies=sorted(list(allergies_set)),
        all_disliked_ingredients=sorted(list(disliked_set)),
        recommended_cuisines=sorted_cuisines,
        individual_profiles=individual_summaries,
        onboarding_schema=onboarding_schema,
    )


def generate_onboarding_schema(unrecognized_emails: List[str]) -> dict[str, Any]:
    """Generate lightweight JSON schema query for onboarding missing attendees."""
    return {
        "title": "Swiggy Concierge Taste Profile Onboarding",
        "description": "Please specify dietary restrictions for unrecognized event attendees.",
        "target_emails": unrecognized_emails,
        "fields": {
            "is_vegetarian": {"type": "boolean", "default": False},
            "is_vegan": {"type": "boolean", "default": False},
            "spice_tolerance": {"type": "integer", "min": 1, "max": 5, "default": 3},
            "allergies": {"type": "array", "items": {"type": "string"}},
            "favorite_cuisines": {"type": "array", "items": {"type": "string"}},
        },
    }
