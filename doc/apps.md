# DESCprod applications

David Adams  
Version 0.2  
May 11, 2023

Applications provide the interface between the DESCprod system and the user code to be run,
here called the *execution code*.
Here we describe how jobs progress through the DESCprod system, how applications are used and the
interface they are expected to provide.

## Job progression

DESCprod jobs are specified on the server with three strings: jobtype, config and howfig.
The first two specify what to process and the last how to carry out the processing.
The last two are config strings and the convention for those are specified in
a [separate document](doc/configs.md).

DESCprod jobs are run as follows:
* Client issues the descprod-start-job command specifying the job ID. That script does the following:
  * Creates the run directory (subdirectory jobXXXXX of the current directory.
  * Copies the the job wrapper script [descprod-wrap](descprod/desprod-wrap) to that directory
  * Fetches the job description from the server.
  * Uses that description to generate the arguments to pass to the wrapper including the name of the application to run, APPNAME
  * Runs the wrapper with those arguments
  * Status is reported to stdout and the start script exits with a return code (0 for success)
* The wrapper continues to run as an orphan process:
  * The wrapper starts the application command (runapp-APPNAME) in another shell
  * At regular intervals, the wrapper checks and reports progress back to the DESCprod server
  * After the application command completes, the wrapper send a final report to the server and exits

To determine APPNAME (and hence which application to run), the first howfig constitutent HFLD1
(the string preceding the first dash, i.e. in HFLD1-HFLD2-...) is checked agains a list of know
howfig application types.
If HFLD1 is not in the list, then APPNAME is set to JOBTYPE, the configured job type,
and the job is said to be *direct*.
If it is found in that list, then APPNAME is set to HFLD1 and the job is said to be *indirect*.

For *direct jobs*, the script runapp-APPNAME is called with the config and howfig strings as arguments.
The application is expected to deduce what processing to carry out from the config string and to use
howfig for hints or requirements on how to carry out that processing.

For indirect jobs, no arguments are passed but the script can find the full job description in config.json
in the working directory.
The application should ensure that runapp_JOBTYPE is eventually called with appropriate config and howfig arguments.
The application can do other operations before, after or during that direct running
including setting up and environment, splitting, submitting to batch, creating subjobs, ....

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
The server uses the desc-prod package but does not depend on the application or execution code.
The client requires desc-prod and the application but does not require the execution code.
The executor requires the application and execution code but does not require desc-prod.
The following table summarizes which code iw required by each actor.

| Actor | desc-prod | application | execution |
|---|:---:|:---:|:---:|
| server | X | | |
| client | X | X | |
| executor | | X | X |

## Application interface

At a minimum, a package providing one or more applications must provide a script runapp_JOBTYPE for each
direct application and runapp_HNAM for each indirect application HNAM.
These scripts are executable and appear on the user's path after the package is installed or set up.
These scripts should have arguments and behavior as described above and should return 0 for success.
They should ensure that current-status.txt is updated regularly.


