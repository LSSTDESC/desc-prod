# desc-prod

David Adams  
May 13, 2023  
Version 0.2.1

The DESCprod project has the goal to make it easy for DESC members to run production jobs at NERSC.
This package (desc-prod) provides the code to run the DESC production service at NERSC SPIN,
a [web interface](https://www.descprod.org/home) to that service,
and client commands to access the service from other nodes.
An interface is defined so different applications can be run without modifying the code here.
This package provides on example application, parsltest, which runs many test jobs in parallel.
Suppport for LSST pipeline jobs is being added in the [desc-gen3-prod package](https://github.com/LSSTDESC/desc-gen3-prod).

More information on the project and this and other applications may be found on the
[service help page](https://www.descprod.org/help).

## Service
A web service is provided at https://www.descprod.org.
Follow that link and log in with google credentials to view a page where you can submit jobs and track theior progress.
New users should follow the instructions on the page to register.
Client scripts (9including those listedd below) below contact this service by default.

## Installation
To use the descprod client code, install this package.
Check it out from git and build with pip:
<pre>
module load python
mkdir &lt;install-dir>
cd &lt;install-dir>
git clone https://github.com/LSSTDESC/desc-prod.git
cd desc-prod
pip install .
</pre>
The first line ensures a recent version of python at NERSC and can be omitted if you
have already set one up in another way.

## Applications

Applications provide a simple means for users to extend DESCprod to run arbitrary production code.
The progress of jobs through the DESCprod system and the application interface are described
in the [application document](doc/apps.md).

## Client interface
Client commands include:
* descprod-version - Shows the installed version of this package.
* descprod-show-job - Shows the job data for a given job ID.
* desprod-start-job - Start a job on the local machine.
* descprod-add-job - Add a new job.

Use option -h for help on any of these commands.
The last three refer to jobs configured on the server.
At present, the start command is the only way to start a job.
It is intended that jobs be added using the web interface but the add command provides
means to circumvent that.

## Contents
[descprod](descprod) - Installed python code used by clients and servers.  
[docker](docker) - Configuration files and supporting scripts for building docker images for the service.  
[server](server) - Scripts and html to suppoprt the production service.  
[apps](apps) - Example applications.

## More information

[SpinUp exercises (how to guide)](https://www.dropbox.com/sh/102smpnhmbimg4a/AAA2nNnRWOPYrRi6oq_QLrnYa/Self-Guided%20SpinUp/Self-Guided%20SpinUp%20Exercises.pdf?dl=0)

[Superfacility API](https://docs.nersc.gov/services/sfapi/)
