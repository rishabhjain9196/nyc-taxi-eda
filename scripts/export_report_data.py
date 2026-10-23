"""Export aggregate chart data and simplified public zone boundaries."""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FRACTION = 0.0075


def series_view(label: str, series: dict[str, pd.Series], unit: str, note: str, bars: bool = False) -> dict:
    first = next(iter(series.values()))
    return {
        "label": label, "yTitle": unit, "note": note,
        "columns": ["Period", *series], "rows": [[str(x), *[round(float(s.loc[x]), 4) for s in series.values()]] for x in first.index],
        "traces": [{"name": name, "type": "bar" if bars else "scatter", "mode": "lines+markers",
                    "x": [str(x) for x in s.index], "y": [round(float(v), 4) for v in s.values],
                    "hovertemplate": "%{x}<br>%{y:,.2f}<extra>%{fullData.name}</extra>"} for name, s in series.items()]
    }


def main() -> None:
    df = pd.read_parquet(ROOT / "data" / "processed" / "trips_clean.parquet")
    if len(df) != 283908:
        raise ValueError("The cleaned sample differs from the published 283,908 trips.")
    pickup = df["tpep_pickup_datetime"]
    df["hour"] = pickup.dt.hour
    df["month"] = pickup.dt.month
    df["weekend"] = pickup.dt.dayofweek >= 5
    days = df.groupby(pickup.dt.normalize()).weekend.first().value_counts()
    pattern = df.groupby(["hour", "weekend"]).size().unstack().div(days)
    pattern.index = [f"{h:02}:00" for h in pattern.index]
    counts = df.groupby("hour").size()
    counts.index = [f"{h:02}:00" for h in counts.index]
    monthly = df.groupby("month").size()
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly.index = months
    financial = df[(df.fare_amount > 0) & (df.total_amount > 0)]
    revenue = financial.groupby("month").total_amount.sum() / FRACTION / 1e6
    revenue.index = months
    moving = df[(df.trip_distance > 0) & (df.trip_duration_min > 0)]
    sums = moving.groupby("hour")[["trip_distance", "trip_duration_min"]].sum()
    speed = sums.trip_distance / (sums.trip_duration_min / 60)
    priced = financial[financial.trip_distance > 0].copy()
    totals = priced.groupby("hour")[["fare_amount", "trip_distance"]].sum()
    fare = totals.fare_amount / totals.trip_distance
    speed.index = fare.index = [f"{h:02}:00" for h in range(24)]
    tipped = priced[priced.payment_type == 1].copy()
    tipped["tier"] = pd.cut(tipped.trip_distance, [0, 2, 5, np.inf], labels=["Up to 2 miles", "2 to 5 miles", "Over 5 miles"])
    tip_views = {}
    for by, title in [("tier", "By distance"), ("hour", "By pickup hour")]:
        total = tipped.groupby(by, observed=True)[["tip_amount", "fare_amount"]].sum()
        rates = total.tip_amount / total.fare_amount * 100
        if by == "hour":
            rates.index = [f"{h:02}:00" for h in rates.index]
        tip_views[by] = series_view(title, {"Tip rate": rates}, "Tips / fares (%)", "Total recorded tips divided by total fares; positive-distance, positive-fare credit card trips only. Cash tips are not recorded.", by == "tier")

    zones = gpd.read_file(ROOT / "data" / "raw" / "taxi_zones" / "taxi_zones.shp")
    if zones["LocationID"].nunique() != len(zones):
        raise ValueError("Zone IDs are not unique.")
    pickups = pd.crosstab(df.PULocationID, df.hour).reindex(columns=range(24), fill_value=0)
    dropoffs = pd.crosstab(df.DOLocationID, df.tpep_dropoff_datetime.dt.hour).reindex(columns=range(24), fill_value=0)
    shapes = []
    for _, zone in zones.iterrows():
        geometry = zone.geometry.simplify(130, preserve_topology=True)
        polygons = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
        xs, ys = [], []
        for polygon in polygons:
            for x, y in polygon.exterior.coords:
                xs.append(round(x, 1))
                ys.append(round(y, 1))
            xs.append(None)
            ys.append(None)
        zone_id = int(zone.LocationID)
        shapes.append({
            "id": zone_id, "name": zone.zone, "borough": zone.borough, "x": xs, "y": ys,
            "pickups": [int(v) for v in pickups.loc[zone_id]] if zone_id in pickups.index else [0] * 24,
            "dropoffs": [int(v) for v in dropoffs.loc[zone_id]] if zone_id in dropoffs.index else [0] * 24
        })
    top = df.PULocationID.value_counts().head(10).index
    lookup = zones.set_index("LocationID").zone
    heat = pickups.reindex(top)
    chart_data = {
        "demand": {"title": "When people ride", "views": {
            "daytype": series_view("Weekdays and weekends", {"Weekday": pattern[False], "Weekend": pattern[True]}, "Sampled pickups per day", "Normalised by observed calendar days: 260 weekdays and 105 weekend days. Values describe completed trips, not unmet demand."),
            "all": series_view("All trips by hour", {"Estimated trips": counts / FRACTION}, "Estimated 2023 trips", "Counts in the cleaned 0.75% sample divided by 0.0075. Every value sums the same hour across the year.")
        }},
        "zones": {"title": "Taxi activity by zone", "kind": "zones", "zones": shapes, "views": {
            key: {"label": label, "note": "Darker zones have more sampled trips, on a logarithmic colour scale. Drag to pan and use the toolbar to zoom. Unknown and outside-NYC IDs have no polygon. Night means 23:00 to 04:59."}
            for key, label in [("pickups", "All pickups"), ("dropoffs", "All dropoffs"), ("night", "Night pickups")]
        }},
        "zone-hours": {"title": "Hourly pickups in the ten busiest zones", "views": {"all": {
            "label": "Top ten zones", "note": "Sampled pickups by pickup hour, aggregated over the full year.",
            "traces": [{"type": "heatmap", "x": [f"{h:02}:00" for h in range(24)], "y": [lookup.loc[i] for i in top],
                        "z": heat.values.tolist(), "showscale": False, "xgap": 1, "ygap": 2,
                        "hovertemplate": "%{y}<br>%{x}: %{z:,} sampled pickups<extra></extra>"}],
            "columns": ["Zone", *[f"{h:02}:00" for h in range(24)]],
            "rows": [[lookup.loc[i], *map(int, heat.loc[i])] for i in top],
            "yaxis": {"autorange": "reversed"}, "xaxis": {"dtick": 3},
            "layout": {"margin": {"l": 155, "r": 5, "t": 10, "b": 45}}
        }}},
        "speed-price": {"title": "Speed and fare through the day", "views": {
            "speed": series_view("Average speed", {"Speed": speed}, "Miles per hour", "Total distance divided by total trip hours. This is not a simple mean of individual trip speeds."),
            "fare": series_view("Fare per mile", {"Fare": fare}, "Fare per mile (USD)", "Total fares divided by total miles for positive-distance, positive-fare trips. Differences also reflect trip mix.")
        }},
        "months": {"title": "Monthly activity", "views": {
            "revenue": series_view("Recorded payments", {"Payments": revenue}, "Estimated payments (USD millions)", "Positive-fare, positive-total trips scaled by 1 / 0.0075. Total amounts include recorded fees, tolls and card tips, but not cash tips or operating costs.", True),
            "trips": series_view("Trip counts", {"Trips": monthly / FRACTION / 1e6}, "Estimated trips (millions)", "Monthly counts in the cleaned sample divided by the 0.75% sampling fraction.", True)
        }},
        "tips": {"title": "Recorded tip rates", "views": tip_views}
    }
    flow = pd.DataFrame({"pickups": df.PULocationID.value_counts(), "dropoffs": df.DOLocationID.value_counts()}).fillna(0)
    flow = flow[(flow.pickups + flow.dropoffs >= 100) & (flow.dropoffs > 0)]
    flow["ratio"] = flow.pickups / flow.dropoffs
    flow = flow.join(lookup).dropna(subset=["zone"]).sort_values("ratio", ascending=False)
    flow_views = {}
    for key, label, part in [("sources", "More pickups than dropoffs", flow.head(10)), ("destinations", "More dropoffs than pickups", flow.tail(10).sort_values("ratio"))]:
        flow_views[key] = {
            "label": label, "xTitle": "Pickups per dropoff", "yaxis": {"autorange": "reversed"},
            "note": "Only zones with at least 100 combined sampled trips and at least one dropoff are compared. The records do not track empty travel, queues or unmet demand.",
            "columns": ["Zone", "Sampled pickups", "Sampled dropoffs", "Ratio"],
            "rows": [[row.zone, int(row.pickups), int(row.dropoffs), round(row.ratio, 4)] for row in part.itertuples()],
            "traces": [{"type": "bar", "orientation": "h", "x": part.ratio.round(4).tolist(), "y": part.zone.tolist(),
                        "hovertemplate": "%{y}<br>%{x:.2f} pickups per dropoff<extra></extra>"}]
        }
    chart_data["flows"] = {"title": "Pickup and dropoff imbalance", "views": flow_views}
    payments = df.payment_type.value_counts(normalize=True).sort_index() * 100
    payments.index = payments.index.map({0: "Not recorded", 1: "Credit card", 2: "Cash", 3: "No charge", 4: "Dispute", 5: "Unknown", 6: "Voided"})
    if payments.index.isna().any():
        raise ValueError("An unexpected payment category needs an explicit label.")
    chart_data["payments"] = {"title": "How passengers pay", "views": {"all": series_view(
        "Payment methods", {"Share": payments}, "Share of cleaned trips (%)",
        "Payment type 0 remains 'Not recorded'. It is not reassigned to credit card.", True)}}
    passengers = df.passenger_count.value_counts(normalize=True).sort_index() * 100
    passengers.index = passengers.index.map(lambda value: f"{value} passenger" if value == 1 else f"{value} passengers")
    chart_data["passengers"] = {"title": "Passenger group sizes", "views": {"all": series_view(
        "Group size", {"Share": passengers}, "Share of cleaned trips (%)",
        "Zero and missing passenger counts were imputed to one. These shares therefore reflect a processing assumption as well as recorded values.", True)}}
    fees = ["improvement_surcharge", "mta_tax", "congestion_surcharge", "extra", "airport_fee", "tolls_amount"]
    fee_names = ["Improvement surcharge", "MTA tax", "Congestion surcharge", "Extra charge", "Airport fee", "Tolls"]
    shares = df[fees].gt(0).groupby(df.hour).mean().T * 100
    chart_data["surcharges"] = {"title": "Charge frequency by hour", "views": {"all": {
        "label": "Charge frequency", "note": "The colour shows the percentage of trips charged, not the dollar amount. Some missing congestion and airport fees were inferred from the fare breakdown.",
        "columns": ["Charge", *[f"{h:02}:00" for h in range(24)]],
        "rows": [[name, *shares.loc[fee].round(2).tolist()] for name, fee in zip(fee_names, fees)],
        "traces": [{"type": "heatmap", "x": [f"{h:02}:00" for h in range(24)], "y": fee_names,
                    "z": shares.round(2).values.tolist(), "zmin": 0, "zmax": 100, "showscale": False,
                    "xgap": 1, "ygap": 3, "hovertemplate": "%{y}<br>%{x}: %{z:.1f}% of trips<extra></extra>"}],
        "yaxis": {"autorange": "reversed"}, "xaxis": {"dtick": 3},
        "layout": {"margin": {"l": 145, "r": 5, "t": 10, "b": 40}}
    }}}
    report = {"source": "NYC TLC 2023; aggregates from trips_clean.parquet; simplified NYC taxi zone boundaries.", "sample": len(df), "charts": chart_data}
    output = ROOT / "docs" / "report-data.js"
    output.write_text("window.REPORT = " + json.dumps(report, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Exported {len(chart_data)} charts and {len(shapes)} zone aggregates. No trip records exported.")


if __name__ == "__main__":
    main()
