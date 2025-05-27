

echo "GENASSIST_API_PUBLIC_URL: $GENASSIST_API_PUBLIC_URL"
echo "GENASSIST_API_PRIVATE_URL: $GENASSIST_API_PRIVATE_URL"

# # Print list of files where values are found
#grep -r -l '###_GENASSIST_API_PRIVATE_URL_###' /usr/share/nginx/html/
#grep -r -l '###_GENASSIST_API_PUBLIC_URL_###' /usr/share/nginx/html/


# Replace placeholders with environment variable values in files only
find /usr/share/nginx/html/ -type f -exec sed -i "s,###_GENASSIST_API_PUBLIC_URL_###,$GENASSIST_API_PUBLIC_URL,g" {} +
find /usr/share/nginx/html/ -type f -exec sed -i "s,###_GENASSIST_API_PRIVATE_URL_###,$GENASSIST_API_PRIVATE_URL,g" {} +




#KEEP NGINX DAEMON RUNNING
nginx -g 'daemon off;'; nginx -s reload;

