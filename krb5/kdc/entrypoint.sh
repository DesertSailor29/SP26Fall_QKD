#!/bin/bash

set -e

echo "Starting Kerberos KDC..."

if [ ! -f /var/lib/krb5kdc/principal ]; then
    echo "Initializing Kerberos database..."

    kdb5_util create -s -P "$KDC_MASTER_PASSWORD" \
        -r "$KRB5_REALM"
else
    echo "Kerberos database already exists."
fi

echo "Starting KDC daemon..."

krb5kdc -n &
KDC_PID=$!

echo "Starting Kerberos administration daemon..."

kadmind -nofork &
KADMIN_PID=$!

wait -n "$KDC_PID" "$KADMIN_PID"
