# Data

The data is not stored in this repository. Download it from the repository root:

```bash
python scripts/download_data.py
```

The script downloads about 610 MB and creates this layout:

```text
data/
  raw/
    trip_records/
      yellow_tripdata_2023-01.parquet
      ...
      yellow_tripdata_2023-12.parquet
    taxi_zones/
      taxi_zones.shp
      taxi_zones.dbf
      taxi_zones.shx
      taxi_zones.prj
      taxi_zones.cpg
  processed/
```

The notebook writes intermediate files to `data/processed/`.

## Sources

| File | Source |
| --- | --- |
| Yellow taxi trip records, January to December 2023 | [NYC TLC trip record data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) |
| Taxi zone shapefile | [NYC TLC taxi zones](https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip) |
| Field definitions | [Yellow taxi data dictionary](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf) |

## Dataset facts

- The twelve monthly files contain 38,310,226 trips and 19 columns.
- January names the airport fee column `airport_fee`. February to December name it `Airport_fee`.
- Each month has a block of trips where `passenger_count`, `RatecodeID`, `store_and_fwd_flag`, `congestion_surcharge` and `airport_fee` are all missing, and `payment_type` is 0. This block totals 1,309,356 trips, or 3.4% of the year.
- About 1% of trips have a negative fare. All of them come from VendorID 2.
- The shapefile has 263 zones. Trip records also use IDs 264 and 265 for unknown and out-of-city locations.

The TLC updates published files from time to time, so counts from a later download may differ slightly.
