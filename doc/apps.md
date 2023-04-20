# DESCprod applications

David Adams  
Version 0.1  
April 20, 2023

DESCprod jobs are specified are specified with three strings: jobtype,
config and howfig.
The first two specify what to process and the last how to carry out the processing.
The last two are config strings and the convention for those are specified in
a [separate document](doc/configs.md).


DESCprod jobs are run as follows:
* User issues the descprod-start-job command where
  * A run directory is created
  * The wrapper [descprod-wrap](descprod/desprod-wrap) is copied to that directory
  * An application command of the form runapp-APPNAME is selected
  * The wrapper copy is started in a fresh shell with series af arguments including that command
  * Status is reported to stdout and the return code (0 for success)
* The wrapper continues to run as an orphan process:
  * The wrapper starts the application command in another shell
  * At regular intervals, the wrapper checks and reports progress back to the DESCprod server
  * After the command completes, the wrapper send final report to the server and exits

For *direct jobs*, the application name is the job type (e.g. parsltest) but this may be overriden
(and the job run indirectly) by registering a howfig type and using that name in first howfig constituent.
I.e., APPNAME is name of the first howfig constitent if that name is registered, and otherwise is the job type.
The script runapp-APPNAME is run with the config and howfig strings as arguments.
For direct jobs, this script is expected to deduce what processing to carry out from the config string and to use
howfig for hints or requirements on how to carry out that processing.

For indirect jobs, no arguments are passed but the script can find the full job description in config.json
in the working directory.
The script might strip its constituent to create a subjob and the start the latter in batch or on a
dedicated scheduling sytem. Or submit itelf to batch.
Or it might split the job into pieces by assigning a different config to each and run those
directly or as subjobs.

Part of the regular status report sent from the wrapper to server is the job progress.
This is obtained from the last line in the file current-status.txt in the working directory.
The runapp script or application itself should regularly update that file.
