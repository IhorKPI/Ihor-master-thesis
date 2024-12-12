from fastapi import FastAPI, HTTPException
from elasticsearch import AsyncElasticsearch, NotFoundError
from pydantic import BaseModel

app = FastAPI()

es = AsyncElasticsearch(hosts=[
        "http://elasticsearch-node1:9200",
        "http://elasticsearch-node2:9200"
    ],
    sniff_on_start=False,
    sniff_on_connection_fail=False
)

class NumberPlateRequest(BaseModel):
    number_plate: list[str]

@app.post("/all-trips")
async def get_trips_by_car_number(input_data: NumberPlateRequest):
    trips = {}
    msearch_body = []
    for plate in input_data.number_plate:
        msearch_body.append({
            "index": "trips",
            "routing": plate
        })
        msearch_body.append({
            "query": {
                "term": {
                    "plate": plate
                }
            }
        })
    try:
        response = await es.msearch(body=msearch_body)
        print(response)
        for idx, res in enumerate(response['responses']):
            plate = input_data.number_plate[idx]
            hits = res.get('hits', {}).get('hits', [])
            trip_details = []
            for hit in hits:
                trip = hit['_source']
                trip['price'] = str(trip['price'])
                trip['distance'] = str(trip['distance'])
                trip_details.append(trip)
            trips[plate] = trip_details

        return trips

    except NotFoundError:
        raise HTTPException(status_code=404, detail="Index not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TripQueryRequest(BaseModel):
    number_plate: str
    ids: list[str]


@app.post("/all-trips-by-ids")
async def get_trips(trip_request: TripQueryRequest):
    try:
        response = await es.mget(
            index="trips",
            body={"ids": trip_request.ids},
            routing=trip_request.number_plate,
            _source=["transport_type", "price", "entry_gate", "exit_gate", "distance", "exit_timestamp"]
        )

        trips = []

        for doc in response['docs']:
            if doc.get('found'):
                source = doc['_source']
                trips.append(source)

        return trips

    except NotFoundError:
        raise HTTPException(status_code=404, detail="The 'trips' index was not found in Elasticsearch.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.on_event("shutdown")
async def shutdown():
    await es.close()
