# Property Facts API

Get basic property facts (sqft, beds, baths, year built, lot size) for any US address.

## Endpoints

### GET /health
Health check endpoint - no API key required.

```bash
curl https://property-facts.vercel.app/health
```

### POST /lookup
Get all property facts for an address.

```bash
curl -X POST https://property-facts.vercel.app/lookup \
  -H "Content-Type: application/json" \
  -H "x-api-key: demo-key-change-in-production" \
  -d '{"address": "123 Main St", "city": "New York", "state": "NY", "zip": "10001"}'
```

### GET /sqft
Get square footage for an address.

```bash
curl "https://property-facts.vercel.app/sqft?address=123%20Main%20St&city=New%20York&state=NY" \
  -H "x-api-key: demo-key-change-in-production"
```

### GET /beds-baths
Get bedroom and bathroom count.

```bash
curl "https://property-facts.vercel.app/beds-baths?address=123%20Main%20St&city=New%20York&state=NY" \
  -H "x-api-key: demo-key-change-in-production"
```

### GET /year-built
Get year built for a property.

```bash
curl "https://property-facts.vercel.app/year-built?address=123%20Main%20St&city=New%20York&state=NY" \
  -H "x-api-key: demo-key-change-in-production"
```

## Response Format

```json
{
  "address": "123 Main St, New York, NY 10001",
  "sqft": 1500,
  "beds": 2,
  "baths": 1.5,
  "year_built": 1985,
  "lot_size_sqft": 5000,
  "lot_size_acres": 0.115,
  "property_type": "single_family",
  "source": "estated"
}
```

## Authentication

All endpoints except `/health` require `x-api-key` header.

## Monetization

List on RapidAPI for $19-29/month team plan.

## Postman
[![Run in Postman](https://run.pstmn.io/button.svg)](https://raw.githubusercontent.com/BT-Builds/property-facts/main/postman_collection.json)
