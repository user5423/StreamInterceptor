#!/bin/bash

set -e
## SI = StreamInterceptor

FTP_GROUP='SI_FTPTestGroup'
export FTP_GROUP

## Currently only one FTP_USER
FTP_USER='SI_FTPTestUser1'
export FTP_USER

FTP_PASSWORD_LENGTH=20

VSFTPD_CHROOT_LIST_FILE='/etc/vsftpd.chroot_list'

if id -u "$FTP_USER" >/dev/null 2>&1
then 
    if groups "$FTP_USER" | grep -qw "$FTP_GROUP"
    then 
        echo "An existing FTP_USER - $FTP_USER - in the test FTP_GROUP $FTP_GROUP"
    else 
        echo "An existing FTP_USER - $FTP_USER - not in the test FTP_GROUP $FTP_GROUP"
        echo "There might be a conflicting FTP_USER already existing. Please verify."
    fi
else
    if groups | grep -qw "$FTP_GROUP"
    then
        echo "The FTP_GROUP - $FTP_GROUP - already exists"
    else
        echo "Creating the FTP_GROUP - $FTP_GROUP"
        sudo groupadd "$FTP_GROUP"
    fi
    
    SI_FTP_PASSWORD=$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c $FTP_PASSWORD_LENGTH 2>/dev/null)
    export SI_FTP_PASSWORD
    
    mkdir -p /var/ftp
    sudo useradd -m -d "/var/ftp/$FTP_USER" -g "$FTP_GROUP" -c "FTP Test Account for StreamInterceptor Project" $FTP_USER
    echo -e "$SI_FTP_PASSWORD\n$SI_FTP_PASSWORD" | sudo passwd "$FTP_USER"
    
    sudo touch "$VSFTPD_CHROOT_LIST_FILE"
    if sudo grep -Fxq "$FTP_USER" "$VSFTPD_CHROOT_LIST_FILE"
    then 
        echo "FTP User already exists in the file: $VSFTPD_CHROOT_LIST_FILE"
    else
        echo "$FTP_USER" | sudo tee -a "$VSFTPD_CHROOT_LIST_FILE"
    fi
    echo "Created a new FTP_USER"

    service vsftpd start
    echo "Started vsftpd service"
fi

set +e