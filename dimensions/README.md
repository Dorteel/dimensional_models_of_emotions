# Dimension vocabulary

`dimension_catalogue.ods` has one `Catalogue` sheet, with Dimension and Dimension
ID columns. `dimension_dictionary.ods` has one `Dictionary` sheet, with Dimension
followed by a definition/source pair for each research model. Formatting follows
the existing emotion spreadsheets. Neither workbook contains macros.

The current inventory covers circumplex, PAD, Plutchik, and vector, including
models without prototypes: eight occurrences of five IDs, sorted by name:
`arousal`, `dominance`, `intensity`, `pleasure`, `valence`. All currently lack
documented definitions. Blank definition cells preserve that absence; adjacent
Source cells retain the originating model, YAML path, original dimension name
and ID, and verbatim dimension/model notes with their documented references.
An entirely blank pair means that dimension does not occur in that model.

Discovery recursively reads standardized `.yaml` and `.yml` models under
`domains/`, including incomplete and draft models. `examples/` and the legacy
example filenames are excluded. The unmarked `domains/testingmodel.yaml` was
inspected and confirmed by the user as test data: it contains example prose and
a dimension defined as `dsad`. It is excluded from the official vocabulary.
This exception is explicit in the builder.

Concepts merge only by exact, unmodified dimension ID. Identical names with
different IDs remain separate rows. If names differ for one ID, the first name
in sorted model-path order labels the row and every original name stays in its
Source cell. Dictionary rows follow the catalogue's name/ID order. Each model
file keeps a separate column pair, preserving different definitions or sources
even for a shared ID. `undefined`, `no known definitions`, null, and empty
definitions become blank cells; genuine definition text is copied unchanged.

There are no conflicting names/IDs in the four research models. Whether
`pleasure` and `valence` refer to equivalent psychological concepts remains
unresolved; they are separate IDs and have not been merged. Shared `arousal`
occurrences retain each model's provenance without inventing a common definition.

Regenerate and validate from the repository root (existing PyYAML dependency):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 dimensions/build_dimension_tables.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_dimension_tables.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/libreoffice -p test_dimension_spreadsheets.py -v
```

Regeneration replaces only the two dimension ODS files. Tests check coverage,
blank missing definitions, verbatim provenance, exact-ID identity, distinct
model definitions, byte-reproducible rebuilding, and unchanged input files.
The LibreOffice test additionally requires `soffice` and the Python UNO bridge;
it opens both files read-only and compares every cell, including whitespace.
