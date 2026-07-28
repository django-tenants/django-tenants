from django.core.exceptions import ValidationError

# Valid MySQL database (schema) name.
# Criteria:
#  1. Cannot be empty
#  2. Cannot exceed 64 characters
#  3. Cannot contain '/', '\', '.', or a backtick (the identifier-quote
#     character) — disallowed here to avoid needing to escape it when
#     building `USE `<name>`` statements
#  4. Cannot have a trailing space
#
# Reference: https://dev.mysql.com/doc/refman/8.0/en/identifiers.html
DISALLOWED_CHARACTERS = ('/', '\\', '.', '`')


def is_valid_schema_name(name):
    if not name or len(name) > 64:
        return False
    if name != name.rstrip():
        return False
    return not any(char in name for char in DISALLOWED_CHARACTERS)


def _check_schema_name(name):
    if not is_valid_schema_name(name):
        raise ValidationError("Invalid string used for the schema name.")
