# DESCprod applications

David Adams  
Version 0.2  
May 11, 2023 ---- IN PROGRESSS -----

Applications provide the interface between the DESCprod system and the user code to be run.
Here we describe how a job progresses and the interface that applications must provide.

## Job progression

DESCprod jobs are specified are specified on the server with three strings: jobtype,
config and howfig.
The first two specify what to process and the last how to carry out the processing.
The last two are config strings and the convention for those are specified in
a [separate document](doc/configs.md).

DESCprod jobs are run as follows:
* Client issues the descprod-start-job command specifying the job ID. That script does the following:
  * Creates run directory (subdirectory jobXXXXX of the current directory.
  * Copies the the job wrapper [descprod-wrap](descprod/desprod-wrap) to that directory
  * Fetches the job description from the server.
  * The description is used to generate the arguments to pass to the wrapper including the name of the application to run, APPNAME
  * The wrapper copy is started in a fresh shell with those arguments
  * Status is reported to stdout and the start script exits with a return code (0 for success)
* The wrapper continues to run as an orphan process:
  * The wrapper starts the application command (runapp-APPNAME) in another shell
  * At regular intervals, the wrapper checks and reports progress back to the DESCprod server
  * After the application command completes, the wrapper send final report to the server and exits

For *direct jobs*, the application name (APPNAME) is the job type (e.g. parsltest) but this may be overriden
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

## Application running

As noted above, the application is run by the wrapper which monitors and reports progress back to the server.
The application will typically start a new shell, the *executor*, in a dedicated job execution environment
to run the user code.
This executor might run on a remote machine and could event be a different OS (e.g. GPUs).
Or the script might submit a request (or requests) to run the executor in batch or some other workload management system (WMS).
In any case, the application script should not exit until all executors have finished because that exit causes
the wrapper to report back to the server that the job is done.

An alternative for remote processing is to create DESCprod subjobs, i.e. jobs whose parent is the original job.
The application might then submit requests to batch/WMS to start the subjobs or could leave that to
the user or some automatic system.
In any case, the application can exit immediately after creating and submitting (or not) the subjobs.
Each of those will run with its own wrapper and the user can monitor their progress on the server.

## Actors and their environments

Above we see there are three actors: the server where jobs are defined and tracked, the client which fetches the
job description and runs the wrapper whichs runs the application, 
and the executor which runs the user code.
Each of these runs in a separate environment.
The server uses the desc-prod package but does not depend on the application code.
The client requires both
The wrapper uses the application code but, even though it was copied from desc-prod and communicates with the server,
does not make use of desc-prod.

## Application interface


