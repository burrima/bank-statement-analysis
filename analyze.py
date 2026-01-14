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
from textwrap import dedent
import argparse
import logging
import yaml


logger = logging.getLogger(__name__)


info_text: str = dedent(
    """
    Tool to process bank statements and categorize the expenses.
    Provides advanced filtering and reporting to further refine
    the displayed information.

    Further help can be found in:
      * README.md
      * https://github.com/burrima/bank-statement-analysis
    """)


def load_categories(path):
    """
    Load categories from yaml file.
    """
    with open(path, "r") as f:
        categories = yaml.safe_load(f)
    return categories


def store_categories(categories, path):
    """
    Store categories to yaml file.
    """
    class MyDumper(yaml.Dumper):
        # Required to fix indentation, see:
        # https://stackoverflow.com/questions/25108581/python-yaml-dump-bad-indentation
        def increase_indent(self, flow=False, indentless=False):
            return super(MyDumper, self).increase_indent(flow, False)

    with open(path, "w") as f:
        yaml.dump(categories, f, Dumper=MyDumper, default_flow_style=False, encoding='utf-8',
                  indent=2, allow_unicode=True)


def invert_categories(categories):
    """
    Invert the categories dictionary: key-values => value-key.
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
    for i, line in enumerate(lines[1:]):
        cells = line.strip().split(";")
        row = {
            "ID": i,
            "Datum": cells[0],
            "Buchungstext": cells[2].replace("\"", "").strip(),
            "Belastung": float(cells[3].replace("'", "")) if cells[3] != "" else 0.0,
            "Gutschrift": float(cells[4].replace("'", "")) if cells[4] != "" else 0.0,
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
        amount = float(cells[3]) if cells[3] != "" else 0.0
        row = {
            "Datum": cells[1].split(" ")[0],
            "Buchungstext": cells[2].replace("\"", "").strip(),
            "Belastung": -amount if amount < 0 else 0.0,
            "Gutschrift": amount if amount > 0 else 0.0,
        }
        table.append(row)

    # NOTE: Raiffeisen format has entries which span over different rows in the csv. There are
    # different cases where this can happen, e.g. with Sammelzahlung or Dauerauftrag, but generally
    # also with others. The strategy in this case is to drop the first (collective) row and update
    # the sub-rows accordingly with details from the collective row.

    final_table = []
    for i, row in enumerate(table):

        if i > 0 and row["Datum"] == "":
            # Rows without booking date take their details from the previous line and the amount
            # from the last word in the Buchungstext of the current line (with exceptions).
            if prev_full_row["Buchungstext"].startswith("Gutschrift"):
                # In this and next case, the current row could contain EUR instead of CHF, thus rely
                # on the previous full row. Gutschrift and Zahlung may only have non-full row after
                # them!
                amount = prev_full_row["Gutschrift"]
            elif prev_full_row["Buchungstext"].startswith("Zahlung"):
                amount = prev_full_row["Belastung"]
            else:
                amount = float((row["Buchungstext"].split(" ")[-1]).replace("'", ""))
            row["Buchungstext"] = prev_full_row["Buchungstext"] + " " + row["Buchungstext"]
            row["Datum"] = prev_full_row["Datum"]
            row["Belastung"] = amount if prev_full_row["Belastung"] != 0 else 0.0
            row["Gutschrift"] = amount if prev_full_row["Gutschrift"] != 0 else 0.0

            # If previous full row was the one before the current, remove it from the final table:
            if table[i-1] == prev_full_row:
                final_table.pop()
        else:
            # Full rows are processed normally
            prev_full_row = row

        final_table.append(row)

    for i, row in enumerate(final_table):  # set row IDs
        row["ID"] = i

    return final_table


def load_bank_statement(statement_file, statement_type):
    match statement_type:
        case "Raiffeisen":
            table = load_bank_statement_raiffeisen(statement_file)
        case "AKB":
            table = load_bank_statement_akb(statement_file)
        case _:
            raise ValueError(f"{statement_type=} not supported!")
    return table


def add_category(table, categories):
    """
    Add a category to each row in the table according to the category definitions.
    """
    categories_inv = invert_categories(categories)

    for row in table:
        category = "unknown"
        pat_len = 0
        for pat, cat in categories_inv.items():
            if pat.lower() in row["Buchungstext"].lower() and len(pat) > pat_len:
                category = cat
                pat_len = len(pat)
        row["Kategorie"] = category
    return table


def apply_filter(table, filter_str, categories):
    """
    Create new table which only contains rows matching the given filter string.
    """
    if len(filter_str) == 0:
        return table

    # Prepare a table of filters to be applied later:
    filters = []
    for filter_part in filter_str.split(","):
        filter_part = filter_part.strip()

        for operator in ["=", "<", ">", "?", "!"]:
            if operator not in filter_part:
                continue

            key = None
            tmpkey, value = filter_part.split(operator)
            for fullkey in table[0].keys():
                if tmpkey.lower() in fullkey.lower():  # ignore case
                    key = fullkey
                    break
            if key is None and tmpkey.lower() in "KategorieIdx".lower():
                key = "Kategorie"
                value = list(categories.keys())[int(value)]
            if key is None:
                raise RuntimeError(f"Key '{tmpkey}' does not match any column name!")

            match operator:
                case "=":
                    is_match_func = lambda a, b: a == float(b) if str(a)[0].isdigit() else a == b
                case "<":
                    is_match_func = lambda a, b: float(a) < float(b)
                case ">":
                    is_match_func = lambda a, b: float(a) > float(b)
                case "?":
                    is_match_func = lambda a, b: str(b).lower() in str(a).lower()  # ignore case
                case "!":
                    is_match_func = lambda a, b: str(b).lower() not in str(a).lower()  # ignore case

            filters.append({
                "operator": operator,
                "key": key,
                "value": value,
                "is_match": is_match_func,
            })

    # Apply filters to table:
    out_table = []
    for i, row in enumerate(table):

        is_match = True
        for f in filters:
            is_match = is_match and f["is_match"](row[f["key"]], f["value"])

        if is_match:
            out_table.append(row)

    return out_table


def print_as_table(table, keys):
    # determine max column widths:
    max_lengths = {}
    for key in keys:
        max_lengths[key] = len(key)
        for row in table:
            length = len(str(row[key]))
            if length > max_lengths[key]:
                max_lengths[key] = length

    # print title:
    title = ""
    for key in keys:
        title += " " + str(key).ljust(max_lengths[key]) + " "
    print(title.rstrip())
    print("-" * len(title))

    # print rows:
    for row in table:
        line = ""
        for key in keys:
            value = row[key]
            if isinstance(value, float):
                line += " " + f"{value:.2f}".rjust(max_lengths[key]) + " "
            elif isinstance(value, int):
                line += " " + str(value).rjust(max_lengths[key]) + " "
            else:
                line += " " + str(value).ljust(max_lengths[key]) + " "
        print(line.rstrip())


def print_to_stdout(table, print_options):
    if "csv" in print_options and print_options != "csv":
        raise ValueError("Print option 'csv' cannot be combined with others!")

    if "csv" in print_options:
        print(";".join(["Datum", "Belastung", "Gutschrift", "Kategorie", "Buchungstext"]))
        for row in table:
            print(";".join([
                row["Datum"],
                str(row["Belastung"]),
                str(row["Gutschrift"]),
                row["Kategorie"],
                row["Buchungstext"]]))

    if "table" in print_options:
        print_as_table(
            table,
            keys = ("ID", "Datum", "Belastung", "Gutschrift", "Kategorie", "Buchungstext"))
        print(f"\nAnzahl Buchungen: {len(table)}")

    if "summary" in print_options:
        print("\nZusammenfassung:\n")
        # Generate summary dicts:
        sums = {}
        dummy = { "Kategorie": "", "Belastung": "", "Gutschrift": "" }
        sums_of_sums = { "Kategorie": "GESAMT-TOTAL", "Belastung": 0.0, "Gutschrift": 0.0 }
        for i, row in enumerate(table):
            category = row["Kategorie"]
            if category not in sums:
                sums[category] = { "Belastung": 0.0, "Gutschrift": 0.0}
            sums[category]["Belastung"] += row["Belastung"]
            sums[category]["Gutschrift"] += row["Gutschrift"]
            sums_of_sums["Belastung"] += row["Belastung"]
            sums_of_sums["Gutschrift"] += row["Gutschrift"]
        # convert summary dicts to table:
        keys = list(sums.keys())
        keys.sort()
        table = [{"Kategorie": key,
                  "Belastung": round(sums[key]['Belastung'], 2),
                  "Gutschrift": round(sums[key]['Gutschrift'], 2)} for key in keys]
        if len(table) > 1:
            sums_of_sums["Belastung"] = round(sums_of_sums["Belastung"], 2)
            sums_of_sums["Gutschrift"] = round(sums_of_sums["Gutschrift"], 2)
            table += [dummy, sums_of_sums]
        # finally print summary table:
        print_as_table(table, keys=("Kategorie", "Belastung", "Gutschrift"))


def classify_interactive(categories_file, statement_file, statement_type, filter_str):
    """
    Go through the list of "unknown" entries and ask the user for each one what category it shall
    belong to. Categories are auto-added to the categories.yaml file.

    Categorization can be stopped with ctrl-c at any time.
    """
    last_idx = 0
    while True:
        categories = load_categories(categories_file)

        table = load_bank_statement(statement_file, statement_type)
        table = add_category(table, categories)
        table = apply_filter(table, filter_str, categories)

        for i, row in enumerate(table[last_idx:]):
            if row["Kategorie"] != "unknown":
                continue

            print("Line of interest:\n")
            print_to_stdout([row], "table")

            print("\nEnter category number or category name",
                  "(not existing one will be auto-created, empty string means 'unknown'):")
            # print categories in 2 columns, which makes it a bit more complex
            keys = ["unknown"] + sorted([k for k in categories.keys()])
            num_lines = int(len(keys) / 2) + (1 if len(keys) % 2 != 0 else 0)
            for j in range(num_lines):
                k = num_lines + j
                if k < len(keys):
                    print(str(j).rjust(3), keys[j].ljust(20), str(k).rjust(3), keys[k])
                else:
                    print(str(j).rjust(3), keys[j])

            # Read user input:
            category = input("> ") or 0  # set to 0 in case of empty string
            if str(category).isdigit():
                category = keys[int(category)]
            logger.debug(f"{category=}")

            if category == "unknown":
                continue

            print("Define matching text string (take full string by just hitting Enter):")
            print(" ", row["Buchungstext"])
            # Read user input:
            text = input("> ") or row["Buchungstext"]
            logger.debug(f"{text=}")

            if category not in categories:
                categories[category] = list()
            categories[category] += [text]

            store_categories(categories, categories_file)

            if text != row["Buchungstext"]:
                last_idx += i
                break  # break inner loop to re-load whole table

        if i + last_idx + 1 >= len(table):
            print("No more entries to categorize!")
            break


def main(categories_file, statement_file, statement_type, filter_str, print_options):

    categories = load_categories(categories_file)

    table = load_bank_statement(statement_file, statement_type)
    table = add_category(table, categories)
    table = apply_filter(table, filter_str, categories)

    print_to_stdout(table, print_options)


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
    parser.add_argument("-i", "--interactive",
                        help="Update categories by going through unclassified expenses",
                        action="store_true", default=False)
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
        if args.categories is None:
            raise ValueError("No categories definitions file provided!")
        if args.statement is None:
            raise ValueError("No bank statement file provided!")
        if args.statement_type is None:
            raise ValueError("Bank statement type provided!")

        if args.interactive in ["1", "True", "true", True]:
            classify_interactive(Path(args.categories), Path(args.statement), args.statement_type,
                                 args.filter)
        else:
            main(Path(args.categories), Path(args.statement), args.statement_type,
                 args.filter, args.print)
    except Exception as ex:
        if args.loglevel.upper() == "DEBUG":
            raise
        logger.error(str(ex))
