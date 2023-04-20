# DESCprod configuration strings

David Adams  
Version 2.0  
April 20, 2023

DESCpprod jobs are specified are specified with three strings: jobtype,
config and howfig.
The first two specify what to process and the last how to carry out the processing.
The last two are config strings and the covention for those are specified here.

1. Simple configuration strings may only include letters, digits, dash and colon
[a-z, A-Z, 0-9, -, :] with capital letters discouraged.

2. Howfig may be compound, i.e. consist of a series comma-separated constituents.
Each constituent is a simple configuration strings.
An empty howfig has no constuents and one that is not empty and has no commas
has one constituent.

3. Each simple configuration string is a series of fields separated by a single dash (-).
For howfig constituents, the first field (i.e. the substring preceding the first dash)
is the howfig type.
If the type of the first howfig constitutent is registered with DESCprod,
the application associated with them is run in place of that associated with the job type.

4. It is intended that colons within a field separate the field name from a trailing sequence of optional values.
For example a string might be nam1:v11-nam2-nam3:v31:v32".

