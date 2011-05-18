# Handles building and installing our packages.

#on the container, in /etc/apt/sources.list
#deb http://10.0.2.15/ubuntu lucid main

dbaas_pkg_create_tmpbuild() {
    if [ -d /tmp/build ]
    then
        echo /tmp/build already exists.
    else
        sudo mkdir /tmp/build
    fi
}


dbaas_pkg_install_dbaasmycnf() {
    # Builds and installs dbaasmycnf package.

    dbaas_pkg_create_tmpbuild
    sudo cp -R /src/dbaas-mycnf /tmp/build/dbaas
    cd /tmp/build/dbaas
    sudo ./dbaas-mycnf/builddeb.sh
    #remove the old version in case this is a 2nd run
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid dbaas-mycnf
    sudo reprepro --ignore=wrongdistribution -Vb /var/www/ubuntu/ includedeb lucid dbaas-mycnf/*.deb
}

dbaas_pkg_install_firstboot() {
    # Builds and installs firstboot package.

    dbaas_pkg_create_tmpbuild
    sudo cp -R /src/firstboot /tmp/build/dbaas
    cd /tmp/build/dbaas
    sudo ./firstboot/builddeb.sh
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid firstboot
    sudo reprepro --ignore=wrongdistribution -Vb /var/www/ubuntu/ includedeb lucid firstboot/*.deb
}

dbaas_pkg_install_nova() {
    # Builds and installs all of the stuff for Nova.

    dbaas_pkg_create_tmpbuild

    echo Building Nova packages...
    sudo bash /vagrant-common/nova_builddeb.sh
    if [ $? -ne 0 ]
    then
        echo "Failure to build Nova package."
        exit 1
    fi

    gitversion=`cat /tmp/build/dbaas/_version.txt`

    echo Removing old versions of the packages in case this is a 2nd run.
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid nova-ajax-console-proxy
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid nova-api
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid nova-common
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid nova-compute
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid nova-doc
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid nova-guest
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid nova-instancemonitor
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid nova-network
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid nova-objectstore
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid nova-scheduler
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid nova-volume
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid platform-api
    sudo reprepro -Vb /var/www/ubuntu/ remove lucid python-nova


    echo Installing Nova packages into the local repo.
    cd /tmp/build
    sudo reprepro --ignore=wrongdistribution -Vb /var/www/ubuntu/ include lucid nova_`echo $gitversion`_amd64.changes
}