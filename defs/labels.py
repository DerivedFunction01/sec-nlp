from enum import Enum

class LABELS(Enum):
    # --- Counts ---
    LABOR = "LABOR"  # employee counts, union members, hires/fires, job cuts
    LOCATION_COUNT = "LOCATION_COUNT"  # facilities + geographic coverage (stores, regions, offices)
    ENTITY_COUNT =  "ENTITY_COUNT"  # products, customers, segments, companies, unions, debts, markets
    SHARE = "SHARE"  # shares, stock units, equity counts

    # --- Quantities ---
    MONEY = "MONEY"  # $100, EUR 50, 10 per barrel/hour
    QUANTITY = "QUANTITY"  # barrels, tons, sq ft, basis points, meters

    # --- Time ---
    TIME = "TIME"  # 2001, January 1 2020, 10 days, 5-year, Q3 2002, fiscal 1997

    # --- Percentages ---
    PCT_CHANGE = "PCT_CHANGE"  # 10% increase, reduction of 5%
    PCT_RATE = "PCT_RATE"  # 10% interest rate, exchange rate of 5%
    PCT_OTHER = "PCT_OTHER"  # 10% coverage, 5% unionized, 10% turnover

    # --- Location / Info ---
    REFERENCE = "REFERENCE"  # Exhibit 10.2, Note 5, ASC 845-12, Page 10, p. 5
    ADDRESS = "ADDRESS"  # 123 Main St, Suite 200, zip codes, phone numbers

    # --- Discard ---
    BULLET = "BULLET"  # 1. First, (2) Second, 3) Third
    NOISE = "NOISE"  # standalone artifacts with no semantic value
    PROPER_NUM = "PROPER_NUM"  # 3M, 7-Eleven, Fortune 500, B-52, COVID-19, 401(k), Zero Corp, Local 50, proposition 50
