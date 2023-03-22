# DESCprod configuration strings

ohat to process and how process it are specified for DESCprod jobs by respectively
providing the config and howfig configuration strings.
Here we give conventions for such strings.

1. Configuration strings may only include letters, dash and colon [a-z, A-Z, -, :]
with capital letters discouraged.

2. Each string is a series of fields separated by a single dash (-).
Exactlty two successive dashes (--) and four or more (----, -----, ...)
are not allowed.
Dash triplets (---) delimit simple configuration strings in a compound
configuration string.

3. Single dashes within a (simple) configuration string separate fields
and colons within a field separate the field name from a sequence of optional values.
For example a sting might be #NAM1:V11-NAM2-NAM3:V31:V32".
