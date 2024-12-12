from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import NotFoundError, RequestError

es = AsyncElasticsearch(hosts=[
    "http://elasticsearch-node1:9200",
    "http://elasticsearch-node2:9200"
],
    sniff_on_start=False,
    sniff_on_connection_fail=False
)

async def table_init():
    index_name = "trips"
    settings = {
        "settings": {
            "number_of_shards": 4,
            "number_of_replicas": 1,
            "routing": {
                "allocation": {
                    "total_shards_per_node": 2
                }
            }
        },
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "plate": {"type": "keyword"},
                "transport_type": {"type": "keyword"},
                "trip_cost": {"type": "double"},
                "entry_gate": {"type": "keyword"},
                "exit_gate": {"type": "keyword"},
                "distance": {"type": "double"},
                "entry_timestamp": {"type": "date"},
                "exit_timestamp": {"type": "date"}
            }
        }
    }
    try:
        exists = await es.indices.exists(index=index_name)
        if not exists:
            await es.indices.create(index=index_name, body=settings)
        else:
            print("already exiist")
    except RequestError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")

async def add_to_elasticsearch(index, document):
    try:
        routing_value = document["plate"]
        response = await es.index(index=index, id=document["id"], document=document, routing=routing_value)
        print(f"Document added with ID: {response['_id']}")
    except Exception as e:
        print(f"Error adding document to Elasticsearch: {e}")

async def delete_from_elasticsearch(index, doc_id):
    try:
        response = await es.delete(index=index, id=doc_id)
        print(f"Document with ID {doc_id} deleted from index {index}.")
        return response
    except Exception as e:
        print(f"Error deleting document from Elasticsearch: {e}")

async def close_connection():
    await es.close()