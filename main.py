import pandas as pd
import argparse
from datetime import datetime, timedelta

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate a CSV file with daily work and travel events, including per‐diem and per‐km rates."
    )
    parser.add_argument(
        '--inland-rate',
        type=float,
        default=14.0,
        help='Default per‐diem rate for remote work (domestic).'
    )
    parser.add_argument(
        '--foreign-rate',
        type=float,
        default=28.0,
        help='Default per‐diem rate for remote work (foreign).'
    )
    parser.add_argument(
        '--km-rate',
        type=float,
        default=0.30,
        help='Default rate per kilometer for travel (e.g., 0.30 for €0.30/km).'
    )
    return parser.parse_args()

def main():
    args = parse_arguments()

    # Prompt for start and end datetime
    start_str = input("Enter the start datetime (YYYY-MM-DDTHH:MM): ")
    end_str   = input("Enter the end datetime (YYYY-MM-DDTHH:MM): ")

    try:
        start_dt = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
        end_dt   = datetime.strptime(end_str,   "%Y-%m-%dT%H:%M")
    except ValueError:
        print("Invalid format. Please use YYYY-MM-DDTHH:MM (e.g., 2025-06-01T09:00).")
        return

    # Build a list of all dates in the inclusive range
    date_list = []
    current_date = start_dt.date()
    while current_date <= end_dt.date():
        date_list.append(current_date)
        current_date += timedelta(days=1)

    records = []
    for date in date_list:
        print(f"\nDate: {date.isoformat()}")

        # 1) Prompt for work mode
        while True:
            mode = input("Did you work onsite or remote on this day? (onsite/remote): ").strip().lower()
            if mode in ["onsite", "remote"]:
                break
            print("Invalid input. Please enter 'onsite' or 'remote'.")

        # 2) Prompt for a description of the work event
        description_work = input("Enter a description for this work event: ").strip()

        if mode == "remote":
            # If remote, ask domestic vs foreign
            while True:
                location = input("Was the remote work domestic or foreign? (domestic/foreign): ").strip().lower()
                if location in ["domestic", "foreign"]:
                    break
                print("Invalid input. Please enter 'domestic' or 'foreign'.")

            # Determine per‐diem rate based on location
            per_diem = args.inland_rate if location == "domestic" else args.foreign_rate

            # Record the primary work event
            records.append({
                "Date": date.isoformat(),
                "Event_Type": "work",
                "Work_Mode": mode,
                "Remote_Type": location,
                "Per_Diem_Rate": per_diem,
                "Km_Rate": 0.0,
                "Distance_km": 0.0,
                "Travel_Cost": 0.0,
                "Description": description_work
            })

            # 3) Prompt for distance (km) for travel event, or 0 if not used
            print("\nIf you want to record a travel event for this remote day, enter the distance in kilometers.")
            print("If you do not want to record travel, enter 0.")
            while True:
                try:
                    distance_km = float(input("Enter distance in km (or 0 to skip): ").strip())
                    if distance_km < 0:
                        raise ValueError
                    break
                except ValueError:
                    print("Invalid input. Please enter a non‐negative number (e.g., 0, 15.5).")

            if distance_km > 0:
                # Prompt for a description of the travel event
                description_travel = input("Enter a description for this travel event: ").strip()
                travel_cost = distance_km * args.km_rate

                # Record a separate travel event
                records.append({
                    "Date": date.isoformat(),
                    "Event_Type": "travel",
                    "Work_Mode": mode,
                    "Remote_Type": location,
                    "Per_Diem_Rate": 0.0,
                    "Km_Rate": args.km_rate,
                    "Distance_km": distance_km,
                    "Travel_Cost": travel_cost,
                    "Description": description_travel
                })

        else:
            # Onsite: no remote type or per‐diem, and no travel event
            records.append({
                "Date": date.isoformat(),
                "Event_Type": "work",
                "Work_Mode": mode,
                "Remote_Type": "n/a",
                "Per_Diem_Rate": 0.0,
                "Km_Rate": 0.0,
                "Distance_km": 0.0,
                "Travel_Cost": 0.0,
                "Description": description_work
            })

    # Create DataFrame and save to CSV
    df = pd.DataFrame(records, columns=[
        "Date",
        "Event_Type",
        "Work_Mode",
        "Remote_Type",
        "Per_Diem_Rate",
        "Km_Rate",
        "Distance_km",
        "Travel_Cost",
        "Description"
    ])
    csv_path = "events_with_per_diem_and_travel.csv"
    df.to_csv(csv_path, index=False)

    # Output a preview and the file location
    print("\nSample of generated DataFrame:")
    print(df.head(10).to_string(index=False))
    print(f"\nData successfully saved to: {csv_path}")

if __name__ == "__main__":
    main()
