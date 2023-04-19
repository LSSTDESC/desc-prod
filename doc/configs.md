# DESCprod configuration strings

What to process and how process it are specified for DESCprod jobs by respectively
providing the config and howfig configuration strings.
Here we give conventions for such strings.

1. Configuration strings may only include letters, digits, dash and colon
[a-z, A-Z, 0-9, -, :] with capital letters discouraged.

2. Each string is a series of fields separated by a single dash (-).
Exactly two successive dashes (--) and four or more (----, -----, ...)
are not allowed.
A configuration string amy not begin or end with a dash.

3. Dash triplets (---) delimit simple configuration strings in a compound
configuration string.

4. Single dashes within a (simple) configuration string separate fields.

5. Colons within a field separate the field name from a trailing sequence of optional
values. For example a string might be nam1:v11-nam2-nam3:v31:v32".
Two or more succesive colons are not allowed, i.e. values may not be ommitted except
at the end of a field.
A string may not begin or end with a colon.
