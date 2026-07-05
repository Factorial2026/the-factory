"""
Example: fetch weather for Milano using The Factory client.

Before running:
    pip install the-factory-client

    # Get your Solana private key from Phantom:
    # Phantom → Settings → Show Private Key → enter password → copy the base58 string
    # Set it as environment variable:
    export THE_FACTORY_PRIVATE_KEY="your_base58_private_key_here"

Then:
    python example_usage.py
"""
import os
import sys

from the_factory_client import Factory, FactoryError


def main():
    private_key = os.environ.get("THE_FACTORY_PRIVATE_KEY")
    if not private_key:
        print("ERROR: set THE_FACTORY_PRIVATE_KEY environment variable first.")
        print("Get it from Phantom → Settings → Show Private Key.")
        sys.exit(1)

    # Initialize the client
    with Factory(private_key_base58=private_key) as f:
        print("=== Weather in Milano (last 3 days) ===")
        try:
            data = f.get("/api/v1/meteo", params={"q": "Milano", "days": 3})
            print(f"Location: {data.get('location')}")
            print(f"Summary:  {data.get('summary')}")
            print(f"Avg temp: {data.get('avg_temp_c')}°C")
            print(f"Days:")
            for d in data.get("days", []):
                print(f"  {d['date']}: {d['t_min_c']}–{d['t_max_c']}°C, {d['description']}")
        except FactoryError as e:
            print(f"Failed: {e}")
            sys.exit(1)

        print()
        print("=== EUR/USD exchange rate (last 7 days) ===")
        try:
            data = f.get("/api/v1/fx", params={"base": "EUR", "target": "USD", "days": 7})
            print(f"Pair:    {data.get('pair')}")
            print(f"Latest:  {data.get('latest_rate')}")
            print(f"Trend:   {data.get('trend_summary')}")
        except FactoryError as e:
            print(f"Failed: {e}")

        print()
        print("=== Vienna transit (Karlsplatz) ===")
        try:
            data = f.get("/api/v1/transit", params={"stop": "4205"})
            print(f"Stop: {data.get('stop_name')}")
            print(f"Time: {data.get('server_time')}")
            print(f"Arrivals:")
            for a in data.get("arrivals", [])[:5]:
                print(f"  Line {a['line']} → {a['direction']}: {a['eta_minutes']} min")
        except FactoryError as e:
            print(f"Failed: {e}")


if __name__ == "__main__":
    main()
