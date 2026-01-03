#!/usr/bin/env python3
# Copyright 2026 Martin Burri
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

from pathlib import Path
from pprint import pprint
from textwrap import dedent
import argparse
import logging
import yaml


logger = logging.getLogger(__name__)


info_text: str = dedent(
    """
    Tool to process bank statements and categorize the expenses.
    """)


def load_categories(path):
    """
    Load categories from yaml file.
    """
    with open(path, "r") as f:
        categories = yaml.safe_load(f)

    return categories


def invert_categories(categories):
    """
    Invert the categories dictionary.

    Categories in the definition file are stored as category: list-of-matches. This method inverts
    the data to be match: category. This allows for a faster and simpler look-up mechanism.
    """
    categories_inv = {}
    for category, patterns in categories.items():
        for pattern in patterns:
            categories_inv[pattern] = category

    return categories_inv


def load_bank_statement_akb(path):
    """
    Read and load an AKB Bank statement CSV file.
    """
    with open(path) as f:
        lines = f.readlines()

    table = []
    for line in lines[1:]:
        cells = line.strip().split(";")
        text = cells[2]
        text = text.replace("\"", "")
        text = text.strip()
        row = {
            "Buchung": cells[0],
            "Valuta": cells[1],
            "Buchungstext": text,
            "Belastung": float(cells[3].replace("'", "")) if cells[3] != "" else 0.0,
            "Gutschrift": float(cells[4].replace("'", "")) if cells[4] != "" else 0.0,
            "Saldo": float(cells[5].replace("'", "")) if cells[5] != "" else 0.0,
        }
        table.append(row)

    return table


def load_bank_statement_raiffeisen(path):
    """
    Read and load a Raiffeisen Bank statement CSV file.
    """
    with open(path, encoding="latin-1") as f:  # NOTE: Latin-1 encoding
        lines = f.readlines()

    # Load initial table as is from csv:
    table = []
    for line in lines[1:-1]:
        cells = line.strip().split(";")
        text = cells[2]
        text = text.replace("\"", "")
        text = text.strip()
        amount = float(cells[3]) if cells[3] != "" else 0.0
        booking_date = cells[1].split(" ")[0]
        row = {
            "Buchung": booking_date,
            "Valuta": cells[5],
            "Buchungstext": text,
            "Belastung": -amount if amount < 0 else 0.0,
            "Gutschrift": amount if amount > 0 else 0.0,
            "Saldo": float(cells[4]) if cells[4] != "" else 0.0,
        }
        table.append(row)

    # NOTE: Raiffeisen format has entries which span over different rows in the csv. There are
    # different cases where this can happen, e.g. with Sammelzahlung or Dauerauftrag, but generally
    # also with others. The strategy in this case is to drop the first (collective) row and update
    # the sub-rows accordingly with details from the collective row.

    final_table = []
    for i, row in enumerate(table):

        if i > 0 and row["Buchung"] == "":
            # Rows without booking date take their details from the previous line and the amount
            # from the last word in the Buchungstext of the current line.
            amount = float((row["Buchungstext"].split(" ")[-1]).replace("'", ""))
            row["Buchungstext"] = prev_full_row["Buchungstext"] + " " + row["Buchungstext"]
            row["Buchung"] = prev_full_row["Buchung"]
            row["Valuta"] = prev_full_row["Valuta"]
            row["Belastung"] = amount if prev_full_row["Belastung"] != 0 else 0.0
            row["Gutschrift"] = amount if prev_full_row["Gutschrift"] != 0 else 0.0
            row["Saldo"] = prev_full_row["Saldo"] - amount  # TODO: won't be correct!

            # If previous full row was the one before the current, remove it from the final table:
            if table[i-1] == prev_full_row:
                final_table.pop()
        else:
            # Full rows are processed normally
            prev_full_row = row

        final_table.append(row)

    return final_table


def add_category(table, categories):
    """
    Add a category to each row in the table according to the category definitions.
    """
    categories_inv = invert_categories(categories)

    for row in table:
        category = "unknown"
        text = row["Buchungstext"]
        for pat, cat in categories_inv.items():
            if pat.lower() in text.lower():
                category = cat
                break
        row["Kategorie"] = category

    return table


def apply_filter(table, filter_str, categories):
    """
    Create new table which only contains rows matching the given filter string.
    """
    out_table = []
    for i, row in enumerate(table):

        is_match = True
        if len(filter_str) > 0:
            for filter_part in filter_str.split(","):
                filter_part = filter_part.strip()
                is_inner_match = False
                if "=" in filter_part:
                    key, value = filter_part.split("=")
                    if key == "KategorieIdx":
                        key = "Kategorie"
                        value = list(categories.keys())[int(value)]
                    if row[key] == value:
                        is_inner_match = True
                elif ">" in filter_part:
                    key, value = filter_part.split(">")
                    if row[key] > float(value):
                        is_inner_match = True
                elif "<" in filter_part:
                    key, value = filter_part.split("<")
                    if row[key] < float(value):
                        is_inner_match = True
                is_match = is_match and is_inner_match

        if is_match:
            out_table.append(row)

    return out_table


def main(categories_file, statement_file, statement_type, filter_str, print_options):

    categories = load_categories(categories_file)

    match statement_type:
        case "Raiffeisen":
            table = load_bank_statement_raiffeisen(statement_file)
        case "AKB":
            table = load_bank_statement_akb(statement_file)
        case _:
            raise ValueError(f"{statement_type=} not supported!")

    table = add_category(table, categories)
    table = apply_filter(table, filter_str, categories)
    sums = {}

    if "csv" in print_options and print_options != "csv":
        raise ValueError("Print option 'csv' cannot be combined with others!")

    if "csv" in print_options:
        print(";".join(["Buchung", "Belastung", "Gutschrift", "Kategorie", "Buchungstext"]))
        for row in table:
            print(";".join([
                row["Buchung"],
                str(row["Belastung"]),
                str(row["Gutschrift"]),
                row["Kategorie"],
                row["Buchungstext"]]))

    if "table" in print_options:
        for i, row in enumerate(table):
            print(
                str(i).ljust(5),
                row["Buchung"].rjust(11),
                str(row["Belastung"]).rjust(10),
                str(row["Gutschrift"]).rjust(10),
                row["Kategorie"].ljust(15),
                row["Buchungstext"])

    if "summary" in print_options:
        for i, row in enumerate(table):
            category = row["Kategorie"]
            if category not in sums:
                sums[category] = { "Belastungen": 0.0, "Gutschriften": 0.0}
            sums[category]["Belastungen"] += row["Belastung"]
            sums[category]["Gutschriften"] += row["Gutschrift"]
        pprint(sums)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=info_text)

    parser.add_argument("-c", "--categories",
                        help="Categories definitions file (yaml)")
    parser.add_argument("-s", "--statement",
                        help="Bank statement file (csv)")
    parser.add_argument("-t", "--statement_type",
                        help="Bank statement type (Raiffeisen or AKB)")
    parser.add_argument("-f", "--filter",
                        help="Apply display filter (e.g. 'Kategorie=unknown,Belastung>50')",
                        default="")
    parser.add_argument("-p", "--print",
                        help="Print options: table, summary, csv (default: 'table,summary')",
                        default="table,summary")
    parser.add_argument("-l", "--loglevel",
                        help="log level to use",
                        default="INFO")
    args = parser.parse_args()

    logging.basicConfig(format='%(levelname)s: %(message)s',
                        level=args.loglevel.upper())
    logger.debug(f"{args=}")

    try:
        main(Path(args.categories), Path(args.statement), args.statement_type,
             args.filter, args.print)
    except Exception as ex:
        if args.loglevel.upper() == "DEBUG":
            raise
        logger.error(str(ex))
