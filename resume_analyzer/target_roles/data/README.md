# Target-role data files

`role_catalog.json` is the complete catalog used at runtime. Add a role by
adding one validated object; Python changes are not required. IDs must be
unique lowercase snake case, names must be non-empty, and every signal field
must be an array of strings.

`skill_aliases.json` maps English and Arabic surface forms to canonical terms.
The matcher keeps original evidence values and uses canonical forms only for
matching and duplicate removal.
