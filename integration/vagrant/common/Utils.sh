#!/bin/bash
export PYTHON_NOVACLIENT_VERSION=28
export GLANCE_VERSION=139

exclaim () {
    echo "*******************************************************************************"
    echo "$@"
    echo "*******************************************************************************"
}

fail_if_exists () {
    if [ -d $1 ] || [ -f $1 ]
    then
        echo The Nova cert file or directory $1 already exists. Aborting.
        exit 1
    fi
}

ip_chunk() {
    # Given 1-4 returns a bit of where the ip range starts.
    # Full IP= `ip_chunk 1`.`ip_chunk 2`.`ip_chunk 3`.`ip_chunk 4`
    ifconfig br100| grep 'inet addr:' | awk '{print $2} '| cut -d: -f2|cut -d. -f$@
}

pkg_install () {
    echo Installing $@...
    sudo -E DEBIAN_FRONTEND=noninteractive apt-get -y --allow-unauthenticated install $@
}

pkg_remove () {
    echo Uninstalling $@...
    sudo -E DEBIAN_FRONTEND=noninteractive apt-get -y --allow-unauthenticated remove $@
}
