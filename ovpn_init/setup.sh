#!/usr/bin/env bash

set -e

echo "Contents of bin/vars"
cat <<EOF | tee bin/vars
set_var EASYRSA_PKI            "$PWD/pki"

set_var EASYRSA_BATCH          "yes"

set_var EASYRSA_ALGO           rsa
set_var EASYRSA_KEY_SIZE       2048

set_var EASYRSA_DN             "org"

set_var EASYRSA_REQ_COUNTRY    "$EASYRSA_REQ_COUNTRY"
set_var EASYRSA_REQ_PROVINCE   "$EASYRSA_REQ_PROVINCE"
set_var EASYRSA_REQ_CITY       "$EASYRSA_REQ_CITY"
set_var EASYRSA_REQ_ORG        "$EASYRSA_REQ_ORG"
set_var EASYRSA_REQ_OU         "OpenVPN PKI"
set_var EASYRSA_REQ_EMAIL      "$EASYRSA_REQ_EMAIL"
set_var EASYRSA_REQ_CN         "CA"

set_var EASYRSA_CA_EXPIRE      3650
set_var EASYRSA_CRL_DAYS       180
set_var EASYRSA_CERT_EXPIRE    3650
set_var EASYRSA_CERT_RENEW     30

set_var EASYRSA_RAND_SN        "yes"

EOF

echo "Initialize PKI"
bin/easyrsa init-pki
bin/easyrsa build-ca nopass
openvpn --genkey --secret pki/ta.key

echo "Create bot certificate"
bin/easyrsa --req-cn="OpenVPN Bot" gen-req bot nopass
bin/easyrsa sign-req ca bot
mkdir bot_certs
cp pki/ca.crt bot_certs
cp pki/issued/bot.crt bot_certs/root.crt
cp pki/private/bot.key bot_certs/root.key
cp pki/ta.key bot_certs

echo "Create server certificate"
bin/easyrsa build-server-full "OpenVPN Server" nopass
bin/easyrsa gen-dh
mkdir server_certs
cp pki/ca.crt server_certs
cat pki/ca.crt pki/issued/bot.crt > server_certs/ca_bundle.crt
cp pki/issued/OpenVPN\ Server.crt server_certs/server.crt
cp pki/private/OpenVPN\ Server.key server_certs/server.key
cp pki/dh.pem server_certs
cp pki/ta.key server_certs
