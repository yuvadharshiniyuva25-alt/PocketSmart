import os
import re
import json
import urllib.parse
from datetime import datetime
from typing import Optional
from PIL import Image
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import google.generativeai as genai

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()

if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None

app = FastAPI(title="PocketSmart AI")

os.makedirs("static/uploads", exist_ok=True)
os.makedirs("templates", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

history_db = []

def extract_json_from_response(text: str) -> dict:
    cleaned = re.sub(r"^(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"$", "", cleaned.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return json.loads(cleaned)

class HomeBudgetInput(BaseModel):
    total_budget: float
    num_lights: int = 0
    num_fans: int = 0
    num_furniture: int = 0
    num_dining_tables: int = 0

class PartyBudgetInput(BaseModel):
    total_budget: float
    party_type: str
    num_guests: int

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/home-planner", response_class=HTMLResponse)
async def home_planner_page(request: Request):
    return templates.TemplateResponse(request=request, name="home_planner.html")

@app.post("/home-budget")
async def plan_home(budget_input: HomeBudgetInput):
    try:
        prompt = f"""
        Provide home interior items for India within budget INR {budget_input.total_budget}.
        Requirements: {budget_input.num_lights} lights, {budget_input.num_fans} fans, {budget_input.num_furniture} furniture, {budget_input.num_dining_tables} dining tables.
        Output ONLY valid JSON with no markdown wrapping:
        {{
            "total_budget": {budget_input.total_budget},
            "items": [
                {{"name": "Philips LED Smart Bulb", "price": 600, "category": "lighting"}},
                {{"name": "Atomberg BLDC Ceiling Fan", "price": 3200, "category": "fans"}},
                {{"name": "Engineered Wood Sofa Set", "price": 14000, "category": "furniture"}},
                {{"name": "Solid Wood 4-Seater Dining Table", "price": 7200, "category": "dining"}}
            ],
            "remaining_budget": 0
        }}
        """
        response = model.generate_content(prompt)
        result = extract_json_from_response(response.text)
    except Exception as e:
        print(f"Error calling Gemini, falling back to local budget calculation: {e}")
        result = {
            "total_budget": budget_input.total_budget,
            "items": [
                {"name": f"{budget_input.num_lights}x Energy Efficient LED Bulbs", "price": round(budget_input.total_budget * 0.15), "category": "lighting"},
                {"name": f"{budget_input.num_fans}x BLDC Ceiling Fans", "price": round(budget_input.total_budget * 0.25), "category": "fans"},
                {"name": f"{budget_input.num_furniture}x Living Room Furniture Set", "price": round(budget_input.total_budget * 0.40), "category": "furniture"},
                {"name": f"{budget_input.num_dining_tables}x Wooden Dining Table", "price": round(budget_input.total_budget * 0.20), "category": "dining"}
            ],
            "remaining_budget": 0
        }

    for it in result.get("items", []):
        q = urllib.parse.quote_plus(it.get("name", "decor"))
        it["amazon"] = f"https://www.amazon.in/s?k={q}"
        it["ikea"] = f"https://www.ikea.com/in/en/search/?q={q}"

    history_db.append({"type": "Home", "date": datetime.now().strftime("%d %b, %Y"), "data": result})
    return result

@app.get("/party-planner", response_class=HTMLResponse)
async def party_planner_page(request: Request):
    return templates.TemplateResponse(request=request, name="party_planner.html")

@app.post("/party-budget")
async def plan_party(budget_input: PartyBudgetInput):
    try:
        prompt = f"""
        Provide party planning allocations for India within budget INR {budget_input.total_budget}.
        Type: {budget_input.party_type}, Guests: {budget_input.num_guests}.
        Output ONLY valid JSON with no markdown wrapping:
        {{
            "total_budget": {budget_input.total_budget},
            "items": [
                {{"name": "Buffet Food Catering", "price": 5000, "category": "food"}},
                {{"name": "Party Balloons & Fairy Lights", "price": 1500, "category": "decor"}},
                {{"name": "Sound & Speaker Rental", "price": 2000, "category": "entertainment"}},
                {{"name": "Custom Cake & Beverages", "price": 1500, "category": "dessert"}}
            ],
            "remaining_budget": 0
        }}
        """
        response = model.generate_content(prompt)
        result = extract_json_from_response(response.text)
    except Exception as e:
        print(f"Error calling Gemini, falling back to local budget calculation: {e}")
        result = {
            "total_budget": budget_input.total_budget,
            "items": [
                {"name": f"Food Catering for {budget_input.num_guests} Guests", "price": round(budget_input.total_budget * 0.50), "category": "food"},
                {"name": "Party Decoration & Theme Lights", "price": round(budget_input.total_budget * 0.20), "category": "decor"},
                {"name": "Party Music & Sound Setup", "price": round(budget_input.total_budget * 0.15), "category": "entertainment"},
                {"name": "Beverages & Celebration Cake", "price": round(budget_input.total_budget * 0.15), "category": "dessert"}
            ],
            "remaining_budget": 0
        }

    for it in result.get("items", []):
        q = urllib.parse.quote_plus(it.get("name", "party"))
        it["swiggy"] = f"https://www.swiggy.com/search?query={q}"
        it["amazon"] = f"https://www.amazon.in/s?k={q}"

    history_db.append({"type": "Party", "date": datetime.now().strftime("%d %b, %Y"), "data": result})
    return result

@app.get("/jewelry-planner", response_class=HTMLResponse)
async def jewelry_planner_page(request: Request):
    return templates.TemplateResponse(request=request, name="jewelry_planner.html")

@app.post("/jewelry-budget")
async def plan_jewelry(
    total_budget: float = Form(...),
    occasion: str = Form(...),
    image: Optional[UploadFile] = File(None)
):
    image_path = None
    if image and image.filename:
        image_path = os.path.join("static/uploads", image.filename)
        with open(image_path, "wb") as f:
            f.write(await image.read())

    try:
        base_prompt = f"""
        Recommend jewelry in India for INR {total_budget} budget. Occasion: {occasion}.
        Output ONLY valid JSON:
        {{
            "total_budget": {total_budget},
            "items": [
                {{"name": "Gold Plated Kundan Necklace Set", "price": 4500, "style": "Traditional"}},
                {{"name": "Zircon Drop Earrings", "price": 1500, "style": "Modern"}},
                {{"name": "Matching Bangles & Ring", "price": 2000, "style": "Ethnic"}}
            ],
            "remaining_budget": 0
        }}
        """
        if image_path and os.path.exists(image_path):
            img = Image.open(image_path)
            response = model.generate_content([base_prompt, img])
        else:
            response = model.generate_content(base_prompt)

        result = extract_json_from_response(response.text)
    except Exception as e:
        print(f"Error calling Gemini, falling back to local recommendations: {e}")
        result = {
            "total_budget": total_budget,
            "items": [
                {"name": f"Occasion Necklace ({occasion})", "price": round(total_budget * 0.55), "style": "Festive"},
                {"name": "Complementary Drop Earrings", "price": round(total_budget * 0.25), "style": "Classic"},
                {"name": "Accessory Bracelet / Ring", "price": round(total_budget * 0.20), "style": "Modern"}
            ],
            "remaining_budget": 0
        }

    for it in result.get("items", []):
        q = urllib.parse.quote_plus(it.get("name", "jewelry"))
        it["amazon"] = f"https://www.amazon.in/s?k={q}"
        it["tanishq"] = f"https://www.tanishq.co.in/search?q={q}"

    history_db.append({"type": "Jewelry", "date": datetime.now().strftime("%d %b, %Y"), "data": result})
    return result

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return templates.TemplateResponse(request=request, name="history.html", context={"history": history_db})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)    