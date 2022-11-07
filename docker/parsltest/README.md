# images/parsltest

This directory contains scripts and configs (dockerfiles) to 
create and run docker images that include desc-wfmon and parsl.

The user must first install the docker desktop--see https://docs.docker.com/get-docker.

Below XX rpresents a version tag. Replace it with your value.

## Creating and using version XX

First create ./dockerfile-XXX most likely by copying one of the
dockerfiles here and making modifications.

Build the image with
<pre>
> ./build XX
</pre>

Test the image by running locally.
<pre>
> ./start XX
descprod> com1
descprod> com2
descprod> ...
descprod> exit
>
</pre>

Push the image to dockerhub.
<pre>
./push XX
</pre>

Pull the image on another machine.
Replace dladams with the docker username of the installer.
<pre>
> docker pull dladams/parsltest:XX
</pre>
Test as above.

On perlmutter or cori, install with shifter:
<pre>
> shifterimg -v pull dladams/parsltest:XX
</pre>

## Version history 
02 - Ubuntu with python, pip, git  
02 - 01 plus pip workqueue, parsl and desc-wfmon  
03 - 02 plus python-is-python3, vim, user descprod  
04 - 03 plus sudo, wget, conda, ndcctools. Drop pip workqueue.  
