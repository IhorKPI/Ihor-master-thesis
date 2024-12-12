import json

CONFIG_PATH = "/app/config/config.json"

GATE_DISTANCES = {}
TRANSPORT_RATES = {}

async def load_config():

    global GATE_DISTANCES, TRANSPORT_RATES
    try:
        with open(CONFIG_PATH, "r") as file:
            config = json.load(file)
            GATE_DISTANCES = {
                tuple(sorted(route.split("-"))): distance
                for route, distance in config["gate_distances"].items()
            }
            TRANSPORT_RATES = config["transport_rates"]
    except Exception as e:
        print(f"Error loading configuration: {e}")

def calculate_price(entry_gate, exit_gate, transport_type):
    dist = GATE_DISTANCES.get(tuple(sorted([entry_gate, exit_gate])))
    return dist, dist*TRANSPORT_RATES.get(transport_type)