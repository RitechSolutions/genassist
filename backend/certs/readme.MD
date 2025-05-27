To generate self signed ssl certificates:

openssl req -x509 -newkey rsa:4096 -keyout self-signed.key -out self-signed.crt -sha256 -days 36500 -nodes -subj "/C=US/ST=WA/O=Ritech/OU=GenAssist/CN=genassist-dev.ritech.io" -addext "subjectAltName = DNS:localhost"
