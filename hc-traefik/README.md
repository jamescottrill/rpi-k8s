## Root CA
2. Generate Private Key `openssl genrsa -out rootCA.key 2048`
2. Generate root CA Cert `openssl req -x509 -new -nodes -key rootCA.key -sha256 -days 1024 -out rootCA.pem`
## SSL Certificates
1. Generate a Private Key `openssl genrsa -out lab.cloud.key 2048`
2. Generate a Certificate Signing Request `openssl req -new -key lab.cloud.key -out lab.cloud.csr`
3. Update the v3.ext file if required to add the domain name
4. Generate the certificate using the CSR, PK and ext file `openssl x509 -req -in lab.cloud.csr -CA rootCA.pem -CAkey rootCA.key -CAcreateserial -out lab.cloud.crt -days 500 -sha256 -extfile v3.ext`
5. Export the certificate in pfx `openssl pkcs12 -export -out lab.cloud.pfx -inkey lab.cloud.key -in lab.cloud.crt -certfile rootCA.pem`


https://gist.github.com/GJaminon/66804cbe4d51535d69738691e136dda5