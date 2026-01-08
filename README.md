# Python script to categorize and lookup expenses in CSV bank statements

This tool enables users to read bank statements in comma-separated value (CSV)
format and generate filtered summaries of financial entries. Its primary purpose
is to categorize expenses and income, providing clear visibility into spending
patterns and revenue streams across different categories throughout the year.

The tool features a built-in filtering system that, while simple to use, proves
remarkably powerful in practice. Beyond basic category analysis, these filters
can be leveraged to identify, group, and analyze virtually any data pattern
within the financial records, making it a versatile solution for comprehensive
financial analysis.

For the time being, only CSV files of the following banks are supported:

  - Raiffeisen
  - Aargauische Kantonalbank (AKB)

It might work for other banks as well, probably with only minor code changes.
You might kindly ask me to extend it for you, don't hesitate to contact me.

## Important Note

This tool, distributed under MIT license, comes without any warranty. Use it at
your own risk. Please let me know if you have suggestions or improvements. The
code is quick and dirty. Quality is OK for private use but no code reviews, unit
tests, static code analysis, code optimizations, nor any other quality measures
are systematically applied. Error handling is also very limited. However, it
works fine and stable for my purpose. When I find an issue, I usually fix it
quickly, so you can expect updates over time.

## Basic use

To get help and further information, I strongly recommend, you once run:

    ./analyze.py -h

To run the tool in general, at least the following three parameters are
required: `-s`, `-t` and `-c`, as shown in the following example:

    ./analyze.py -s statement.csv -t AKB -c categories.yaml

The categories.yaml file follows a simple structure of key-to-text-matches, as
shown in the following example:

    Category:
      - String-to-be-found-in-row-Buchungstext
    Fahrzeug:
      - Autogarage XY
    Steuern:
      - Zahlung Steueramt des Kantons Aargau
      - Strassenverkehrsamt
    Fahrkosten:
      - Zahlung SBB

Note that the YAML file itself can be empty or even non-existing, but the
parameter `-s` must still be provided. You can run the tool in interactive
identification mode, as explained below, to let the tool manage the
categories.yaml by its own.

When running the tool, it loads the transactions from the statement and
categorizes each one based on the categories defined in categories.yaml.
Transactions not matching any category will be marked as "unknown".

So, when the tool is run for the first time (i.e. without any categories
defined), it will just print all transactions found in the CSV bank statement
file, followed by the summary of total expenses and income. The user then has to
define categories and so the output will improve and show the expenses and
income based on categories.

To refine categories, the user has to edit the categories YAML file manually and
re-run the tool. This is a bit an iterative process until everything is fine.

This is the basic functionality: categorize and show transactions based on
categories. The following sections explain advanced features of the tool.

## Interactive identification mode

Finding and defining common categories is simple: find a sub-string that matches
all transaction texts belonging to a category. Once the simple ones are done it
gets tedious to add single transactions to the YAML file. Therefore, the
interactive identification mode has been invented. Run the tool as follows:

    ./analyze.py -s statement.csv -t AKB -c categories.yaml -i

The `-i` starts the interactive mode. The tool goes though all unknown
transactions and asks the user which category each one belongs to. Enter a
number or a text and press Enter (press just Enter without any input to ignore
the transaction = not categorize). It then asks the user for the search string.
Enter a sub-string of what is printed or just press Enter without typing any
character. The longer the search string, the more specific. All entered values
will go into the categories.yaml file each time when Enter was pressed after
asking for the search string.

At any time you can press CTRL-C to abort. You can continue later where you left
off with a small trick: remember the last ID and use an ID filter (see below):

    ./analyze.py -s statement.csv -t AKB -c categories.yaml -i -f 'ID>22'

This is also handy if you just want to categorize one single transaction:

    ./analyze.py -s statement.csv -t AKB -c categories.yaml -i -f 'ID=53'

## Filters

Filters have shown to be surprisingly powerful. Multiple filters can be combined
together to flexibly find and group transactions. Together with the printed
summary this becomes way more powerful than plain categorization.

See this example:

    ./analyze.py -s ... -t ... -c ... -f 'Kategorie=Fahrzeug,Belastung>100'

This will print all expenses with the category "Fahrzeug" which are of value >
CHF 100.

Filters can be combined with a comma, as shown above. Each filter can contain
one of the following operations: `=`, `>`, `<`, `?` or `!`. The text before the
operation must match a valid column header, the text after the operation is the
value which must match. The question mark operator performs a textual search of
the given value in each cell of the specified column. The exclamation mark
operator does the opposite of the `?`, it only matches when the value is not in
the cell.

And there is one more trick: Since I found it tedious to always enter the full
column name in filters, you can now just provide a sub-string which uniquely
identifies the column (e.g. `'text?Migros'` instead of `'Buchungstext?Migros'`).
Combine it with the `?` operator for even more power (e.g. `'Kat?Fahr'` instead
of `'Kategorie=Fahrzeug'`).

If you are clever, you could even define sub-categories this way. For example,
you could define categories "Fahrzeug-Auto" and "Fahrzeug-Motorrad" and then
filter with `'Kat?Fahr'` to see all expenses related to any vehicle but
`'Kat?Auto'` to see just the expenses for the car.

## Iterate through categories

There is another powerful feature: To go through all categories and for each one
see the transactions, you can use the following filter:

    ./analyze.py -s ... -t ... -c ... -f 'KategorieIdx=0'

This will show all transactions of category index 0. Increase the number in each
call to iterate over the categories.

## Controlling print output

The parameter `-p` controls the output:

    ./analyze.py -s ... -t ... -c ... -p table,summary
    ./analyze.py -s ... -t ... -c ... -p csv > output.csv

The options `table` and `summary` can be used separate or together, while `csv`
can only be used stand-alone. It prints in CSV format which can be redirected
into a file as shown in the example above.

## Ideas for the future

I still have some ideas which I might implement in future:

  * Use regex instead of sub-string search for categorization
  * If several categories would match a transaction, prefer the one with the
    longest search-string (the longer the more specific)
  * Add simple category-change of a transaction
