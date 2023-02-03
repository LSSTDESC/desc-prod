# images/descprod

This directory contains scripts and configs (dockerfiles) to 
create and run docker images that include desc-wfmon and parsl.

The user must first install the docker desktop--see https://docs.docker.com/get-docker.

Below XX represents a version tag. Replace it with your value.

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
> docker pull dladams/descprod:XX
</pre>
Test as above.

On perlmutter or cori, install with shifter:
<pre>
> shifterimg -v pull dladams/descprod:XX
</pre>

## Version history 
01 - Copy dockerfile parsltest:12 and add jupyterlab
02 - Fix sudo config so descprod can run as anyone
03 - Add ssh. Add cond setup file.
04 - Move to descprod 0.2.45 to allow update of self.
     Move to desc-wfmon 0.26.11 to allow simultaneous parsl jobs.
05 - Add mysql server.
