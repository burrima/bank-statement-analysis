# Quick and dirty tool to process bank statements and categorize the expenses

This tool allows the user to read the bank statements in CSV form of the
following Swiss banks:

  - Raiffeisen
  - Aargauische Kantonalbank (AKB)

It might work for other banks as well - or users with basic Python knowledge
might extend it by their own.

The tool can be used to classify each expense freely and helps the author to see
what the money throughout a year has been spent for.

Along with the bank statement file (in csv) the user must create a yaml file
defining the different categories. The file follows a simple structure of
key-to-text-matches, as shown in the following example:

    Fahrzeug:
      - Autogarage XY
    Steuern:
      - Zahlung Steueramt des Kantons Aargau
      - Strassenverkehrsamt
    Fahrkosten:
      - Zahlung SBB

The tool can then be called as follows:

    ./analyze.py -s statement.csv -t AKB -c categories.yaml

Expenses not matching any category will be marked as "unknown".

To refine the categories.yaml file, the user has to edit it manually and re-run
the tool. This is a bit an iterative process until everything is fine. I am
still working on a better solution for this.

There is also a parameter to apply filters, to finally see how much has been
spent and also to find certain expenses:

    ./analyze.py -s ... -t ... -c ... -f "Kategorie=Fahrzeug,Belastung>0"

Filters can be combined with a comma, as shown above. Each filter can contain
one of the following operations: =, < or >. The text before the operation must
match a valid tag, the text after the operation is the value which must match.
It sounds a bit complex but is very powerful.

In addition to the built-in filter, the user can also use "grep" to further
refine a search, however, the statistics will then be filtered out by grep:

    ./analyze.py ... | grep -i "extra-text"

The tool "wc -l" is helpful to count the number of lines printed, which might
also be handy in some cases (e.g. to clarify the question of how many regular
payments of a specific kind have been made).

# Important Note

This tool comes without warranty and is licensed under the MIT license. Please
let me know if you have suggestions or improvements.

It is really quick and dirty, not a high-quality software. It works for my
purpose and it might be improved over time.

