#!/usr/bin/env python3
"""Convert QCC financing API CSV into 14 business fields plus 7 amount audit fields."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


OUTPUT_FIELDS = [
    "融资日期",
    "项目名称",
    "业务描述",
    "融资轮次",
    "融资金额",
    "投资方",
    "行业门类",
    "行业大类",
    "所属城市",
    "企业名称",
    "成立日期",
    "估值",
    "来源标题",
    "来源链接",
    "amount_original",
    "currency_original",
    "amount_rmb",
    "amount_usd",
    "fx_rate_usd_cny",
    "fx_rate_date",
    "fx_source",
]

REQUIRED_RAW_FIELDS = {
    "Id",
    "FinanceDate",
    "ProductName",
    "Round",
    "Amount",
    "Area",
    "CompanyName",
    "EstablishDate",
    "Slogan",
    "Institutions",
    "ParticipantDetails",
    "QccIndustry",
    "Valuation",
    "NewsTitle",
    "NewsOriginalUrl",
}

QCC_TIMEZONE = ZoneInfo("Asia/Shanghai")

AMOUNT_PATTERNS = [
    (re.compile(r"^(?P<prefix>约|超|超过|近)?\s*(?P<num>[\d,.]+)\s*(?P<unit>亿|万)?\s*(?P<currency>美元|美金|USD)$", re.I), "USD"),
    (re.compile(r"^(?P<prefix>约|超|超过|近)?\s*(?P<currency>USD|US\$|\$)\s*(?P<num>[\d,.]+)\s*(?P<unit>B|M|K)?$", re.I), "USD"),
    (re.compile(r"^(?P<prefix>约|超|超过|近)?\s*(?P<num>[\d,.]+)\s*(?P<unit>亿|万)?\s*(?P<currency>元人民币|人民币|CNY|RMB)$", re.I), "CNY"),
    (re.compile(r"^(?P<prefix>约|超|超过|近)?\s*(?P<currency>CNY|RMB|¥|￥)\s*(?P<num>[\d,.]+)\s*(?P<unit>B|M|K)?$", re.I), "CNY"),
]
DEFAULT_CURRENCY_PATTERN = re.compile(
    r"^(?P<prefix>约|超|超过|近)?\s*(?P<num>[\d,.]+)\s*(?P<unit>亿|万|B|M|K)?\s*元?$",
    re.I,
)


def parse_amount(value: str, default_currency: str | None = None) -> tuple[str, Decimal, str] | None:
    text = value.strip()
    for pattern, currency in AMOUNT_PATTERNS:
        match = pattern.fullmatch(text)
        if not match:
            continue
        try:
            number = Decimal(match.group("num").replace(",", ""))
        except (InvalidOperation, AttributeError):
            return None
        unit = (match.groupdict().get("unit") or "").upper()
        multiplier = {
            "": Decimal(1),
            "万": Decimal(10_000),
            "亿": Decimal(100_000_000),
            "K": Decimal(1_000),
            "M": Decimal(1_000_000),
            "B": Decimal(1_000_000_000),
        }[unit]
        return currency, number * multiplier, match.groupdict().get("prefix") or ""
    if default_currency:
        match = DEFAULT_CURRENCY_PATTERN.fullmatch(text)
        if match:
            try:
                number = Decimal(match.group("num").replace(",", ""))
            except (InvalidOperation, AttributeError):
                return None
            unit = (match.group("unit") or "").upper()
            multiplier = {
                "": Decimal(1),
                "万": Decimal(10_000),
                "亿": Decimal(100_000_000),
                "K": Decimal(1_000),
                "M": Decimal(1_000_000),
                "B": Decimal(1_000_000_000),
            }[unit]
            return default_currency, number * multiplier, match.group("prefix") or ""
    return None


def decimal_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def amount_audit_fields(
    value: str,
    usd_cny_rate: Decimal | None,
    fx_date: str | None,
    fx_source: str | None,
    default_currency: str,
) -> tuple[dict[str, str], str]:
    fields = {
        "amount_original": value,
        "currency_original": "",
        "amount_rmb": "",
        "amount_usd": "",
        "fx_rate_usd_cny": str(usd_cny_rate) if usd_cny_rate is not None else "",
        "fx_rate_date": fx_date or "",
        "fx_source": fx_source or "",
    }
    if not value:
        return fields, "blank"
    if value in {"未披露", "未透露", "不详", "--", "-"}:
        return fields, "not_disclosed"
    if usd_cny_rate is None:
        return fields, "no_rate"
    parsed = parse_amount(value, default_currency)
    if parsed is None:
        fuzzy_markers = ("数", "上亿", "上千万", "数亿", "数千万", "数百万", "亿元级", "千万级")
        if any(marker in value for marker in fuzzy_markers):
            explicit_currency = "USD" if re.search(r"美元|美金|USD|US\$|\$", value, re.I) else "CNY" if re.search(r"人民币|CNY|RMB|¥|￥", value, re.I) else default_currency
            fields["currency_original"] = explicit_currency
            return fields, "fuzzy"
        return fields, "unparsed"
    currency, base_amount, _prefix = parsed
    fields["currency_original"] = currency
    if currency == "USD":
        fields["amount_usd"] = decimal_text(base_amount)
        fields["amount_rmb"] = decimal_text(base_amount * usd_cny_rate)
    else:
        fields["amount_rmb"] = decimal_text(base_amount)
        fields["amount_usd"] = decimal_text(base_amount / usd_cny_rate)
    return fields, "converted"


def parse_json(value: str, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


def timestamp_to_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromtimestamp(int(value), tz=QCC_TIMEZONE).date().isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def unique_names(items: Any) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    if not isinstance(items, list):
        return names
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name") or "").strip()
        if name and name not in seen:
            names.append(name)
            seen.add(name)
    return names


def extract_investors(row: dict[str, str]) -> str:
    names = unique_names(parse_json(row.get("Institutions", ""), []))
    if not names:
        names = unique_names(parse_json(row.get("ParticipantDetails", ""), []))
    if not names:
        names = unique_names(parse_json(row.get("PlaceFinanceInvestorCollection", ""), []))
    return "；".join(names)


def convert_row(
    row: dict[str, str],
    usd_cny_rate: Decimal | None,
    fx_date: str | None,
    fx_source: str | None,
    default_currency: str,
) -> tuple[dict[str, str], str]:
    area = parse_json(row.get("Area", ""), {})
    qcc_industries = parse_json(row.get("QccIndustry", ""), [])
    qcc_industry = qcc_industries[0] if isinstance(qcc_industries, list) and qcc_industries else {}
    if not isinstance(area, dict):
        area = {}
    if not isinstance(qcc_industry, dict):
        qcc_industry = {}

    amount_original = row.get("Amount", "").strip()
    audit_fields, amount_status = amount_audit_fields(
        amount_original, usd_cny_rate, fx_date, fx_source, default_currency
    )
    output = {
        "融资日期": timestamp_to_date(row.get("FinanceDate", "")),
        "项目名称": row.get("ProductName", "").strip(),
        "业务描述": (row.get("Slogan", "") or row.get("EventDecCt", "")).strip(),
        "融资轮次": row.get("Round", "").strip(),
        "融资金额": amount_original,
        "投资方": extract_investors(row),
        "行业门类": str(qcc_industry.get("An") or "").strip(),
        "行业大类": str(qcc_industry.get("Bn") or "").strip(),
        "所属城市": str(area.get("CityName") or "").strip(),
        "企业名称": row.get("CompanyName", "").strip(),
        "成立日期": timestamp_to_date(row.get("EstablishDate", "")),
        "估值": row.get("Valuation", "").strip(),
        "来源标题": row.get("NewsTitle", "").strip(),
        "来源链接": row.get("NewsOriginalUrl", "").strip(),
    }
    output.update(audit_fields)
    return output, amount_status


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert QCC financing API raw CSV to 14 business fields plus 7 amount audit fields."
    )
    parser.add_argument("input", type=Path, help="Raw CSV downloaded from the QCC page API")
    parser.add_argument("--out", required=True, type=Path, help="Standardized output CSV")
    parser.add_argument(
        "--market",
        required=True,
        choices=("domestic", "overseas"),
        help="Market scope; supplies CNY/USD only when the amount text has no explicit currency",
    )
    parser.add_argument("--start-date", help="Expected inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Expected inclusive end date (YYYY-MM-DD)")
    parser.add_argument("--usd-cny-rate", required=True, help="Auditable USD/CNY rate")
    parser.add_argument("--fx-date", required=True, help="Rate date (YYYY-MM-DD)")
    parser.add_argument("--fx-source", required=True, help="Traceable rate source")
    args = parser.parse_args()

    try:
        usd_cny_rate = Decimal(args.usd_cny_rate)
    except InvalidOperation as exc:
        raise SystemExit("--usd-cny-rate must be numeric") from exc
    if usd_cny_rate <= 0:
        raise SystemExit("--usd-cny-rate must be positive")

    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED_RAW_FIELDS - set(reader.fieldnames or []))
        if missing:
            raise SystemExit(f"missing required raw fields: {', '.join(missing)}")
        raw_rows = list(reader)

    ids = [row.get("Id", "") for row in raw_rows]
    if any(not value for value in ids):
        raise SystemExit("raw input contains blank Id values")
    if len(set(ids)) != len(ids):
        raise SystemExit(f"raw input contains {len(ids) - len(set(ids))} duplicate Id values")

    default_currency = "CNY" if args.market == "domestic" else "USD"
    converted = [
        convert_row(row, usd_cny_rate, args.fx_date, args.fx_source, default_currency)
        for row in raw_rows
    ]
    output_rows = [item[0] for item in converted]
    amount_statuses = [item[1] for item in converted]
    dates = [row["融资日期"] for row in output_rows]
    if any(not value for value in dates):
        raise SystemExit("one or more FinanceDate values could not be converted")
    if args.start_date and min(dates) < args.start_date:
        raise SystemExit(f"minimum financing date {min(dates)} is before {args.start_date}")
    if args.end_date and max(dates) > args.end_date:
        raise SystemExit(f"maximum financing date {max(dates)} is after {args.end_date}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)

    metadata_path = args.out.with_suffix(".meta.json")
    metadata = {
        "raw_input": str(args.input),
        "standardized_output": str(args.out),
        "amount_conversion": {
            "market": args.market,
            "default_currency": default_currency,
            "usd_cny_rate": str(usd_cny_rate) if usd_cny_rate is not None else None,
            "fx_date": args.fx_date,
            "fx_source": args.fx_source,
            "converted_rows": amount_statuses.count("converted"),
            "fuzzy_rows": amount_statuses.count("fuzzy"),
            "unparsed_rows": amount_statuses.count("unparsed"),
            "not_disclosed_rows": amount_statuses.count("not_disclosed"),
            "blank_rows": amount_statuses.count("blank"),
            "not_converted_without_rate": amount_statuses.count("no_rate"),
        },
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    blank_counts = {
        field: sum(not row[field] for row in output_rows)
        for field in OUTPUT_FIELDS
    }
    summary = {
        "input": str(args.input),
        "output": str(args.out),
        "metadata": str(metadata_path),
        "rows": len(output_rows),
        "columns": len(OUTPUT_FIELDS),
        "unique_ids": len(set(ids)),
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "blank_counts": blank_counts,
        "amount_conversion": metadata["amount_conversion"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
