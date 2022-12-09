# desc-prod/ptenv
This directory contains the scripts that comprise *ptenv* which is used to build conda environments (envs) to run
[desc-wfmon](https://github.com/LSSTDESC/desc-wfmon) parsltest with specified code versions at specified locations (NERSC file systems).
The package in each conda env include versioned builds of

* python
* ndcctools (work_queue)
* parsl
* desc-wfmon

The versions for each of these are specified by version tags listed in [ptenv-config](ptenv-config).

Supported locations are identified by the following location tags:

* hom - User home directory
* scr - Perlmutter scratch
* tmp - Tmp files system (/tmp/...)
* tmi - Again the tmp file sytes but including "install-dir" in the path name
* cfs - CFS files sytem
* com - Common file system
* shm - In-memory file system (/dev/shm/...)

See [ptenv-dir](ptenv/ptenv-dir) for the full path used for each of these.

A conda env for version tag VER at location LOC is installed at the location in this table with name LOCptenvVER.
The env includes file *setup.sh* that may be sourced (from bash) to set up the env.
Each env is tarred up and automatically installed so it does not have to be recreated on transient or non-shared file systems
like shm and tmp.
The original can also be removed to save space on persistent file systems.
An attempt to set up an env that is not present will extract it from the tar file if the latter is present.

The following scripts are provided:
* [ptenv-config](ptenv/ptenv-config) - Assigns version tags that set version for each of the above packages.
* [ptenv-dir](ptenv/ptenv-dir) - Returns the directory for given location.
* [ptenv-find](ptenv/ptenv-find) - Return the directory for an env with given location and version tag
* [ptenv-create](ptenv/ptenv-create) - Create an env and its tar file.
* [ptenv-remove](ptenv/ptenv-remove) - Remove an env (but not its tar).
* [ptenv-setup](ptenv/ptenv-setup) - Set up an env in the current shell.
* [ptenv-shell](ptenv/ptenv-shell) - Start a new shell with the env.
* [ptenv-versions](ptenv/ptenv-versions) - Displays the versions of the installed SW in the current env.

The scripts may be run from this directory (*./ptenvXXX ...*) or by adding the directory to your PATH.
