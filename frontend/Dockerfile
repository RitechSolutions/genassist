# This Dockerfile is for building and running a Node.js application using multi-stage builds.
# The first stage builds the application,
# The second stage serves the built files using Nginx.
# Use an official Node.js runtime as the base image
FROM node:18-alpine AS builder

# Set the working directory inside the container
WORKDIR /app

# Install git, python3, and build tools required for native modules
RUN apk add --no-cache git python3 make g++

# Copy package.json and package-lock.json to the container
COPY package.json package-lock.json ./

# Copy the rest of the application code
COPY . .

RUN npm run clean

#Install customplugin
RUN mkdir -p /plugins
COPY --from=plugins . /plugins/react
#RUN npm install /app/plugins/react

RUN npm install typescript
RUN npm install

#Audit and maybe fix some packages
#RUN npm audit
#RUN npm audit fix --force
#RUN npm audit fix --legacy-peer-deps

# Build the application

RUN npm run build

# Use a lightweight web server to serve the built files
FROM nginx:1.29.4-alpine3.23-slim AS production

# Set working directory to nginx asset directory
WORKDIR /usr/share/nginx/html
# Remove default nginx static assets
RUN rm -rf ./*
# Copy static assets from builder stage
COPY --from=builder /app/container/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --from=builder /app/dist .
COPY container/nginx/nginx.conf  /etc/nginx/conf.d/default.conf

EXPOSE 8080

ENTRYPOINT ["/bin/sh", "/usr/local/bin/entrypoint.sh"]
