#!/bin/bash

dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source ${dir}/cleanupFTPenv.sh;
source ${dir}/setupFTPenv.sh;
