# desc-prod
This package provides code to supporting the descprod project which includes a DESC production service and clients for that service.
The goal of the project is to make it easy for DESC members to run jobs at NERSC.
The system provides (or will provide soon) direct support to run LSST pipeline jobs
and can run working group and user analysis jobs that provide a specified application interface.
For a recent status report see the
[talk at the January 25, 2023 DESC CO meeting](https://drive.google.com/file/d/1uAMfWpQLenxF_50mjmBWqISEEDxOkdrc/view?usp=share_link).

## Service
A web service is provided at [https://www.descprod.org].
Follow that link and log in with google credentials to view a page where you can submit jobs and track theior progress.
if you afre not already registered with descprod, follow the instructions to register.

## Installation
To use the descprod clients, you must first install this package.
Check it out from git and build with pip:
<pre>
mkdir &lt;install-dir>
cd &lt;install-dir>
git clone https://github.com/LSSTDESC/desc-prod.git
cd desc-prod
pip install .
</pre>
Note the installation requires a recent version of python.
One option at NERSC is to use the default python module:
<pre>
module load python
</pre>

## Clients
The following clients are provided:
descprod-version - Shows the installed version of this package.

## Contents
[descprod](descprod) - Installed code used by clients and servers.  
[docker](docker) - Configuration files and supporting scripts for building docker images.  
[service](service) - Scripts useful for building the production service.  
[ptenv](ptenv) - Scripts to build and use parsltest conda envs at NERC.  

## More information

[SpinUp exercises (how to guide)](https://www.dropbox.com/sh/102smpnhmbimg4a/AAA2nNnRWOPYrRi6oq_QLrnYa/Self-Guided%20SpinUp/Self-Guided%20SpinUp%20Exercises.pdf?dl=0)

[Superfacility API](https://docs.nersc.gov/services/sfapi/)
