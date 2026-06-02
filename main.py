from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import httpx
import os

app = FastAPI(
    title="Property Facts API",
    description="Get basic property facts (sqft, beds, baths, year, lot size) for any US address",
    version="1.0.0"
)

API_KEY=os.get...sync def verify_api_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

class PropertyLookup(BaseModel):
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

class PropertyFacts(BaseModel):
    address: str
    sqft: Optional[int] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    year_built: Optional[int] = None
    lot_size_sqft: Optional[int] = None
    lot_size_acres: Optional[float] = None
    property_type: Optional[str] = None
    source: str = "estated"

def search_estated(address: str) -> Dict[str, Any]:
    """Search Estated public API for property data."""
    try:
        url = f"https://api.estated.com/v3/property"
        params = {
            "address": address,
            "token": os.getenv("ESTATED_API_KEY", "")
        }
        if not params["token"]:
            return {"error": "API not configured"}
        
        resp = httpx.get(url, params=params, timeout=10.0)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"API error: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def extract_property_data(data: Dict) -> PropertyFacts:
    """Extract relevant fields from Estated response."""
    props = data.get("property", {})
    
    sqft = props.get("sqft")
    beds = props.get("beds")
    baths = props.get("baths")
    year_built = props.get("year_built")
    lot_size_sqft = props.get("lot_size_sqft")
    lot_size_acres = lot_size_sqft / 43560 if lot_size_sqft else None
    property_type = props.get("property_type")
    
    address = f"{props.get('address', '')}, {props.get('city', '')}, {props.get('state', '')} {props.get('zip', '')}".strip(", ")
    
    return PropertyFacts(
        address=address or data.get("address", ""),
        sqft=sqft,
        beds=beds,
        baths=baths,
        year_built=year_built,
        lot_size_sqft=lot_size_sqft,
        lot_size_acres=round(lot_size_acres, 4) if lot_size_acres else None,
        property_type=property_type
    )

def estimate_property_facts(address: str) -> PropertyFacts:
    """Fallback estimation using address patterns when APIs unavailable."""
    result = PropertyFacts(
        address=address,
        sqft=None,
        beds=None,
        baths=None,
        year_built=None,
        lot_size_sqft=None,
        lot_size_acres=None,
        property_type="unknown",
        source="estimated"
    )
    
    addr_upper = address.upper()
    if "APT" in addr_upper or "#" in addr_upper:
        result.property_type = "apartment"
    elif "UNIT" in addr_upper:
        result.property_type = "condo"
    
    return result

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/lookup", dependencies=[Depends(verify_api_key)])
async def lookup_property(payload: PropertyLookup):
    address = payload.address
    if payload.city and payload.state:
        address = f"{payload.address}, {payload.city}, {payload.state}"
        if payload.zip:
            address += f" {payload.zip}"
    
    estated_key = os.getenv("ESTATED_API_KEY", "")
    if estated_key:
        data = search_estated(address)
        if "error" not in data:
            return extract_property_data(data)
    
    return estimate_property_facts(address)

@app.get("/sqft", dependencies=[Depends(verify_api_key)])
async def get_sqft(address: str, city: str = None, state: str = None, zip: str = None):
    full_address = address
    if city and state:
        full_address = f"{address}, {city}, {state}"
        if zip:
            full_address += f" {zip}"
    
    estated_key = os.getenv("ESTATED_API_KEY", "")
    if estated_key:
        data = search_estated(full_address)
        if "error" not in data:
            props = data.get("property", {})
            return {"address": full_address, "sqft": props.get("sqft"), "source": "estated"}
    
    facts = estimate_property_facts(full_address)
    return {"address": full_address, "sqft": facts.sqft, "source": facts.source}

@app.get("/beds-baths", dependencies=[Depends(verify_api_key)])
async def get_beds_baths(address: str, city: str = None, state: str = None, zip: str = None):
    full_address = address
    if city and state:
        full_address = f"{address}, {city}, {state}"
        if zip:
            full_address += f" {zip}"
    
    estated_key = os.getenv("ESTATED_API_KEY", "")
    if estated_key:
        data = search_estated(full_address)
        if "error" not in data:
            props = data.get("property", {})
            return {
                "address": full_address,
                "beds": props.get("beds"),
                "baths": props.get("baths"),
                "source": "estated"
            }
    
    facts = estimate_property_facts(full_address)
    return {
        "address": full_address,
        "beds": facts.beds,
        "baths": facts.baths,
        "source": facts.source
    }

@app.get("/year-built", dependencies=[Depends(verify_api_key)])
async def get_year_built(address: str, city: str = None, state: str = None, zip: str = None):
    full_address = address
    if city and state:
        full_address = f"{address}, {city}, {state}"
        if zip:
            full_address += f" {zip}"
    
    estated_key = os.getenv("ESTATED_API_KEY", "")
    if estated_key:
        data = search_estated(full_address)
        if "error" not in data:
            props = data.get("property", {})
            return {"address": full_address, "year_built": props.get("year_built"), "source": "estated"}
    
    facts = estimate_property_facts(full_address)
    return {"address": full_address, "year_built": facts.year_built, "source": facts.source}