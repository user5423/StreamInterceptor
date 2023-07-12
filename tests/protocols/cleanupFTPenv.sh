#!/bin/bash

## SI = StreamInterceptor

FTP_GROUP='SI_FTPTestGroup'

## Currently only one FTP_USER
FTP_USER='SI_FTPTestUser1'

VSFTPD_CHROOT_LIST_FILE='/etc/vsftpd.chroot_list'

## Delete password
unset SI_FTP_PASSWORD

## Delete user from chrootlist
sudo sed -i "/$FTP_USER/d" $VSFTPD_CHROOT_LIST_FILE

## Delete user and group
sudo userdel "$FTP_USER"
sudo groupdel "$FTP_GROUP"

