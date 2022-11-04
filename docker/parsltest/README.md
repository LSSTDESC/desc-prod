# images/parsltest

This directory contains scripts and configs (dockerfiles) to 
create and run docker images tat include desc-wfmon and parsl.

The user must first install the docker desktop--see https://docs.docker.com/get-docker.

## Creating version XXX

First create ./dockerfile-XXX most likely by copying one of the
dockerfiles here and making modifications.

Build the image with  
&gt; ./build XXX

Test the image by running locally.
descprod> ./start XX
descprod> com1
descprod> com2
descprod> ...
descprod> exit

Push the image to dockerhub.
./push XX

Pull the image on another machine.
Replace dladams with the docker username of the installer.
&gt; docker pull dladams/parsltest:XX
Test as above.

On perlmutter or cori, install with shifter:
&gt; shifterimg -v pull dladams/parsltest:XX

## Version history
02 - Ubuntu with python, pip, git
02 - 01 plus pip workqueue, parsl and desc-wfmon
03 - 02 plus python-is-python3, vim, user descprod
04 - 03 plus sudo, wget, conda, ndcctools. Drop pip workqueue.
