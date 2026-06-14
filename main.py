from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import httpx

# ── API Key Auth (Upstash Redis) ───────────────────────────────────────────────
import os, time, json as _json
from urllib.request import Request as _Req, urlopen as _urlopen

_UPSTASH_URL   = os.environ.get('UPSTASH_REDIS_REST_URL', '')
_UPSTASH_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
_TIERS = {'free': 1000, 'starter': 25000, 'pro': 200000, 'demo': 50}

def _redis(cmd):
    url = f'{_UPSTASH_URL}/{cmd[0]}/' + '/'.join(str(x) for x in cmd[1:])
    req = _Req(url, headers={'Authorization': f'Bearer {_UPSTASH_TOKEN}'})
    try:
        return _json.loads(_urlopen(req, timeout=3).read()).get('result')
    except: return None

def verify_api_key(x_api_key: str = Header(default='free-demo-key')):
    if not _UPSTASH_URL:  # no Upstash configured, allow all (dev mode)
        return {'key': x_api_key, 'tier': 'free'}
    tier = 'demo'
    if x_api_key != 'free-demo-key':
        raw = _redis(['GET', f'key:{x_api_key}'])
        if not raw:
            raise HTTPException(401, 'Invalid API key. Get one at btbuilds.lemonsqueezy.com')
        data = _json.loads(raw)
        if not data.get('active', True):
            raise HTTPException(401, 'API key revoked')
        tier = data.get('tier', 'free')
    month = time.strftime('%Y-%m')
    used = int(_redis(['INCR', f'usage:{x_api_key}:{month}']) or 1)
    if used == 1: _redis(['EXPIRE', f'usage:{x_api_key}:{month}', 2678400])
    limit = _TIERS.get(tier, 1000)
    if used > limit:
        raise HTTPException(429, f'Monthly limit reached ({limit:,}/mo). Upgrade at btbuilds.lemonsqueezy.com')
    return {'key': x_api_key, 'tier': tier, 'used': used}


app = FastAPI(
    title="Property Facts API",
    description="Get basic property facts (sqft, beds, baths, year, lot size)
# === BT Builds Standard Middleware (auto-injected) ===
from fastapi.middleware.cors import CORSMiddleware as _BTCors
app.add_middleware(_BTCors, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"], expose_headers=["X-RateLimit-Limit","X-RateLimit-Remaining","X-RateLimit-Reset"])

@app.middleware("http")
async def _bt_add_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Powered-By"] = "btbuilds"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response
 for any US address",
    version="1.0.0"
)

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

class BulkPropertyLookup(BaseModel):
    items: List[PropertyLookup]

class BulkResult(BaseModel):
    input: PropertyLookup
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

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

def build_full_address(payload: PropertyLookup) -> str:
    """Build full address string from lookup payload."""
    address = payload.address
    if payload.city and payload.state:
        address = f"{payload.address}, {payload.city}, {payload.state}"
        if payload.zip:
            address += f" {payload.zip}"
    return address

def process_property_lookup(payload: PropertyLookup) -> Dict[str, Any]:
    """Process a single property lookup and return results dict."""
    address = build_full_address(payload)
    
    estated_key = os.getenv("ESTATED_API_KEY", "")
    if estated_key:
        data = search_estated(address)
        if "error" not in data:
            return extract_property_data(data).dict()
    
    return estimate_property_facts(address).dict()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/lookup", dependencies=[Depends(verify_api_key)])
async def lookup_property(payload: PropertyLookup):
    address = build_full_address(payload)
    
    estated_key = os.getenv("ESTATED_API_KEY", "")
    if estated_key:
        data = search_estated(address)
        if "error" not in data:
            return extract_property_data(data)
    
    return estimate_property_facts(address)

@app.post("/bulk/lookup", dependencies=[Depends(verify_api_key)])
async def bulk_lookup_property(payload: BulkPropertyLookup):
    if len(payload.items) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 items per request")

    results = []
    successful = 0

    for item in payload.items:
        try:
            output = process_property_lookup(item)
            results.append(BulkResult(input=item, output=output).dict())
            successful += 1
        except Exception as e:
            results.append(BulkResult(input=item, error=str(e)).dict())

    return {"results": results, "total": len(payload.items), "successful": successful}

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

@app.post("/bulk/sqft", dependencies=[Depends(verify_api_key)])
async def bulk_get_sqft(payload: BulkPropertyLookup):
    if len(payload.items) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 items per request")

    results = []
    successful = 0

    for item in payload.items:
        try:
            full_address = build_full_address(item)
            estated_key = os.getenv("ESTATED_API_KEY", "")
            if estated_key:
                data = search_estated(full_address)
                if "error" not in data:
                    props = data.get("property", {})
                    results.append(BulkResult(input=item, output={"address": full_address, "sqft": props.get("sqft"), "source": "estated"}).dict())
                    successful += 1
                    continue
            facts = estimate_property_facts(full_address)
            results.append(BulkResult(input=item, output={"address": full_address, "sqft": facts.sqft, "source": facts.source}).dict())
            successful += 1
        except Exception as e:
            results.append(BulkResult(input=item, error=str(e)).dict())

    return {"results": results, "total": len(payload.items), "successful": successful}

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

@app.post("/bulk/beds-baths", dependencies=[Depends(verify_api_key)])
async def bulk_get_beds_baths(payload: BulkPropertyLookup):
    if len(payload.items) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 items per request")

    results = []
    successful = 0

    for item in payload.items:
        try:
            full_address = build_full_address(item)
            estated_key = os.getenv("ESTATED_API_KEY", "")
            if estated_key:
                data = search_estated(full_address)
                if "error" not in data:
                    props = data.get("property", {})
                    results.append(BulkResult(input=item, output={"address": full_address, "beds": props.get("beds"), "baths": props.get("baths"), "source": "estated"}).dict())
                    successful += 1
                    continue
            facts = estimate_property_facts(full_address)
            results.append(BulkResult(input=item, output={"address": full_address, "beds": facts.beds, "baths": facts.baths, "source": facts.source}).dict())
            successful += 1
        except Exception as e:
            results.append(BulkResult(input=item, error=str(e)).dict())

    return {"results": results, "total": len(payload.items), "successful": successful}

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

@app.post("/bulk/year-built", dependencies=[Depends(verify_api_key)])
async def bulk_get_year_built(payload: BulkPropertyLookup):
    if len(payload.items) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 items per request")

    results = []
    successful = 0

    for item in payload.items:
        try:
            full_address = build_full_address(item)
            estated_key = os.getenv("ESTATED_API_KEY", "")
            if estated_key:
                data = search_estated(full_address)
                if "error" not in data:
                    props = data.get("property", {})
                    results.append(BulkResult(input=item, output={"address": full_address, "year_built": props.get("year_built"), "source": "estated"}).dict())
                    successful += 1
                    continue
            facts = estimate_property_facts(full_address)
            results.append(BulkResult(input=item, output={"address": full_address, "year_built": facts.year_built, "source": facts.source}).dict())
            successful += 1
        except Exception as e:
            results.append(BulkResult(input=item, error=str(e)).dict())

    return {"results": results, "total": len(payload.items), "successful": successful}

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    pass